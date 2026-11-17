"""Будущие проверки с фиктивным принтером: стикер не проводит и не оплачивает продажу."""
from tempfile import TemporaryDirectory
from unittest.mock import patch
import uuid
import pymupdf
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from warehouse.models import Warehouse
from .models import Sale, SaleLabelPrintJob, PrintAgent
from . import sale_labels, print_agents


class SaleLabelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(username='label-synthetic', password=None)
        self.sale = Sale.objects.create(visible_id='SALE-000594', created_by=self.user, price_type='retail',
            sale_type='retail', payment_method='cash_postpay', warehouse=Warehouse.objects.create(name='Склад стикеров'))
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.enterContext(self.settings(MEDIA_ROOT=folder.name))
        self.enterContext(patch('sales.sale_labels.require_live_operation'))

    def request(self, key=None, target=None):
        with patch('sales.market_fulfillment._printer_target', return_value=target or {'printer_name': 'Fake', 'print_backend': 'native'}):
            return sale_labels.request_label(actor=self.user, sale_id=self.sale.pk, request_id=key or uuid.uuid4(),
                sale_url=f'https://crm.example.invalid/crm/sales/{self.sale.pk}/')

    def test_one_label_has_large_number_and_only_qr_on_58x40(self):
        pdf = sale_labels.render_label('SALE-000594', 'https://crm.example.invalid/crm/sales/594/')
        with pymupdf.open(stream=pdf, filetype='pdf') as document:
            self.assertEqual(len(document), 1)
            page = document[0]
            self.assertAlmostEqual(page.rect.width * 25.4 / 72, 58, places=2)
            self.assertAlmostEqual(page.rect.height * 25.4 / 72, 40, places=2)
            self.assertIn('000594', page.get_text())
            self.assertEqual(len(page.get_images()), 1)
        with self.assertRaises(ValidationError):
            sale_labels.render_label('not-a-sale', 'https://crm.example.invalid/')

    def test_idempotent_print_keeps_sale_and_money_unchanged(self):
        before = Sale.objects.filter(pk=self.sale.pk).values().get()
        key = uuid.uuid4()
        job = self.request(key)
        self.assertEqual(self.request(key).pk, job.pk)
        self.assertEqual(self.request().pk, job.pk)
        self.assertEqual(SaleLabelPrintJob.objects.count(), 1)
        self.assertEqual(Sale.objects.filter(pk=self.sale.pk).values().get(), before)
        self.assertFalse(self.sale.cash_transactions.exists())
        self.assertFalse(self.sale.creditor_movements.exists())
        job.state = 'uncertain'
        job.save(update_fields=['state'])
        self.assertEqual(self.request(key).pk, job.pk)
        self.assertNotEqual(self.request().pk, job.pk)

    def test_scan_uses_exact_visible_id_and_requires_detail_permission(self):
        self.client.force_login(self.user)
        self.assertRedirects(self.client.get(reverse('sales:scan'), {'code': self.sale.visible_id}),
            reverse('sales:detail', args=[self.sale.pk]), fetch_redirect_response=False)
        self.assertRedirects(self.client.get(reverse('sales:scan'), {'sale_id': self.sale.pk}),
            reverse('sales:detail', args=[self.sale.pk]), fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse('sales:scan'), {'code': 'https://other.invalid'}).status_code, 404)
        visitor = get_user_model().objects.create_user(username='label-no-permission')
        self.client.force_login(visitor)
        self.assertEqual(self.client.get(reverse('sales:scan'), {'code': self.sale.visible_id}).status_code, 403)

    def test_existing_agent_protocol_confirms_label_without_sale_status_change(self):
        agent = PrintAgent.objects.create(name='Synthetic', printer_name='Fake', token_hash='1' * 64,
            enabled=True, session=uuid.uuid4(), last_seen_at=timezone.now(), printer_available=True)
        job = self.request(target={'printer_name': 'Fake', 'print_backend': 'agent', 'agent': agent})
        assigned = print_agents.claim(agent.pk, agent.session)['job']
        self.assertEqual(assigned['id'], str(job.request_id))
        payload = {'claim': assigned['claim'], 'sha256': assigned['sha256'], 'state': 'begin'}
        sale_labels.agent_result(agent.pk, agent.session, job.request_id, payload)
        payload.update(state='confirmed', spool_job_id=77)
        sale_labels.agent_result(agent.pk, agent.session, job.request_id, payload)
        job.refresh_from_db()
        self.assertEqual(job.state, 'done')
        self.sale.refresh_from_db()
        self.assertEqual((self.sale.order_status, self.sale.payment_status), ('created', 'unpaid'))
