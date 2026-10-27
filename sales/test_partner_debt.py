"""Продажа в долг, нулевое получение наличных и обратимость финансового журнала."""
import uuid
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from cash.models import CashTransaction
from catalog.models import CD, Platform
from creditors.models import CreditorTransaction
from creditors.services import adjust_creditor_debt
from partners.models import Partner
from warehouse.models import CDWarehouseStock, Warehouse
from .models import Sale
from .services import create_sale, cancel_sale, mark_sale_paid, advance_order_status
from .statistics_service import build_sales_statistics_report
from .partner_payments import quote, SALT


class PartnerDebtTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_superuser('debt-admin')
        self.partner = Partner.objects.create(name='Игромир')
        self.warehouse = Warehouse.objects.create(name='Склад')
        self.product = CD.objects.create(name='Игра', platform=Platform.objects.create(name='PS5'),
            cost='6000.00', wholesale_price='10000.25', avito_price='11000.00')
        self.stock = CDWarehouseStock.objects.create(warehouse=self.warehouse, cd=self.product, quantity=10)
        self.key = uuid.uuid4()

    def sale(self, **kwargs):
        data = dict(actor=self.actor, warehouse_id=self.warehouse.pk, sale_type='wholesale', price_type='wholesale',
            partner_id=self.partner.pk, payment_method='partner_debt', creation_key=self.key,
            lines=[{'product_type': 'cd', 'product_id': self.product.pk, 'quantity': 1}])
        data.update(kwargs)
        return create_sale(**data)

    def assert_debt(self, sale, amount):
        self.partner.creditor.refresh_from_db()
        self.warehouse.cash_register.refresh_from_db()
        self.warehouse.safe.refresh_from_db()
        self.assertEqual(self.partner.creditor.current_debt, Decimal(amount))
        self.assertEqual((self.warehouse.cash_register.balance, self.warehouse.safe.balance), (0, 0))
        self.assertFalse(CashTransaction.objects.filter(sale=sale).exists())

    def test_explicit_and_cash_zero_add_exact_total_once(self):
        for method in ('partner_debt', 'cash'):
            with self.subTest(method=method):
                self.key = uuid.uuid4()
                sale = self.sale(payment_method=method, cash_received_amount='0.00')
                replay = self.sale(payment_method=method, cash_received_amount='0.00')
                self.assertEqual(replay.pk, sale.pk)
                self.assertEqual(sale.payment_method, 'partner_debt')
                self.assertEqual(sale.get_payment_status_display(), 'В долг')
                self.assertTrue(sale.is_completed)
                self.assertEqual((sale.cash_received_amount, sale.extra_cash_amount, sale.debt_offset_amount), (0, 0, 0))
                entry = sale.creditor_movements.get()
                self.assertEqual((entry.kind, entry.delta, entry.money_source_type), ('sale_debt', sale.total_amount, 'offset'))
                self.assertIsNone(entry.cash_transaction_id)
                self.assert_debt(sale, '10000.25')
                self.stock.refresh_from_db()
                self.assertEqual(self.stock.quantity, 9)
                self.client.force_login(self.actor)
                response = self.client.get(reverse('creditors:list'))
                self.assertContains(response, self.partner.name)
                response = self.client.get(reverse('sales:detail', args=[sale.pk]))
                self.assertContains(response, 'Начислено в долг партнёру')
                report = build_sales_statistics_report({'partner': self.partner})
                self.assertEqual((report.totals.sales_count, report.totals.profit), (1, Decimal('4000.25')))
                self.assertEqual(sum(row.actual_money for row in report.operations), 0)
                self.assertEqual(sum(row.debt_change for row in report.operations), sale.total_amount)
                cancel_sale(actor=self.actor, sale_id=sale.pk, comment='Возврат')
                cancel_sale(actor=self.actor, sale_id=sale.pk, comment='Повтор')
                self.assert_debt(sale, '0')
                self.stock.refresh_from_db()
                self.assertEqual(self.stock.quantity, 10)
                self.assertEqual(sale.creditor_movements.count(), 2)
        call_command('verify_cash', stdout=StringIO())
        call_command('verify_inventory', stdout=StringIO())

    def test_existing_debt_of_either_direction_increases_by_total(self):
        for old in ('3000.10', '-15000.50'):
            with self.subTest(old=old):
                adjust_creditor_debt(actor=self.actor, creditor_id=self.partner.creditor_id,
                    warehouse_id=self.warehouse.pk, money_source_type='offset', new_debt=old, comment='Начальный долг')
                self.key = uuid.uuid4()
                sale = self.sale(payment_method='cash', cash_received_amount=0)
                self.assert_debt(sale, str(Decimal(old) + sale.total_amount))
                cancel_sale(actor=self.actor, sale_id=sale.pk, comment='Возврат')
                self.assert_debt(sale, old)

    def test_cash_postpayment_zero_transfers_to_creditor_once(self):
        sale = self.sale(payment_method='cash_postpay')
        self.assert_debt(sale, '0')
        self.assertFalse(sale.creditor_movements.exists())
        sale = mark_sale_paid(actor=self.actor, sale_id=sale.pk, cash_received_amount=0)
        self.assert_debt(sale, '10000.25')
        with self.assertRaises(ValidationError):
            mark_sale_paid(actor=self.actor, sale_id=sale.pk)
        for status in ('assembled', 'delivered'):
            sale = advance_order_status(actor=self.actor, sale_id=sale.pk, next_status=status)
        self.assertTrue(sale.is_completed)
        self.assertEqual(sale.creditor_movements.count(), 1)

    def partial_token(self, sale, received, debt):
        return signing.dumps(quote(total=sale.total_amount, received=received, debt=debt,
            partner_id=self.partner.pk, sale_id=sale.pk), salt=SALT)

    def test_partial_payment_and_cancellation_preserve_cash_stock_and_other_partner_debt(self):
        self.product.wholesale_price = Decimal('65900')
        self.product.save(update_fields=['wholesale_price'])
        for method in ('cash_postpay', 'bank_transfer_postpay'):
            for old in ('0', '2000', '-5000', '-20000'):
                with self.subTest(method=method, old=old):
                    self.partner.creditor.refresh_from_db()
                    if self.partner.creditor.current_debt != Decimal(old):
                        adjust_creditor_debt(actor=self.actor, creditor_id=self.partner.creditor_id,
                            warehouse_id=self.warehouse.pk, money_source_type='offset', new_debt=old, comment='Начальный долг')
                    self.key = uuid.uuid4()
                    sale = self.sale(payment_method=method)
                    self.assertFalse(sale.creditor_movements.exists())
                    sale = mark_sale_paid(actor=self.actor, sale_id=sale.pk, cash_received_amount='52900',
                        note='Частичная оплата', settlement_confirmation=self.partial_token(sale, '52900', old))
                    expected_offset = min(Decimal('13000'), max(-Decimal(old), 0))
                    self.assertEqual((sale.cash_received_amount, sale.debt_offset_amount, sale.debt_charge_amount),
                        (Decimal('52900'), expected_offset, Decimal('13000') - expected_offset))
                    entry = sale.creditor_movements.get()
                    self.assertEqual((entry.delta, entry.amount), (13000, 13000))
                    self.partner.creditor.refresh_from_db()
                    self.assertEqual(self.partner.creditor.current_debt, Decimal(old) + 13000)
                    self.warehouse.cash_register.refresh_from_db()
                    self.assertEqual(self.warehouse.cash_register.balance, 52900 if method == 'cash_postpay' else 0)
                    with self.assertRaises(ValidationError):
                        mark_sale_paid(actor=self.actor, sale_id=sale.pk, cash_received_amount='52900')
                    # Последующее движение по счёту не должно исчезнуть при отмене этой продажи.
                    adjust_creditor_debt(actor=self.actor, creditor_id=self.partner.creditor_id,
                        warehouse_id=self.warehouse.pk, money_source_type='offset',
                        new_debt=Decimal(old) + 13100, comment='Другая операция')
                    cancel_sale(actor=self.actor, sale_id=sale.pk, comment='Отмена частично оплаченной продажи')
                    self.assertFalse(cancel_sale(actor=self.actor, sale_id=sale.pk, comment='Повтор').cancelled)
                    self.partner.creditor.refresh_from_db()
                    self.warehouse.cash_register.refresh_from_db()
                    self.stock.refresh_from_db()
                    self.assertEqual((self.partner.creditor.current_debt, self.warehouse.cash_register.balance,
                        self.stock.quantity), (Decimal(old) + 100, 0, 10))
                    self.assertEqual(sale.creditor_movements.count(), 2)
                    sale.refresh_from_db()
                    self.assertEqual(sale.refunded_amount, 52900)
        call_command('verify_cash', stdout=StringIO())
        call_command('verify_inventory', stdout=StringIO())

    def test_partial_payment_requires_permission_confirmation_note_and_current_balance(self):
        sale = self.sale(payment_method='cash_postpay')
        token = self.partial_token(sale, '8000', 0)
        with self.assertRaisesMessage(ValidationError, 'примечание'):
            mark_sale_paid(actor=self.actor, sale_id=sale.pk, cash_received_amount='8000', settlement_confirmation=token)
        with self.assertRaisesMessage(ValidationError, 'Подтвердите'):
            mark_sale_paid(actor=self.actor, sale_id=sale.pk, cash_received_amount='8000', note='Часть оплаты')
        actor = User.objects.create_user('partial-cashier')
        with self.assertRaises(PermissionDenied):
            mark_sale_paid(actor=actor, sale_id=sale.pk, cash_received_amount='8000', note='Часть оплаты', settlement_confirmation=token)
        with patch('cash.services.CashTransaction.objects.create', side_effect=RuntimeError('касса')):
            with self.assertRaises(RuntimeError):
                mark_sale_paid(actor=self.actor, sale_id=sale.pk, cash_received_amount='8000', note='Часть оплаты', settlement_confirmation=token)
        self.assert_debt(sale, '0')
        self.assertFalse(sale.creditor_movements.exists())
        sale.refresh_from_db()
        self.assertEqual(sale.payment_status, 'unpaid')
        adjust_creditor_debt(actor=self.actor, creditor_id=self.partner.creditor_id,
            warehouse_id=self.warehouse.pk, money_source_type='offset', new_debt=100, comment='Другой расчёт')
        with self.assertRaisesMessage(ValidationError, 'изменились'):
            mark_sale_paid(actor=self.actor, sale_id=sale.pk, cash_received_amount='8000', note='Часть оплаты', settlement_confirmation=token)

    def test_partial_http_preview_and_payment_then_cancel(self):
        self.client.force_login(self.actor)
        sale = self.sale(payment_method='cash_postpay')
        response = self.client.post(reverse('sales:settlement_preview'),
            {'sale_id': sale.pk, 'received': '8000'})
        self.assertEqual(response.status_code, 200)
        values = response.json()
        self.assertEqual(values['values']['charge'], '2000.25')
        response = self.client.post(reverse('sales:mark_paid', args=[sale.pk]),
            {'cash_received_amount': '8000', 'settlement_confirmation': values['token'], 'settlement_note': 'Часть оплаты'})
        self.assertEqual(response.status_code, 302)
        sale.refresh_from_db()
        self.assertEqual((sale.cash_received_amount, sale.debt_charge_amount), (Decimal('8000'), Decimal('2000.25')))
        self.assertEqual(sale.get_payment_status_display(), 'Частично оплачено, остаток в долг')
        self.assertContains(self.client.get(reverse('sales:detail', args=[sale.pk])), 'Начислено в долг партнёру')

    def test_not_available_to_arbitrary_partner_retail_or_expense(self):
        for changes in (
            {'partner_id': None, 'partner_name': 'Ручное имя'},
            {'sale_type': 'retail', 'price_type': 'retail', 'partner_id': None},
            {'cash_received_amount': '1'},
            {'lines': [{'product_type': 'custom', 'name': 'Бесплатный', 'quantity': 1, 'unit_price': 0, 'unit_cost': 0}]},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.sale(**changes)
        with self.assertRaises(ValidationError):
            self.sale(payment_method='cash', partner_id=None, partner_name='Ручное имя', cash_received_amount=0)
        self.assertFalse(Sale.objects.exists())

    def test_debt_permission_and_atomic_rollback(self):
        actor = User.objects.create_user('seller')
        actor.user_permissions.add(Permission.objects.get(codename='create_sale', content_type__app_label='sales'))
        with self.assertRaises(PermissionDenied):
            self.sale(actor=actor)
        with patch('sales.partner_payments.CreditorTransaction.objects.create', side_effect=RuntimeError('journal failure')):
            with self.assertRaises(RuntimeError):
                self.sale()
        self.assertFalse(Sale.objects.exists())
        self.partner.creditor.refresh_from_db()
        self.stock.refresh_from_db()
        self.assertEqual((self.partner.creditor.current_debt, self.stock.quantity), (0, 10))

    def test_form_posts_both_payment_variants_and_rejects_custom_partner(self):
        self.client.force_login(self.actor)
        payload = {'warehouse': self.warehouse.pk, 'sale_type': 'wholesale', 'price_type': 'wholesale',
            'customer': self.partner.pk, 'product_type': 'cd', 'product_id': self.product.pk, 'quantity': 1,
            'unit_discount': 0, 'cash_received_amount': 0}
        for method in ('partner_debt', 'cash'):
            with self.subTest(method=method):
                response = self.client.post(reverse('sales:create'), {**payload, 'payment_method': method, 'creation_key': uuid.uuid4()})
                self.assertEqual(response.status_code, 302)
        self.assertEqual(Sale.objects.count(), 2)
        response = self.client.post(reverse('sales:create'), {**payload, 'customer': 'custom',
            'custom_partner_name': 'Не из базы', 'payment_method': 'partner_debt'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('payment_method', response.context['form'].errors)

    def test_database_rejects_nonzero_receipt_or_missing_partner(self):
        sale = self.sale()
        for changes in ({'partner': None}, {'cash_received_amount': 1}, {'payment_status': 'unpaid'}, {'extra_cash_amount': 1}):
            with self.subTest(changes=changes), self.assertRaises(IntegrityError), transaction.atomic():
                for key, value in changes.items():
                    setattr(sale, key, value)
                sale.save(update_fields=changes)
            sale.refresh_from_db()
