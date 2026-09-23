from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import connection, close_old_connections, IntegrityError, OperationalError
from django.test import TestCase, TransactionTestCase, Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from accounts.models import User
from cash.models import CashRegister, CashTransaction
from catalog.models import CD, Tech, Platform, ProductType, Brand, BarcodeRegistry
from partners.models import SalesPlatform
from sales.models import Sale
from warehouse.models import Warehouse, CDWarehouseStock, TechWarehouseStock
from .models import CDConsignmentStock, TechConsignmentStock, ConsignmentMovement, ConsignmentActionReceipt
from .row_actions import action_token, perform_row_action
from .services import transfer_to_consignment, record_consignment_sale


class RowFixtures:
    def setUp(self):
        self.user = User.objects.create_superuser('row-admin')
        self.source = Warehouse.objects.create(name='Source')
        self.target = Warehouse.objects.create(name='Chosen warehouse')
        self.platform = SalesPlatform.objects.create(name='Partner')
        self.other = SalesPlatform.objects.create(name='Other partner')
        self.cd = CD.objects.create(platform=Platform.objects.create(name='PS5'), name='Тестовый диск', sku='DISC-ABC', cusa_ppsa_code='PPSA-TEST', cost=50)
        self.tech = Tech.objects.create(brand=Brand.objects.create(name='Sony'), product_type=ProductType.objects.create(name='Pad'), name='Геймпад тест', sku='PAD-XYZ', cost=75)
        CDWarehouseStock.objects.create(warehouse=self.source, cd=self.cd, quantity=100)
        TechWarehouseStock.objects.create(warehouse=self.source, tech=self.tech, quantity=100)
        self.client.force_login(self.user)

    def transfer(self, kind='cd', quantity=5, platform=None):
        return transfer_to_consignment(actor=self.user, warehouse_id=self.source.pk,
            platform_id=(platform or self.platform).pk, product_type=kind,
            product_id=(self.cd if kind == 'cd' else self.tech).pk,
            quantity=quantity, receivable_per_unit='100')

    def post(self, stock, kind='cd', action='return', quantity='1', **extra):
        data = dict(action=action, quantity=quantity, confirmed='1', token=action_token(stock, kind, self.user),
                    warehouse=self.target.pk, payment_method='bank_account')
        data.update(extra)
        return self.client.post(reverse('consignment:row_action', args=[kind, stock.pk]), data)


class RowActionTests(RowFixtures, TestCase):
    def test_return_one_partial_all_both_kinds_to_chosen_warehouse(self):
        for kind, product, model in [('cd', self.cd, CDWarehouseStock), ('tech', self.tech, TechWarehouseStock)]:
            stock = self.transfer(kind, 5)
            for amount, remaining in [(2, 3), (2, 1), (1, 0)]:
                response = self.post(stock, kind, quantity=str(amount))
                self.assertEqual(response.status_code, 200, response.content)
                self.assertEqual(response.json()['quantity'], remaining)
                stock.refresh_from_db()
            self.assertEqual(response.json()['row_html'], '')
            self.assertEqual(model.objects.get(warehouse=self.target, **{kind: product}).quantity, 5)
            self.assertEqual(model.objects.get(warehouse=self.source, **{kind: product}).quantity, 95)
            product.refresh_from_db()
            self.assertEqual(product.quantity_on_consignment, 0)
            movement = ConsignmentMovement.objects.filter(operation_type='return').latest('pk')
            self.assertEqual(movement.warehouse, self.target)
            self.assertEqual(movement.created_by, self.user)
            self.assertEqual(movement.items.get().quantity, 1)
            self.assertTrue(product.change_events.filter(action_object_id=movement.pk, action_kind='consignment').exists())
            self.assertEqual(stock.receivable_per_unit, Decimal('100'))

    def test_sold_one_partial_all_preserves_economics_and_no_second_warehouse_deduction(self):
        for kind, product, model in [('cd', self.cd, CDWarehouseStock), ('tech', self.tech, TechWarehouseStock)]:
            stock = self.transfer(kind, 5)
            for amount, remaining in [(2, 3), (2, 1), (1, 0)]:
                response = self.post(stock, kind, 'sold', str(amount), payment_method='cash')
                self.assertEqual(response.status_code, 200, response.content)
                self.assertEqual(response.json()['quantity'], remaining)
                sale = Sale.objects.latest('pk')
                self.assertEqual(sale.total_amount, Decimal(100 * amount))
                self.assertTrue(sale.is_completed)
                self.assertEqual(sale.consignment_platform, self.platform)
                item = (sale.cd_items if kind == 'cd' else sale.tech_items).get()
                self.assertEqual(item.quantity, amount)
                self.assertEqual(item.unit_cost_snapshot, product.cost)
                self.assertEqual(CashTransaction.objects.filter(sale=sale).count(), 1)
                stock.refresh_from_db()
            self.assertEqual(model.objects.get(warehouse=self.source, **{kind: product}).quantity, 95)
            self.assertEqual(response.json()['row_html'], '')
        self.assertEqual(CashRegister.objects.get(warehouse=self.source).balance, Decimal('1000'))

    def test_invalid_quantities_warehouses_and_payment_roll_back(self):
        for kind in ('cd', 'tech'):
            stock = self.transfer(kind, 2)
            for action in ('sold', 'return'):
                for quantity in ('0', '-1', '1.5', '3', '', 'abc'):
                    with self.subTest(kind=kind, action=action, quantity=quantity):
                        self.assertEqual(self.post(stock, kind, action, quantity).status_code, 400)
            self.assertEqual(self.post(stock, kind, warehouse='').status_code, 400)
            self.assertEqual(self.post(stock, kind, warehouse='99999').status_code, 400)
            self.assertEqual(self.post(stock, kind, 'sold', payment_method='cash_postpay').status_code, 400)
            stock.refresh_from_db(); self.assertEqual(stock.quantity, 2)
        self.assertEqual(ConsignmentActionReceipt.objects.count(), 0)
        self.assertEqual(Sale.objects.count(), 0)

    def test_double_submit_same_token_never_repeats_return_or_sale(self):
        for action in ('return', 'sold'):
            stock = self.transfer(quantity=4)
            token = action_token(stock, 'cd', self.user)
            self.assertEqual(self.post(stock, action=action, token=token).status_code, 200)
            self.assertEqual(self.post(stock, action=action, token=token).status_code, 409)
            stock.refresh_from_db()
            self.assertEqual(stock.quantity, 3 if action == 'return' else 6)
        self.assertEqual(Sale.objects.count(), 1)
        self.assertEqual(ConsignmentActionReceipt.objects.count(), 2)

    def test_stale_return_after_other_user_sold(self):
        stock = self.transfer(quantity=2)
        token = action_token(stock, 'cd', self.user)
        record_consignment_sale(actor=self.user, product_type='cd', stock_id=stock.pk, quantity=1, payment_method='bank_account')
        response = self.post(stock, quantity='2', token=token)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['quantity'], 1)
        self.assertIn('data-quantity="1"', response.json()['row_html'])
        self.assertFalse(CDWarehouseStock.objects.filter(warehouse=self.target).exists())

    def test_cash_failure_and_audit_failure_roll_back_receipt_and_stock(self):
        stock = self.transfer(quantity=3)
        CashRegister.objects.filter(warehouse=self.source).delete()
        response = self.post(stock, action='sold', payment_method='cash')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Sale.objects.count(), 0)
        with patch('consignment.services.record_product_changes', side_effect=RuntimeError('audit failure')):
            with self.assertRaises(RuntimeError):
                self.post(stock)
        stock.refresh_from_db(); self.assertEqual(stock.quantity, 3)
        self.assertFalse(ConsignmentActionReceipt.objects.exists())
        self.assertFalse(CDWarehouseStock.objects.filter(warehouse=self.target).exists())

    def test_search_all_fields_multibarcode_and_platform_scope(self):
        cd_stock = self.transfer()
        tech_stock = self.transfer('tech')
        BarcodeRegistry.objects.create(cd=self.cd, value='999000111', product_kind='cd')
        BarcodeRegistry.objects.create(cd=self.cd, value='999000222', product_kind='cd')
        BarcodeRegistry.objects.create(tech=self.tech, value='888000111', product_kind='tech')
        url = reverse('consignment:platform', args=[self.platform.pk])
        for query in ('тестовый', str(self.cd.pk), 'DISC-ABC', 'PPSA-TEST', '999000111', '999000222'):
            response = self.client.get(url, {'search': query})
            self.assertContains(response, f'data-consignment-row="cd-{cd_stock.pk}"')
        response = self.client.get(url, {'search': '888000111'})
        self.assertContains(response, f'data-consignment-row="tech-{tech_stock.pk}"')
        self.assertNotContains(response, f'data-consignment-row="cd-{cd_stock.pk}"')
        self.assertContains(self.client.get(url, {'search': 'missing-product'}), 'Товары не найдены')
        scoped = self.client.get(reverse('consignment:platform', args=[self.other.pk]), {'search': '999000111'})
        self.assertNotContains(scoped, f'data-consignment-row="cd-{cd_stock.pk}"')
        self.assertContains(self.client.get(reverse('consignment:list'), {'search': 'тест'}), 'data-global-barcode-search')

    def test_ui_permissions_confirmation_and_legacy_endpoints(self):
        stock = self.transfer()
        page = self.client.get(reverse('consignment:list'))
        self.assertNotContains(page, '>Снять товар<')
        self.assertContains(page, 'Снять с реализации')
        self.assertContains(page, 'Товар реализован')
        self.assertContains(page, '<option value="">Выберите склад</option>', html=True)
        self.assertRedirects(self.client.get(reverse('consignment:return')), reverse('consignment:list'))
        self.assertEqual(self.client.post(reverse('consignment:return'), {}).status_code, 405)
        self.assertEqual(self.client.get(reverse('consignment:row_action', args=['cd', stock.pk])).status_code, 405)
        self.assertEqual(self.post(stock, confirmed='').status_code, 400)
        csrf_client = Client(enforce_csrf_checks=True); csrf_client.force_login(self.user)
        self.assertEqual(csrf_client.post(reverse('consignment:row_action', args=['cd', stock.pk]), {}).status_code, 403)
        viewer = User.objects.create_user('viewer')
        viewer.user_permissions.add(Permission.objects.get(codename='view_cdconsignmentstock'))
        self.client.force_login(viewer)
        page = self.client.get(reverse('consignment:list'))
        self.assertNotContains(page, 'data-consignment-action=')
        self.assertEqual(self.post(stock).status_code, 403)
        self.assertEqual(self.post(stock, action='sold').status_code, 403)

    def test_query_count_does_not_grow_per_row(self):
        self.transfer()
        url = reverse('consignment:list')
        with CaptureQueriesContext(connection) as before:
            self.client.get(url)
        for index in range(4):
            platform = SalesPlatform.objects.create(name=f'Another {index}')
            self.transfer(platform=platform)
        with CaptureQueriesContext(connection) as after:
            self.client.get(url)
        self.assertEqual(len(before), len(after))


class ConcurrentRowActionsTests(RowFixtures, TransactionTestCase):
    def test_simultaneous_return_and_sale_cannot_both_consume_same_stock(self):
        def run(action):
            close_old_connections()
            try:
                token = action_token(stock, 'cd', self.user)
                barrier.wait(timeout=10)
                perform_row_action(actor=self.user, kind='cd', stock_id=stock.pk, token=token,
                                   action=action, quantity='2', warehouse_id=self.target.pk, payment_method='bank_account')
                return True
            except (ValidationError, IntegrityError, OperationalError):
                return False
            finally:
                close_old_connections()
        for index, actions in enumerate([['return', 'return'], ['sold', 'sold'], ['return', 'sold']], start=1):
            stock = self.transfer(quantity=2)
            barrier = Barrier(2)
            with self.subTest(actions=actions), ThreadPoolExecutor(max_workers=2) as pool:
                result = list(pool.map(run, actions))
            self.assertEqual(sum(result), 1)
            stock.refresh_from_db(); self.assertEqual(stock.quantity, 0)
            self.assertEqual(ConsignmentActionReceipt.objects.count(), index)
