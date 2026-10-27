"""Прежний worker может писать обычные строки после расширения схемы."""
from uuid import uuid4
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase
from .test_arrival import ArrivalFixture
from sales.models import SaleCDItem


class ArrivalSchemaCompatibilityTests(ArrivalFixture, TestCase):
    def test_previous_sale_item_schema_keeps_database_defaults(self):
        state=MigrationExecutor(connection).loader.project_state([
            ('sales','0032_sale_direct_delivery_sale_procurement_prepaid_amount_and_more')])
        old_sale=state.apps.get_model('sales','Sale')
        old_item=state.apps.get_model('sales','SaleCDItem')
        sale=old_sale.objects.create(warehouse_id=self.warehouse.pk,created_by_id=self.user.pk,
            visible_id='WORKER-'+uuid4().hex[:10],price_type='wholesale',sale_type='wholesale',
            payment_method='cash_postpay',total_amount=100,partner_id=self.partner.pk,partner_name_snapshot=self.partner.name)
        item=old_item.objects.create(sale_id=sale.pk,cd_id=self.cd.pk,quantity=1,unit_price=100,unit_discount=0,
            line_total=100,unit_cost_snapshot=700,product_name_snapshot=self.cd.name,article_snapshot=self.cd.sku)
        current=SaleCDItem.objects.get(pk=item.pk)
        self.assertFalse(current.is_direct_delivery)
        self.assertEqual(current.trip_cost_slot,0)
        self.assertIsNone(current.trip_cost_row_id)
