from decimal import Decimal
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from catalog.models import Brand, CD, Platform, ProductChangeEvent, ProductType, Tech
from pricing.models import SupplierCDPrice, SupplierTechPrice
from partners.models import Supplier

from .forms import ProcurementPriceCreateForm
from .models import ProcurementPriceList
from .services import MissingProcurementWeights, create_procurement_price_list, get_missing_procurement_weights


class ProcurementDeliveryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser("delivery-admin", password="StrongAdmin!123")
        cls.supplier = Supplier.objects.create(
            name="Поставщик", letter="A", highlight_color="#37A7BA", legal_entity="A", phone_1="1",
        )
        cls.brand = Brand.objects.create(name="Sony")
        cls.general = ProductType.objects.create(name="Геймпад")
        cls.devices = ProductType.objects.create(
            name="Игровая консоль", procurement_delivery_group=ProductType.DeliveryGroup.DEVICES,
        )
        cls.storage = ProductType.objects.create(
            name="SSD", procurement_delivery_group=ProductType.DeliveryGroup.STORAGE,
        )
        cls.tech = Tech.objects.create(
            brand=cls.brand, product_type=cls.general, name="Геймпад", sku="T-1", weight_grams=500,
        )
        SupplierTechPrice.objects.create(supplier=cls.supplier, tech=cls.tech, price=100)

    def parameters(self, **overrides):
        return {
            "exchange_rate_usdt_aed": "4", "exchange_rate_usdt_rub": "80",
            "delivery_general_usdt_per_kg": "3", "delivery_devices_usdt_per_kg": "5",
            "delivery_storage_usdt_per_kg": "7", "delivery_cd_rub": "0", **overrides,
        }

    def create(self, **overrides):
        return create_procurement_price_list(actor=self.user, **self.parameters(**overrides))

    def add_tech(self, product_type, *, weight=1250, price=100, name="Техника"):
        product = Tech.objects.create(
            brand=self.brand, product_type=product_type, name=name, weight_grams=weight,
        )
        SupplierTechPrice.objects.create(supplier=self.supplier, tech=product, price=price)
        return product

    def test_three_type_groups_use_distinct_usdt_rates_and_include_delivery_in_customer_prices(self):
        console = self.add_tech(self.devices)
        ssd = self.add_tech(self.storage, weight=125)
        price_list = self.create()
        self.assertEqual(price_list.delivery_general_usdt_per_kg, Decimal("3"))
        self.assertEqual(price_list.delivery_devices_usdt_per_kg, Decimal("5"))
        self.assertEqual(price_list.delivery_storage_usdt_per_kg, Decimal("7"))
        for product, delivery, rate, surcharge in ((self.tech, "120", "3", "200"), (console, "500", "5", "500"), (ssd, "70", "7", "1000")):
            with self.subTest(product=product.pk):
                item = price_list.items.get(tech=product)
                self.assertEqual(item.base_price_rub, Decimal("2000"))
                self.assertEqual(item.delivery_rub, Decimal(delivery))
                self.assertEqual(item.prepayment_price_rub, Decimal("2000") + Decimal(delivery))
                self.assertEqual(item.postpayment_price_rub, item.prepayment_price_rub + Decimal(surcharge))
                self.assertEqual(item.weight_grams_snapshot, product.weight_grams)
                self.assertEqual(item.delivery_group_snapshot, product.product_type.procurement_delivery_group)
                self.assertEqual(item.delivery_usdt_per_kg_snapshot, Decimal(rate))

    def test_delivery_uses_fractional_kg_and_rounds_half_up_only_final_rubles(self):
        self.tech.weight_grams = 1
        self.tech.save(update_fields=("weight_grams",))
        price_list = self.create(delivery_general_usdt_per_kg="0.0625")
        self.assertEqual(price_list.items.get().delivery_rub, Decimal("0.01"))

    def test_cd_uses_fixed_rubles_without_weight_or_currency_conversion(self):
        cd = CD.objects.create(platform=Platform.objects.create(name="PS5"), name="Игра")
        SupplierCDPrice.objects.create(supplier=self.supplier, cd=cd, price=100)
        price_list = self.create(delivery_cd_rub="35.25")
        item = price_list.items.get(cd=cd)
        self.assertEqual(price_list.delivery_cd_rub, Decimal("35.25"))
        self.assertEqual(item.delivery_rub, Decimal("35.25"))
        self.assertEqual(item.prepayment_price_rub, Decimal("2035.25"))
        self.assertEqual(item.postpayment_price_rub, Decimal("2115.25"))
        self.assertIsNone(item.delivery_usdt_per_kg_snapshot)
        self.assertEqual(price_list.items.get(tech=self.tech).delivery_rub, Decimal("120"))
        newer = self.create(delivery_cd_rub="50", exchange_rate_usdt_rub="90")
        self.assertEqual(newer.items.get(cd=cd).delivery_rub, Decimal("50"))
        item.refresh_from_db()
        price_list.refresh_from_db()
        self.assertEqual(item.prepayment_price_rub, Decimal("2035.25"))
        self.assertEqual(price_list.delivery_cd_rub, Decimal("35.25"))

    def test_cd_delivery_is_added_to_each_disc_and_zero_is_allowed(self):
        platform = Platform.objects.create(name="PS5")
        for name in ("Игра 1", "Игра 2"):
            cd = CD.objects.create(platform=platform, name=name)
            SupplierCDPrice.objects.create(supplier=self.supplier, cd=cd, price=100)
        for tariff in ("0", "40.50"):
            with self.subTest(tariff=tariff):
                items = self.create(delivery_cd_rub=tariff).items.filter(product_kind="cd")
                self.assertEqual(items.count(), 2)
                for item in items:
                    self.assertEqual(item.delivery_rub, Decimal(tariff))
                    self.assertEqual(item.prepayment_price_rub, item.base_price_rub + Decimal(tariff))

    def test_cd_delivery_is_required_and_rejects_invalid_money(self):
        self.client.force_login(self.user)
        for value in ("", "-1", "NaN", "Infinity", "1.001", "1000000000000000000"):
            with self.subTest(value=value):
                response = self.client.post(reverse("price:procurement_create"), self.parameters(delivery_cd_rub=value))
                self.assertEqual(response.status_code, 200)
                self.assertIn("delivery_cd_rub", response.context["procurement_form"].errors)
                self.assertFalse(ProcurementPriceList.objects.exists())
        for value in ("-1", "NaN", "Infinity", "1000000000000000000"):
            with self.subTest(service_value=value), self.assertRaises(ValidationError):
                self.create(delivery_cd_rub=value)

    def test_only_active_products_with_positive_offers_need_weight(self):
        self.add_tech(self.general, weight=None, price=0, name="Без предложения")
        archived = self.add_tech(self.devices, weight=None, name="Архив")
        archived.is_archived = True
        archived.save(update_fields=("is_archived",))
        Tech.objects.create(brand=self.brand, product_type=self.storage, name="Без цены", weight_grams=None)
        self.assertEqual(get_missing_procurement_weights(), [])
        self.assertEqual(self.create().items.count(), 1)

    def test_missing_weight_blocks_service_without_creating_version_even_with_zero_tariff(self):
        product = self.add_tech(self.devices, weight=None)
        with self.assertRaises(MissingProcurementWeights) as caught:
            self.create(delivery_devices_usdt_per_kg=0)
        self.assertEqual([p.pk for p in caught.exception.products], [product.pk])
        self.assertFalse(ProcurementPriceList.objects.exists())

    def test_weight_step_preserves_inputs_and_saves_weight_with_audit_on_confirmation(self):
        product = self.add_tech(self.devices, weight=None, name="Портативная консоль")
        self.client.force_login(self.user)
        response = self.client.post(reverse("price:procurement_create"), self.parameters(delivery_cd_rub="35.25"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "price/procurement_prepare.html")
        self.assertContains(response, "Портативная консоль")
        self.assertContains(response, f'name="weight_{product.pk}"')
        self.assertEqual(response.context["procurement_form"]["delivery_devices_usdt_per_kg"].value(), "5")
        self.assertEqual(response.context["procurement_form"]["delivery_cd_rub"].value(), "35.25")
        self.assertFalse(ProcurementPriceList.objects.exists())
        product.refresh_from_db()
        self.assertIsNone(product.weight_grams)
        response = self.client.post(reverse("price:procurement_create"), {
            **self.parameters(delivery_cd_rub="35.25"), "weights_submitted": "1", f"weight_{product.pk}": "1500",
        })
        price_list = ProcurementPriceList.objects.get()
        self.assertRedirects(response, reverse("price:procurement_detail", args=(price_list.pk,)))
        product.refresh_from_db()
        self.assertEqual(product.weight_grams, 1500)
        self.assertEqual(price_list.items.get(tech=product).delivery_rub, Decimal("600"))
        self.assertEqual(price_list.delivery_cd_rub, Decimal("35.25"))
        event = ProductChangeEvent.objects.get(tech=product, source=ProductChangeEvent.Source.CRM)
        change = event.field_changes.get(field_name="weight_grams")
        self.assertEqual((change.old_value, change.new_value), ("", "1500"))

    def test_invalid_or_missing_weight_preserves_form_and_does_not_write(self):
        product = self.add_tech(self.devices, weight=None)
        self.client.force_login(self.user)
        for value in ("", "0", "-5", "1.5", "abc"):
            with self.subTest(value=value):
                response = self.client.post(reverse("price:procurement_create"), {
                    **self.parameters(), "weights_submitted": "1", f"weight_{product.pk}": value,
                })
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["weights_form"].errors)
                self.assertFalse(ProcurementPriceList.objects.exists())
                product.refresh_from_db()
                self.assertIsNone(product.weight_grams)

    def test_missing_and_negative_tariffs_are_rejected_without_losing_input(self):
        self.client.force_login(self.user)
        for value in ("", "-1", "NaN", "Infinity"):
            with self.subTest(value=value):
                data = self.parameters(delivery_general_usdt_per_kg=value)
                self.assertFalse(ProcurementPriceCreateForm(data).is_valid())
                response = self.client.post(reverse("price:procurement_create"), data)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["procurement_form"].errors)
                self.assertEqual(response.context["procurement_form"]["exchange_rate_usdt_aed"].value(), "4")
                self.assertFalse(ProcurementPriceList.objects.exists())

    def test_invalid_tariff_on_weight_step_preserves_entered_weight(self):
        product = self.add_tech(self.devices, weight=None)
        self.client.force_login(self.user)
        response = self.client.post(reverse("price:procurement_create"), {
            **self.parameters(delivery_devices_usdt_per_kg="-1"),
            "weights_submitted": "1", f"weight_{product.pk}": "1500",
        })
        self.assertEqual(response.context["weights_form"][f"weight_{product.pk}"].value(), "1500")
        self.assertFalse(ProcurementPriceList.objects.exists())

    def test_new_missing_weight_after_preflight_keeps_previous_weight_input(self):
        first = self.add_tech(self.devices, weight=None, name="Первая")
        second = self.add_tech(self.storage, weight=None, name="Вторая")
        self.client.force_login(self.user)
        with patch("price.views.get_missing_procurement_weights", return_value=[first]):
            response = self.client.post(reverse("price:procurement_create"), {
                **self.parameters(), "weights_submitted": "1", f"weight_{first.pk}": "1500",
            })
        weights_form = response.context["weights_form"]
        self.assertEqual(weights_form[f"weight_{first.pk}"].value(), "1500")
        self.assertIn(f"weight_{second.pk}", weights_form.fields)
        self.assertFalse(ProcurementPriceList.objects.exists())

    def test_service_rejects_negative_or_nonfinite_tariffs(self):
        for value in ("-1", "NaN", "Infinity"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                self.create(delivery_general_usdt_per_kg=value)
        self.assertFalse(ProcurementPriceList.objects.exists())

    def test_worker_cannot_set_weight_without_weight_permission(self):
        product = self.add_tech(self.devices, weight=None)
        worker = User.objects.create_user("delivery-worker")
        worker.user_permissions.add(Permission.objects.get(codename="create_procurement_price_list"))
        self.client.force_login(worker)
        response = self.client.post(reverse("price:procurement_create"), {
            **self.parameters(), "weights_submitted": "1", f"weight_{product.pk}": "1500",
        })
        self.assertContains(response, "нет права изменения веса техники")
        with self.assertRaisesMessage(ValidationError, "право изменения веса"):
            create_procurement_price_list(actor=worker, **self.parameters(), weights={product.pk: 1500})
        product.refresh_from_db()
        self.assertIsNone(product.weight_grams)
        self.assertFalse(ProcurementPriceList.objects.exists())

    def test_worker_with_weight_permission_can_complete_generation(self):
        product = self.add_tech(self.devices, weight=None)
        worker = User.objects.create_user("weight-worker")
        worker.user_permissions.add(*Permission.objects.filter(codename__in=(
            "create_procurement_price_list", "change_tech_weight",
        )))
        self.client.force_login(worker)
        response = self.client.post(reverse("price:procurement_create"), {
            **self.parameters(), "weights_submitted": "1", f"weight_{product.pk}": "1500",
        })
        self.assertEqual(response.status_code, 302)
        product.refresh_from_db()
        self.assertEqual(product.weight_grams, 1500)
        self.assertEqual(ProcurementPriceList.objects.count(), 1)

    def test_invalid_second_weight_rolls_back_first_weight_and_audit(self):
        first = self.add_tech(self.devices, weight=None, name="Первая")
        second = self.add_tech(self.storage, weight=None, name="Вторая")
        with self.assertRaises(ValidationError):
            self.create(weights={first.pk: 1500, second.pk: "1.5"})
        first.refresh_from_db()
        self.assertIsNone(first.weight_grams)
        self.assertFalse(ProductChangeEvent.objects.filter(field_changes__field_name="weight_grams").exists())
        self.assertFalse(ProcurementPriceList.objects.exists())

    def test_stale_weight_input_never_overwrites_an_existing_weight(self):
        item = self.create(weights={self.tech.pk: 9999}).items.get()
        self.tech.refresh_from_db()
        self.assertEqual(self.tech.weight_grams, 500)
        self.assertEqual(item.weight_grams_snapshot, 500)

    def test_unrelated_weight_id_is_rejected(self):
        with self.assertRaisesMessage(ValidationError, "не участвует"):
            self.create(weights={999999: 1500})

    def test_audit_failure_rolls_back_saved_weight_and_price_list(self):
        product = self.add_tech(self.devices, weight=None)
        with patch("catalog.product_identifiers.record_product_changes", side_effect=RuntimeError("audit failed")):
            with self.assertRaises(RuntimeError):
                self.create(weights={product.pk: 1500})
        product.refresh_from_db()
        self.assertIsNone(product.weight_grams)
        self.assertFalse(ProcurementPriceList.objects.exists())

    def test_known_weights_generate_without_extra_step_and_tariffs_stay_private(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("price:procurement_create"), self.parameters())
        price_list = ProcurementPriceList.objects.get()
        self.assertRedirects(response, reverse("price:procurement_detail", args=(price_list.pk,)))
        viewer = User.objects.create_user("price-viewer")
        viewer.user_permissions.add(Permission.objects.get(codename="view_price_page"))
        self.client.force_login(viewer)
        response = self.client.get(reverse("price:procurement_detail", args=(price_list.pk,)))
        self.assertNotContains(response, "Доставка при создании прайса")
        self.assertNotContains(response, "USDT/кг")

    def test_snapshot_stays_unchanged_after_weight_group_and_exchange_rate_changes(self):
        price_list = self.create()
        item = price_list.items.get()
        self.tech.weight_grams = 3000
        self.tech.save(update_fields=("weight_grams",))
        self.general.procurement_delivery_group = ProductType.DeliveryGroup.STORAGE
        self.general.save(update_fields=("procurement_delivery_group",))
        self.create(exchange_rate_usdt_rub=90)
        item.refresh_from_db()
        self.assertEqual(item.weight_grams_snapshot, 500)
        self.assertEqual(item.delivery_group_snapshot, ProductType.DeliveryGroup.GENERAL)
        self.assertEqual(item.delivery_rub, Decimal("120"))
        self.assertEqual(item.prepayment_price_rub, Decimal("2120"))

    def test_type_migration_assigns_specific_groups_without_classifying_accessories_as_devices(self):
        handheld = ProductType.objects.create(name="Портативная игровая консоль")
        accessory = ProductType.objects.create(name="Аксессуар для игровой консоли")
        memory = ProductType.objects.create(name="MicroSD-карта")
        migration = import_module("catalog.migrations.0029_producttype_procurement_delivery_group")
        migration.assign_delivery_groups(apps, SimpleNamespace(connection=connection))
        for product_type, expected in (
            (handheld, "devices"), (self.devices, "devices"), (memory, "storage"), (accessory, "general"),
        ):
            product_type.refresh_from_db()
            self.assertEqual(product_type.procurement_delivery_group, expected)

    def test_detail_opens_price_list_with_more_than_a_thousand_products_of_each_kind(self):
        platform = Platform.objects.create(name="PS5")
        discs = CD.objects.bulk_create([
            CD(platform=platform, name=f"Диск {index:04d}", sku=f"LARGE-CD-{index}")
            for index in range(1005)
        ])
        tech = Tech.objects.bulk_create([
            Tech(brand=self.brand, product_type=self.general, name=f"Техника {index:04d}",
                 sku=f"LARGE-TECH-{index}", weight_grams=500)
            for index in range(1005)
        ])
        SupplierCDPrice.objects.bulk_create([
            SupplierCDPrice(supplier=self.supplier, cd=product, price=100) for product in discs
        ])
        SupplierTechPrice.objects.bulk_create([
            SupplierTechPrice(supplier=self.supplier, tech=product, price=100) for product in tech
        ])
        price_list = self.create(delivery_cd_rub="35.25")
        self.client.force_login(self.user)
        response = self.client.get(reverse("price:procurement_detail", args=(price_list.pk,)))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-procurement-row", count=2011)
        self.assertContains(response, discs[-1].sku)
        self.assertContains(response, tech[-1].sku)
        with self.assertNumQueries(0):
            for item in response.context["price_list"].items.all():
                self.assertEqual(item.selected_supplier.pk, self.supplier.pk)
                self.assertEqual(item.product.pk, item.product_id)
