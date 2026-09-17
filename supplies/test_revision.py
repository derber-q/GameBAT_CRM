from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from catalog.models import CD, Platform
from partners.models import Supplier
from sales.models import Sale
from sales.services import create_sale
from warehouse.models import CDWarehouseStock, Warehouse
from warehouse.storage_services import update_storage_locations

from .models import SupplyRevision
from .services import accept_supply, cancel_supply, revise_supply


class SupplyRevisionServiceTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_superuser("revision-admin", password="StrongAdmin!123")
        self.platform = Platform.objects.create(name="PS5")
        self.warehouse = Warehouse.objects.create(name="Склад A")
        self.other_warehouse = Warehouse.objects.create(name="Склад B")
        self.supplier = Supplier.objects.create(
            name="Поставщик A", letter="A", highlight_color="#37A7BA",
            legal_entity="ООО A", phone_1="1",
        )
        self.other_supplier = Supplier.objects.create(
            name="Поставщик B", letter="B", highlight_color="#AA7733",
            legal_entity="ООО B", phone_1="2",
        )
        self.cd = CD.objects.create(
            platform=self.platform, name="Игра A", sku="CD-A", barcode="101", cost=100,
            avito_price=1000,
        )
        self.other_cd = CD.objects.create(
            platform=self.platform, name="Игра B", sku="CD-B", barcode="102", cost=50,
        )
        CDWarehouseStock.objects.create(warehouse=self.warehouse, cd=self.cd, quantity=10)
        CDWarehouseStock.objects.create(warehouse=self.warehouse, cd=self.other_cd, quantity=4)

    def line(self, product=None, quantity=10, cost="200", supplier=None):
        return {
            "product_type": "cd", "product_id": (product or self.cd).pk,
            "supplier_id": (supplier or self.supplier).pk,
            "quantity": quantity, "purchase_unit_cost": cost,
        }

    def accept(self, **kwargs):
        return accept_supply(
            accepted_by=self.actor, warehouse_id=self.warehouse.pk,
            lines=kwargs.pop("lines", [self.line()]),
            expenses=kwargs.pop("expenses", []),
            weight_transport_cost=kwargs.pop("weight_transport_cost", 0),
            **kwargs,
        )

    def revise(self, supply, **kwargs):
        supply.refresh_from_db()
        return revise_supply(
            actor=self.actor, supply_id=supply.pk,
            expected_revision_number=kwargs.pop("expected_revision_number", supply.revision_number),
            warehouse_id=kwargs.pop("warehouse_id", self.warehouse.pk),
            lines=kwargs.pop("lines", [self.line(quantity=7)]),
            expenses=kwargs.pop("expenses", []),
            weight_transport_cost=kwargs.pop("weight_transport_cost", 0),
            reason=kwargs.pop("reason", "Исправление документа"),
            **kwargs,
        )

    def test_quantity_down_creates_immutable_snapshot_and_recalculates_cost(self):
        supply = self.accept()
        result = self.revise(supply)
        supply.refresh_from_db()
        self.cd.refresh_from_db()
        stock = CDWarehouseStock.objects.get(warehouse=self.warehouse, cd=self.cd)
        self.assertEqual(stock.quantity, 17)
        self.assertEqual(self.cd.cost, Decimal("141.18"))
        self.assertEqual(supply.cd_items.get().quantity, 7)
        self.assertEqual(supply.revision_number, 2)
        self.assertEqual(result.revision.revision_number, 1)
        self.assertEqual(result.revision.items.get().quantity, 10)
        self.assertEqual(result.revision.reason, "Исправление документа")

    def test_quantity_up_add_remove_supplier_expenses_and_transport(self):
        supply = self.accept(lines=[self.line(quantity=5)], expenses=[{"name": "Сбор", "amount": 10}])
        self.revise(
            supply,
            lines=[
                self.line(quantity=8, cost="150", supplier=self.other_supplier),
                self.line(product=self.other_cd, quantity=3, cost="75"),
            ],
            expenses=[{"name": "Доставка", "amount": 33}],
            weight_transport_cost="11.00",
        )
        supply.refresh_from_db()
        self.assertEqual(supply.total_units, 11)
        self.assertEqual(supply.expenses_total, Decimal("33.00"))
        self.assertEqual(supply.weight_transport_cost, Decimal("11.00"))
        self.assertEqual(supply.cd_items.count(), 2)
        self.assertEqual(supply.cd_items.get(product=self.cd).supplier, self.other_supplier)
        self.assertEqual(supply.revisions.get().expenses.get().name, "Сбор")
        self.assertEqual(
            sum(supply.cd_items.values_list("allocated_transport_cost", flat=True), Decimal("0")),
            Decimal("11.00"),
        )

    def test_remove_item_reverses_its_stock_and_cost_effect(self):
        supply = self.accept(lines=[self.line(quantity=5), self.line(self.other_cd, quantity=3, cost="100")])
        self.revise(supply, lines=[self.line(quantity=5)])
        self.other_cd.refresh_from_db()
        self.assertEqual(
            CDWarehouseStock.objects.get(warehouse=self.warehouse, cd=self.other_cd).quantity, 4
        )
        self.assertEqual(self.other_cd.cost, Decimal("50.00"))

    def test_later_supply_is_replayed_over_new_earlier_revision(self):
        first = self.accept()
        second = self.accept(lines=[self.line(quantity=10, cost="300")])
        self.revise(first)
        self.cd.refresh_from_db()
        second.refresh_from_db()
        calculation = second.cost_calculations.get(cd=self.cd)
        self.assertEqual(self.cd.cost, Decimal("200.00"))
        self.assertEqual(calculation.old_owned_quantity, 17)
        self.assertEqual(calculation.old_unit_cost, Decimal("141.18"))
        self.assertEqual(calculation.resulting_quantity, 27)

    def test_quantity_changing_sale_before_later_supply_is_replayed(self):
        first = self.accept()
        create_sale(
            actor=self.actor, warehouse_id=self.warehouse.pk,
            price_type=Sale.PriceType.RETAIL, sale_type=Sale.SaleType.RETAIL,
            payment_method=Sale.PaymentMethod.BANK_ACCOUNT,
            lines=[{"product_type": "cd", "product_id": self.cd.pk, "quantity": 5}],
        )
        second = self.accept(lines=[self.line(quantity=10, cost="300")])
        self.revise(first)
        self.cd.refresh_from_db()
        calculation = second.cost_calculations.get(cd=self.cd)
        self.assertEqual(calculation.old_owned_quantity, 12)
        self.assertEqual(calculation.old_unit_cost, Decimal("141.18"))
        self.assertEqual(calculation.resulting_quantity, 22)
        self.assertEqual(self.cd.cost, Decimal("213.37"))

    def test_cancelled_later_supply_is_excluded_from_replay(self):
        first = self.accept()
        later = self.accept(lines=[self.line(quantity=10, cost="300")])
        cancel_supply(actor=self.actor, supply_id=later.pk, comment="Ошибка")
        self.revise(first)
        self.cd.refresh_from_db()
        self.assertEqual(self.cd.cost, Decimal("141.18"))
        self.assertEqual(
            CDWarehouseStock.objects.get(warehouse=self.warehouse, cd=self.cd).quantity, 17
        )

    def test_supplier_only_revision_does_not_change_cost_or_stock(self):
        supply = self.accept()
        old_cost = CD.objects.get(pk=self.cd.pk).cost
        old_stock = CDWarehouseStock.objects.get(warehouse=self.warehouse, cd=self.cd).quantity
        self.revise(supply, lines=[self.line(supplier=self.other_supplier)])
        self.cd.refresh_from_db()
        self.assertEqual(self.cd.cost, old_cost)
        self.assertEqual(
            CDWarehouseStock.objects.get(warehouse=self.warehouse, cd=self.cd).quantity,
            old_stock,
        )
        self.assertEqual(supply.revisions.get().items.get().supplier, self.supplier)

    def test_two_revisions_preserve_each_previous_version(self):
        supply = self.accept()
        self.revise(supply, lines=[self.line(quantity=7)], reason="Первая правка")
        self.revise(supply, lines=[self.line(quantity=6)], reason="Вторая правка")
        supply.refresh_from_db()
        self.assertEqual(supply.revision_number, 3)
        revisions = supply.revisions.order_by("revision_number")
        self.assertEqual(
            [(row.revision_number, row.items.get().quantity, row.reason) for row in revisions],
            [(1, 10, "Первая правка"), (2, 7, "Вторая правка")],
        )

    def test_warehouse_switch_moves_full_current_effect_and_clears_location(self):
        fresh_cd = CD.objects.create(
            platform=self.platform, name="Игра C", sku="CD-C", barcode="103", cost=0,
        )
        supply = self.accept(lines=[self.line(product=fresh_cd, quantity=2)])
        update_storage_locations(
            actor=self.actor, warehouse_id=self.warehouse.pk, product_type="cd",
            product_id=fresh_cd.pk, raw_value="A1-1",
        )
        self.revise(
            supply, warehouse_id=self.other_warehouse.pk,
            lines=[self.line(product=fresh_cd, quantity=2)],
        )
        source = CDWarehouseStock.objects.get(warehouse=self.warehouse, cd=fresh_cd)
        destination = CDWarehouseStock.objects.get(warehouse=self.other_warehouse, cd=fresh_cd)
        self.assertEqual((source.quantity, destination.quantity), (0, 2))
        self.assertFalse(source.storage_assignments.exists())

    def test_insufficient_stock_and_stale_revision_are_atomic(self):
        supply = self.accept(lines=[self.line(quantity=10)])
        stock = CDWarehouseStock.objects.get(warehouse=self.warehouse, cd=self.cd)
        stock.quantity = 1
        stock.save(update_fields=("quantity",))
        with self.assertRaises(ValidationError):
            self.revise(supply, lines=[self.line(quantity=7)])
        supply.refresh_from_db()
        self.assertEqual(supply.revision_number, 1)
        self.assertFalse(SupplyRevision.objects.exists())
        self.assertEqual(supply.cd_items.get().quantity, 10)
        with self.assertRaises(ValidationError):
            self.revise(supply, expected_revision_number=0, lines=[self.line(quantity=10)])

    def test_transaction_rolls_back_after_stock_change(self):
        supply = self.accept()
        before_stock = CDWarehouseStock.objects.get(warehouse=self.warehouse, cd=self.cd).quantity
        with patch("supplies.services._replay_product_valuation", side_effect=RuntimeError("failure")):
            with self.assertRaises(RuntimeError):
                self.revise(supply)
        supply.refresh_from_db()
        self.assertEqual(supply.revision_number, 1)
        self.assertEqual(supply.cd_items.get().quantity, 10)
        self.assertEqual(
            CDWarehouseStock.objects.get(warehouse=self.warehouse, cd=self.cd).quantity,
            before_stock,
        )
        self.assertFalse(SupplyRevision.objects.exists())

    def test_cancel_after_revision_uses_current_quantity(self):
        supply = self.accept()
        self.revise(supply)
        cancel_supply(actor=self.actor, supply_id=supply.pk, comment="Отмена исправленного прихода")
        self.assertEqual(
            CDWarehouseStock.objects.get(warehouse=self.warehouse, cd=self.cd).quantity, 10
        )
        self.cd.refresh_from_db()
        self.assertEqual(self.cd.cost, Decimal("100.00"))


class SupplyRevisionPermissionTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("admin", password="StrongAdmin!123")
        self.worker = User.objects.create_user("worker", password="StrongWorker!123")
        platform = Platform.objects.create(name="PS5")
        self.cd = CD.objects.create(platform=platform, name="Игра", sku="CD-1", cost=100)
        self.warehouse = Warehouse.objects.create(name="Склад")
        self.supplier = Supplier.objects.create(
            name="Поставщик", letter="A", highlight_color="#37A7BA",
            legal_entity="ООО", phone_1="1",
        )
        self.supply = accept_supply(
            accepted_by=self.admin, warehouse_id=self.warehouse.pk,
            lines=[{
                "product_type": "cd", "product_id": self.cd.pk,
                "supplier_id": self.supplier.pk, "quantity": 2, "purchase_unit_cost": 100,
            }], weight_transport_cost=0,
        )
        self.worker.user_permissions.add(Permission.objects.get(codename="view_supply"))
        self.client.force_login(self.worker)

    def test_button_and_endpoint_require_separate_permission(self):
        detail = self.client.get(reverse("supplies:detail", args=(self.supply.pk,)))
        self.assertNotContains(detail, "Редактировать приход")
        edit_url = reverse("supplies:edit", args=(self.supply.pk,))
        self.assertEqual(self.client.get(edit_url).status_code, 403)
        self.assertEqual(self.client.post(edit_url, {}).status_code, 403)
        self.worker.user_permissions.add(Permission.objects.get(codename="edit_accepted_supply"))
        edit = self.client.get(edit_url)
        self.assertEqual(edit.status_code, 200)
        self.assertContains(edit, "Причина изменения")
        self.assertContains(edit, "Подтвердить изменение")

    def test_confirmed_post_uses_service_and_revision_history_is_viewable(self):
        self.worker.user_permissions.add(Permission.objects.get(codename="edit_accepted_supply"))
        response = self.client.post(reverse("supplies:edit", args=(self.supply.pk,)), {
            "expected_revision_number": 1,
            "revision_confirmed": "1",
            "warehouse_id": self.warehouse.pk,
            "weight_transport_cost": "0",
            "revision_reason": "Исправлена цена",
            "product_search": "CD — Игра — PS5",
            "product_type": "cd",
            "product_id": self.cd.pk,
            "supplier_id": self.supplier.pk,
            "quantity": 2,
            "purchase_unit_cost": "120",
            "expense_name": "",
            "expense_amount": "",
        })
        self.assertRedirects(response, reverse("supplies:detail", args=(self.supply.pk,)))
        self.supply.refresh_from_db()
        self.assertEqual(self.supply.revision_number, 2)
        revision_url = reverse("supplies:revision_detail", args=(self.supply.pk, 1))
        revision = self.client.get(revision_url)
        self.assertEqual(revision.status_code, 200)
        self.assertContains(revision, "Исправлена цена")
        self.assertContains(revision, "100,000000")
