import json
from decimal import Decimal
from types import SimpleNamespace

from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from accounts.models import User
from catalog.models import Brand, CD, Platform, ProductType, Tech
from orders.services import create_customer_procurement_order
from partners.models import Supplier
from pricing.models import SupplierCDPrice, SupplierTechPrice

from .models import ProcurementPriceList, ProcurementPriceListItem, ProcurementPricePreference
from .postpayment_rules import tech_postpayment_surcharge
from .services import (
    MissingProcurementSurcharges, calculate_postpayment, calculate_prepayment,
    create_procurement_price_list, update_procurement_pricing,
)


class PostpaymentRuleTests(SimpleTestCase):
    def test_document_rules_and_user_clarifications(self):
        for kind, brand, name, expected in (
            ("Геймпад", "Sony", "PS4 DualShock", 200),
            ("Геймпад", "Sony", "PS5 DualSense", 200),
            ("Геймпад", "Sony", "DualSense Edge 30th Anniversary", 500),
            ("Геймпад", "Nintendo", "NS2 Pro Controller", 200),
            ("Геймпад", "Microsoft", "Xbox Elite Series 2", 200),
            ("Геймпад", "Valve", "Steam Controller", 500),
            ("Геймпад", "Backbone", "Backbone One PlayStation Edition for iPhone", 100),
            ("Геймпад", "Sega", "SEGA Genesis Control Pad", 100),
            ("Геймпад", "Nacon", "Revolution 5", 200),
            ("Геймпад", "PowerA", "Nintendo Switch 2 Advantage", 200),
            ("Игровая консоль", "Sony", "PS5 Slim 30th Anniversary", 500),
            ("Игровая консоль", "Sony", "PS5 1216A Europe", 500),
            ("Игровая консоль", "Sony", "PS5 Pro 7100B", 1000),
            ("Игровая консоль", "Microsoft", "Xbox Series X", 500),
            ("Игровая консоль", "Nintendo", "Nintendo Switch", 500),
            ("Игровая консоль", "Valve", "Steam Machine 512gb + Steam Controller", 1000),
            ("Портативная игровая консоль", "Valve", "Steam Deck OLED", 500),
            ("Портативная игровая консоль", "Lenovo", "Lenovo Go", 500),
            ("Портативная игровая консоль", "Nintendo", "Nintendo Switch 2", 500),
            ("Стриминговая приставка", "Sony", "PS5 Remote Portal", 500),
            ("Сменные панели для игровой консоли", "Sony", "PS5 Pro Console Covers", 200),
            ("VR-шлем", "Meta", "Oculus Quest 3S", 500),
            ("VR-шлем", "Meta", "Meta Quest Elite Strap with Battery", 100),
            ("VR-аксессуар", "Meta", "Quest 3 Charging Station", 100),
            ("VR-аксессуар", "Sony", "PS VR2 PC Adapter", 100),
            ("AR-очки", "Xreal", "Xreal Air 2 Pro", 500),
            ("Умные очки", "Ray-Ban", "Meta Wayfarer", 500),
            ("Адаптер для геймпада", "Cronus", "Cronus Zen", 200),
            ("Адаптер для геймпада", "XIM", "XIM Matrix", 200),
            ("Внешний привод для консоли", "Sony", "PS5 Disc Drive", 200),
            ("SSD", "WD_BLACK", "PS5 NVMe SSD", 1000),
            ("HDD", "WD", "HDD", 1000),
            ("MicroSD-карта", "Nintendo", "NS2 microSD 256", 100),
            ("Подставка для игровой консоли", "Без бренда", "Vertical Stand PS5", 50),
            ("Охлаждающая подставка для консоли", "Без бренда", "PS5 Slim Silent", 100),
            ("Зарядная станция для геймпадов", "Sony", "DualSense Charging Station", 100),
            ("Камера для игровой консоли", "Sony", "PS5 HD Camera", 100),
            ("Аксессуар для игровой консоли", "Nintendo", "NS2 Joy-Con Wheel", 100),
            ("Аксессуар для игровой консоли", "Microsoft", "Xbox Rechargeable Battery", 100),
            ("Руль", "Logitech G", "G29 + Astro A10", 500),
            ("Ручная коробка передач для симрейсинга", "Logitech G", "Shifter G29", 200),
            ("Игровая гарнитура", "Nintendo", "NS2 Airlite", 200),
            ("Наушники", "Sony", "WH-1000 XM6", 200),
            ("Ретро-консоль", "Sony", "PlayStation Classic", 200),
            ("Ретро-консоль", "Kinhank", "Motion X", 200),
            ("Коллекционная фигурка", "POP MART", "Labubu Energy", 100),
            ("Кабель питания", "Без бренда", "Кабель питания", 100),
        ):
            with self.subTest(kind=kind, brand=brand, name=name):
                product = SimpleNamespace(product_type=SimpleNamespace(name=kind), brand=SimpleNamespace(name=brand), name=name)
                self.assertEqual(tech_postpayment_surcharge(product), Decimal(expected))

    def test_unknown_type_requires_explicit_rate(self):
        product = SimpleNamespace(product_type=SimpleNamespace(name="Неизвестный тип"),
                                  brand=SimpleNamespace(name="Новый бренд"), name="Новый товар")
        self.assertIsNone(tech_postpayment_surcharge(product))

    def test_fixed_surcharge_inverse_and_zero(self):
        for fee in ("0", "100", "1000", "250.25"):
            self.assertEqual(calculate_prepayment(calculate_postpayment("2000.01", surcharge=fee), surcharge=fee), Decimal("2000.01"))
        with self.assertRaises(ValidationError):
            calculate_prepayment("99.99", surcharge="100")


class ProcurementSurchargeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser("surcharge-admin")
        cls.supplier = Supplier.objects.create(name="Поставщик", letter="A", legal_entity="A", phone_1="1")
        cls.brand = Brand.objects.create(name="Sony")
        cls.kind = ProductType.objects.create(name="Геймпад")
        cls.tech = Tech.objects.create(brand=cls.brand, product_type=cls.kind, name="PS5 DualSense", weight_grams=500)
        cls.cd = CD.objects.create(platform=Platform.objects.create(name="PS5"), name="Игра")
        SupplierTechPrice.objects.create(supplier=cls.supplier, tech=cls.tech, price=100)
        SupplierCDPrice.objects.create(supplier=cls.supplier, cd=cls.cd, price=100)

    def parameters(self, **overrides):
        return {"exchange_rate_usdt_aed": "4", "exchange_rate_usdt_rub": "80", "delivery_cd_rub": "0",
                "delivery_general_usdt_per_kg": "0", "delivery_devices_usdt_per_kg": "0",
                "delivery_storage_usdt_per_kg": "0", **overrides}

    def create(self, **overrides):
        return create_procurement_price_list(actor=self.user, **self.parameters(**overrides))

    def rows(self, price_list, *, product_kind="tech", **changes):
        rows = {item.pk: {"markup": str(item.markup_rub), "delivery": str(item.delivery_rub)} for item in price_list.items.all()}
        rows[price_list.items.get(product_kind=product_kind).pk].update(changes)
        return rows

    def update(self, price_list, rows, **overrides):
        return update_procurement_pricing(actor=self.user, price_list_id=price_list.pk, rows=rows,
                                         **{"can_change_markup": True, "can_change_delivery": True, **overrides})

    def test_new_tech_uses_document_rate_and_cd_keeps_tiered_rule(self):
        for rate, cd_fee in (("40", "60"), ("80", "80"), ("120", "100")):
            version = self.create(exchange_rate_usdt_rub=rate)
            tech = version.items.get(tech=self.tech)
            cd = version.items.get(cd=self.cd)
            self.assertEqual(tech.postpayment_surcharge_rub, Decimal("200"))
            self.assertEqual(tech.postpayment_price_rub, tech.prepayment_price_rub + Decimal("200"))
            self.assertIsNone(cd.postpayment_surcharge_rub)
            self.assertEqual(cd.effective_postpayment_surcharge_rub, Decimal(cd_fee))

    def test_edit_surcharge_changes_only_postpayment_and_is_remembered(self):
        version = self.create()
        self.update(version, self.rows(version, postpayment_surcharge="500.25", surcharge_mode="fixed"))
        item = version.items.get(tech=self.tech)
        self.assertEqual(item.markup_rub, 0)
        self.assertEqual(item.prepayment_price_rub, Decimal("2000"))
        self.assertEqual(item.postpayment_price_rub, Decimal("2510"))
        self.assertEqual(ProcurementPricePreference.objects.get(tech=self.tech).postpayment_surcharge_rub, Decimal("500.25"))
        newer = self.create(exchange_rate_usdt_rub="90")
        self.assertEqual(newer.items.get(tech=self.tech).postpayment_price_rub, Decimal("2760"))
        self.assertEqual(version.items.get(tech=self.tech).postpayment_price_rub, Decimal("2510"))

    def test_postpayment_edit_uses_fixed_surcharge_and_current_negative_confirmation(self):
        version = self.create()
        self.update(version, self.rows(version, price_source="postpayment", postpayment="2060",
                                      postpayment_surcharge="200", surcharge_mode="fixed"), negative_markup_confirmed=True)
        item = version.items.get(tech=self.tech)
        self.assertEqual(item.prepayment_price_rub, Decimal("1860"))
        self.assertEqual(item.markup_rub, Decimal("-140"))

    def test_cd_manual_override_is_remembered_while_unedited_cd_remains_tiered(self):
        version = self.create()
        self.update(version, self.rows(version, product_kind="cd", postpayment_surcharge="333.33", surcharge_mode="fixed"))
        newer = self.create(exchange_rate_usdt_rub="120")
        self.assertEqual(newer.items.get(cd=self.cd).postpayment_price_rub, Decimal("3340"))
        self.assertEqual(ProcurementPricePreference.objects.get(cd=self.cd).postpayment_surcharge_rub, Decimal("333.33"))

    def test_invalid_surcharge_rolls_back_all_rows_and_memory(self):
        version = self.create()
        for value in ("", "-1", "-0.001", "1.001", "NaN", "Infinity", "1000000000000000000"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                self.update(version, self.rows(version, postpayment_surcharge=value))
            self.assertEqual(version.items.get(tech=self.tech).postpayment_price_rub, Decimal("2200"))
            self.assertFalse(ProcurementPricePreference.objects.exists())

    def test_surcharge_edit_requires_markup_permission(self):
        version = self.create()
        with self.assertRaisesMessage(ValidationError, "нет права изменять доплату"):
            self.update(version, self.rows(version, postpayment_surcharge="500"), can_change_markup=False)
        self.assertFalse(ProcurementPricePreference.objects.exists())

    def test_unknown_tech_prompts_before_creation_and_saves_custom_rate(self):
        self.kind.name = "Новый тип"
        self.kind.save(update_fields=("name",))
        with self.assertRaises(MissingProcurementSurcharges):
            self.create()
        self.assertFalse(ProcurementPriceList.objects.exists())
        self.client.force_login(self.user)
        response = self.client.post(reverse("price:procurement_create"), self.parameters())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Укажите доплаты за постоплату")
        response = self.client.post(reverse("price:procurement_create"), {
            **self.parameters(), "surcharges_submitted": "1", f"surcharge_{self.tech.pk}": "450.50",
        })
        self.assertEqual(response.status_code, 302)
        version = ProcurementPriceList.objects.get()
        self.assertEqual(version.items.get(tech=self.tech).postpayment_price_rub, Decimal("2460"))
        self.assertEqual(self.create().items.get(tech=self.tech).postpayment_surcharge_rub, Decimal("450.50"))

    def test_unknown_rate_and_missing_weight_share_preparation_and_invalid_input_writes_nothing(self):
        self.kind.name = "Новый тип"
        self.kind.save(update_fields=("name",))
        self.tech.weight_grams = None
        self.tech.save(update_fields=("weight_grams",))
        self.client.force_login(self.user)
        response = self.client.post(reverse("price:procurement_create"), self.parameters())
        self.assertIsNotNone(response.context["weights_form"])
        self.assertIsNotNone(response.context["surcharges_form"])
        response = self.client.post(reverse("price:procurement_create"), {
            **self.parameters(), "weights_submitted": "1", "surcharges_submitted": "1",
            f"weight_{self.tech.pk}": "500", f"surcharge_{self.tech.pk}": "-1",
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["surcharges_form"].errors)
        self.tech.refresh_from_db()
        self.assertIsNone(self.tech.weight_grams)
        self.assertFalse(ProcurementPriceList.objects.exists())

    def test_missing_surcharge_rolls_back_weight_saved_during_creation(self):
        self.kind.name = "Новый тип"
        self.kind.save(update_fields=("name",))
        self.tech.weight_grams = None
        self.tech.save(update_fields=("weight_grams",))
        with self.assertRaises(MissingProcurementSurcharges):
            self.create(weights={self.tech.pk: 600})
        self.tech.refresh_from_db()
        self.assertIsNone(self.tech.weight_grams)
        self.assertFalse(ProcurementPriceList.objects.exists())

    def test_legacy_tech_snapshot_is_not_recalculated_by_new_default(self):
        version = ProcurementPriceList.objects.create(created_by=self.user, exchange_rate_aed_rub=20)
        item = ProcurementPriceListItem.objects.create(
            price_list=version, product_kind="tech", tech=self.tech, product_name_snapshot=self.tech.name,
            article_snapshot="T", selected_supplier=self.supplier, supplier_price_aed=100, exchange_rate_aed_rub=20,
            base_price_rub=2000, prepayment_price_rub=2000, postpayment_price_rub=2080,
        )
        self.assertEqual(item.effective_postpayment_surcharge_rub, Decimal("80"))
        self.update(version, {item.pk: {"markup": "100", "delivery": "0"}})
        item.refresh_from_db()
        self.assertEqual(item.postpayment_price_rub, Decimal("2180"))
        self.assertEqual(item.postpayment_surcharge_rub, Decimal("80"))
        self.assertIsNone(ProcurementPricePreference.objects.get(tech=self.tech).postpayment_surcharge_rub)
        self.assertEqual(self.create().items.get(tech=self.tech).postpayment_surcharge_rub, Decimal("200"))

    def test_default_is_not_frozen_but_explicit_override_survives_model_change(self):
        version = self.create()
        self.update(version, self.rows(version))
        self.assertIsNone(ProcurementPricePreference.objects.get(tech=self.tech).postpayment_surcharge_rub)
        self.tech.brand = Brand.objects.create(name="Valve")
        self.tech.save(update_fields=("brand",))
        self.assertEqual(self.create().items.get(tech=self.tech).postpayment_surcharge_rub, Decimal("500"))
        self.update(version, self.rows(version, postpayment_surcharge="350"))
        self.assertEqual(self.create().items.get(tech=self.tech).postpayment_surcharge_rub, Decimal("350"))

    def test_json_endpoint_and_readonly_fields_follow_markup_permission(self):
        version = self.create()
        worker = User.objects.create_user("surcharge-worker")
        worker.user_permissions.add(*Permission.objects.filter(codename__in=("view_price_page", "change_procurement_delivery")))
        self.client.force_login(worker)
        response = self.client.get(reverse("price:procurement_detail", args=(version.pk,)))
        self.assertContains(response, 'data-postpayment-surcharge aria-label="Доплата за постоплату: PS5 DualSense" readonly')
        data = {"pricing_rows": json.dumps(self.rows(version, postpayment_surcharge="500"))}
        self.client.post(reverse("price:procurement_update", args=(version.pk,)), data)
        self.assertEqual(version.items.get(tech=self.tech).postpayment_price_rub, Decimal("2200"))
        worker.user_permissions.add(Permission.objects.get(codename="change_procurement_markup"))
        response = self.client.post(reverse("price:procurement_update", args=(version.pk,)), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(version.items.get(tech=self.tech).postpayment_price_rub, Decimal("2500"))

    def test_used_version_remains_protected(self):
        version = self.create()
        order = create_customer_procurement_order(actor=self.user, price_list_id=version.pk, recipient="Покупатель", comment="",
                                                 lines=[{"price_list_item_id": version.items.get(tech=self.tech).pk,
                                                         "prepayment_quantity": 0, "postpayment_quantity": 1}])
        with self.assertRaisesMessage(ValidationError, "уже использован"):
            self.update(version, self.rows(version, postpayment_surcharge="500"))
        self.assertEqual(order.items.get().postpayment_unit_price, Decimal("2200"))
