from decimal import Decimal
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import patch

from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase

from accounts.models import User
from catalog.models import Brand, CD, Platform, ProductType, Tech
from partners.models import Supplier
from pricing.models import SupplierCDPrice, SupplierTechPrice

from .models import ProcurementPriceList, ProcurementPricePreference
from .services import create_procurement_price_list, update_procurement_pricing


class ProcurementPriceMemoryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser("memory-admin")
        cls.supplier = Supplier.objects.create(
            name="Поставщик", letter="A", highlight_color="#37A7BA", legal_entity="A", phone_1="1",
        )
        cls.cd = CD.objects.create(platform=Platform.objects.create(name="PS5"), name="Игра")
        cls.tech = Tech.objects.create(
            brand=Brand.objects.create(name="Sony"), product_type=ProductType.objects.create(name="Геймпад"),
            name="Геймпад", weight_grams=1000,
        )
        cls.cd_offer = SupplierCDPrice.objects.create(supplier=cls.supplier, cd=cls.cd, price=50)
        cls.tech_offer = SupplierTechPrice.objects.create(supplier=cls.supplier, tech=cls.tech, price=100)

    def create(self, **overrides):
        return create_procurement_price_list(actor=self.user, **{
            "exchange_rate_usdt_aed": "4", "exchange_rate_usdt_rub": "80", "delivery_cd_rub": "35",
            "delivery_general_usdt_per_kg": "1", "delivery_devices_usdt_per_kg": "2",
            "delivery_storage_usdt_per_kg": "3", **overrides,
        })

    def save_prices(self, price_list, cd="1500", tech="3000"):
        rows = {item.pk: {
            "price_source": "prepayment", "prepayment": cd if item.product_kind == "cd" else tech,
            "delivery": str(item.delivery_rub),
        } for item in price_list.items.all()}
        return update_procurement_pricing(
            actor=self.user, price_list_id=price_list.pk, rows=rows,
            can_change_markup=True, can_change_delivery=True, negative_markup_confirmed=True,
        )

    def test_remembers_markup_and_recalculates_final_prices_for_changed_costs_and_delivery(self):
        original = self.create()
        self.save_prices(original)
        self.cd_offer.price = 60
        self.cd_offer.save(update_fields=("price",))
        self.tech_offer.price = 120
        self.tech_offer.save(update_fields=("price",))
        self.tech.weight_grams = 1500
        self.tech.save(update_fields=("weight_grams",))
        newer = self.create(exchange_rate_usdt_rub="90", delivery_cd_rub="200", delivery_general_usdt_per_kg="2")
        cd_item = newer.items.get(cd=self.cd)
        tech_item = newer.items.get(tech=self.tech)
        self.assertEqual(cd_item.prepayment_price_rub, Decimal("2020"))
        self.assertEqual(cd_item.postpayment_price_rub, Decimal("2100"))
        self.assertEqual(cd_item.base_price_rub, Decimal("1350"))
        self.assertEqual(cd_item.delivery_rub, Decimal("200"))
        self.assertEqual(cd_item.markup_rub, Decimal("470"))
        self.assertEqual(cd_item.original_markup_rub, Decimal('465'))
        self.assertEqual(tech_item.prepayment_price_rub, Decimal("3890"))
        self.assertEqual(tech_item.postpayment_price_rub, Decimal("4090"))
        self.assertEqual(tech_item.markup_rub, Decimal("920"))
        self.assertEqual(original.items.get(cd=self.cd).markup_rub, Decimal("465"))
        self.assertEqual(ProcurementPricePreference.objects.count(), 2)

    def test_generating_unedited_versions_does_not_overwrite_remembered_markup(self):
        first = self.create()
        self.save_prices(first)
        second = self.create(exchange_rate_usdt_rub="160")
        third = self.create(exchange_rate_usdt_rub="40")
        for version, expected_price in ((second, "2500"), (third, "1000")):
            item = version.items.get(cd=self.cd)
            self.assertEqual(item.prepayment_price_rub, Decimal(expected_price))
            self.assertEqual(item.markup_rub, Decimal("465"))
        preference = ProcurementPricePreference.objects.get(cd=self.cd)
        self.assertEqual(preference.source_item.price_list_id, first.pk)
        self.assertEqual(preference.markup_rub, Decimal("465"))

    def test_last_explicit_save_wins_even_when_editing_an_older_version(self):
        first = self.create()
        self.save_prices(first)
        second = self.create()
        self.save_prices(second, cd="1600")
        self.save_prices(first, cd="1700")
        self.assertEqual(self.create().items.get(cd=self.cd).prepayment_price_rub, Decimal("1700"))
        preference = ProcurementPricePreference.objects.get(cd=self.cd)
        self.assertEqual(preference.source_item.price_list_id, first.pk)
        self.assertEqual(preference.updated_by, self.user)
        self.assertEqual(preference.markup_rub, Decimal("665"))

    def test_product_absent_from_intermediate_version_keeps_memory_and_new_product_starts_at_zero_markup(self):
        self.save_prices(self.create())
        self.cd_offer.price = 0
        self.cd_offer.save(update_fields=("price",))
        self.assertFalse(self.create().items.filter(cd=self.cd).exists())
        self.cd_offer.price = 60
        self.cd_offer.save(update_fields=("price",))
        new_cd = CD.objects.create(platform=self.cd.platform, name="Новая игра")
        SupplierCDPrice.objects.create(supplier=self.supplier, cd=new_cd, price=70)
        newer = self.create()
        self.assertEqual(newer.items.get(cd=self.cd).prepayment_price_rub, Decimal("1700"))
        self.assertEqual(newer.items.get(cd=self.cd).markup_rub, Decimal("465"))
        item = newer.items.get(cd=new_cd)
        self.assertEqual(item.original_markup_rub, 0)
        self.assertEqual(item.markup_rub, 5)
        self.assertEqual(item.prepayment_price_rub, item.base_price_rub + item.delivery_rub + item.prepayment_rounding_extra_rub)

    def test_preference_failure_rolls_back_prices_and_all_memory(self):
        original = self.create()
        self.save_prices(original)
        with patch("price.services.ProcurementPricePreference.save", side_effect=RuntimeError("memory failed")):
            with self.assertRaises(RuntimeError):
                self.save_prices(original, cd="1700", tech="3200")
        self.assertEqual(original.items.get(cd=self.cd).prepayment_price_rub, Decimal("1500"))
        self.assertEqual(ProcurementPricePreference.objects.get(cd=self.cd).markup_rub, Decimal("465"))

    def test_migration_copies_markup_from_confirmed_source_instead_of_final_price_or_newer_unsaved_version(self):
        first = self.create()
        self.save_prices(first)
        self.tech_offer.price = 0
        self.tech_offer.save(update_fields=("price",))
        self.create(delivery_cd_rub="100")
        before = list(first.items.values_list("id", "markup_rub", "prepayment_price_rub", "postpayment_price_rub"))
        preference = ProcurementPricePreference.objects.get(cd=self.cd)
        preference.markup_rub = Decimal("1500")
        preference.save()
        migration = import_module("price.migrations.0006_remember_markup_instead_of_final_price")
        migration.remember_markup(apps, SimpleNamespace(connection=connection))
        preference.refresh_from_db()
        self.assertEqual(preference.markup_rub, Decimal("465"))
        self.assertEqual(preference.source_item.price_list_id, first.pk)
        self.assertEqual(ProcurementPricePreference.objects.get(tech=self.tech).markup_rub, Decimal("920"))
        self.assertEqual(list(first.items.values_list("id", "markup_rub", "prepayment_price_rub", "postpayment_price_rub")), before)

    def test_negative_markup_is_remembered_and_reapplied_with_updated_costs(self):
        first = self.create()
        self.save_prices(first, cd="1000", tech="2000")
        newer = self.create(exchange_rate_usdt_rub="90")
        item = newer.items.get(cd=self.cd)
        self.assertEqual(item.original_markup_rub, Decimal('-35'))
        self.assertEqual(item.markup_rub, Decimal("-30"))
        self.assertEqual(item.prepayment_price_rub, Decimal("1130"))
        self.assertEqual(item.postpayment_price_rub, Decimal("1190"))
        self.assertEqual(newer.items.get(tech=self.tech).markup_rub, Decimal("-80"))

    def test_negative_saved_markup_cannot_generate_a_negative_final_price(self):
        self.save_prices(self.create(), cd="0")
        before_count = ProcurementPriceList.objects.count()
        with self.assertRaisesMessage(ValidationError, "сохранённая наценка даёт отрицательную итоговую цену"):
            self.create(exchange_rate_usdt_rub="1")
        self.assertEqual(ProcurementPriceList.objects.count(), before_count)
        self.assertEqual(ProcurementPricePreference.objects.get(cd=self.cd).markup_rub, Decimal("-1035"))

    def test_migration_preserves_negative_markup_and_handles_missing_source(self):
        first = self.create()
        self.save_prices(first, cd="1000")
        cd_preference = ProcurementPricePreference.objects.get(cd=self.cd)
        cd_preference.markup_rub = Decimal("1000")
        cd_preference.save()
        tech_preference = ProcurementPricePreference.objects.get(tech=self.tech)
        tech_preference.source_item = None
        tech_preference.save()
        migration = import_module("price.migrations.0006_remember_markup_instead_of_final_price")
        migration.remember_markup(apps, SimpleNamespace(connection=connection))
        cd_preference.refresh_from_db()
        tech_preference.refresh_from_db()
        self.assertEqual(cd_preference.markup_rub, Decimal("-35"))
        self.assertEqual(tech_preference.markup_rub, Decimal("920"))
