"""Стикер и разрешённые действия Маркета доступны из продажи без ручной подмены статусов."""
from unittest.mock import patch, Mock
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile

from django.contrib.auth.models import Permission
from django.test import TestCase, Client
from django.test.utils import CaptureQueriesContext
from django.db import connection, OperationalError
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from warehouse.models import Warehouse
from yandex_market.models import Integration, OrderMetadata, LabelDocument, SyncJob, AuditEvent
from .models import Sale, MarketPrintJob


class MarketSaleControlsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_superuser('market-sales-owner')
        cls.warehouse = Warehouse.objects.create(name='Склад Маркета')
        cls.integration = Integration.objects.create(business_id=100, campaign_id=200, enabled=True,
            fulfillment_warehouse=cls.warehouse, operator=cls.owner)
        cls.sale = Sale.objects.create(warehouse=cls.warehouse, created_by=cls.owner, price_type='yandex_market',
            sale_type='yandex_market', payment_method='bank_transfer_postpay', total_amount=100)
        cls.order = OrderMetadata.objects.create(integration=cls.integration, sale=cls.sale, order_id=123,
            status='PROCESSING', substatus='STARTED', boxes=[{'items': [{'id': 789, 'fullCount': 1}]}],
            items=[{'id': 789, 'offerName': 'Игра', 'count': 1}])
        MarketPrintJob.objects.create(order=cls.order, actor=cls.owner, printer_name='Test printer',
            state='done', printed_at=timezone.now(), printer_job_id=1)

    def setUp(self):
        self.client.force_login(self.owner)

    def action(self, **changes):
        data = {'action': 'ready', 'market_status': 'PROCESSING',
                'market_substatus': 'STARTED', 'return_to': 'list'}
        data.update(changes)
        return self.client.post(reverse('sales:market_action', args=[self.sale.pk]), data)

    def test_list_and_detail_show_market_status_actions_and_label(self):
        for name, args in [('incomplete', []), ('detail', [self.sale.pk])]:
            response = self.client.get(reverse('sales:' + name, args=args))
            self.assertContains(response, 'Напечатать стикер Яндекса')
            self.assertNotContains(response, 'Получить официальный PDF стикера')
            self.assertNotContains(response, 'name="format"')
            self.assertContains(response, 'data-market-print')
            self.assertContains(response, 'Готов к отгрузке')
            self.assertContains(response, 'Отменить заказ')
            self.assertContains(response, 'data-market-action="ready"')
            self.assertContains(response, 'data-market-action="cancel"')
            self.assertNotContains(response, 'name="action" required')
            self.assertNotContains(response, 'Действия Маркета')
            self.assertNotContains(response, 'Подтверждаю выбранное действие в Маркете')
            self.assertNotContains(response, '<strong>В обработке</strong>')
            self.assertNotContains(response, 'Яндекс Маркет №123')
            self.assertNotContains(response, 'PROCESSING / STARTED')
            self.assertNotContains(response, 'Заказ и коробки Маркета')
            self.assertContains(response, reverse('sales:market_action', args=[self.sale.pk]))
            self.assertContains(response, reverse('sales:market_print', args=[self.sale.pk]))
            self.assertNotContains(response, 'data-status-field="order"')

    def test_market_action_queues_and_audits_without_local_status_or_money_change(self):
        before = Sale.objects.values().get(pk=self.sale.pk)
        with patch('yandex_market.client.YandexMarketClient.call', side_effect=AssertionError('Внешний API нельзя вызывать из POST')):
            response = self.action()
        self.assertRedirects(response, reverse('sales:incomplete'), fetch_redirect_response=False)
        job = SyncJob.objects.get(kind='order_action')
        self.assertEqual(job.payload, {'order_id': 123, 'action': 'ready'})
        self.assertEqual(job.actor_id, self.owner.pk)
        self.assertTrue(AuditEvent.objects.filter(action='order_action', actor=self.owner).exists())
        self.assertEqual(Sale.objects.values().get(pk=self.sale.pk), before)
        self.order.refresh_from_db()
        self.assertEqual((self.order.status, self.order.substatus), ('PROCESSING', 'STARTED'))

    def test_stale_forbidden_unconfirmed_cancellation_and_unpacked_actions_do_not_queue(self):
        for changes in [{'action': 'cancel'}, {'action': 'delivered'}, {'market_substatus': 'READY_TO_SHIP'}]:
            self.action(**changes)
            self.assertFalse(SyncJob.objects.exists())
        self.order.boxes = []
        self.order.save(update_fields=['boxes'])
        self.action()
        self.assertFalse(SyncJob.objects.exists())
        page = self.client.get(reverse('sales:incomplete'))
        self.assertNotContains(page, 'value="ready"')
        self.assertContains(page, 'Укажите коробки')
        self.integration.enabled = False
        self.integration.save(update_fields=['enabled'])
        self.action(action='cancel', confirm='yes')
        self.assertFalse(SyncJob.objects.exists())

    def test_label_is_scoped_to_sale_and_reuses_pending_request(self):
        url = reverse('sales:market_label', args=[self.sale.pk])
        data = {'format': 'A7', 'orders': '99999', 'integration': '99999'}
        for _ in range(2):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(url, data)
        document = LabelDocument.objects.get()
        self.assertEqual((document.order_id, document.integration_id, document.format, document.created_by_id),
                         (self.order.pk, self.integration.pk, 'A9_HORIZONTALLY', self.owner.pk))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['state'], 'pending')
        self.assertEqual(response.json()['status_url'], reverse('sales:market_label_status', args=[self.sale.pk, document.pk]))
        self.assertEqual(SyncJob.objects.filter(kind='label').count(), 1)
        page = self.client.get(reverse('sales:detail', args=[self.sale.pk]))
        self.assertContains(page, 'Напечатать стикер Яндекса')
        label_page = self.client.get(reverse('yandex_market:label', args=[document.pk]))
        self.assertContains(label_page, reverse('sales:detail', args=[self.sale.pk]))

    def test_permissions_csrf_and_get_are_enforced(self):
        viewer = User.objects.create_user('market-sale-viewer')
        viewer.user_permissions.add(Permission.objects.get(codename='view_sales'))
        self.client.force_login(viewer)
        response = self.client.get(reverse('sales:incomplete'))
        self.assertNotContains(response, reverse('sales:market_action', args=[self.sale.pk]))
        self.assertNotContains(response, reverse('sales:market_print', args=[self.sale.pk]))
        self.assertContains(response, 'data-market-order=')
        self.assertEqual(self.action().status_code, 403)
        self.assertEqual(self.client.post(reverse('sales:market_label', args=[self.sale.pk]), {'confirm': 'yes'}).status_code, 403)
        viewer.user_permissions.add(Permission.objects.get(codename='manage_orders', content_type__app_label='yandex_market'))
        self.assertEqual(self.client.get(reverse('sales:market_action', args=[self.sale.pk])).status_code, 405)
        self.assertEqual(self.action().status_code, 302)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.owner)
        self.assertEqual(csrf.post(reverse('sales:market_action', args=[self.sale.pk]), {'confirm': 'yes'}).status_code, 403)
        self.assertEqual(csrf.post(reverse('sales:market_label', args=[self.sale.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse('sales:market_label', args=[self.sale.pk])).status_code, 405)

    def test_labels_and_market_orders_do_not_add_query_per_sale(self):
        url = reverse('sales:incomplete')
        with CaptureQueriesContext(connection) as single:
            self.client.get(url)
        for number in range(5):
            sale = Sale.objects.create(warehouse=self.warehouse, price_type='yandex_market', sale_type='yandex_market', payment_method='bank_transfer_postpay')
            order = OrderMetadata.objects.create(integration=self.integration, sale=sale, order_id=200 + number, status='DELIVERY')
            LabelDocument.objects.create(integration=self.integration, order=order, created_by=self.owner)
        with CaptureQueriesContext(connection) as many:
            response = self.client.get(url)
        self.assertContains(response, 'data-market-order=', count=6)
        self.assertEqual(len(single), len(many))

    def test_worker_rechecks_remote_status_before_cancel_and_does_not_repeat_ready(self):
        from yandex_market.tasks import process

        self.action()
        job = SyncJob.objects.get(kind='order_action')
        client = Mock()
        self.order.substatus = 'READY_TO_SHIP'
        with patch('yandex_market.tasks.YandexMarketClient', return_value=client), patch('yandex_market.tasks.import_order', return_value=self.order):
            process(job)
        client.call.assert_not_called()
        self.order.status, self.order.substatus = 'DELIVERY', ''
        job.payload = {'order_id': 123, 'action': 'cancel'}
        with patch('yandex_market.tasks.YandexMarketClient', return_value=client), patch('yandex_market.tasks.import_order', return_value=self.order):
            with self.assertRaises(ValidationError):
                process(job)
        client.call.assert_not_called()

    def test_cancel_and_refresh_use_existing_queue_and_ignore_redirect_url(self):
        self.action(action='cancel', confirm='yes', return_to='https://example.com/')
        self.assertEqual(SyncJob.objects.get(kind='order_action').payload, {'order_id': 123, 'action': 'cancel'})
        response = self.action(action='refresh', market_status='OLD', market_substatus='OLD')
        self.assertRedirects(response, reverse('sales:incomplete'), fetch_redirect_response=False)
        self.assertEqual(SyncJob.objects.get(kind='order').payload, {'order_id': 123})

    def test_only_cancellation_requires_confirmation_and_tracks_its_actor(self):
        self.action(action='cancel')
        self.assertFalse(SyncJob.objects.exists())
        self.assertFalse(AuditEvent.objects.filter(action='order_action').exists())
        response = self.action(action='cancel', confirm='yes')
        self.assertRedirects(response, reverse('sales:incomplete'), fetch_redirect_response=False)
        self.assertEqual(SyncJob.objects.get(kind='order_action').payload, {'order_id': 123, 'action': 'cancel'})
        self.assertTrue(AuditEvent.objects.filter(action='order_action', actor=self.owner).exists())

    def test_ready_and_cancel_buttons_follow_market_status(self):
        self.order.substatus = 'READY_TO_SHIP'
        self.order.save(update_fields=['substatus'])
        response = self.client.get(reverse('sales:detail', args=[self.sale.pk]))
        self.assertNotContains(response, 'data-market-action="ready"')
        self.assertContains(response, 'data-market-action="cancel"')
        self.order.status = 'DELIVERY'
        self.order.substatus = ''
        self.order.save(update_fields=['status', 'substatus'])
        response = self.client.get(reverse('sales:detail', args=[self.sale.pk]))
        self.assertNotContains(response, 'data-market-action="ready"')
        self.assertNotContains(response, 'data-market-action="cancel"')

    def test_ready_is_blocked_until_windows_confirms_printing(self):
        MarketPrintJob.objects.filter(order=self.order).delete()
        self.action()
        self.assertFalse(SyncJob.objects.exists())
        job = MarketPrintJob.objects.create(order=self.order, actor=self.owner, printer_name='test',
            state='spooled', printer_job_id=55, spooled_at=timezone.now())
        self.action()
        self.assertFalse(SyncJob.objects.exists())
        job.printed_at = timezone.now()
        job.save(update_fields=['printed_at'])
        self.action()
        self.assertTrue(SyncJob.objects.filter(kind='order_action').exists())

    def test_fake_terminal_order_and_unknown_sale_cannot_queue(self):
        self.order.fake = True
        self.order.save(update_fields=['fake'])
        self.action()
        self.assertFalse(SyncJob.objects.exists())
        self.client.post(reverse('sales:market_label', args=[self.sale.pk]), {'confirm': 'yes'})
        self.assertFalse(LabelDocument.objects.exists())
        self.order.fake = False
        self.order.status = 'DELIVERY'
        self.order.substatus = ''
        self.order.save(update_fields=['fake', 'status', 'substatus'])
        self.action(action='cancel', confirm='yes', market_status='DELIVERY', market_substatus='')
        self.assertFalse(SyncJob.objects.exists())
        self.assertEqual(self.client.post(reverse('sales:market_action', args=[99999]), {'confirm': 'yes'}).status_code, 404)

    def test_label_validation_and_error_retry(self):
        url = reverse('sales:market_label', args=[self.sale.pk])
        failed = LabelDocument.objects.create(integration=self.integration, order=self.order, created_by=self.owner,
            format='A9_HORIZONTALLY', state='error', last_error='Ошибка тестового API')
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(LabelDocument.objects.count(), 2)
        failed.refresh_from_db()
        self.assertEqual(failed.state, 'error')
        self.assertEqual(SyncJob.objects.filter(kind='label').count(), 1)

    def test_label_status_is_readonly_scoped_and_requires_print_permission(self):
        document = LabelDocument.objects.create(integration=self.integration, order=self.order, created_by=self.owner,
            format='A9_HORIZONTALLY', state='error', last_error='Маркет не сформировал стикер')
        url = reverse('sales:market_label_status', args=[self.sale.pk, document.pk])
        response = self.client.get(url)
        self.assertEqual(response.json()['error'], document.last_error)
        self.assertEqual(response.json()['state'], 'error')
        self.assertIn('no-store', response.headers['Cache-Control'])
        self.assertFalse(SyncJob.objects.exists())
        self.assertEqual(self.client.post(url).status_code, 405)
        self.assertEqual(self.client.get(reverse('sales:market_label_status', args=[self.sale.pk, 99999])).status_code, 404)
        other = Sale.objects.create(warehouse=self.warehouse, price_type='yandex_market')
        self.assertEqual(self.client.get(reverse('sales:market_label_status', args=[other.pk, document.pk])).status_code, 404)
        viewer = User.objects.create_user('label-status-viewer')
        viewer.user_permissions.add(Permission.objects.get(codename='view_sales'))
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_ready_58x40_label_is_reused_and_other_formats_are_not_printed(self):
        from tempfile import TemporaryDirectory
        from django.test import override_settings
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            old = LabelDocument.objects.create(integration=self.integration, order=self.order,
                created_by=self.owner, format='A7', state='done', file='old.pdf')
            url = reverse('sales:market_label', args=[self.sale.pk])
            response = self.client.post(url)
            document = LabelDocument.objects.exclude(pk=old.pk).get()
            self.assertEqual(document.format, 'A9_HORIZONTALLY')
            self.assertNotIn('file_url', response.json())
            document.file.save('label.pdf', ContentFile(b'%PDF-1.4\n%%EOF'), save=False)
            document.state = 'done'
            document.save(update_fields=['file', 'state'])
            response = self.client.post(url)
            self.assertEqual(response.json()['file_url'], reverse('yandex_market:label_file', args=[document.pk]))
            self.assertEqual(LabelDocument.objects.count(), 2)
            self.assertEqual(SyncJob.objects.filter(kind='label').count(), 1)
            polled = self.client.get(response.json()['status_url'])
            self.assertEqual(polled.json()['file_url'], response.json()['file_url'])

    def test_pending_and_failed_requests_are_visible_without_inventing_new_status(self):
        self.action()
        page = self.client.get(reverse('sales:incomplete'))
        self.assertContains(page, 'Запрос в Маркет обрабатывается')
        job = SyncJob.objects.get(kind='order_action')
        job.state, job.last_error = 'error', 'Тестовая ошибка Маркета'
        job.save(update_fields=['state', 'last_error'])
        page = self.client.get(reverse('sales:detail', args=[self.sale.pk]))
        self.assertContains(page, 'Тестовая ошибка Маркета')
        self.assertContains(page, 'data-market-order=')

    def test_label_and_queue_are_created_atomically(self):
        with patch('yandex_market.queue.enqueue', side_effect=OperationalError('database is locked')):
            with self.captureOnCommitCallbacks(execute=True):
                self.client.post(reverse('sales:market_label', args=[self.sale.pk]), {'confirm': 'yes', 'format': 'A7'})
        self.assertFalse(LabelDocument.objects.exists())
        self.assertFalse(SyncJob.objects.exists())
