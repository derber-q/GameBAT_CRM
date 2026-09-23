from decimal import Decimal
from django.contrib.auth.models import Permission
from django.db import connection
from django.test import TestCase, Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from accounts.models import User
from cash.models import CashRegister, CashTransaction
from catalog.models import CD, Platform
from warehouse.models import CDWarehouseStock, Warehouse
from .models import Sale
from .services import create_sale, advance_order_status, mark_sale_paid, cancel_sale


class SaleListingTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_superuser('status-admin', password='test-password')
        self.warehouse = Warehouse.objects.create(name='Status warehouse')
        self.cd = CD.objects.create(platform=Platform.objects.create(name='PS5'), name='Disc', avito_price=100)
        self.stock = CDWarehouseStock.objects.create(cd=self.cd, warehouse=self.warehouse, quantity=1000)
        self.client.force_login(self.actor)

    def sale(self, kind=Sale.SaleType.RETAIL, method=Sale.PaymentMethod.BANK_ACCOUNT):
        return create_sale(actor=self.actor, warehouse_id=self.warehouse.pk, price_type=Sale.PriceType.RETAIL,
                           sale_type=kind, payment_method=method,
                           lines=[{'product_type': 'cd', 'product_id': self.cd.pk, 'quantity': 1}], note='Keep this note')

    def post(self, sale, field='order', value='assembled', **extra):
        data = {'field': field, 'value': value, 'confirmed': '1', 'version': sale.updated_at.isoformat()}
        data.update(extra)
        return self.client.post(reverse('sales:inline_status', args=[sale.pk]), data)

    def test_pages_group_all_types_exclusively_and_keep_columns(self):
        expected = {name: [] for name in ('incomplete', 'completed', 'cancelled')}
        for kind in Sale.SaleType.values:
            expected['incomplete'].append(self.sale(kind).pk)
            expected['completed'].append(self.sale(kind, Sale.PaymentMethod.CASH).pk)
            cancelled = self.sale(kind)
            cancel_sale(actor=self.actor, sale_id=cancelled.pk, comment='Duplicate order')
            expected['cancelled'].append(cancelled.pk)
        for name, pks in expected.items():
            response = self.client.get(reverse('sales:' + name))
            self.assertEqual(response.status_code, 200)
            groups = response.context['groups']
            self.assertEqual([g['kind'] for g in groups], Sale.SaleType.values)
            self.assertEqual(sorted(row['sale'].pk for g in groups for row in g['rows']), sorted(pks))
            for group in groups:
                self.assertTrue(all(row['sale'].sale_type == group['kind'] for row in group['rows']))
                self.assertContains(response, f'aria-controls="sales-group-{group["kind"]}" data-collapse-toggle')
                self.assertContains(response, f'id="sales-group-{group["kind"]}" class="collapsible-content"')
            self.assertContains(response, 'Keep this note')
            self.assertContains(response, 'Статус заказа')
            self.assertContains(response, 'Статус оплаты')
            if name != 'incomplete':
                self.assertNotContains(response, 'data-status-field=')

    def test_navigation_and_old_list_url(self):
        response = self.client.get(reverse('sales:list'))
        self.assertContains(response, 'href="/sales/new/" aria-haspopup="true">Продажа</a>')
        for name in ('incomplete', 'completed', 'cancelled'):
            self.assertContains(response, reverse('sales:' + name))
        self.assertEqual(response.context['state'], 'incomplete')
        self.assertEqual(self.client.get(reverse('sales:create')).status_code, 200)

    def test_order_steps_payment_completion_and_actual_row_version(self):
        sale = self.sale()
        page = self.client.get(reverse('sales:incomplete'))
        self.assertContains(page, f'data-version="{sale.updated_at.isoformat()}"')
        self.assertContains(page, 'value="assembled"')
        self.assertNotContains(page, 'value="delivered"')
        self.assertEqual(self.post(sale, value='delivered').status_code, 400)
        for value in ('assembled', 'shipped', 'delivered'):
            response = self.post(sale, value=value)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['order_status'], value)
            sale.refresh_from_db()
        response = self.post(sale, field='payment', value='paid')
        self.assertTrue(response.json()['is_completed'])
        self.assertEqual(response.json()['payment_status'], 'paid')
        self.assertFalse(CashTransaction.objects.filter(sale=sale).exists())
        self.assertNotContains(self.client.get(reverse('sales:incomplete')), f'data-sale-row="{sale.pk}"')
        self.assertContains(self.client.get(reverse('sales:completed')), f'data-sale-row="{sale.pk}"')

    def test_confirmation_permissions_csrf_and_get(self):
        sale = self.sale()
        url = reverse('sales:inline_status', args=[sale.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.post(sale, confirmed='').status_code, 400)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.actor)
        self.assertEqual(csrf_client.post(url, {}).status_code, 403)
        user = User.objects.create_user('viewer')
        user.user_permissions.add(Permission.objects.get(codename='view_sales'))
        self.client.force_login(user)
        page = self.client.get(reverse('sales:incomplete'))
        self.assertNotContains(page, 'data-status-field=')
        self.assertEqual(self.post(sale).status_code, 403)
        self.assertEqual(self.client.get(reverse('sales:completed')).status_code, 403)
        user.user_permissions.add(Permission.objects.get(codename='advance_order_status'))
        self.assertEqual(self.post(sale, field='payment', value='paid').status_code, 403)
        self.assertEqual(self.post(sale).status_code, 200)

    def test_stale_and_double_request_do_not_advance_again(self):
        sale = self.sale()
        self.assertEqual(self.post(sale).status_code, 200)
        response = self.post(sale, value='shipped')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['order_status'], 'assembled')
        sale.refresh_from_db()
        self.assertEqual(sale.order_status, 'assembled')

    def test_cash_postpay_exactly_once_and_stock_unchanged(self):
        sale = self.sale(method=Sale.PaymentMethod.CASH_POSTPAY)
        self.stock.refresh_from_db()
        quantity = self.stock.quantity
        response = self.post(sale, field='payment', value='paid', cash_received_amount='125')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.post(sale, field='payment', value='paid').status_code, 409)
        self.assertEqual(CashTransaction.objects.filter(sale=sale).count(), 1)
        self.assertEqual(CashRegister.objects.get(warehouse=self.warehouse).balance, Decimal('125'))
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, quantity)
        sale.refresh_from_db()
        self.assertEqual(sale.extra_cash_amount, Decimal('25'))
        self.assertFalse(sale.is_completed)
        self.assertEqual(self.post(sale, field='payment', value='unpaid').status_code, 400)

    def test_missing_register_and_bad_amount_roll_back(self):
        sale = self.sale(method=Sale.PaymentMethod.CASH_POSTPAY)
        response = self.post(sale, field='payment', value='paid', cash_received_amount='99')
        self.assertEqual(response.status_code, 400)
        CashRegister.objects.filter(warehouse=self.warehouse).delete()
        response = self.post(sale, field='payment', value='paid')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['payment_status'], 'unpaid')
        self.assertFalse(CashTransaction.objects.filter(sale=sale).exists())

    def test_terminal_states_reject_changes(self):
        completed = self.sale(method=Sale.PaymentMethod.CASH)
        self.assertEqual(self.post(completed).status_code, 409)
        cancelled = self.sale()
        cancel_sale(actor=self.actor, sale_id=cancelled.pk, comment='Cancel')
        response = self.post(cancelled, field='payment', value='paid')
        self.assertEqual(response.status_code, 409)
        self.assertTrue(response.json()['is_cancelled'])

    def test_no_n_plus_one_and_per_type_pagination(self):
        self.sale()
        url = reverse('sales:incomplete')
        with CaptureQueriesContext(connection) as first:
            self.client.get(url)
        for _ in range(6):
            self.sale()
        with CaptureQueriesContext(connection) as second:
            self.client.get(url)
        self.assertEqual(len(first), len(second))
        # No business transitions needed for pagination fixtures.
        Sale.objects.bulk_create([
            Sale(warehouse=self.warehouse, created_by=self.actor, price_type='retail',
                 sale_type='retail', payment_method='bank_account') for _ in range(45)
        ])
        self.sale(Sale.SaleType.AVITO)
        response = self.client.get(url, {'page_retail': 2})
        groups = {group['kind']: group for group in response.context['groups']}
        self.assertEqual(len(groups['retail']['rows']), 2)
        self.assertEqual(len(groups['avito']['rows']), 1)
