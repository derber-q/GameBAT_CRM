import importlib
from decimal import Decimal

from django.apps import apps
from django.test import TestCase

from catalog.models import CD, Platform
from price.services import resolve_best_suppliers
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

    def test_priority_does_not_affect_best_supplier_selection(self):
        platform = Platform.objects.create(name="PS5")
        product = CD.objects.create(platform=platform, name="Игра")
        alphabetical = supplier("Alpha", "X", priority=999)
        priority_one = supplier("Zulu", "Y", priority=1)
        offers = {("cd", product.pk): [
            (priority_one, Decimal("10"), product),
            (alphabetical, Decimal("10"), product),
        ]}
        winners, _ = resolve_best_suppliers(offers)
        self.assertEqual(winners[("cd", product.pk)][0], alphabetical)
