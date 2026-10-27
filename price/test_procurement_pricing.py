import json
from decimal import Decimal

from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from catalog.models import CD, Platform
from orders.services import create_customer_procurement_order
from partners.models import Supplier

from .models import ProcurementPriceList, ProcurementPriceListItem, ProcurementPricePreference
from .services import NegativeProcurementMarkup, calculate_postpayment, calculate_prepayment, update_procurement_pricing


class ProcurementPricingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser("pricing-admin")
        cls.supplier = Supplier.objects.create(
            name="Поставщик", letter="A", highlight_color="#37A7BA", legal_entity="A", phone_1="1",
        )
        cls.price_list = ProcurementPriceList.objects.create(exchange_rate_aed_rub=20, created_by=cls.user)
        platform = Platform.objects.create(name="PS5")
        cls.items = []
        for number in range(2):
            cd = CD.objects.create(platform=platform, name=f"Игра {number}", sku=f"CD-{number}")
            cls.items.append(ProcurementPriceListItem.objects.create(
                price_list=cls.price_list, product_kind="cd", cd=cd,
                product_name_snapshot=cd.name, article_snapshot=cd.sku,
                selected_supplier=cls.supplier, supplier_price_aed=50, exchange_rate_aed_rub=20,
                base_price_rub=1000, delivery_rub=35, prepayment_price_rub=1035, postpayment_price_rub=1095,
            ))

    def rows(self, **changes):
        rows = {item.pk: {"markup": "0", "delivery": "35"} for item in self.items}
        rows[self.items[0].pk].update(changes)
        return rows

    def update(self, rows=None, **permissions):
        return update_procurement_pricing(
            actor=self.user, price_list_id=self.price_list.pk, rows=rows or self.rows(),
            **{"can_change_markup": True, "can_change_delivery": True, **permissions},
        )

    def assert_prices(self, markup, prepayment, postpayment):
        item = self.items[0]
        item.refresh_from_db()
        self.assertEqual(item.markup_rub, Decimal(markup))
        self.assertEqual(item.prepayment_price_rub, Decimal(prepayment))
        self.assertEqual(item.postpayment_price_rub, Decimal(postpayment))

    def test_inverse_rule_at_all_boundaries(self):
        for prepayment in ("0", "0.01", "1999.99", "2000", "2999.99", "3000", "90071992547409.91"):
            with self.subTest(prepayment=prepayment):
                self.assertEqual(calculate_prepayment(calculate_postpayment(prepayment)), Decimal(prepayment))

    def test_postpayment_gaps_have_no_valid_prepayment(self):
        for value in ("0", "59.99", "2060", "2079.99", "3080", "3099.99", "NaN", "Infinity", "-1"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                calculate_prepayment(value)

    def test_prepayment_is_authoritative_and_markup_is_derived_on_server(self):
        self.update(self.rows(price_source="prepayment", prepayment="2000.01", markup="999", postpayment="1"))
        self.assert_prices("975", "2010", "2090")

    def test_postpayment_is_authoritative_and_both_other_values_are_derived(self):
        self.update(self.rows(price_source="postpayment", postpayment="3100", prepayment="1", markup="999"))
        self.assert_prices("1965", "3000", "3100")

    def test_changed_delivery_is_used_in_reverse_markup(self):
        self.update(self.rows(price_source="prepayment", prepayment="2000", delivery="100.25"))
        self.assert_prices("899.75", "2000", "2080")

    def test_original_markup_editing_still_works(self):
        self.update(self.rows(markup="0.01", delivery="35.25"))
        self.assert_prices("4.75", "1040", "1100")

    def test_invalid_final_prices_and_unknown_source_do_not_write(self):
        for changes in (
            {"price_source": "prepayment", "prepayment": "1034.99"},
            {"price_source": "prepayment", "prepayment": "NaN"},
            {"price_source": "prepayment", "prepayment": "1000000000000000000"},
            {"price_source": "postpayment", "postpayment": "2070"},
            {"price_source": "postpayment", "postpayment": "60"},
            {"price_source": "other"},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.update(self.rows(**changes))
            self.assert_prices("0", "1035", "1095")

    def test_final_price_edits_require_markup_permission(self):
        for source, value in (("prepayment", "2000"), ("postpayment", "2080")):
            with self.subTest(source=source), self.assertRaisesMessage(ValidationError, "нет права изменять наценку"):
                self.update(self.rows(price_source=source, **{source: value}), can_change_markup=False)
        self.assert_prices("0", "1035", "1095")

    def test_final_price_cannot_bypass_delivery_permission(self):
        with self.assertRaisesMessage(ValidationError, "нет права изменять доставку"):
            self.update(self.rows(price_source="prepayment", prepayment="2000", delivery="100"),
                        can_change_delivery=False)
        self.assert_prices("0", "1035", "1095")

    def test_invalid_later_row_rolls_back_earlier_row(self):
        rows = self.rows(price_source="prepayment", prepayment="2000")
        rows[self.items[1].pk].update(price_source="postpayment", postpayment="2070")
        with self.assertRaises(ValidationError):
            self.update(rows)
        self.assert_prices("0", "1035", "1095")

    @override_settings(DATA_UPLOAD_MAX_NUMBER_FIELDS=2)
    def test_json_form_recalculates_on_backend_with_small_field_limit(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("price:procurement_update", args=(self.price_list.pk,)), {
            "pricing_rows": json.dumps(self.rows(price_source="postpayment", postpayment="2080.01")),
        })
        self.assertRedirects(response, reverse("price:procurement_detail", args=(self.price_list.pk,)))
        self.assert_prices("975", "2010", "2090")

    def test_malformed_json_or_wrong_composition_does_not_write(self):
        self.client.force_login(self.user)
        for payload in ("{", "[]", "{}", json.dumps({str(item.pk): [] for item in self.items})):
            with self.subTest(payload=payload):
                response = self.client.post(reverse("price:procurement_update", args=(self.price_list.pk,)), {
                    "pricing_rows": payload,
                })
                self.assertEqual(response.status_code, 302)
                self.assert_prices("0", "1035", "1095")

    def test_legacy_form_submission_still_works(self):
        self.client.force_login(self.user)
        data = {f"{name}_{item.pk}": value for item in self.items
                for name, value in (("markup", "10.25"), ("delivery", "35"))}
        response = self.client.post(reverse("price:procurement_update", args=(self.price_list.pk,)), data)
        self.assertEqual(response.status_code, 302)
        self.assert_prices("15", "1050", "1110")

    def test_delivery_only_user_cannot_change_final_price_through_json(self):
        worker = User.objects.create_user("delivery-only")
        worker.user_permissions.add(Permission.objects.get(codename="change_procurement_delivery"))
        self.client.force_login(worker)
        response = self.client.post(reverse("price:procurement_update", args=(self.price_list.pk,)), {
            "pricing_rows": json.dumps(self.rows(price_source="prepayment", prepayment="2000")),
        })
        self.assertEqual(response.status_code, 302)
        self.assert_prices("0", "1035", "1095")

    def test_final_price_inputs_follow_markup_permission_and_script_has_version(self):
        worker = User.objects.create_user("delivery-editor")
        worker.user_permissions.add(*Permission.objects.filter(codename__in=("view_price_page", "change_procurement_delivery")))
        self.client.force_login(worker)
        response = self.client.get(reverse("price:procurement_detail", args=(self.price_list.pk,)))
        self.assertContains(response, "procurement-pricing.js?v=20261027-suppliers-3")
        self.assertContains(response, 'class="compact-input danger-text" name="markup_', count=2)
        self.assertContains(response, 'data-base="1000.00"')
        self.assertContains(response, f'name="prepayment_{self.items[0].pk}" value="1035.00"')
        self.assertContains(response, 'data-prepayment aria-label="Предоплата: Игра 0" readonly')
        self.assertContains(response, 'data-postpayment aria-label="Постоплата: Игра 0" readonly')
        worker.user_permissions.add(Permission.objects.get(codename="change_procurement_markup"))
        response = self.client.get(reverse("price:procurement_detail", args=(self.price_list.pk,)))
        self.assertNotContains(response, 'data-prepayment aria-label="Предоплата: Игра 0" readonly')

    def test_used_price_list_cannot_be_changed_through_final_price(self):
        order = create_customer_procurement_order(
            actor=self.user, price_list_id=self.price_list.pk, recipient="Покупатель", comment="",
            lines=[{"price_list_item_id": self.items[0].pk, "prepayment_quantity": 1, "postpayment_quantity": 1}],
        )
        with self.assertRaisesMessage(ValidationError, "уже использован"):
            self.update(self.rows(price_source="prepayment", prepayment="2000"))
        self.assert_prices("0", "1035", "1095")
        self.assertEqual(order.items.get().prepayment_unit_price, Decimal("1035"))

    def test_negative_markup_requires_confirmation_and_rolls_back_all_prices_and_memory(self):
        rows = self.rows(markup="10")
        rows[self.items[1].pk].update(markup="-0.01")
        with self.assertRaises(NegativeProcurementMarkup):
            self.update(rows)
        self.assert_prices("0", "1035", "1095")
        self.assertFalse(ProcurementPricePreference.objects.exists())
        self.update(rows, negative_markup_confirmed=True)
        item = self.items[1]
        item.refresh_from_db()
        self.assertEqual(item.original_markup_rub, Decimal('-0.01'))
        self.assertEqual(item.markup_rub, Decimal("5"))
        self.assertEqual(item.prepayment_price_rub, Decimal("1040"))
        self.assertEqual(ProcurementPricePreference.objects.get(cd=item.cd).markup_rub, Decimal("-0.01"))

    def test_negative_markup_from_either_final_price_is_allowed_after_confirmation(self):
        for source, value in (("prepayment", "1000"), ("postpayment", "1060")):
            with self.subTest(source=source):
                self.update(self.rows(price_source=source, **{source: value}), negative_markup_confirmed=True)
                self.assert_prices("-35", "1000", "1060")

    def test_negative_prepayment_is_rejected_even_with_confirmation(self):
        with self.assertRaises(ValidationError):
            self.update(self.rows(markup="-1035.01"), negative_markup_confirmed=True)
        self.assert_prices("0", "1035", "1095")

    def test_backend_returns_confirmation_page_then_saves_explicit_confirmation(self):
        self.client.force_login(self.user)
        data = {"pricing_rows": json.dumps(self.rows(price_source="prepayment", prepayment="1000"))}
        response = self.client.post(reverse("price:procurement_update", args=(self.price_list.pk,)), data)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "price/procurement_confirm.html")
        self.assertContains(response, "Сохранить отрицательную наценку?")
        self.assert_prices("0", "1035", "1095")
        self.assertFalse(ProcurementPricePreference.objects.exists())
        response = self.client.post(reverse("price:procurement_update", args=(self.price_list.pk,)), {
            **data, "negative_markup_confirmed": "true",
        })
        self.assertEqual(response.status_code, 302)
        self.assert_prices("-35", "1000", "1060")
        response = self.client.get(reverse("price:procurement_detail", args=(self.price_list.pk,)))
        self.assertContains(response, 'class="compact-input danger-text" name="markup_')

    def test_confirmation_does_not_bypass_markup_permission(self):
        with self.assertRaisesMessage(ValidationError, "нет права изменять наценку"):
            self.update(self.rows(markup="-35"), can_change_markup=False, negative_markup_confirmed=True)
        self.assert_prices("0", "1035", "1095")
