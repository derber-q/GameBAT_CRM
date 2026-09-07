from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from catalog.models import Brand, CD, Platform, ProductChangeEvent, ProductType, Tech
from consignment.models import CDConsignmentStock
from partners.models import SalesPlatform, Supplier
from warehouse.models import CDWarehouseStock, Warehouse
from warehouse.services import create_transfer
from .models import Supply, SupplyCDItem, SupplyCostCalculation
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
        self.warehouse = Warehouse.objects.create(name="Тестовый склад")
        self.cd = CD.objects.create(
            platform=self.platform, name="Игра", sku="CD-1", barcode="001", cost=0
        )
        self.tech = Tech.objects.create(
            brand=self.brand, product_type=self.product_type, name="Консоль", sku="T-1",
            barcode="002", cost=0,
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
        supply = accept_supply(
            accepted_by=self.user, warehouse_id=self.warehouse.pk,
            lines=[self.line(quantity=3)], expenses=[],
        )
        stock = CDWarehouseStock.objects.get(warehouse=self.warehouse, cd=self.cd)
        self.cd.refresh_from_db()
        self.assertEqual(stock.quantity, 3)
        self.assertEqual(self.cd.quantity_on_consignment, 0)
        self.assertEqual(self.cd.cost, Decimal("100.00"))
        self.assertEqual(self.cd.cost.as_tuple().exponent, -2)
        event = self.cd.change_events.get()
        self.assertEqual(event.action_kind, ProductChangeEvent.ActionKind.SUPPLY)
        self.assertEqual(event.action_label, f"Поставка №{supply.pk}")
        self.assertEqual(event.action_url, reverse("supplies:detail", args=(supply.pk,)))
        changes = {change.field_name: change for change in event.field_changes.all()}
        self.assertEqual((changes[f"warehouse_stock_{self.warehouse.pk}"].old_value,
                          changes[f"warehouse_stock_{self.warehouse.pk}"].new_value), ("0", "3"))
        self.assertEqual((changes["cost"].old_value, changes["cost"].new_value), ("0.00", "100.00"))
        calculation = supply.cost_calculations.get()
        self.assertEqual(calculation.product, self.cd)
        self.assertEqual(calculation.old_owned_quantity, 0)
        self.assertEqual(calculation.old_unit_cost, Decimal("0.00"))
        self.assertEqual(calculation.old_inventory_value, Decimal("0.000000"))
        self.assertEqual(calculation.incoming_quantity, 3)
        self.assertEqual(calculation.incoming_value, Decimal("300.000000"))
        self.assertEqual(calculation.resulting_quantity, 3)
        self.assertEqual(calculation.resulting_unit_cost, Decimal("100.00"))

    def test_expenses_are_summed_and_divided_by_physical_units(self):
        supply = accept_supply(
            accepted_by=self.user,
            warehouse_id=self.warehouse.pk,
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
        CDWarehouseStock.objects.create(warehouse=self.warehouse, cd=self.cd, quantity=5)
        self.cd.quantity_on_consignment = 5
        self.cd.cost = Decimal("100")
        self.cd.save()
        sales_platform = SalesPlatform.objects.create(
            name="Магазин", address="Адрес", legal_entity="ООО Магазин", phone_1="+70000000000"
        )
        CDConsignmentStock.objects.create(
            platform=sales_platform, warehouse=self.warehouse, cd=self.cd,
            quantity=5, receivable_per_unit=10,
        )
        supply = accept_supply(
            accepted_by=self.user,
            warehouse_id=self.warehouse.pk,
            lines=[self.line(quantity=10, cost="200")],
        )
        self.cd.refresh_from_db()
        self.assertEqual(CDWarehouseStock.objects.get(warehouse=self.warehouse, cd=self.cd).quantity, 15)
        self.assertEqual(self.cd.quantity_on_consignment, 5)
        self.assertEqual(self.cd.cost, Decimal("150.00"))
        self.assertEqual(self.cd.cost.as_tuple().exponent, -2)
        calculation = supply.cost_calculations.get()
        self.assertEqual(calculation.old_owned_quantity, 10)
        self.assertEqual(calculation.old_unit_cost, Decimal("100.00"))
        self.assertEqual(calculation.old_inventory_value, Decimal("1000.000000"))
        self.assertEqual(calculation.incoming_quantity, 10)
        self.assertEqual(calculation.incoming_value, Decimal("2000.000000"))
        self.assertEqual(calculation.resulting_quantity, 20)
        self.assertEqual(calculation.resulting_value, Decimal("3000.000000"))
        self.assertEqual(calculation.resulting_unit_cost, Decimal("150.00"))

    def test_weighted_average_includes_all_warehouses_consignment_and_transit_once(self):
        other = Warehouse.objects.create(name="Второй склад")
        CDWarehouseStock.objects.create(warehouse=self.warehouse, cd=self.cd, quantity=4)
        CDWarehouseStock.objects.create(warehouse=other, cd=self.cd, quantity=3)
        self.cd.cost = Decimal("100")
        self.cd.quantity_on_consignment = 2
        self.cd.save(update_fields=("cost", "quantity_on_consignment"))
        platform = SalesPlatform.objects.create(
            name="Площадка", address="Адрес", legal_entity="ООО", phone_1="+70000000000"
        )
        CDConsignmentStock.objects.create(
            platform=platform, warehouse=self.warehouse, cd=self.cd,
            quantity=2, receivable_per_unit=10,
        )
        create_transfer(
            actor=self.user, source_warehouse_id=self.warehouse.pk, destination_warehouse_id=other.pk,
            lines=[{"product_type": "cd", "product_id": self.cd.pk, "quantity": 1}],
        )
        accept_supply(
            accepted_by=self.user, warehouse_id=other.pk, lines=[self.line(quantity=1, cost="200")]
        )
        self.cd.refresh_from_db()
        self.assertEqual(self.cd.cost, Decimal("110.00"))
        self.assertEqual(self.cd.cost.as_tuple().exponent, -2)

    def test_same_product_in_multiple_lines_is_aggregated(self):
        supply = accept_supply(
            accepted_by=self.user,
            warehouse_id=self.warehouse.pk,
            lines=[self.line(quantity=2, cost="100"), self.line(quantity=2, cost="200")],
        )
        self.assertEqual(supply.cd_items.count(), 2)
        self.assertEqual(CDWarehouseStock.objects.get(warehouse=self.warehouse, cd=self.cd).quantity, 4)
        self.assertEqual(supply.cost_calculations.count(), 1)
        self.cd.refresh_from_db()
        self.assertEqual(self.cd.cost, Decimal("150.00"))
        self.assertEqual(self.cd.cost.as_tuple().exponent, -2)

    def test_old_zero_quantity_uses_new_supply_value(self):
        accept_supply(accepted_by=self.user, warehouse_id=self.warehouse.pk, lines=[self.line(quantity=4, cost="125.50")])
        self.cd.refresh_from_db()
        self.assertEqual(self.cd.cost, Decimal("125.50"))
        self.assertEqual(self.cd.cost.as_tuple().exponent, -2)

    def test_supply_accepts_legacy_product_with_blank_barcode(self):
        self.cd.barcode = ""
        self.cd.save(update_fields=("barcode",))

        supply = accept_supply(
            accepted_by=self.user,
            warehouse_id=self.warehouse.pk,
            lines=[self.line(quantity=2, cost="125.50")],
        )

        self.assertEqual(supply.total_units, 2)
        self.assertEqual(
            CDWarehouseStock.objects.get(warehouse=self.warehouse, cd=self.cd).quantity,
            2,
        )
        self.cd.refresh_from_db()
        self.assertEqual(self.cd.cost, Decimal("125.50"))

    def test_failure_rolls_back_supply_and_inventory(self):
        with patch("supplies.services.SupplyCDItem.objects.bulk_create", side_effect=RuntimeError("failure")):
            with self.assertRaises(RuntimeError):
                accept_supply(accepted_by=self.user, warehouse_id=self.warehouse.pk, lines=[self.line(quantity=3)])
        self.assertFalse(CDWarehouseStock.objects.filter(warehouse=self.warehouse, cd=self.cd).exists())
        self.assertEqual(Supply.objects.count(), 0)

    def test_invalid_quantity_is_rejected_before_changes(self):
        with self.assertRaises(ValidationError):
            accept_supply(accepted_by=self.user, warehouse_id=self.warehouse.pk, lines=[self.line(quantity=0)])
        self.assertEqual(Supply.objects.count(), 0)

    def test_create_page_preserves_submitted_rows_after_business_error(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("supplies:create"), {
            "warehouse_id": self.warehouse.pk,
            "product_search": "CD — Игра — PlayStation 5",
            "product_type": "cd",
            "product_id": self.cd.pk,
            "supplier_id": self.supplier.pk,
            "quantity": "0",
            "purchase_unit_cost": "125.50",
            "expense_name": "Доставка",
            "expense_amount": "50.00",
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["initial_supply_lines"][0]["product_id"], str(self.cd.pk))
        self.assertEqual(response.context["initial_supply_lines"][0]["purchase_unit_cost"], "125.50")
        self.assertEqual(response.context["initial_expenses"][0]["name"], "Доставка")

    def test_detail_uses_historical_cost_not_current_product_cost(self):
        supply = accept_supply(accepted_by=self.user, warehouse_id=self.warehouse.pk, lines=[self.line(quantity=1, cost="140")])
        self.cd.cost = Decimal("135")
        self.cd.save(update_fields=("cost",))
        self.client.force_login(self.user)
        response = self.client.get(reverse("supplies:detail", args=(supply.pk,)))
        self.assertContains(response, "140,000000")
        self.assertNotContains(response, "135,000000")
        self.assertContains(response, "Перерасчёт себестоимости")
        self.assertContains(response, "Формула средней себестоимости")
        self.assertContains(response, "140,00 ₽ за единицу")


class SupplyAutocompleteTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("admin", password="StrongAdmin!123")
        platform = Platform.objects.create(name="PS5")
        self.cd = CD.objects.create(
            platform=platform, name="Grand Theft Auto V", sku="GTA5", barcode="123"
        )
        self.warehouse = Warehouse.objects.create(name="Склад")
        CDWarehouseStock.objects.create(warehouse=self.warehouse, cd=self.cd, quantity=4)
        self.client.force_login(self.user)

    def test_autocomplete_is_case_insensitive_and_marks_product_type(self):
        response = self.client.get(reverse("supplies:autocomplete"), {"q": "grand theft"})
        self.assertEqual(response.status_code, 200)
        result = response.json()["results"][0]
        self.assertEqual(result["type"], "cd")
        self.assertIn("CD — Grand Theft Auto V — PS5", result["label"])
