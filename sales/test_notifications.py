"""Новые заказы, права и подтверждение без влияния на склад/деньги/статусы."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import time
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import OperationalError, connections
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse

from accounts.models import User
from yandex_market import tests as market_tests
from yandex_market.models import AuditEvent, Integration, OrderMetadata
from yandex_market.orders import import_order
from warehouse.models import Warehouse
from .forms import SaleCreateForm
from .models import MarketOrderAttention, Sale
from .notifications import acknowledge_order
from .services import create_sale


class MarketAttentionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        market_tests.MarketTests.setUpTestData.__func__(cls)

    def setUp(self):
        self.client.force_login(self.user)

    def payload(self, **changes):
        return market_tests.MarketTests.payload(self, **changes)

    def snapshot(self):
        return self.client.get(reverse('sales:market_notifications'))

    def test_new_import_requires_ack_and_repeated_import_never_resets_it(self):
        payload = self.payload()
        order = import_order(self.integration, payload)
        attention = order.staff_attention
        self.assertIsNone(attention.acknowledged_at)
        self.assertEqual(self.snapshot().json()['count'], 1)
        before = self.snapshot().json()['orders'][0]['started_at']
        import_order(self.integration, payload)
        self.assertEqual(MarketOrderAttention.objects.count(), 1)
        self.assertEqual(self.snapshot().json()['orders'][0]['started_at'], before)
        url = reverse('sales:market_acknowledge', args=[attention.pk])
        with patch('yandex_market.client.YandexMarketClient.call', side_effect=AssertionError('API запрещён')):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['count'], 0)
        attention.refresh_from_db()
        stamp = attention.acknowledged_at
        import_order(self.integration, payload)
        self.assertEqual(self.client.post(url).json()['acknowledged_at'], stamp.isoformat())
        attention.refresh_from_db()
        self.assertEqual((attention.acknowledged_at, attention.acknowledged_by_id), (stamp, self.user.pk))
        self.assertEqual(AuditEvent.objects.filter(action='staff_order_acknowledged').count(), 1)

    def test_ack_only_changes_internal_attention(self):
        order = import_order(self.integration, self.payload())
        sale_before = Sale.objects.values().get(pk=order.sale_id)
        order_before = OrderMetadata.objects.values().get(pk=order.pk)
        stock_before = self.stock.__class__.objects.values().get(pk=self.stock.pk)
        with patch('yandex_market.client.YandexMarketClient.call', side_effect=AssertionError('API запрещён')):
            acknowledge_order(actor=self.user, attention_id=order.staff_attention.pk)
        self.assertEqual(Sale.objects.values().get(pk=order.sale_id), sale_before)
        self.assertEqual(OrderMetadata.objects.values().get(pk=order.pk), order_before)
        self.assertEqual(self.stock.__class__.objects.values().get(pk=self.stock.pk), stock_before)

    def test_historical_sale_and_page_views_do_not_become_new(self):
        sale = Sale.objects.create(warehouse=self.warehouse, created_by=self.user,
            price_type='yandex_market', sale_type='yandex_market', payment_method='bank_transfer_postpay')
        OrderMetadata.objects.create(integration=self.integration, sale=sale, order_id=222)
        self.assertEqual(self.snapshot().json()['count'], 0)
        self.client.get(reverse('sales:detail', args=[sale.pk]))
        self.assertFalse(MarketOrderAttention.objects.exists())
        order = import_order(self.integration, self.payload())
        self.client.get(reverse('sales:detail', args=[order.sale_id]))
        self.client.get(reverse('sales:incomplete'))
        self.assertEqual(self.snapshot().json()['count'], 1)

    def test_failed_and_fake_imports_do_not_create_attention(self):
        import_order(self.integration, self.payload(fake=True))
        self.assertFalse(MarketOrderAttention.objects.exists())
        with self.assertRaises(ValidationError):
            import_order(self.integration, self.payload(orderId=124, items=[]))
        self.assertFalse(MarketOrderAttention.objects.exists())

    def test_completion_and_cancellation_do_not_lose_pending_attention(self):
        order = import_order(self.integration, self.payload())
        Sale.objects.filter(pk=order.sale_id).update(order_status='delivered', payment_status='paid')
        self.assertEqual(self.snapshot().json()['count'], 1)
        Sale.objects.filter(pk=order.sale_id).update(cancelled_at=order.last_sync_at,
            cancelled_by=self.user, cancellation_comment='Отмена в тестовом сценарии')
        self.assertEqual(self.snapshot().json()['count'], 1)

    def test_permissions_csrf_and_get_never_acknowledge(self):
        order = import_order(self.integration, self.payload())
        url = reverse('sales:market_acknowledge', args=[order.staff_attention.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(Client(enforce_csrf_checks=True).post(url).status_code, 403)
        self.client.force_login(self.worker)
        self.assertEqual(self.snapshot().status_code, 403)
        self.assertEqual(self.client.post(url).status_code, 403)
        self.worker.user_permissions.add(Permission.objects.get(content_type__app_label='sales', codename='view_sales'))
        self.assertEqual(self.snapshot().status_code, 200)
        self.assertEqual(self.client.post(url).status_code, 403)
        self.assertIsNone(MarketOrderAttention.objects.get().acknowledged_at)

    def test_manual_market_type_and_price_are_rejected_but_import_is_kept(self):
        for field in ('sale_type', 'price_type'):
            choices = dict(SaleCreateForm().fields[field].choices)
            self.assertNotIn('yandex_market', choices)
        for sale_type, price_type in [('yandex_market', 'retail'), ('retail', 'yandex_market')]:
            with self.subTest(sale_type=sale_type), self.assertRaisesMessage(ValidationError, 'автоматическую интеграцию'):
                create_sale(actor=self.user, warehouse_id=self.warehouse.pk, sale_type=sale_type,
                    price_type=price_type, payment_method='bank_transfer_postpay', lines=[], partner_name='Тестовый заказчик' if sale_type == 'wholesale' else '')
            response = self.client.post(reverse('sales:create'), {
                'warehouse': self.warehouse.pk, 'sale_type': sale_type, 'price_type': price_type,
                'payment_method': 'bank_transfer_postpay', '_market': '1', 'automatic': 'true',
            })
            self.assertEqual(response.status_code, 200)
            self.assertFalse(Sale.objects.exists())
        order = import_order(self.integration, self.payload())
        self.assertEqual(order.sale.sale_type, 'yandex_market')
        self.assertEqual(order.sale.price_type, 'yandex_market')

    def test_ack_one_of_three_preserves_remaining_orders_and_start_times(self):
        orders = [import_order(self.integration, self.payload(orderId=number)) for number in (101, 102, 103)]
        snapshot = self.snapshot().json()
        self.assertEqual(snapshot['count'], 3)
        starts = {row['id']: row['started_at'] for row in snapshot['orders']}
        attention = orders[1].staff_attention
        self.client.post(reverse('sales:market_acknowledge', args=[attention.pk]))
        remaining = self.snapshot().json()
        self.assertEqual(remaining['count'], 2)
        self.assertEqual({row['order_id'] for row in remaining['orders']}, {'101', '103'})
        self.assertTrue(all(starts[row['id']] == row['started_at'] for row in remaining['orders']))


class AttentionConcurrencyTests(TransactionTestCase):
    def test_first_employee_and_timestamp_are_preserved(self):
        users = [User.objects.create_superuser(f'ack-worker-{i}') for i in range(2)]
        warehouse = Warehouse.objects.create(name='Подтверждение заказов')
        sale = Sale.objects.create(warehouse=warehouse, sale_type='yandex_market', price_type='yandex_market')
        integration = Integration.objects.create(business_id=1, campaign_id=2,
            fulfillment_warehouse=warehouse, operator=users[0])
        order = OrderMetadata.objects.create(integration=integration, order_id=1, sale=sale)
        attention = MarketOrderAttention.objects.create(order=order)
        barrier = Barrier(2)
        def submit(pk):
            try:
                actor = User.objects.get(pk=pk)
                barrier.wait(timeout=10)
                for attempt in range(10):
                    try:
                        record = acknowledge_order(actor=actor, attention_id=attention.pk)
                        return record.acknowledged_at, record.acknowledged_by_id
                    except OperationalError:
                        if attempt == 9:
                            raise
                        time.sleep(.05)
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(submit, [user.pk for user in users]))
        self.assertEqual(results[0], results[1])
        self.assertEqual(AuditEvent.objects.filter(action='staff_order_acknowledged').count(), 1)
