import tempfile
import uuid
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.test import Client
from django.contrib.auth.models import Permission
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from catalog.models import CD, Platform, BarcodeRegistry
from warehouse.models import Warehouse
from yandex_market.models import Integration, OrderMetadata, OrderLine, OfferConnection, RemoteOffer, SyncJob
from sales.models import Sale, SaleCDItem, MarketPicking, MarketPrintJob, MarketScanEvent
from sales.market_fulfillment import record_scan, process_print_jobs
from sales.test_label_printing import label_pdf


class MarketScanningTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor = User.objects.create_superuser('scan-owner')
        cls.warehouse = Warehouse.objects.create(name='Scan warehouse')
        cls.integration = Integration.objects.create(business_id=100, campaign_id=200, enabled=True,
            fulfillment_warehouse=cls.warehouse, operator=cls.actor)
        cls.platform = Platform.objects.create(name='PS5')
        cls.products = [CD.objects.create(name='Scan game ' + str(i), platform=cls.platform) for i in range(2)]
        cls.barcodes = ['0000000012345', '0000000054321']
        cls.connections = []
        for i, product in enumerate(cls.products):
            BarcodeRegistry.objects.create(value=cls.barcodes[i], cd=product, product_kind='cd')
            remote = RemoteOffer.objects.create(integration=cls.integration, offer_id=str(i))
            cls.connections.append(OfferConnection.objects.create(integration=cls.integration, cd=product, remote_offer=remote))

    def make_order(self, number=123, counts=(1, 1), age=0):
        sale = Sale.objects.create(warehouse=self.warehouse, created_by=self.actor, price_type='yandex_market',
            sale_type='yandex_market', payment_method='bank_transfer_postpay')
        order = OrderMetadata.objects.create(integration=self.integration, sale=sale, order_id=number,
            status='PROCESSING', substatus='STARTED', created_remote_at=timezone.now() - timedelta(days=age),
            items=[{'id': i + 1, 'count': count} for i, count in enumerate(counts) if count])
        for i, count in enumerate(counts):
            if count:
                OrderLine.objects.create(order=order, connection=self.connections[i], remote_item_id=i + 1, quantity=count, unit_price=10)
                SaleCDItem.objects.create(sale=sale, cd=self.products[i], quantity=count, unit_price=10,
                    line_total=10 * count, unit_cost_snapshot=1, product_name_snapshot=self.products[i].name, article_snapshot='x')
        return order

    def scan(self, index=0, request_id=None):
        with patch('sales.market_fulfillment.printer_configuration', return_value='Test printer'):
            return record_scan(actor=self.actor, barcode=self.barcodes[index], request_id=request_id or uuid.uuid4())

    def test_oldest_order_full_composition_alternate_barcode_and_idempotency(self):
        newer = self.make_order(200, age=0)
        oldest = self.make_order(300, counts=(2, 1), age=2)
        key = uuid.uuid4()
        first = self.scan(request_id=key)
        self.assertEqual(first['order_id'], oldest.order_id)
        self.assertEqual(first['scanned'], 1)
        self.assertEqual(self.scan(request_id=key), first)
        self.assertEqual(MarketScanEvent.objects.count(), 1)
        self.assertFalse(MarketPrintJob.objects.exists())
        BarcodeRegistry.objects.create(value='0000999999999', cd=self.products[0], product_kind='cd')
        with patch('sales.market_fulfillment.printer_configuration', return_value='Test printer'):
            record_scan(actor=self.actor, barcode='0000999999999', request_id=uuid.uuid4())
        self.assertFalse(MarketPrintJob.objects.exists())
        done = self.scan(index=1)
        self.assertTrue(done['complete'])
        self.assertEqual(MarketPrintJob.objects.get().order_id, oldest.pk)
        self.assertEqual(self.scan()['order_id'], newer.order_id)

    def test_unknown_changed_completed_and_fake_orders_do_not_trigger_work(self):
        order = self.make_order(counts=(1, 0))
        order.fake = True
        order.save(update_fields=['fake'])
        with self.assertRaises(ValidationError):
            self.scan()
        self.assertFalse(MarketPrintJob.objects.exists())
        self.assertFalse(MarketScanEvent.objects.exists())
        order.fake = False
        order.save(update_fields=['fake'])
        self.scan()
        with self.assertRaises(ValidationError):
            self.scan()
        self.assertEqual(MarketPrintJob.objects.count(), 1)

    def test_scan_endpoint_permissions_csrf_uuid_and_same_request(self):
        order = self.make_order(counts=(2, 0))
        self.client.force_login(self.actor)
        url = reverse('sales:market_scan')
        data = {'barcode': self.barcodes[0], 'request_id': str(uuid.uuid4())}
        with patch('sales.market_fulfillment.printer_configuration', return_value='test'):
            first = self.client.post(url, data)
            again = self.client.post(url, data)
            self.assertEqual(first.json(), again.json())
            self.assertEqual(first.json()['scanned'], 1)
            self.assertEqual(self.client.post(url, {**data, 'request_id': 'bad'}).status_code, 400)
        self.assertEqual(MarketScanEvent.objects.count(), 1)
        self.assertEqual(self.client.get(url).status_code, 405)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.actor)
        self.assertEqual(csrf.post(url, data).status_code, 403)
        viewer = User.objects.create_user('scan-viewer')
        viewer.user_permissions.add(Permission.objects.get(codename='view_sales'))
        self.client.force_login(viewer)
        self.assertEqual(self.client.post(url, data).status_code, 403)

    def test_failed_or_unknown_print_never_queues_ready(self):
        order = self.make_order(counts=(1, 0))
        self.scan()
        job = MarketPrintJob.objects.get()
        job.state, job.printer_job_id, job.spooled_at = 'spooled', 999, timezone.now()
        from yandex_market.models import LabelDocument
        job.document = LabelDocument.objects.create(integration=self.integration, order=order, created_by=self.actor,
            format='A9_HORIZONTALLY', state='done', file='test.pdf')
        job.refresh_job = SyncJob.objects.create(key='test-refresh', kind='order', integration=self.integration,
            state='done', payload={'order_id': order.order_id})
        order.boxes = [{'id': 1}]
        order.save(update_fields=['boxes'])
        job.save()
        with patch('sales.market_fulfillment.print_job_completed', side_effect=ValidationError('Printer error')), \
                patch('sales.market_fulfillment.print_pdf') as printer:
            process_print_jobs()
            process_print_jobs()
        job.refresh_from_db()
        self.assertEqual(job.state, 'uncertain')
        self.assertIsNone(job.printed_at)
        self.assertIsNone(job.ready_job_id)
        printer.assert_not_called()

    def test_stale_printing_is_never_automatically_printed_again(self):
        order = self.make_order(counts=(1, 0))
        self.scan()
        job = MarketPrintJob.objects.get()
        job.state, job.lease, job.leased_at = 'printing', uuid.uuid4(), timezone.now() - timedelta(minutes=4)
        job.save()
        with patch('sales.market_fulfillment.print_pdf') as printer:
            process_print_jobs()
        printer.assert_not_called()
        job.refresh_from_db()
        self.assertEqual(job.state, 'uncertain')
        self.assertIsNone(job.ready_job_id)

    def test_manual_print_is_idempotent_and_never_requests_readiness(self):
        order = self.make_order(counts=(1, 0))
        self.client.force_login(self.actor)
        url = reverse('sales:market_print', args=[order.sale_id])
        data = {'request_id': str(uuid.uuid4()), 'printer_name': 'Injected printer'}
        with patch('sales.market_fulfillment.printer_configuration', return_value='Configured printer'):
            first = self.client.post(url, data)
            again = self.client.post(url, data)
        self.assertEqual(first.json(), again.json())
        job = MarketPrintJob.objects.get()
        self.assertEqual(job.printer_name, 'Configured printer')
        self.assertFalse(job.ready_after_print)
        self.assertFalse(SyncJob.objects.exists())

    def test_workflow_waits_for_boxes_pdf_and_spooling_before_ready_and_never_reprints(self):
        order = self.make_order(counts=(1, 0))
        self.scan()
        job = MarketPrintJob.objects.get()
        process_print_jobs()
        job.refresh_from_db()
        self.assertIsNotNone(job.refresh_job_id)
        job.refresh_job.state = 'done'
        job.refresh_job.save(update_fields=['state'])
        process_print_jobs()
        job.refresh_from_db()
        self.assertEqual(job.boxes_job.payload['boxes'], [{'items': [{'id': 1, 'fullCount': 1}]}])
        order.boxes = [{'id': 9}]
        order.save(update_fields=['boxes'])
        job.boxes_job.state = 'done'
        job.boxes_job.save(update_fields=['state'])
        process_print_jobs()
        job.refresh_from_db()
        self.assertEqual(job.document.format, 'A9_HORIZONTALLY')
        with patch('sales.market_fulfillment.print_pdf', return_value=88) as printer, \
                patch('sales.market_fulfillment.print_job_completed', return_value=False) as completed, \
                patch('sales.market_fulfillment.release_print_job'):
            process_print_jobs()
            printer.assert_not_called()
            with tempfile.TemporaryDirectory() as folder, override_settings(MEDIA_ROOT=folder):
                job.document.file.save('label.pdf', ContentFile(label_pdf()), save=False)
                job.document.state = 'done'
                job.document.save(update_fields=['state', 'file'])
                process_print_jobs()
                job.refresh_from_db()
                self.assertIsNone(job.printed_at)
                self.assertEqual(job.printer_job_id, 88)
                self.assertIsNone(job.ready_job_id)
                process_print_jobs()
                job.refresh_from_db()
                self.assertIsNone(job.ready_job_id)
                self.assertIsNone(job.printed_at)
                completed.return_value = True
                process_print_jobs()
                job.refresh_from_db()
                self.assertIsNotNone(job.printed_at)
                self.assertIsNone(job.ready_job_id)
                process_print_jobs()
                job.refresh_from_db()
                self.assertEqual(job.ready_job.payload['action'], 'ready')
                order.substatus = 'READY_TO_SHIP'
                order.save(update_fields=['substatus'])
                job.ready_job.state = 'done'
                job.ready_job.save(update_fields=['state'])
                process_print_jobs()
                process_print_jobs()
                self.assertEqual(printer.call_count, 1)
                job.refresh_from_db()
                self.assertEqual(job.state, 'done')
