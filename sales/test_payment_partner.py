"""Явная привязка партнёра при частичной оплате ранее созданной продажи."""
import uuid
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from catalog.models import CD, Platform
from partners.models import Partner
from warehouse.models import CDWarehouseStock, Warehouse
from .models import Sale
from .services import advance_order_status, cancel_sale, create_sale, mark_sale_paid


class PaymentPartnerTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_superuser('payment-partner-admin')
        self.partner = Partner.objects.create(name='Zona61')
        self.other = Partner.objects.create(name='Другой партнёр')
        self.archived = Partner.objects.create(name='Архивный', is_archived=True)
        self.warehouse = Warehouse.objects.create(name='Склад оплаты')
        self.product = CD.objects.create(name='Игра', platform=Platform.objects.create(name='PS5'),
            cost='6000', wholesale_price='35300', avito_price='36000')
        self.stock = CDWarehouseStock.objects.create(warehouse=self.warehouse, cd=self.product, quantity=10)
        self.client.force_login(self.actor)

    def sale(self, **kwargs):
        data = dict(actor=self.actor, warehouse_id=self.warehouse.pk, sale_type='wholesale',
            price_type='wholesale', partner_name='Zona 61', payment_method='cash_postpay',
            creation_key=uuid.uuid4(), lines=[{'product_type': 'cd', 'product_id': self.product.pk, 'quantity': 1}])
        data.update(kwargs)
        return create_sale(**data)

    def preview(self, sale, partner=None, received='30000'):
        return self.client.post(reverse('sales:settlement_preview'), {
            'sale_id': sale.pk, 'partner_id': (partner or self.partner).pk, 'received': received})

    def pay(self, sale, **kwargs):
        data = dict(actor=self.actor, sale_id=sale.pk, cash_received_amount='30000',
            settlement_partner_id=self.partner.pk, note='Остаток в долг')
        if 'settlement_confirmation' not in kwargs:
            response = self.preview(sale)
            data['settlement_confirmation'] = response.json().get('token', '') if response.status_code == 200 else ''
        data.update(kwargs)
        return mark_sale_paid(**data)

    def assert_unpaid(self, sale):
        sale.refresh_from_db()
        self.partner.creditor.refresh_from_db()
        self.assertEqual((sale.partner_id, sale.partner_name_snapshot, sale.payment_status), (None, 'Zona 61', 'unpaid'))
        self.assertEqual(self.partner.creditor.current_debt, 0)
        self.assertFalse(sale.creditor_movements.exists())
        self.assertFalse(sale.cash_transactions.exists())

    def test_delivered_sale_can_choose_partner_and_partial_payment_is_reversible(self):
        for method in ('cash_postpay', 'bank_transfer_postpay'):
            with self.subTest(method=method):
                sale = self.sale(payment_method=method)
                for status in ('assembled', 'delivered'):
                    sale = advance_order_status(actor=self.actor, sale_id=sale.pk, next_status=status)
                self.assertTrue(sale.can_select_payment_partner)
                preview = self.preview(sale)
                self.assertEqual(preview.status_code, 200)
                self.assertEqual(preview.json()['values']['charge'], '5300.00')
                self.assert_unpaid(sale)
                sale = self.pay(sale)
                self.assertEqual((sale.partner_id, sale.partner_name_snapshot), (self.partner.pk, self.partner.name))
                self.assertEqual((sale.cash_received_amount, sale.debt_charge_amount), (30000, 5300))
                self.assertTrue(sale.is_completed)
                self.partner.creditor.refresh_from_db()
                self.warehouse.cash_register.refresh_from_db()
                self.assertEqual(self.partner.creditor.current_debt, 5300)
                self.assertEqual(self.warehouse.cash_register.balance, 30000 if method == 'cash_postpay' else 0)
                self.assertEqual(sale.creditor_movements.get().partner_name_snapshot, self.partner.name)
                with self.assertRaises(ValidationError):
                    self.pay(sale)
                cancel_sale(actor=self.actor, sale_id=sale.pk, comment='Возврат')
                self.partner.creditor.refresh_from_db()
                self.warehouse.cash_register.refresh_from_db()
                self.stock.refresh_from_db()
                self.assertEqual((self.partner.creditor.current_debt, self.warehouse.cash_register.balance,
                    self.stock.quantity), (0, 0, 10))

    def test_full_payment_does_not_match_partner_by_name(self):
        sale = self.sale(partner_name=self.partner.name)
        sale = mark_sale_paid(actor=self.actor, sale_id=sale.pk)
        self.assertIsNone(sale.partner_id)
        self.assertFalse(sale.creditor_movements.exists())
        self.assertEqual(sale.cash_received_amount, sale.total_amount)

    def test_missing_invalid_archived_partner_and_stale_confirmation_leave_sale_unchanged(self):
        sale = self.sale()
        token = self.preview(sale).json()['token']
        for choice in (None, '', 'bad', '1' * 30, self.archived.pk, 999999):
            with self.subTest(choice=choice), self.assertRaises(ValidationError):
                self.pay(sale, settlement_partner_id=choice, settlement_confirmation=token)
            self.assert_unpaid(sale)
        with self.assertRaisesMessage(ValidationError, 'изменились'):
            self.pay(sale, settlement_partner_id=self.other.pk, settlement_confirmation=token)
        self.assert_unpaid(sale)
        with self.assertRaisesMessage(ValidationError, 'изменились'):
            self.pay(sale, cash_received_amount='29000', settlement_confirmation=token)
        self.assert_unpaid(sale)

    def test_link_and_debt_rollback_on_cash_error(self):
        sale = self.sale()
        token = self.preview(sale).json()['token']
        with patch('cash.services.CashTransaction.objects.create', side_effect=RuntimeError('касса')):
            with self.assertRaises(RuntimeError):
                self.pay(sale, settlement_confirmation=token)
        self.assert_unpaid(sale)

    def test_existing_partner_cannot_be_replaced(self):
        sale = self.sale(partner_id=self.partner.pk, partner_name='')
        self.assertFalse(sale.can_select_payment_partner)
        self.assertEqual(self.preview(sale, self.other).status_code, 400)
        with self.assertRaisesMessage(ValidationError, 'другой партнёр'):
            self.pay(sale, settlement_partner_id=self.other.pk)
        sale.refresh_from_db()
        self.assertEqual(sale.partner_id, self.partner.pk)

    def test_retail_cancelled_and_paid_sales_cannot_choose_partner(self):
        retail = self.sale(sale_type='retail', price_type='retail', partner_name='')
        cancelled = self.sale()
        cancel_sale(actor=self.actor, sale_id=cancelled.pk, comment='Отмена')
        paid = self.sale()
        mark_sale_paid(actor=self.actor, sale_id=paid.pk)
        for sale in (retail, cancelled, paid):
            sale.refresh_from_db()
            self.assertFalse(sale.can_select_payment_partner)
            self.assertEqual(self.preview(sale).status_code, 404)
            with self.assertRaises(ValidationError):
                self.pay(sale, settlement_confirmation='')

    def test_new_choice_requires_payment_and_debt_permissions(self):
        sale = self.sale()
        token = self.preview(sale).json()['token']
        actor = User.objects.create_user('payment-partner-cashier')
        with self.assertRaises(PermissionDenied):
            self.pay(sale, actor=actor, settlement_confirmation=token)
        actor.user_permissions.add(Permission.objects.get(content_type__app_label='sales', codename='mark_sale_paid'))
        actor = User.objects.get(pk=actor.pk)
        self.client.force_login(actor)
        self.assertEqual(self.preview(sale).status_code, 403)
        with self.assertRaises(PermissionDenied):
            self.pay(sale, actor=actor, settlement_confirmation=token)
        self.assert_unpaid(sale)

    def test_detail_and_inline_payment_forward_explicit_choice(self):
        for inline in (False, True):
            with self.subTest(inline=inline):
                sale = self.sale()
                self.assertContains(self.client.get(reverse('sales:detail', args=[sale.pk])), 'id="sale-payment-partner"')
                token = self.preview(sale).json()['token']
                data = {'cash_received_amount': '30000', 'settlement_partner_id': self.partner.pk,
                    'settlement_confirmation': token, 'settlement_note': 'Остаток в долг'}
                endpoint = 'inline_status' if inline else 'mark_paid'
                if inline:
                    data.update(field='payment', value='paid', confirmed='1', version=sale.updated_at.isoformat())
                response = self.client.post(reverse('sales:' + endpoint, args=[sale.pk]), data)
                self.assertEqual(response.status_code, 200 if inline else 302)
                if inline:
                    self.assertTrue(response.json()['success'])
                sale.refresh_from_db()
                self.assertEqual((sale.partner_id, sale.cash_received_amount, sale.debt_charge_amount),
                    (self.partner.pk, Decimal('30000'), Decimal('5300')))
                cancel_sale(actor=self.actor, sale_id=sale.pk, comment='Возврат')
