from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from cash.models import CashTransaction
from cash.services import collect_cash
from catalog.models import ProductChangeEvent, ProductFieldChange
from catalog.models import Brand, CD, Platform, ProductType, Tech
from consignment.models import CDConsignmentStock
from consignment.services import record_consignment_sale, transfer_to_consignment
from partners.models import SalesPlatform
from warehouse.models import CDWarehouseStock, TechWarehouseStock, Warehouse

from .models import Sale
from .services import cancel_sale, create_sale, mark_sale_paid


class SaleCancellationTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_superuser("admin", password="StrongAdmin!123")
        platform = Platform.objects.create(name="PS5")
        self.product = CD.objects.create(
            platform=platform, name="Игра", sku="CD-1", barcode="1", avito_price=100,
        )
        self.warehouse = Warehouse.objects.create(name="Склад")
        self.stock = CDWarehouseStock.objects.create(
            warehouse=self.warehouse, cd=self.product, quantity=10,
        )
        self.register = self.warehouse.cash_register

    def create(self, payment_method):
        return create_sale(
            actor=self.actor,
            warehouse_id=self.warehouse.pk,
            price_type=Sale.PriceType.RETAIL,
            sale_type=Sale.SaleType.RETAIL,
            payment_method=payment_method,
            lines=[{"product_type": "cd", "product_id": self.product.pk, "quantity": 2}],
        )

    def test_unpaid_sale_returns_stock_without_cash_refund(self):
        sale = self.create(Sale.PaymentMethod.CASH_POSTPAY)
        result = cancel_sale(actor=self.actor, sale_id=sale.pk, comment="Клиент отказался")
        self.stock.refresh_from_db()
        sale.refresh_from_db()
        self.register.refresh_from_db()
        self.assertTrue(result.cancelled)
        self.assertEqual(self.stock.quantity, 10)
        self.assertEqual(self.register.balance, Decimal("0.00"))
        self.assertEqual(CashTransaction.objects.count(), 0)
        self.assertTrue(sale.is_cancelled)
        self.assertEqual(sale.refunded_amount, Decimal("0.00"))

    def test_multiple_cd_and_tech_items_return_to_the_original_warehouse(self):
        brand = Brand.objects.create(name="Sony")
        product_type = ProductType.objects.create(name="Консоли")
        tech = Tech.objects.create(
            brand=brand, product_type=product_type, name="Консоль", sku="TECH-1", avito_price=50,
        )
        tech_stock = TechWarehouseStock.objects.create(warehouse=self.warehouse, tech=tech, quantity=5)
        sale = create_sale(
            actor=self.actor, warehouse_id=self.warehouse.pk,
            price_type=Sale.PriceType.RETAIL, sale_type=Sale.SaleType.RETAIL,
            payment_method=Sale.PaymentMethod.CASH_POSTPAY,
            lines=[
                {"product_type": "cd", "product_id": self.product.pk, "quantity": 2},
                {"product_type": "tech", "product_id": tech.pk, "quantity": 3},
            ],
        )
        cancel_sale(actor=self.actor, sale_id=sale.pk, comment="Полный возврат")
        self.stock.refresh_from_db()
        tech_stock.refresh_from_db()
        self.assertEqual((self.stock.quantity, tech_stock.quantity), (10, 5))

    def test_cancellation_uses_sale_cost_snapshot_and_all_warehouse_stock(self):
        self.stock.quantity = 2
        self.stock.save(update_fields=("quantity",))
        self.product.cost = Decimal("61272.00")
        self.product.save(update_fields=("cost",))
        sale = create_sale(
            actor=self.actor, warehouse_id=self.warehouse.pk,
            price_type=Sale.PriceType.RETAIL, sale_type=Sale.SaleType.RETAIL,
            payment_method=Sale.PaymentMethod.CASH_POSTPAY,
            lines=[{"product_type": "cd", "product_id": self.product.pk, "quantity": 1}],
        )
        other_warehouse = Warehouse.objects.create(name="Другой склад")
        CDWarehouseStock.objects.create(warehouse=other_warehouse, cd=self.product, quantity=2)
        self.product.cost = Decimal("61094.00")
        self.product.save(update_fields=("cost",))

        cancel_sale(actor=self.actor, sale_id=sale.pk, comment="Возврат")

        self.product.refresh_from_db()
        self.stock.refresh_from_db()
        self.assertEqual(self.product.cost, Decimal("61138.50"))
        self.assertEqual(self.stock.quantity, 2)
        self.assertEqual(sale.cd_items.get().unit_cost_snapshot, Decimal("61272.00"))
        event = ProductChangeEvent.objects.get(
            action_kind=ProductChangeEvent.ActionKind.SALE,
            action_object_id=sale.pk,
            action_label=f"Отмена продажи {sale.visible_id}",
        )
        self.assertTrue(ProductFieldChange.objects.filter(
            event=event, field_name="cost", old_value="61094.00", new_value="61138.50",
        ).exists())

    def test_tech_cancellation_restores_snapshot_cost_to_empty_stock(self):
        brand = Brand.objects.create(name="Sony")
        product_type = ProductType.objects.create(name="Консоли")
        tech = Tech.objects.create(
            brand=brand, product_type=product_type, name="Консоль", sku="TECH-1",
            avito_price=100, cost=Decimal("61272.00"),
        )
        stock = TechWarehouseStock.objects.create(warehouse=self.warehouse, tech=tech, quantity=1)
        sale = create_sale(
            actor=self.actor, warehouse_id=self.warehouse.pk,
            price_type=Sale.PriceType.RETAIL, sale_type=Sale.SaleType.RETAIL,
            payment_method=Sale.PaymentMethod.CASH_POSTPAY,
            lines=[{"product_type": "tech", "product_id": tech.pk, "quantity": 1}],
        )
        tech.cost = Decimal("61094.00")
        tech.save(update_fields=("cost",))

        cancel_sale(actor=self.actor, sale_id=sale.pk, comment="Возврат")

        tech.refresh_from_db()
        stock.refresh_from_db()
        self.assertEqual((stock.quantity, tech.cost), (1, Decimal("61272.00")))

    def test_missing_historical_cost_rolls_back_cancellation(self):
        sale = self.create(Sale.PaymentMethod.CASH_POSTPAY)
        sale.cd_items.update(unit_cost_snapshot=None)
        with self.assertRaisesMessage(ValidationError, "нет снимка себестоимости"):
            cancel_sale(actor=self.actor, sale_id=sale.pk, comment="Возврат")
        self.stock.refresh_from_db()
        sale.refresh_from_db()
        self.assertEqual(self.stock.quantity, 8)
        self.assertFalse(sale.is_cancelled)

    def test_consignment_sale_cancellation_restores_original_consignment_lot(self):
        shop = SalesPlatform.objects.create(
            name="Площадка", address="Адрес", legal_entity="ООО", phone_1="1",
        )
        consignment_stock = transfer_to_consignment(
            actor=self.actor, warehouse_id=self.warehouse.pk, platform_id=shop.pk,
            product_type="cd", product_id=self.product.pk, quantity=2, receivable_per_unit="150",
        )
        sale = record_consignment_sale(
            actor=self.actor, product_type="cd", stock_id=consignment_stock.pk,
            quantity=1, payment_method=Sale.PaymentMethod.CASH,
        )
        cancel_sale(actor=self.actor, sale_id=sale.pk, comment="Возврат с площадки")
        self.stock.refresh_from_db()
        consignment_stock = CDConsignmentStock.objects.get(pk=consignment_stock.pk)
        self.product.refresh_from_db()
        self.assertEqual(self.stock.quantity, 8)
        self.assertEqual(consignment_stock.quantity, 2)
        self.assertEqual(self.product.quantity_on_consignment, 2)

    def test_paid_cash_sale_refunds_actual_payment_and_is_idempotent(self):
        sale = self.create(Sale.PaymentMethod.CASH)
        self.register.refresh_from_db()
        self.assertEqual(self.register.balance, Decimal("200.00"))
        first = cancel_sale(actor=self.actor, sale_id=sale.pk, comment="Возврат")
        second = cancel_sale(actor=self.actor, sale_id=sale.pk, comment="Повтор")
        self.stock.refresh_from_db()
        self.register.refresh_from_db()
        sale.refresh_from_db()
        self.assertTrue(first.cancelled)
        self.assertFalse(second.cancelled)
        self.assertEqual(self.stock.quantity, 10)
        self.assertEqual(self.register.balance, Decimal("0.00"))
        self.assertEqual(sale.refunded_amount, Decimal("200.00"))
        self.assertEqual(sale.cash_transactions.count(), 2)
        refund = sale.cash_transactions.get(operation_type=CashTransaction.OperationType.SALE_REFUND)
        self.assertEqual((refund.amount, refund.signed_amount), (Decimal("200.00"), Decimal("-200.00")))

    def test_paid_postpay_is_refunded_and_bank_refund_does_not_touch_cash(self):
        postpay = self.create(Sale.PaymentMethod.CASH_POSTPAY)
        mark_sale_paid(actor=self.actor, sale_id=postpay.pk)
        cancel_sale(actor=self.actor, sale_id=postpay.pk, comment="Постоплата возвращена")
        postpay.refresh_from_db()
        self.register.refresh_from_db()
        self.assertEqual(postpay.refunded_amount, Decimal("200.00"))
        self.assertEqual(self.register.balance, Decimal("0.00"))

        bank = self.create(Sale.PaymentMethod.BANK_ACCOUNT)
        self.assertTrue(bank.is_completed)
        before = self.register.balance
        cancel_sale(actor=self.actor, sale_id=bank.pk, comment="Безналичный возврат подтверждён")
        bank.refresh_from_db()
        self.register.refresh_from_db()
        self.assertEqual(self.register.balance, before)
        self.assertEqual(bank.refunded_amount, Decimal("200.00"))
        self.assertFalse(bank.cash_transactions.exists())

    def test_insufficient_cash_rolls_back_entire_cancellation(self):
        sale = self.create(Sale.PaymentMethod.CASH)
        collect_cash(
            actor=self.actor, warehouse_id=self.warehouse.pk, amount="200", comment="Инкассация",
        )
        with self.assertRaisesMessage(ValidationError, "Недостаточно наличных в кассе"):
            cancel_sale(actor=self.actor, sale_id=sale.pk, comment="Возврат")
        self.stock.refresh_from_db()
        sale.refresh_from_db()
        self.assertEqual(self.stock.quantity, 8)
        self.assertFalse(sale.is_cancelled)
        self.assertFalse(sale.cash_transactions.filter(
            operation_type=CashTransaction.OperationType.SALE_REFUND
        ).exists())

    def test_audit_failure_rolls_back_stock_cash_and_state(self):
        sale = self.create(Sale.PaymentMethod.CASH)
        with patch("sales.services.record_product_changes", side_effect=RuntimeError("audit failed")):
            with self.assertRaisesMessage(RuntimeError, "audit failed"):
                cancel_sale(actor=self.actor, sale_id=sale.pk, comment="Возврат")
        self.stock.refresh_from_db()
        self.register.refresh_from_db()
        sale.refresh_from_db()
        self.assertEqual((self.stock.quantity, self.register.balance), (8, Decimal("200.00")))
        self.assertFalse(sale.is_cancelled)
        self.assertEqual(sale.cash_transactions.count(), 1)

    def test_permission_confirmation_post_only_and_history_visibility(self):
        sale = self.create(Sale.PaymentMethod.CASH_POSTPAY)
        worker = User.objects.create_user("worker", password="StrongWorker!123")
        worker.user_permissions.add(
            Permission.objects.get(content_type__app_label="sales", codename="view_sales"),
            Permission.objects.get(content_type__app_label="sales", codename="view_sale_detail"),
        )
        self.client.force_login(worker)
        detail_url = reverse("sales:detail", args=(sale.pk,))
        cancel_url = reverse("sales:cancel", args=(sale.pk,))
        self.assertNotContains(self.client.get(detail_url), "Отменить продажу")
        self.assertEqual(self.client.post(cancel_url, {"cancellation_comment": "Нет"}).status_code, 403)

        worker.user_permissions.add(Permission.objects.get(
            content_type__app_label="sales", codename="cancel_sale"
        ))
        self.client.force_login(worker)
        response = self.client.get(detail_url)
        self.assertContains(response, 'data-dialog-open="sale-cancel-dialog"')
        self.assertContains(response, "Это действие нельзя отменить")
        self.assertEqual(self.client.get(cancel_url).status_code, 405)
        self.assertRedirects(
            self.client.post(cancel_url, {"cancellation_comment": "Отказ клиента"}), detail_url
        )
        list_response = self.client.get(reverse("sales:cancelled"))
        self.assertContains(list_response, "Отменённые продажи")
        self.assertContains(list_response, sale.visible_id)

    def test_comment_is_required_and_cancelled_sale_cannot_be_advanced_or_paid(self):
        sale = self.create(Sale.PaymentMethod.CASH_POSTPAY)
        with self.assertRaisesMessage(ValidationError, "причину отмены"):
            cancel_sale(actor=self.actor, sale_id=sale.pk, comment="")
        cancel_sale(actor=self.actor, sale_id=sale.pk, comment="Отказ")
        with self.assertRaisesMessage(ValidationError, "Отменённую продажу"):
            mark_sale_paid(actor=self.actor, sale_id=sale.pk)
