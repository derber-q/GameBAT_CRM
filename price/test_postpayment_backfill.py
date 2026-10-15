from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase

from accounts.models import User
from catalog.models import Brand, CD, Platform, ProductType, Tech
from orders.services import create_customer_procurement_order
from partners.models import Supplier

from .models import ProcurementPriceList, ProcurementPriceListItem, ProcurementPricePreference
from .services import MissingProcurementSurcharges, backfill_procurement_tech_surcharges


class PostpaymentBackfillTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser("backfill-admin")
        cls.supplier = Supplier.objects.create(name="Поставщик", letter="A", legal_entity="A", phone_1="1")
        cls.brand = Brand.objects.create(name="Sony")
        cls.kind = ProductType.objects.create(name="Геймпад")
        cls.tech = Tech.objects.create(brand=cls.brand, product_type=cls.kind, name="DualSense")
        cls.version = ProcurementPriceList.objects.create(created_by=cls.user, exchange_rate_aed_rub=20)
        cls.item = ProcurementPriceListItem.objects.create(
            price_list=cls.version, product_kind="tech", tech=cls.tech, product_name_snapshot=cls.tech.name,
            article_snapshot="T", selected_supplier=cls.supplier, supplier_price_aed=100, exchange_rate_aed_rub=20,
            base_price_rub=2000, markup_rub=123, delivery_rub=20, prepayment_price_rub=2143, postpayment_price_rub=2223,
        )
        cd = CD.objects.create(platform=Platform.objects.create(name="PS5"), name="Игра")
        cls.cd_item = ProcurementPriceListItem.objects.create(
            price_list=cls.version, product_kind="cd", cd=cd, product_name_snapshot=cd.name,
            article_snapshot="CD", selected_supplier=cls.supplier, supplier_price_aed=100, exchange_rate_aed_rub=20,
            base_price_rub=2000, prepayment_price_rub=2000, postpayment_price_rub=2080,
        )
        cls.preference = ProcurementPricePreference.objects.create(
            tech=cls.tech, markup_rub=123, source_item=cls.item, updated_by=cls.user,
        )

    def run_backfill(self, **overrides):
        return backfill_procurement_tech_surcharges(**{
            "actor": self.user, "price_list_id": self.version.pk, "apply": True, **overrides,
        })

    def add_item(self, name, **overrides):
        product = Tech.objects.create(brand=self.brand, product_type=self.kind, name=name)
        return ProcurementPriceListItem.objects.create(**{
            "price_list": self.version, "product_kind": "tech", "tech": product,
            "product_name_snapshot": name, "article_snapshot": name, "selected_supplier": self.supplier,
            "supplier_price_aed": 100, "exchange_rate_aed_rub": 20, "base_price_rub": 2000,
            "prepayment_price_rub": 2000, "postpayment_price_rub": 2080, **overrides,
        })

    def test_preview_does_not_write(self):
        changes = self.run_backfill(apply=False)
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["old_surcharge"], Decimal("80"))
        self.assertEqual(changes[0]["new_surcharge"], Decimal("200"))
        self.item.refresh_from_db()
        self.assertIsNone(self.item.postpayment_surcharge_rub)
        self.assertEqual(self.item.postpayment_price_rub, Decimal("2223"))

    def test_repairs_only_legacy_tech_fee_and_postpayment_and_is_idempotent(self):
        cd_before = ProcurementPriceListItem.objects.filter(pk=self.cd_item.pk).values().get()
        pref_before = ProcurementPricePreference.objects.filter(pk=self.preference.pk).values().get()
        self.run_backfill()
        self.item.refresh_from_db()
        self.assertEqual(self.item.postpayment_surcharge_rub, Decimal("200"))
        self.assertEqual(self.item.postpayment_price_rub, Decimal("2343"))
        self.assertEqual((self.item.base_price_rub, self.item.markup_rub, self.item.delivery_rub, self.item.prepayment_price_rub),
                         (Decimal("2000"), Decimal("123"), Decimal("20"), Decimal("2143")))
        self.assertEqual(ProcurementPriceListItem.objects.filter(pk=self.cd_item.pk).values().get(), cd_before)
        self.assertEqual(ProcurementPricePreference.objects.filter(pk=self.preference.pk).values().get(), pref_before)
        self.assertEqual(self.run_backfill(), [])

    def test_manual_and_new_fixed_surcharges_are_preserved(self):
        manual = self.add_item("Ручная", postpayment_surcharge_rub=350, postpayment_price_rub=2350)
        default = self.add_item("Новая", postpayment_surcharge_rub=200, postpayment_price_rub=2200)
        changes = self.run_backfill()
        self.assertEqual([row["item_id"] for row in changes], [self.item.pk])
        manual.refresh_from_db()
        default.refresh_from_db()
        self.assertEqual(manual.postpayment_price_rub, Decimal("2350"))
        self.assertEqual(default.postpayment_price_rub, Decimal("2200"))

    def test_used_price_list_and_order_snapshot_are_protected(self):
        order = create_customer_procurement_order(
            actor=self.user, price_list_id=self.version.pk, recipient="Покупатель", comment="",
            lines=[{"price_list_item_id": self.item.pk, "prepayment_quantity": 0, "postpayment_quantity": 1}],
        )
        with self.assertRaisesMessage(ValidationError, "уже использован"):
            self.run_backfill()
        self.assertEqual(order.items.get().postpayment_unit_price, Decimal("2223"))

    def test_unknown_rule_blocks_entire_correction(self):
        unknown = self.add_item("Неизвестная")
        unknown.tech.product_type = ProductType.objects.create(name="Новый тип")
        unknown.tech.save(update_fields=("product_type",))
        with self.assertRaises(MissingProcurementSurcharges):
            self.run_backfill()
        self.item.refresh_from_db()
        self.assertIsNone(self.item.postpayment_surcharge_rub)
        self.assertEqual(self.item.postpayment_price_rub, Decimal("2223"))

    def test_save_failure_rolls_back_earlier_correction(self):
        self.add_item("Z Second")
        original_save = ProcurementPriceListItem.save
        calls = []

        def fail_after_first(item, **kwargs):
            calls.append(item.pk)
            if len(calls) == 2:
                raise RuntimeError("save failed")
            return original_save(item, **kwargs)

        with patch.object(ProcurementPriceListItem, "save", autospec=True, side_effect=fail_after_first):
            with self.assertRaises(RuntimeError):
                self.run_backfill()
        self.assertEqual(len(calls), 2)
        self.item.refresh_from_db()
        self.assertIsNone(self.item.postpayment_surcharge_rub)
        self.assertEqual(self.item.postpayment_price_rub, Decimal("2223"))

    def test_permissions_are_required(self):
        with self.assertRaisesMessage(ValidationError, "нет права"):
            self.run_backfill(actor=User.objects.create_user("restricted-backfill"))

    def test_command_defaults_to_preview_and_apply_is_explicit(self):
        output = StringIO()
        call_command("backfill_procurement_tech_surcharges", price_list=self.version.pk, actor=self.user.pk, stdout=output)
        self.assertIn("Будет исправлено строк Tech: 1", output.getvalue())
        self.item.refresh_from_db()
        self.assertIsNone(self.item.postpayment_surcharge_rub)
        call_command("backfill_procurement_tech_surcharges", price_list=self.version.pk, actor=self.user.pk, apply=True, stdout=output)
        self.item.refresh_from_db()
        self.assertEqual(self.item.postpayment_surcharge_rub, Decimal("200"))
