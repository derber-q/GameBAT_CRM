"""PDF готовится отдельно от печати и хранится до завершения заказа."""
import tempfile
import uuid
from pathlib import Path
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
from accounts.models import User
from warehouse.models import Warehouse
from sales.models import Sale, MarketPrintJob
from sales.market_fulfillment import request_print, process_print_jobs
from sales.test_label_printing import label_pdf
from .models import Integration, OrderMetadata, LabelDocument
from .label_cache import maintain_label_cache
from .documents import process_label


class LabelCacheTests(TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        override=override_settings(MEDIA_ROOT=self.folder.name)
        override.enable(); self.addCleanup(override.disable)
        self.actor=User.objects.create_superuser('label-cache-owner')
        self.warehouse=Warehouse.objects.create(name='Label cache')
        self.integration=Integration.objects.create(business_id=900,campaign_id=901,enabled=True,
            operator=self.actor,fulfillment_warehouse=self.warehouse)
        self.sale=Sale.objects.create(warehouse=self.warehouse,created_by=self.actor,
            price_type='yandex_market',sale_type='yandex_market',payment_method='bank_transfer_postpay')
        self.order=OrderMetadata.objects.create(integration=self.integration,sale=self.sale,order_id=9001,
            status='PROCESSING',substatus='STARTED',items=[{'id':1,'offerId':'test','count':1}])

    def prepared(self):
        document=maintain_label_cache(self.order.pk)
        client=Mock(); client.call.return_value=label_pdf()
        process_label(document.pk,client)
        document.refresh_from_db()
        return document

    def test_import_save_schedules_prefetch_after_commit_without_printing(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.order.save(update_fields=['status'])
        self.assertEqual(LabelDocument.objects.get().format,'A9_HORIZONTALLY')
        self.assertFalse(MarketPrintJob.objects.exists())
        self.assertEqual(maintain_label_cache(self.order.pk).pk,LabelDocument.objects.get().pk)

    def test_changed_boxes_get_fresh_pdf_and_keep_previous_until_completion(self):
        first=self.prepared()
        self.order.boxes=[{'id':7}];self.order.save(update_fields=['boxes'])
        second=maintain_label_cache(self.order.pk)
        self.assertNotEqual(first.pk,second.pk)
        self.assertTrue(Path(first.file.path).is_file())

    def test_print_uses_prepared_pdf_and_never_sets_readiness(self):
        document=self.prepared()
        with patch('sales.market_fulfillment.printer_configuration',return_value='test'):
            job=request_print(order=self.order,actor=self.actor,request_id=uuid.uuid4())
        with patch('sales.market_fulfillment.print_pdf',return_value=77) as printer, \
             patch('sales.market_fulfillment.print_job_completed',return_value=True), \
             patch('sales.market_fulfillment.release_print_job'):
            for _ in range(4):process_print_jobs()
        job.refresh_from_db()
        self.assertEqual(job.document_id,document.pk)
        self.assertEqual(job.state,'done')
        self.assertIsNone(job.ready_job_id)
        printer.assert_called_once()
        self.assertTrue(Path(document.file.path).is_file())

    def test_delivery_cleans_pdf_but_preserves_document_history(self):
        document=self.prepared(); path=Path(document.file.path)
        with self.captureOnCommitCallbacks(execute=True):
            self.order.status='DELIVERED';self.order.save(update_fields=['status'])
        document.refresh_from_db()
        self.assertFalse(path.exists())
        self.assertEqual(document.state,'expired')
        self.assertFalse(document.file)
        client=Mock();process_label(document.pk,client);client.call.assert_not_called()

    def test_terminal_order_waits_for_active_print_before_deleting(self):
        document=self.prepared();path=Path(document.file.path)
        job=MarketPrintJob.objects.create(order=self.order,actor=self.actor,document=document,printer_name='test')
        self.order.status='CANCELLED';self.order.save(update_fields=['status'])
        maintain_label_cache(self.order.pk)
        self.assertTrue(path.exists())
        with self.captureOnCommitCallbacks(execute=True):
            job.state='done';job.save(update_fields=['state'])
        self.assertFalse(path.exists())

    def test_completed_sale_cleans_without_waiting_for_another_api_import(self):
        from catalog.models import CD, Platform
        from sales.models import SaleCDItem
        product=CD.objects.create(name='Cache cancellation',platform=Platform.objects.create(name='PS5'))
        SaleCDItem.objects.create(sale=self.sale,cd=product,quantity=1,unit_price=10,line_total=10,
            unit_cost_snapshot=0,product_name_snapshot=product.name,article_snapshot='cache-test')
        document=self.prepared();path=Path(document.file.path)
        with self.captureOnCommitCallbacks(execute=True):
            from sales.services import cancel_sale
            cancel_sale(actor=self.actor,sale_id=self.sale.pk,comment='test',_market=True)
        self.assertFalse(path.exists())
