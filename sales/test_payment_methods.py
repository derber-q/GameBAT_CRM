"""Четыре способа оплаты: суммы, склад, касса, история и общие отчёты."""
import importlib
import uuid
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace

from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import connection
from django.db.migrations.exceptions import IrreversibleError
from django.test import TestCase
from django.urls import reverse
from openpyxl import load_workbook

from accounts.models import User
from cash.models import CashTransaction
from cash.services import credit_sale_payment, refund_sale_payment
from catalog.models import CD, Platform
from warehouse.models import CDWarehouseStock, Warehouse
from .forms import SaleCreateForm
from .models import Sale
from .services import advance_order_status, cancel_sale, create_sale, edit_postpay_sale_items, mark_sale_paid
from .statistics_forms import SaleStatisticsFilterForm
from .statistics_service import build_sales_statistics_report


class PaymentMethodsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor = User.objects.create_superuser("payment-admin", password="TestPassword123!")
        cls.warehouse = Warehouse.objects.create(name="Склад оплаты")
        cls.product = CD.objects.create(
            name="Игра", sku="PAY-CD", platform=Platform.objects.create(name="PS5"),
            avito_price=10000, cost=8000,
        )
        cls.stock = CDWarehouseStock.objects.create(warehouse=cls.warehouse, cd=cls.product, quantity=100)

    def lines(self, quantity=1):
        return [{"product_type": "cd", "product_id": self.product.pk, "quantity": quantity}]

    def sale(self, method, received=None, **kwargs):
        return create_sale(
            actor=self.actor, warehouse_id=self.warehouse.pk, price_type="retail", sale_type="retail",
            payment_method=method, cash_received_amount=received, lines=self.lines(), **kwargs,
        )

    def deliver(self, sale):
        for status in ("assembled", "delivered"):
            sale = advance_order_status(actor=self.actor, sale_id=sale.pk, next_status=status)
        return sale

    def balances(self):
        self.warehouse.cash_register.refresh_from_db()
        self.warehouse.safe.refresh_from_db()
        return self.warehouse.cash_register.balance, self.warehouse.safe.balance

    def test_forms_offer_exactly_four_payment_methods(self):
        expected = {"cash", "cash_postpay", "bank_account", "bank_transfer_postpay"}
        self.assertEqual({key for key, _ in SaleCreateForm().fields["payment_method"].choices}, expected)
        self.assertEqual({key for key, _ in SaleStatisticsFilterForm().fields["payment_methods"].choices}, expected)

    def test_immediate_payment_receipt_overpayment_completion_and_stock(self):
        for method in ("cash", "bank_account"):
            for received in (None, "10500.01"):
                with self.subTest(method=method, received=received):
                    before = self.balances()
                    self.stock.refresh_from_db()
                    stock_before = self.stock.quantity
                    sale = self.sale(method, received)
                    actual = Decimal(received or "10000")
                    self.assertTrue(sale.is_completed)
                    self.assertIsNotNone(sale.completed_at)
                    self.assertEqual(sale.paid_by, self.actor)
                    self.assertIsNotNone(sale.paid_at)
                    self.assertEqual((sale.total_amount, sale.cash_received_amount, sale.extra_cash_amount),
                                     (Decimal("10000"), actual, actual - 10000))
                    self.stock.refresh_from_db()
                    self.assertEqual(self.stock.quantity, stock_before - 1)
                    self.assertEqual(self.balances(), (before[0] + (actual if method == "cash" else 0), before[1]))
                    self.assertEqual(sale.cash_transactions.count(), int(method == "cash"))

    def test_postpayment_all_delivery_payment_combinations_and_no_duplicate_stock(self):
        for method in ("cash_postpay", "bank_transfer_postpay"):
            for pay_first in (True, False):
                with self.subTest(method=method, pay_first=pay_first):
                    before = self.balances()
                    sale = self.sale(method, "99999")
                    self.stock.refresh_from_db()
                    stock_after_create = self.stock.quantity
                    self.assertEqual(sale.payment_status, "unpaid")
                    self.assertIsNone(sale.cash_received_amount)
                    self.assertEqual(sale.extra_cash_amount, 0)
                    self.assertIsNone(sale.paid_at)
                    self.assertEqual(self.balances(), before)
                    self.assertFalse(sale.is_completed)
                    self.assertFalse(build_sales_statistics_report({"sale_ids": {sale.pk}}).sales)
                    if pay_first:
                        sale = mark_sale_paid(actor=self.actor, sale_id=sale.pk, cash_received_amount="10500")
                        self.assertFalse(sale.is_completed)
                        self.assertIsNone(sale.completed_at)
                        self.assertFalse(build_sales_statistics_report({"sale_ids": {sale.pk}}).sales)
                        sale = self.deliver(sale)
                    else:
                        sale = self.deliver(sale)
                        self.assertFalse(sale.is_completed)
                        self.assertIsNone(sale.completed_at)
                        self.assertFalse(build_sales_statistics_report({"sale_ids": {sale.pk}}).sales)
                        sale = mark_sale_paid(actor=self.actor, sale_id=sale.pk, cash_received_amount="10500")
                    self.assertTrue(sale.is_completed)
                    completed_at = sale.completed_at
                    self.assertIsNotNone(completed_at)
                    self.assertEqual((sale.cash_received_amount, sale.extra_cash_amount), (Decimal("10500"), Decimal("500")))
                    self.assertEqual(sale.paid_by, self.actor)
                    with self.assertRaises(ValidationError):
                        mark_sale_paid(actor=self.actor, sale_id=sale.pk, cash_received_amount="11000")
                    sale.refresh_from_db()
                    self.assertEqual(sale.completed_at, completed_at)
                    self.assertEqual(sale.cash_received_amount, Decimal("10500"))
                    self.stock.refresh_from_db()
                    self.assertEqual(self.stock.quantity, stock_after_create)
                    self.assertEqual(self.balances(), (before[0] + (10500 if method == "cash_postpay" else 0), before[1]))

    def test_bank_invalid_receipts_roll_back_and_blank_postpay_uses_total(self):
        for amount in ("9999.99", "-1", "NaN", "Infinity", "1000000000000000000", "abc"):
            with self.subTest(amount=amount), self.assertRaises(ValidationError):
                self.sale("bank_account", amount)
        self.assertFalse(Sale.objects.exists())
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 100)
        sale = self.sale("bank_transfer_postpay")
        with self.assertRaises(ValidationError):
            mark_sale_paid(actor=self.actor, sale_id=sale.pk, cash_received_amount="9999.99")
        sale.refresh_from_db()
        self.assertEqual(sale.payment_status, "unpaid")
        self.assertIsNone(sale.cash_received_amount)
        sale = mark_sale_paid(actor=self.actor, sale_id=sale.pk, cash_received_amount="")
        self.assertEqual(sale.cash_received_amount, Decimal("10000"))
        self.assertEqual(sale.extra_cash_amount, 0)
        self.assertEqual(self.balances(), (0, 0))

    def test_bank_postpay_edit_uses_stock_delta_then_locks_on_payment_or_delivery(self):
        sale = self.sale("bank_transfer_postpay")
        edit_postpay_sale_items(actor=self.actor, sale_id=sale.pk, lines=self.lines(3))
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 97)
        with self.assertRaises(ValidationError):
            edit_postpay_sale_items(actor=self.actor, sale_id=sale.pk, lines=self.lines(101))
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 97)
        sale = mark_sale_paid(actor=self.actor, sale_id=sale.pk)
        self.assertEqual(sale.cash_received_amount, Decimal("30000"))
        with self.assertRaises(ValidationError):
            edit_postpay_sale_items(actor=self.actor, sale_id=sale.pk, lines=self.lines(1))
        delivered = self.deliver(self.sale("bank_transfer_postpay"))
        with self.assertRaises(ValidationError):
            edit_postpay_sale_items(actor=self.actor, sale_id=delivered.pk, lines=self.lines(1))
        self.assertEqual(self.balances(), (0, 0))

    def test_cancellation_matrix_refunds_actual_receipt_once(self):
        for method in ("cash", "bank_account", "cash_postpay", "bank_transfer_postpay"):
            for paid in ((False, True) if Sale.PaymentMethod(method).is_postpayment else (True,)):
                with self.subTest(method=method, paid=paid):
                    before = self.balances()
                    sale = self.sale(method, "10500")
                    if sale.is_postpayment and paid:
                        sale = mark_sale_paid(actor=self.actor, sale_id=sale.pk, cash_received_amount="10500")
                    result = cancel_sale(actor=self.actor, sale_id=sale.pk, comment="Возврат")
                    self.assertEqual(result.sale.refunded_amount, Decimal("10500") if paid else 0)
                    self.assertFalse(result.sale.is_completed)
                    self.assertEqual(self.balances(), before)
                    self.stock.refresh_from_db()
                    self.assertEqual(self.stock.quantity, 100)
                    self.assertFalse(cancel_sale(actor=self.actor, sale_id=sale.pk, comment="Повтор").cancelled)
                    self.assertEqual(self.balances(), before)
                    self.stock.refresh_from_db()
                    self.assertEqual(self.stock.quantity, 100)
                    self.assertEqual(sale.cash_transactions.count(), 2 if sale.is_cash_payment and paid else 0)

    def test_cash_helpers_reject_all_bank_payments(self):
        for method in ("bank_account", "bank_transfer_postpay"):
            sale = self.sale(method)
            with self.assertRaises(ValidationError):
                credit_sale_payment(sale=sale, actor=self.actor)
            with self.assertRaises(ValidationError):
                refund_sale_payment(sale=sale, actor=self.actor, comment="Запрещено")
        self.assertFalse(CashTransaction.objects.exists())
        self.assertEqual(self.balances(), (0, 0))

    def test_repeated_create_does_not_deduct_stock_or_duplicate_receipt(self):
        for method in ("cash", "bank_account", "cash_postpay", "bank_transfer_postpay"):
            key = uuid.uuid4()
            sale = self.sale(method, creation_key=key)
            self.assertEqual(self.sale(method, creation_key=key).pk, sale.pk)
        self.assertEqual(Sale.objects.count(), 4)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 96)
        self.assertEqual(CashTransaction.objects.count(), 1)

    def test_statistics_filters_and_excel_use_bank_overpayment_once(self):
        self.client.force_login(self.actor)
        for method in ("bank_account", "bank_transfer_postpay"):
            sale = self.sale(method, "10500")
            if sale.is_postpayment:
                self.deliver(sale)
                mark_sale_paid(actor=self.actor, sale_id=sale.pk, cash_received_amount="10500")
            params = {"payment_methods": [method]}
            page = self.client.get(reverse("statistics:index"), params)
            totals = page.context["report"].totals
            self.assertEqual((totals.goods_total, totals.overpayment, totals.actual_revenue, totals.profit),
                             (Decimal("10000"), Decimal("500"), Decimal("10500"), Decimal("2500")))
            self.assertEqual(totals.sales_count, 1)
            response = self.client.get(reverse("statistics:export"), params)
            self.assertEqual(response.status_code, 200)
            workbook = load_workbook(BytesIO(response.content), data_only=True)
            values = list(workbook["Продажи"].values)
            self.assertEqual(len(values), 2)
            self.assertIn(Sale.PaymentMethod(method).label, values[1])
            self.assertIn(2500, values[1])
        self.assertEqual(self.balances(), (0, 0))

    def test_bank_postpay_inline_payment_and_detail(self):
        self.client.force_login(self.actor)
        sale = self.sale("bank_transfer_postpay")
        detail = self.client.get(reverse("sales:detail", args=[sale.pk]))
        self.assertContains(detail, 'name="cash_received_amount"')
        response = self.client.post(reverse("sales:inline_status", args=[sale.pk]), {
            "field": "payment", "value": "paid", "confirmed": "1", "version": sale.updated_at.isoformat(),
            "cash_received_amount": "10500",
        })
        self.assertEqual(response.status_code, 200)
        sale.refresh_from_db()
        self.assertEqual((sale.payment_status, sale.cash_received_amount), ("paid", Decimal("10500")))
        self.assertEqual(self.balances(), (0, 0))

    def test_migration_preserves_history_and_only_maps_active_incomplete_bank_sales(self):
        terminal = self.sale("bank_account", "10500")
        cancelled = self.sale("bank_account")
        cancel_sale(actor=self.actor, sale_id=cancelled.pk, comment="История")
        legacy = Sale.objects.create(
            warehouse=self.warehouse, price_type="retail", sale_type="retail", payment_method="bank_account",
            order_status="delivered", payment_status="unpaid", total_amount=10000,
        )
        paid_shipped = Sale.objects.create(
            warehouse=self.warehouse, price_type="retail", sale_type="avito", payment_method="bank_account",
            order_status="shipped", payment_status="paid", total_amount=10000,
        )
        snapshot = list(Sale.objects.order_by("pk").values("id", "completed_at", "total_amount", "cash_received_amount", "updated_at"))
        migrate = importlib.import_module("sales.migrations.0020_payment_methods").migrate_pending_bank_sales
        editor = SimpleNamespace(connection=connection)
        migrate(apps, editor)
        migrate(apps, editor)
        terminal.refresh_from_db()
        cancelled.refresh_from_db()
        legacy.refresh_from_db()
        paid_shipped.refresh_from_db()
        self.assertEqual((terminal.payment_method, cancelled.payment_method), ("bank_account", "bank_account"))
        self.assertEqual((legacy.payment_method, paid_shipped.payment_method), ("bank_transfer_postpay", "bank_transfer_postpay"))
        self.assertEqual(snapshot, list(Sale.objects.order_by("pk").values("id", "completed_at", "total_amount", "cash_received_amount", "updated_at")))
        self.assertEqual(self.balances(), (0, 0))
        self.assertFalse(CashTransaction.objects.exists())

    def test_schema_rollback_is_allowed_only_without_sales(self):
        reverse = importlib.import_module("sales.migrations.0020_payment_methods").reverse_only_empty_sales
        editor = SimpleNamespace(connection=connection)
        reverse(apps, editor)
        self.sale("bank_account", "10500")
        with self.assertRaises(IrreversibleError):
            reverse(apps, editor)
