"""Навигация по журналу не меняет деньги и сохраняет ограничения доступа."""
import uuid
from decimal import Decimal

from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from partners.models import Partner
from sales.models import Sale
from warehouse.models import Warehouse
from .models import CreditorTransaction
from .prepayments import fund_prepayment
from .services import adjust_creditor_debt


class CreditorOperationLinksTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_superuser('history-admin', password='History!123')
        self.reader = User.objects.create_user('history-reader', password='History!123')
        self.warehouse = Warehouse.objects.create(name='Склад истории')
        self.partner = Partner.objects.create(name='Партнёр истории')
        self.creditor = self.partner.creditor
        self.operation = adjust_creditor_debt(actor=self.actor, creditor_id=self.creditor.pk,
            warehouse_id=self.warehouse.pk, new_debt='-100', money_source_type='offset', comment='Аванс')
        self.url = reverse('creditors:operation', args=[self.operation.pk])

    def grant(self, *codes):
        self.reader.user_permissions.add(*Permission.objects.filter(codename__in=codes))
        self.client.force_login(self.reader)

    def test_direct_detail_requires_both_history_permissions_and_is_read_only(self):
        self.grant('view_creditors')
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.grant('view_history')
        before = CreditorTransaction.objects.count()
        self.assertContains(self.client.get(self.url), 'Аванс')
        self.assertEqual(self.client.post(self.url, {'new_debt': 0}).status_code, 405)
        self.assertEqual(CreditorTransaction.objects.count(), before)
        self.creditor.refresh_from_db()
        self.assertEqual(self.creditor.current_debt, Decimal('-100'))
        self.assertEqual(self.client.get(reverse('creditors:operation', args=[999999])).status_code, 404)

    def test_sale_link_requires_sale_permission(self):
        sale = Sale.objects.create(warehouse=self.warehouse, created_by=self.actor,
            price_type='wholesale', sale_type='wholesale', payment_method='partner_debt', partner=self.partner)
        self.operation.sale = sale
        self.operation.save(update_fields=['sale'])
        self.grant('view_creditors', 'view_history')
        sale_url = reverse('sales:detail', args=[sale.pk])
        for url in (self.url, reverse('creditors:detail', args=[self.creditor.pk])):
            response = self.client.get(url)
            self.assertContains(response, sale.visible_id)
            self.assertNotContains(response, f'href="{sale_url}"')
        self.grant('view_sale_detail')
        for url in (self.url, reverse('creditors:detail', args=[self.creditor.pk])):
            self.assertContains(self.client.get(url), f'href="{sale_url}"')

    def test_transfer_links_both_ledgers(self):
        entry = fund_prepayment(actor=self.actor, creditor_id=self.creditor.pk,
            warehouse_id=self.warehouse.pk, amount='50', transfer=True, operation_key=uuid.uuid4())
        debt_url = reverse('creditors:operation', args=[entry.debt_transaction_id])
        prepay_url = reverse('creditors:prepayment_operation', args=[entry.pk])
        self.grant('view_creditors', 'view_history')
        self.assertContains(self.client.get(debt_url), f'href="{prepay_url}"')
        self.assertContains(self.client.get(prepay_url), f'href="{debt_url}"')
        self.assertContains(self.client.get(reverse('creditors:detail', args=[self.creditor.pk])),
                            f'href="{prepay_url}"')

    def test_cash_details_follow_cash_and_safe_permissions(self):
        entry = fund_prepayment(actor=self.actor, creditor_id=self.creditor.pk,
            warehouse_id=self.warehouse.pk, amount='25', money_source_type='safe', operation_key=uuid.uuid4())
        url = reverse('creditors:prepayment_operation', args=[entry.pk])
        self.grant('view_creditors', 'view_history')
        self.assertNotContains(self.client.get(url), 'id="cash-operation"')
        self.grant('view_cash_history')
        self.assertNotContains(self.client.get(url), 'id="cash-operation"')
        self.grant('view_safe')
        self.assertContains(self.client.get(url), 'id="cash-operation"')
