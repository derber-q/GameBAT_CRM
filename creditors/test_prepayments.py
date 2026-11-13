"""Проводки отдельной предоплаты, идемпотентность и отмена оплаченной продажи."""
import uuid
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from cash.models import CashTransaction
from catalog.models import CD, Platform
from partners.models import Partner
from sales.models import Sale
from sales.services import create_sale, cancel_sale, mark_sale_paid
from warehouse.models import Warehouse, CDWarehouseStock
from .models import PrepaymentTransaction
from .prepayments import fund_prepayment
from .services import adjust_creditor_debt


class PrepaymentTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_superuser("prepay-admin", password="StrongAdmin!123")
        self.warehouse = Warehouse.objects.create(name="Склад предоплаты")
        self.partner = Partner.objects.create(name="Покупатель предоплаты")
        self.product = CD.objects.create(name="Игра предоплаты", sku="PREPAY-1",
            platform=Platform.objects.create(name="PS5"), wholesale_price=100, avito_price=150, cost=50)
        self.stock = CDWarehouseStock.objects.create(warehouse=self.warehouse, cd=self.product, quantity=10)

    def fund(self, amount="500", **kwargs):
        return fund_prepayment(actor=self.actor, creditor_id=self.partner.creditor_id,
            warehouse_id=self.warehouse.pk, amount=amount,
            operation_key=kwargs.pop("operation_key", uuid.uuid4()), **kwargs)

    def sale(self, method="prepayment_account", **kwargs):
        return create_sale(actor=self.actor, warehouse_id=self.warehouse.pk, price_type="wholesale",
            sale_type=kwargs.pop("sale_type", "wholesale"), partner_id=kwargs.pop("partner_id", self.partner.pk),
            payment_method=method, lines=[{"product_type": "cd", "product_id": self.product.pk, "quantity": 2}],
            **kwargs)

    def balances(self):
        self.partner.creditor.refresh_from_db()
        return self.partner.creditor.current_debt, self.partner.creditor.prepayment_balance

    def test_deposit_is_not_debt_and_repeat_does_not_duplicate_cash(self):
        for source in ("cash", "safe", "bank"):
            with self.subTest(source=source):
                key = uuid.uuid4()
                first = self.fund("50", money_source_type=source, operation_key=key)
                second = self.fund("50", money_source_type=source, operation_key=key)
                self.assertEqual(first.pk, second.pk)
                self.assertEqual(bool(first.cash_transaction_id), source != "bank")
        self.assertEqual(self.balances(), (Decimal("0"), Decimal("150")))
        self.warehouse.cash_register.refresh_from_db()
        self.warehouse.safe.refresh_from_db()
        self.assertEqual(self.warehouse.cash_register.balance, Decimal("50"))
        self.assertEqual(self.warehouse.safe.balance, Decimal("50"))
        with self.assertRaises(ValidationError):
            self.fund("51", money_source_type="bank", operation_key=key)

    def test_transfer_only_negative_available_debt_without_cash(self):
        adjust_creditor_debt(actor=self.actor, creditor_id=self.partner.creditor_id,
            warehouse_id=self.warehouse.pk, new_debt="-1000", money_source_type="offset", comment="Исходный долг")
        cash_count = CashTransaction.objects.count()
        entry = self.fund("400", transfer=True)
        self.assertIsNotNone(entry.debt_transaction_id)
        self.assertEqual(self.balances(), (Decimal("-600"), Decimal("400")))
        self.assertEqual(CashTransaction.objects.count(), cash_count)
        with self.assertRaises(ValidationError):
            self.fund("601", transfer=True)
        self.assertEqual(self.balances(), (Decimal("-600"), Decimal("400")))
        self.fund("600", transfer=True)
        with self.assertRaises(ValidationError):
            self.fund("1", transfer=True)

    def test_prepayment_sale_and_cancellation_restore_only_own_debit(self):
        self.fund()
        sale = self.sale(creation_key=uuid.uuid4())
        self.assertTrue(sale.is_completed)
        self.assertEqual((sale.cash_received_amount, sale.prepayment_used_amount, sale.debt_charge_amount),
                         (Decimal("0"), Decimal("200"), Decimal("0")))
        self.assertFalse(sale.creditor_movements.exists())
        self.assertFalse(CashTransaction.objects.filter(sale=sale).exists())
        self.assertEqual(self.balances(), (Decimal("0"), Decimal("300")))
        self.fund("50")
        cancel_sale(actor=self.actor, sale_id=sale.pk, comment="Отмена")
        cancel_sale(actor=self.actor, sale_id=sale.pk, comment="Повтор")
        self.assertEqual(self.balances(), (Decimal("0"), Decimal("550")))
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 10)
        self.assertEqual(sale.prepayment_movements.count(), 2)

    def test_insufficient_account_rolls_back_sale_and_stock(self):
        self.fund("199.99")
        with self.assertRaisesMessage(ValidationError, "Недостаточно предоплаты"):
            self.sale()
        self.assertEqual(Sale.objects.count(), 0)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 10)
        self.assertEqual(self.balances(), (Decimal("0"), Decimal("199.99")))

    def test_existing_postpayment_can_be_paid_from_account_once(self):
        self.fund()
        sale = self.sale(method="cash_postpay")
        mark_sale_paid(actor=self.actor, sale_id=sale.pk, payment_method="prepayment_account")
        sale.refresh_from_db()
        self.assertEqual(sale.order_status, Sale.OrderStatus.CREATED)
        self.assertEqual(sale.payment_status, Sale.PaymentStatus.PAID)
        self.assertEqual(self.balances(), (Decimal("0"), Decimal("300")))
        with self.assertRaisesMessage(ValidationError, "уже оплачен"):
            mark_sale_paid(actor=self.actor, sale_id=sale.pk, payment_method="prepayment_account")
        self.assertEqual(sale.prepayment_movements.count(), 1)

    def test_account_is_not_used_without_explicit_payment_choice(self):
        self.fund()
        sale = self.sale(method="bank_account")
        self.assertEqual(sale.prepayment_used_amount, 0)
        self.assertEqual(self.balances(), (Decimal("0"), Decimal("500")))

    def test_retail_custom_buyer_and_archived_partner_cannot_spend(self):
        self.fund()
        with self.assertRaises(ValidationError):
            self.sale(sale_type="retail")
        with self.assertRaises(ValidationError):
            self.sale(partner_id=None, partner_name="Без счёта")
        self.partner.is_archived = True
        self.partner.save(update_fields=("is_archived",))
        with self.assertRaises(ValidationError):
            self.sale()
        self.assertEqual(self.balances(), (Decimal("0"), Decimal("500")))

    def test_permissions_and_history_in_ui(self):
        self.client.force_login(self.actor)
        response = self.client.get(reverse("creditors:list"))
        self.assertContains(response, "Предоплата")
        self.assertContains(response, reverse("creditors:prepayment", args=[self.partner.creditor_id]))
        user = User.objects.create_user("no-prepay", password="Password123!")
        with self.assertRaises(PermissionDenied):
            fund_prepayment(actor=user, creditor_id=self.partner.creditor_id, warehouse_id=self.warehouse.pk,
                amount="100", operation_key=uuid.uuid4())
        self.assertEqual(PrepaymentTransaction.objects.count(), 0)
