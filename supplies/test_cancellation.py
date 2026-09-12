from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from catalog.models import Brand, CD, Platform, ProductType, Tech
from partners.models import Supplier
from warehouse.models import CDWarehouseStock, TechWarehouseStock, Warehouse

from .models import Supply
from .services import accept_supply, cancel_supply


class SupplyCancellationTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_superuser("admin", password="StrongAdmin!123")
        platform = Platform.objects.create(name="PS5")
        self.cd = CD.objects.create(
            platform=platform, name="Игра", sku="CD-1", barcode="1", cost=100,
        )
        brand = Brand.objects.create(name="Sony")
        product_type = ProductType.objects.create(name="Консоли")
        self.tech = Tech.objects.create(
            brand=brand, product_type=product_type, name="Консоль", sku="TECH-1", cost=50,
        )
        self.warehouse = Warehouse.objects.create(name="Склад")
        self.cd_stock = CDWarehouseStock.objects.create(
            warehouse=self.warehouse, cd=self.cd, quantity=10,
        )
        self.tech_stock = TechWarehouseStock.objects.create(
            warehouse=self.warehouse, tech=self.tech, quantity=5,
        )
        self.supplier = Supplier.objects.create(
            name="Поставщик", letter="A", highlight_color="#37A7BA",
            legal_entity="ООО", phone_1="1",
        )

    def line(self, *, product_type="cd", product=None, quantity=10, cost="200"):
        product = product or (self.cd if product_type == "cd" else self.tech)
        return {
            "product_type": product_type,
            "product_id": product.pk,
            "supplier_id": self.supplier.pk,
            "quantity": quantity,
            "purchase_unit_cost": cost,
        }

    def test_basic_cancellation_restores_stock_and_previous_cost_and_is_idempotent(self):
        supply = accept_supply(
            accepted_by=self.actor, warehouse_id=self.warehouse.pk, lines=[self.line()],
        )
        self.cd.refresh_from_db()
        self.assertEqual(self.cd.cost, Decimal("150.00"))
        first = cancel_supply(actor=self.actor, supply_id=supply.pk, comment="Ошибка поставки")
        second = cancel_supply(actor=self.actor, supply_id=supply.pk, comment="Повтор")
        self.cd.refresh_from_db()
        self.cd_stock.refresh_from_db()
        supply.refresh_from_db()
        self.assertTrue(first.cancelled)
        self.assertFalse(second.cancelled)
        self.assertEqual((self.cd_stock.quantity, self.cd.cost), (10, Decimal("100.00")))
        self.assertEqual(supply.status, Supply.Status.CANCELLED)
        self.assertEqual(supply.cancelled_by, self.actor)
        event = self.cd.change_events.order_by("-pk").first()
        self.assertEqual(event.action_label, f"Отмена поставки №{supply.pk}")

    def test_multiple_product_types_are_rolled_back_atomically(self):
        supply = accept_supply(
            accepted_by=self.actor,
            warehouse_id=self.warehouse.pk,
            lines=[
                self.line(quantity=3, cost="200"),
                self.line(product_type="tech", quantity=4, cost="150"),
            ],
        )
        cancel_supply(actor=self.actor, supply_id=supply.pk, comment="Ошибка")
        self.cd_stock.refresh_from_db()
        self.tech_stock.refresh_from_db()
        self.cd.refresh_from_db()
        self.tech.refresh_from_db()
        self.assertEqual((self.cd_stock.quantity, self.tech_stock.quantity), (10, 5))
        self.assertEqual((self.cd.cost, self.tech.cost), (Decimal("100.00"), Decimal("50.00")))

    def test_insufficient_source_stock_blocks_every_line(self):
        supply = accept_supply(
            accepted_by=self.actor,
            warehouse_id=self.warehouse.pk,
            lines=[self.line(quantity=3), self.line(product_type="tech", quantity=4, cost="150")],
        )
        self.cd_stock.refresh_from_db()
        self.cd_stock.quantity = 2
        self.cd_stock.save(update_fields=("quantity",))
        with self.assertRaisesMessage(ValidationError, "недостаточно товара"):
            cancel_supply(actor=self.actor, supply_id=supply.pk, comment="Ошибка")
        self.tech_stock.refresh_from_db()
        self.tech.refresh_from_db()
        supply.refresh_from_db()
        self.assertEqual(self.tech_stock.quantity, 9)
        self.assertNotEqual(self.tech.cost, Decimal("50.00"))
        self.assertFalse(supply.is_cancelled)

    def test_later_supply_and_intervening_stock_change_are_replayed(self):
        first = accept_supply(
            accepted_by=self.actor, warehouse_id=self.warehouse.pk,
            lines=[self.line(quantity=10, cost="200")],
        )
        self.cd_stock.refresh_from_db()
        self.cd_stock.quantity -= 10
        self.cd_stock.save(update_fields=("quantity",))
        accept_supply(
            accepted_by=self.actor, warehouse_id=self.warehouse.pk,
            lines=[self.line(quantity=10, cost="300")],
        )
        self.cd.refresh_from_db()
        self.assertEqual(self.cd.cost, Decimal("225.00"))

        cancel_supply(actor=self.actor, supply_id=first.pk, comment="Исключить первую партию")
        self.cd.refresh_from_db()
        self.cd_stock.refresh_from_db()
        self.assertEqual(self.cd_stock.quantity, 10)
        self.assertEqual(self.cd.cost, Decimal("300.00"))
        self.assertNotEqual(self.cd.cost, Decimal("100.00"))

    def test_allocated_expenses_are_included_in_rollback_history(self):
        supply = accept_supply(
            accepted_by=self.actor,
            warehouse_id=self.warehouse.pk,
            lines=[self.line(quantity=10, cost="200")],
            expenses=[{"name": "Доставка", "amount": "100"}],
        )
        calculation = supply.cost_calculations.get()
        self.assertEqual(calculation.incoming_value, Decimal("2100.000000"))
        cancel_supply(actor=self.actor, supply_id=supply.pk, comment="Ошибка")
        self.cd.refresh_from_db()
        self.assertEqual(self.cd.cost, Decimal("100.00"))

    def test_missing_cost_history_blocks_cancellation(self):
        supply = accept_supply(
            accepted_by=self.actor, warehouse_id=self.warehouse.pk,
            lines=[self.line(quantity=2)],
        )
        supply.cost_calculations.all().delete()
        with self.assertRaisesMessage(ValidationError, "отсутствует исторический расчёт"):
            cancel_supply(actor=self.actor, supply_id=supply.pk, comment="Ошибка")
        supply.refresh_from_db()
        self.assertFalse(supply.is_cancelled)

    def test_audit_failure_rolls_back_stock_cost_and_status(self):
        supply = accept_supply(
            accepted_by=self.actor, warehouse_id=self.warehouse.pk,
            lines=[self.line(quantity=2, cost="200")],
        )
        before_cost = CD.objects.get(pk=self.cd.pk).cost
        before_stock = CDWarehouseStock.objects.get(pk=self.cd_stock.pk).quantity
        with patch("supplies.services.record_product_changes", side_effect=RuntimeError("audit failed")):
            with self.assertRaisesMessage(RuntimeError, "audit failed"):
                cancel_supply(actor=self.actor, supply_id=supply.pk, comment="Ошибка")
        self.cd.refresh_from_db()
        self.cd_stock.refresh_from_db()
        supply.refresh_from_db()
        self.assertEqual((self.cd.cost, self.cd_stock.quantity), (before_cost, before_stock))
        self.assertFalse(supply.is_cancelled)

    def test_permission_confirmation_post_only_and_cancelled_record_visibility(self):
        supply = accept_supply(
            accepted_by=self.actor, warehouse_id=self.warehouse.pk,
            lines=[self.line(quantity=2)],
        )
        worker = User.objects.create_user("worker", password="StrongWorker!123")
        worker.user_permissions.add(Permission.objects.get(
            content_type__app_label="supplies", codename="view_supply"
        ))
        self.client.force_login(worker)
        detail_url = reverse("supplies:detail", args=(supply.pk,))
        cancel_url = reverse("supplies:cancel", args=(supply.pk,))
        self.assertNotContains(self.client.get(detail_url), "Отменить приход")
        self.assertEqual(self.client.post(cancel_url, {"cancellation_comment": "Нет"}).status_code, 403)

        worker.user_permissions.add(Permission.objects.get(
            content_type__app_label="supplies", codename="cancel_supply"
        ))
        self.client.force_login(worker)
        response = self.client.get(detail_url)
        self.assertContains(response, 'data-dialog-open="supply-cancel-dialog"')
        self.assertContains(response, "Это действие нельзя отменить")
        self.assertEqual(self.client.get(cancel_url).status_code, 405)
        self.assertRedirects(
            self.client.post(cancel_url, {"cancellation_comment": "Возврат поставщику"}), detail_url
        )
        self.assertContains(self.client.get(reverse("supplies:list")), "Отменена")

    def test_comment_is_required(self):
        supply = accept_supply(
            accepted_by=self.actor, warehouse_id=self.warehouse.pk,
            lines=[self.line(quantity=1)],
        )
        with self.assertRaisesMessage(ValidationError, "причину отмены"):
            cancel_supply(actor=self.actor, supply_id=supply.pk, comment="")
