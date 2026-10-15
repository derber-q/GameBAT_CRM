import importlib
from decimal import Decimal

from django.apps import apps
from django.contrib.auth import get_user_model
from django.test import TestCase

from catalog.models import CD, Platform
from price.services import create_procurement_price_list, resolve_best_suppliers
from pricing.models import SupplierCDPrice
from .models import Supplier


def supplier(name, letter, priority=1000):
    return Supplier.objects.create(
        name=name, letter=letter, highlight_color="#37A7BA",
        legal_entity="ООО", phone_1="1", priority=priority,
    )


class SupplierPriorityTests(TestCase):
    def test_data_migration_assigns_afm_and_leaves_other_letters_neutral(self):
        suppliers = {letter: supplier(letter, letter) for letter in ("A", "F", "M", "Z")}
        migration = importlib.import_module("partners.migrations.0002_supplier_priority")
        migration.assign_supplier_priorities(apps, None)
        for item in suppliers.values():
            item.refresh_from_db()
        self.assertEqual(suppliers["A"].priority, 1)
        self.assertEqual(suppliers["F"].priority, 2)
        self.assertEqual(suppliers["M"].priority, 3)
        self.assertEqual(suppliers["Z"].priority, 1000)

    def test_lower_priority_number_wins_when_supplier_prices_are_equal(self):
        platform = Platform.objects.create(name="PS5")
        product = CD.objects.create(platform=platform, name="Игра")
        alphabetical = supplier("Alpha", "X", priority=999)
        preferred = supplier("Zulu", "Y", priority=1)
        offers = {("cd", product.pk): [
            (preferred, Decimal("10"), product),
            (alphabetical, Decimal("10"), product),
        ]}
        winners, _ = resolve_best_suppliers(offers)
        self.assertEqual(winners[("cd", product.pk)][0], preferred)

    def test_procurement_snapshot_prefers_a_over_f_and_m_at_equal_prices(self):
        actor = get_user_model().objects.create_superuser("admin", password="test")
        product = CD.objects.create(
            platform=Platform.objects.create(name="PS5"),
            name="PS5 Alan Wake 2 Deluxe Edition (rus sub)",
        )
        for letter, priority in (("M", 3), ("F", 2), ("A", 1)):
            SupplierCDPrice.objects.create(
                supplier=supplier(letter, letter, priority=priority), cd=product, price=95,
            )
        price_list = create_procurement_price_list(
            actor=actor, exchange_rate_usdt_aed="4", exchange_rate_usdt_rub="80",
            delivery_general_usdt_per_kg="0", delivery_devices_usdt_per_kg="0",
            delivery_storage_usdt_per_kg="0", delivery_cd_rub="0",
        )
        item = price_list.items.get(cd=product)
        self.assertEqual(item.selected_supplier.letter, "A")
        self.assertEqual(item.supplier_price_aed, Decimal("95"))

    def test_cheaper_price_takes_precedence_over_supplier_priority(self):
        product = CD.objects.create(platform=Platform.objects.create(name="PS5"), name="Игра")
        preferred = supplier("A", "A", priority=1)
        cheaper = supplier("M", "M", priority=3)
        winners, _ = resolve_best_suppliers({("cd", product.pk): [
            (preferred, Decimal("95"), product),
            (cheaper, Decimal("94.99"), product),
        ]})
        self.assertEqual(winners[("cd", product.pk)][0], cheaper)
