from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from catalog.models import Brand, CD, Platform, ProductType, Tech
from consignment.models import CDConsignmentStock
from partners.models import SalesPlatform, Supplier
from .models import Supply, SupplyCDItem
from .services import accept_supply


class SupplyServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("admin", password="StrongAdmin!123")
        self.platform = Platform.objects.create(name="PlayStation 5")
        self.brand = Brand.objects.create(name="Sony")
        self.product_type = ProductType.objects.create(name="Консоль")
        self.supplier = Supplier.objects.create(
            name="Поставщик Альфа", letter="A", highlight_color="#37A7BA",
            legal_entity="ООО Альфа", phone_1="+79990000000",
        )
        self.cd = CD.objects.create(
            platform=self.platform, name="Игра", sku="CD-1", barcode="001", quantity=0, cost=0
        )
        self.tech = Tech.objects.create(
            brand=self.brand, product_type=self.product_type, name="Консоль", sku="T-1",
            barcode="002", quantity=0, cost=0,
        )

    def line(self, product_type="cd", product_id=None, quantity=1, cost="100"):
        return {
            "product_type": product_type,
            "product_id": product_id or (self.cd.pk if product_type == "cd" else self.tech.pk),
            "supplier_id": self.supplier.pk,
            "quantity": quantity,
            "purchase_unit_cost": cost,
        }

    def test_single_product_increases_warehouse_only(self):
        accept_supply(accepted_by=self.user, lines=[self.line(quantity=3)], expenses=[])
        self.cd.refresh_from_db()
        self.assertEqual(self.cd.quantity, 3)
        self.assertEqual(self.cd.quantity_on_consignment, 0)
        self.assertEqual(self.cd.cost, Decimal("100.000000"))

    def test_expenses_are_summed_and_divided_by_physical_units(self):
        supply = accept_supply(
            accepted_by=self.user,
            lines=[self.line(quantity=10, cost="100"), self.line("tech", quantity=5, cost="200")],
            expenses=[{"name": "Доставка", "amount": "200"}, {"name": "Сбор", "amount": "100"}],
        )
        cd_item = supply.cd_items.get()
        tech_item = supply.tech_items.get()
        self.assertEqual(supply.total_units, 15)
        self.assertEqual(supply.expenses_total, Decimal("300.00"))
        self.assertEqual(cd_item.allocated_expense_per_unit, Decimal("20.000000"))
        self.assertEqual(tech_item.allocated_expense_per_unit, Decimal("20.000000"))
        self.assertEqual(cd_item.effective_unit_cost, Decimal("120.000000"))
        self.assertEqual(tech_item.effective_unit_cost, Decimal("220.000000"))

    def test_weighted_average_uses_old_warehouse_and_consignment_quantity(self):
        self.cd.quantity = 5
        self.cd.quantity_on_consignment = 5
        self.cd.cost = Decimal("100")
        self.cd.save()
        sales_platform = SalesPlatform.objects.create(
            name="Магазин", address="Адрес", legal_entity="ООО Магазин", phone_1="+70000000000"
        )
        CDConsignmentStock.objects.create(platform=sales_platform, cd=self.cd, quantity=5, reward_per_unit=10)
        accept_supply(accepted_by=self.user, lines=[self.line(quantity=10, cost="200")])
        self.cd.refresh_from_db()
        self.assertEqual(self.cd.quantity, 15)
        self.assertEqual(self.cd.quantity_on_consignment, 5)
        self.assertEqual(self.cd.cost, Decimal("150.000000"))

    def test_same_product_in_multiple_lines_is_aggregated(self):
        supply = accept_supply(
            accepted_by=self.user,
            lines=[self.line(quantity=2, cost="100"), self.line(quantity=2, cost="200")],
        )
        self.cd.refresh_from_db()
        self.assertEqual(supply.cd_items.count(), 2)
        self.assertEqual(self.cd.quantity, 4)
        self.assertEqual(self.cd.cost, Decimal("150.000000"))

    def test_old_zero_quantity_uses_new_supply_value(self):
        accept_supply(accepted_by=self.user, lines=[self.line(quantity=4, cost="125.50")])
        self.cd.refresh_from_db()
        self.assertEqual(self.cd.cost, Decimal("125.500000"))

    def test_failure_rolls_back_supply_and_inventory(self):
        with patch("supplies.services.SupplyCDItem.objects.bulk_create", side_effect=RuntimeError("failure")):
            with self.assertRaises(RuntimeError):
                accept_supply(accepted_by=self.user, lines=[self.line(quantity=3)])
        self.cd.refresh_from_db()
        self.assertEqual(self.cd.quantity, 0)
        self.assertEqual(Supply.objects.count(), 0)

    def test_invalid_quantity_is_rejected_before_changes(self):
        with self.assertRaises(ValidationError):
            accept_supply(accepted_by=self.user, lines=[self.line(quantity=0)])
        self.assertEqual(Supply.objects.count(), 0)

    def test_detail_uses_historical_cost_not_current_product_cost(self):
        supply = accept_supply(accepted_by=self.user, lines=[self.line(quantity=1, cost="140")])
        self.cd.cost = Decimal("135")
        self.cd.save(update_fields=("cost",))
        self.client.force_login(self.user)
        response = self.client.get(reverse("supplies:detail", args=(supply.pk,)))
        self.assertContains(response, "140,000000")
        self.assertNotContains(response, "135,000000")


class SupplyAutocompleteTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("admin", password="StrongAdmin!123")
        platform = Platform.objects.create(name="PS5")
        self.cd = CD.objects.create(
            platform=platform, name="Grand Theft Auto V", sku="GTA5", barcode="123", quantity=4
        )
        self.client.force_login(self.user)

    def test_autocomplete_is_case_insensitive_and_marks_product_type(self):
        response = self.client.get(reverse("supplies:autocomplete"), {"q": "grand theft"})
        self.assertEqual(response.status_code, 200)
        result = response.json()["results"][0]
        self.assertEqual(result["type"], "cd")
        self.assertIn("CD — Grand Theft Auto V — PS5", result["label"])
