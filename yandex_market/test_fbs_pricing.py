"""FBS: формула, округления, общие габариты и изоляция публикации цены."""
import copy
from decimal import Decimal, ROUND_HALF_UP
from unittest.mock import Mock, patch

from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from catalog.models import CD, Platform, ProductFieldChange
from catalog.nomenclature_forms import product_version
from warehouse.models import Warehouse
from .content import build_content
from .fbs_pricing import DEFAULTS, calculate_fbs_price, product_calculation
from .models import CategorySchema, Integration, OfferConnection, RemoteOffer, SyncJob
from .product_dimensions import fill_integration_dimensions


def configuration(**changes):
    result = copy.deepcopy(DEFAULTS)
    result.update(tax_rate="6.00", payment_rate="2.00")
    result.update(changes)
    return result


class FBSFormulaTests(SimpleTestCase):
    def calc(self, **changes):
        params = dict(cost_price=Decimal("1300.00"), desired_profit=Decimal("200.00"),
                      length_cm=Decimal("17"), width_cm=Decimal("13"), height_cm=Decimal("2"),
                      weight_g=140, placement_rate=Decimal("18"), configuration=configuration())
        params.update(changes)
        return calculate_fbs_price(**params)

    def test_gta_v_volume_and_requested_profit(self):
        result = self.calc()
        self.assertEqual(result["raw_volume_l"], Decimal("0.442"))
        self.assertEqual(result["billing_volume_l"], 1)
        self.assertEqual(result["middle_mile_fee"], 92)
        self.assertGreaterEqual(result["actual_profit"], 200)
        self.assertEqual(result["final_price"], result["final_price"].to_integral_value())

    def test_more_than_one_litre(self):
        result = self.calc(length_cm=20, width_cm=20, height_cm=10)
        self.assertEqual(result["billing_volume_l"], 4)
        self.assertEqual(result["middle_mile_fee"], 116)

    def test_each_dimension_recalculates_volume_and_price(self):
        baseline = self.calc()
        for field in ("length_cm", "width_cm", "height_cm"):
            with self.subTest(field=field):
                changed = self.calc(**{field: Decimal("200")})
                self.assertNotEqual(changed["raw_volume_l"], baseline["raw_volume_l"])
                self.assertGreater(changed["final_price"], baseline["final_price"])

    def test_litre_rounding_is_upward(self):
        self.assertEqual(self.calc(length_cm=10, width_cm=10, height_cm=10)["billing_volume_l"], 1)
        self.assertEqual(self.calc(length_cm=10, width_cm=10, height_cm=Decimal("10.001"))["billing_volume_l"], 2)

    def test_missing_dimensions(self):
        for field in ("length_cm", "width_cm", "height_cm"):
            with self.subTest(field=field), self.assertRaisesMessage(ValidationError, "укажите габариты"):
                self.calc(**{field: None})

    def test_zero_and_negative_dimensions(self):
        for field in ("length_cm", "width_cm", "height_cm"):
            for value in (0, -1):
                with self.subTest(field=field, value=value), self.assertRaises(ValidationError):
                    self.calc(**{field: value})

    def test_percentage_delivery(self):
        result = self.calc()
        self.assertLess(result["final_price"], result["delivery_cap_price"])
        self.assertEqual(result["delivery_fee"], (result["final_price"] * Decimal("0.05")).quantize(Decimal("0.01")))

    def test_delivery_cap_and_dynamic_threshold(self):
        result = self.calc(cost_price=50000, configuration=configuration(delivery_rate="8", delivery_max="800"))
        self.assertEqual(result["delivery_cap_price"], 10000)
        self.assertEqual(result["delivery_fee"], 800)
        self.assertGreaterEqual(result["actual_profit"], 200)

    def test_cap_boundary_and_zero_delivery(self):
        for cost in (13000, 13700, 14000):
            result = self.calc(cost_price=cost)
            self.assertEqual(result["delivery_fee"], min(result["final_price"] * Decimal("0.05"), Decimal(1000)))
        for changes in ({"delivery_rate": "0"}, {"delivery_max": "0"}):
            self.assertEqual(self.calc(configuration=configuration(**changes))["delivery_fee"], 0)

    def test_changed_settings_increase_price(self):
        old = self.calc()["final_price"]
        for changes in ({"packaging": "90"}, {"tax_rate": "10"}, {"payment_rate": "8"}, {"fixed_payment": "20"}, {"other_fbs": "100"}):
            self.assertGreater(self.calc(configuration=configuration(**changes))["final_price"], old)

    def test_category_tariff_changes_price(self):
        self.assertGreater(self.calc(placement_rate=25)["final_price"], self.calc()["final_price"])

    def test_upward_price_rounding_and_minimum_integer_price(self):
        result = self.calc()
        price = result["final_price"] - 1
        fees = sum((price * rate).quantize(Decimal("0.01")) for rate in (Decimal("0.18"), Decimal("0.06"), Decimal("0.02"), Decimal("0.05")))
        self.assertLess(price - 1300 - 92 - 30 - fees, 200)

    def test_extreme_percentage_rounding_still_finds_minimum(self):
        result = self.calc(placement_rate=Decimal("99.99"), configuration=configuration(tax_rate="0", payment_rate="0", delivery_rate="0"))
        self.assertGreaterEqual(result["actual_profit"], 200)
        price = result["final_price"] - 1
        fee = (price * Decimal("0.9999")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        self.assertLess(price - 1300 - 92 - 30 - fee, 200)

    def test_rounding_can_cover_tiny_cost_before_cap_with_nonpositive_margin(self):
        for delivery_rate in ("0.01", "0.02"):
            with self.subTest(delivery_rate=delivery_rate):
                result = self.calc(cost_price=Decimal("0.01"), desired_profit=0, placement_rate="33.33",
                    configuration=configuration(tax_rate="33.33", payment_rate="33.33", delivery_rate=delivery_rate,
                        packaging="0", middle_first_fee="0", middle_max="0"))
                self.assertEqual(result["final_price"], 1)
                self.assertGreaterEqual(result["actual_profit"], 0)

    def test_missing_cost_rate_tax_and_invalid_denominator(self):
        for changes in ({"cost_price": None}, {"cost_price": 0}, {"placement_rate": None},
                        {"configuration": configuration(tax_rate=None)}, {"placement_rate": 99}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.calc(**changes)

    def test_bands_after_200_litres_and_maximum(self):
        result = self.calc(length_cm=200, width_cm=60, height_cm=31)
        self.assertEqual(result["billing_volume_l"], 372)
        self.assertEqual(result["middle_mile_fee"], 2544)
        self.assertEqual(self.calc(length_cm=1000, width_cm=1000, height_cm=1000)["middle_mile_fee"], 5500)

    def test_invalid_bands_and_weight(self):
        with self.assertRaises(ValidationError):
            self.calc(configuration=configuration(middle_bands=[{"until_l": "1", "per_l": "8"}]))
        for weight in (-1, 0, Decimal("1.5")):
            with self.subTest(weight=weight), self.assertRaises(ValidationError):
                self.calc(weight_g=weight)


@override_settings(YANDEX_MARKET_API_KEY="test-key-never-live", YANDEX_MARKET_ALLOW_TEST_TRANSACTION=True)
class FBSIntegrationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("fbs-admin", password="Test-password-123")
        self.warehouse = Warehouse.objects.create(name="Склад FBS")
        self.integration = Integration.objects.create(business_id=998, campaign_id=999, fulfillment_warehouse=self.warehouse,
            operator=self.user, configuration={"fbs_pricing": configuration()})
        self.category = CategorySchema.objects.create(category_id=50, name="Игры", placement_rate=18, schema={"categoryId": 50, "parameters": []})
        self.product = CD.objects.create(platform=Platform.objects.create(name="PlayStation 5"), name="GTA V",
            cost=1300, length_cm=17, width_cm=13, height_cm=2, weight_grams=140, yandex_desired_profit=200,
            yandex_market_price=3990, yandex_pricing_category=self.category, yandex_pricing_integration=self.integration)
        self.client.force_login(self.user)

    def payload(self, **changes):
        self.product.refresh_from_db()
        values = dict(version=product_version(self.product), yandex_desired_profit="200", length_cm="17", width_cm="13", height_cm="2",
                      weight_grams="140", yandex_pricing_category=self.category.pk, yandex_pricing_integration=self.integration.pk)
        values.update(changes)
        return values

    def route(self, action):
        return reverse("pricing:fbs_" + action, args=("cd", self.product.pk))

    def test_page_and_live_preview_dont_write_or_publish(self):
        self.assertContains(self.client.get(self.route("detail")), "Желаемая чистая прибыль")
        previous = self.product.yandex_calculated_price
        response = self.client.post(self.route("preview"), self.payload(yandex_desired_profit="500"))
        self.assertTrue(response.json()["ok"])
        self.product.refresh_from_db()
        self.assertEqual(self.product.yandex_desired_profit, 200)
        self.assertEqual(self.product.yandex_calculated_price, previous)
        self.assertEqual(self.product.yandex_market_price, 3990)
        self.assertFalse(SyncJob.objects.exists())

    def test_preview_cleared_category_does_not_reuse_saved_category(self):
        result = self.client.post(self.route("preview"), self.payload(yandex_pricing_category="")).json()
        self.assertFalse(result["ok"])
        self.assertIn("тариф категории", result["message"])
        self.product.refresh_from_db()
        self.assertEqual(self.product.yandex_pricing_category, self.category)

    def test_pricing_table_offers_dimensions_button_until_all_sizes_are_saved(self):
        self.product.width_cm = None
        self.product.save(update_fields=["width_cm"])
        url = reverse("pricing:list")
        response = self.client.get(url, {"in_stock": "0", "search": self.product.name})
        self.assertContains(response, "Указать размеры")
        self.assertContains(response, "data-fbs-inputs hidden")
        self.assertRegex(response.content.decode(), r'<input[^>]*data-price-field="yandex_market_price"[^>]* hidden>')
        saved = self.client.post(self.route("save"), self.payload()).json()
        self.assertTrue(saved["ok"])
        self.assertTrue(saved["dimensions_complete"])
        self.product.refresh_from_db()
        self.assertEqual(self.product.width_cm, 13)
        self.assertEqual(self.product.yandex_market_price, 3990)
        response = self.client.get(url, {"in_stock": "0", "search": self.product.name})
        self.assertNotContains(response, "data-fbs-inputs hidden")
        self.assertContains(response, "data-fbs-dimensions-open hidden")

    def test_saving_incomplete_dimensions_keeps_existing_market_price(self):
        saved = self.client.post(self.route("save"), self.payload(width_cm="")).json()
        self.assertTrue(saved["ok"])
        self.assertFalse(saved["dimensions_complete"])
        self.product.refresh_from_db()
        self.assertIsNone(self.product.width_cm)
        self.assertEqual(self.product.yandex_market_price, 3990)

    def test_profit_dimensions_cost_and_settings_recalculate_saved_recommendation(self):
        old = self.product.yandex_calculated_price
        response = self.client.post(self.route("save"), self.payload(yandex_desired_profit="500", length_cm="100"))
        self.assertTrue(response.json()["ok"])
        self.product.refresh_from_db()
        self.assertGreater(self.product.yandex_calculated_price, old)
        self.assertEqual(self.product.yandex_market_price, 3990)
        self.assertTrue(ProductFieldChange.objects.filter(event__cd=self.product, field_name="length_cm").exists())
        old = self.product.yandex_calculated_price
        self.product.cost = Decimal("1500")
        self.product.save(update_fields=["cost"])
        self.assertGreater(self.product.yandex_calculated_price, old)
        old = self.product.yandex_calculated_price
        self.integration.configuration["fbs_pricing"]["packaging"] = "500"
        self.integration.save(update_fields=["configuration"])
        self.product.refresh_from_db()
        self.assertGreater(self.product.yandex_calculated_price, old)
        self.assertFalse(SyncJob.objects.exists())

    def test_apply_is_explicit_and_uses_calculated_server_price(self):
        response = self.client.post(self.route("save"), self.payload(action="apply"))
        self.assertTrue(response.json()["ok"])
        self.product.refresh_from_db()
        self.assertEqual(self.product.yandex_market_price, self.product.yandex_calculated_price)

    def test_invalid_dimensions_and_stale_form_are_rejected(self):
        for changes in ({"height_cm": "0"}, {"height_cm": "-1"}, {"height_cm": "abc"}, {"version": "stale"}):
            self.assertEqual(self.client.post(self.route("save"), self.payload(**changes)).status_code, 400)
        self.product.refresh_from_db()
        self.assertEqual(self.product.height_cm, 2)

    def test_model_rejects_nonnumeric_dimensions_with_validation_error(self):
        self.product.length_cm = "abc"
        with self.assertRaises(ValidationError):
            self.product.full_clean()

    def test_inline_save_rejects_malformed_product_id(self):
        response = self.client.post(reverse("pricing:product_update"), {
            "product_type": "cd", "product_id": "abc", "yandex_desired_profit": "500",
        }, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])

    def test_settings_and_product_permissions_are_checked(self):
        reader = User.objects.create_user("fbs-reader", password="Test-password-123")
        reader.user_permissions.add(Permission.objects.get(content_type__app_label="pricing", codename="view_pricing"))
        self.client.force_login(reader)
        self.assertEqual(self.client.post(self.route("save"), self.payload()).status_code, 400)
        self.assertEqual(self.client.get(reverse("yandex_market:pricing_settings", args=(self.integration.pk,))).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.post(self.route("preview"), self.payload()).status_code, 302)

    def test_category_change_and_missing_rate_clear_recommendation(self):
        self.category.placement_rate = None
        self.category.save(update_fields=["placement_rate"])
        self.product.refresh_from_db()
        self.assertIsNone(self.product.yandex_calculated_price)
        self.assertIn("тариф категории", product_calculation(self.product)["message"])

    def test_only_missing_dimensions_are_imported_and_source_is_audited(self):
        remote = RemoteOffer.objects.create(integration=self.integration, offer_id="dimensions-test", category_id=50,
            snapshot={"offer": {"weightDimensions": {"length": "30", "width": "25", "height": "20", "weight": "0.5"}}})
        OfferConnection.objects.create(integration=self.integration, remote_offer=remote, cd=self.product, category_id=50)
        self.product.width_cm = None
        self.product.save(update_fields=["width_cm"])
        self.assertEqual(fill_integration_dimensions(self.integration, actor=self.user), 1)
        self.product.refresh_from_db()
        self.assertEqual(self.product.length_cm, 17)
        self.assertEqual(self.product.width_cm, 25)
        self.assertEqual(self.product.weight_grams, 140)
        self.assertTrue(ProductFieldChange.objects.filter(event__cd=self.product, field_name="dimensions_source", new_value__contains="Яндекс Маркет").exists())

    def test_api_payload_uses_shared_dimensions_and_existing_weight(self):
        remote = RemoteOffer.objects.create(integration=self.integration, offer_id="shared-dimensions", category_id=50)
        connection = OfferConnection.objects.create(integration=self.integration, remote_offer=remote, cd=self.product,
            content={"weightDimensions": {"length": 90, "width": 90, "height": 90}}, dirty_fields=["weightDimensions"])
        payload = build_content(connection)["weightDimensions"]
        self.assertEqual(payload, {"length": 17, "width": 13, "height": 2, "weight": Decimal("0.14")})

    def test_bound_category_is_used_and_override_rejected(self):
        remote = RemoteOffer.objects.create(integration=self.integration, offer_id="category-test", category_id=50)
        OfferConnection.objects.create(integration=self.integration, remote_offer=remote, cd=self.product, category_id=50)
        other = CategorySchema.objects.create(category_id=51, placement_rate=30, schema={"parameters": []})
        self.assertEqual(self.client.post(self.route("save"), self.payload(yandex_pricing_category=other.pk)).status_code, 400)

    def test_remote_category_change_recalculates_fallback_without_publishing(self):
        remote = RemoteOffer.objects.create(integration=self.integration, offer_id="remote-category", category_id=50)
        OfferConnection.objects.create(integration=self.integration, remote_offer=remote, cd=self.product)
        CategorySchema.objects.create(category_id=51, placement_rate=30, schema={"parameters": []})
        self.product.refresh_from_db()
        previous = self.product.yandex_calculated_price
        remote.category_id = 51
        remote.save(update_fields=["category_id"])
        self.product.refresh_from_db()
        self.assertGreater(self.product.yandex_calculated_price, previous)
        self.assertEqual(self.product.yandex_market_price, 3990)
        self.assertFalse(SyncJob.objects.exists())

    def test_pricing_table_ajax_still_saves_profit_without_publishing(self):
        response = self.client.post(reverse("pricing:product_update"), {"product_type": "cd", "product_id": self.product.pk,
            "yandex_desired_profit": "500"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertTrue(response.json()["ok"])
        self.product.refresh_from_db()
        self.assertEqual(self.product.yandex_desired_profit, 500)
        self.assertEqual(self.product.yandex_market_price, 3990)

    def test_settings_page_and_editable_category_table(self):
        response = self.client.get(reverse("yandex_market:pricing_settings", args=(self.integration.pk,)))
        self.assertContains(response, "Тарифы категорий")
        self.assertContains(response, "Средняя миля")

    def test_settings_save_preserves_integration_and_updates_rates(self):
        data = {key: value for key, value in configuration(packaging="60").items() if key != "middle_bands"}
        data.update({"bands-TOTAL_FORMS": "2", "bands-INITIAL_FORMS": "2", "bands-MIN_NUM_FORMS": "0", "bands-MAX_NUM_FORMS": "20",
            "bands-0-until_l": "200", "bands-0-per_l": "8", "bands-1-until_l": "", "bands-1-per_l": "5",
            "rates-TOTAL_FORMS": "1", "rates-INITIAL_FORMS": "1", "rates-MIN_NUM_FORMS": "0", "rates-MAX_NUM_FORMS": "1000",
            "rates-0-category_id": "50", "rates-0-name": "Игры", "rates-0-placement_rate": "25"})
        response = self.client.post(reverse("yandex_market:pricing_settings", args=(self.integration.pk,)), data)
        self.assertEqual(response.status_code, 302)
        self.integration.refresh_from_db()
        self.category.refresh_from_db()
        self.assertEqual(self.category.placement_rate, 25)
        self.assertEqual(self.integration.configuration["fbs_pricing"]["packaging"], "60.00")
        self.assertEqual(self.integration.business_id, 998)
        self.assertFalse(self.integration.enabled)

    def test_new_category_tariff_can_be_saved_before_loading_api_schema(self):
        from .pricing_forms import CategoryRateFormSet
        forms = CategoryRateFormSet({"rates-TOTAL_FORMS": "1", "rates-INITIAL_FORMS": "0", "rates-MIN_NUM_FORMS": "0", "rates-MAX_NUM_FORMS": "1000",
            "rates-0-category_id": "51", "rates-0-name": "Консоли", "rates-0-placement_rate": "10"}, prefix="rates")
        self.assertTrue(forms.is_valid())
        category = CategorySchema(category_id=51, name="Консоли", placement_rate=10)
        category.full_clean(exclude=["schema"])
        category.save()
        self.assertEqual(category.schema, {})
