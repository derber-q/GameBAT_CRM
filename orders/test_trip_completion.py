"""Завершение рейса следует за продажами и приходами без отдельной записи в БД."""
from django.contrib.auth.models import Permission
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from accounts.models import User
from sales.services import advance_order_status, mark_sale_paid, cancel_sale
from supplies.services import confirm_supply_price_review, cancel_supply
from .models import SupplierOrderBatch
from .test_fulfillment import FulfillmentFixture


def complete_trip(fixture):
    sale, supply = fixture.sale(), fixture.supply()
    for status in ('assembled', 'delivered'):
        advance_order_status(actor=fixture.user, sale_id=sale.pk, next_status=status)
    mark_sale_paid(actor=fixture.user, sale_id=sale.pk)
    confirm_supply_price_review(actor=fixture.user, supply_id=supply.pk)
    return sale, supply


class TripCompletionTests(FulfillmentFixture, TestCase):
    def test_all_documents_must_finish_and_cancelling_sale_reopens_trip(self):
        self.assertFalse(self.trip.is_completed)
        sale, supply = self.sale(), self.supply()
        for status in ('assembled', 'delivered'):
            advance_order_status(actor=self.user, sale_id=sale.pk, next_status=status)
        self.assertFalse(self.trip.is_completed)
        confirm_supply_price_review(actor=self.user, supply_id=supply.pk)
        self.assertFalse(self.trip.is_completed)  # Доставка без оплаты ещё не завершает продажу.
        mark_sale_paid(actor=self.user, sale_id=sale.pk)
        self.assertTrue(self.trip.is_completed)
        self.assertEqual(self.trip.completion_label, 'Завершён')

        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse('orders:list'))
        self.assertContains(response, f'data-trip-id="{self.trip.pk}" class="trip-completed"')
        self.assertContains(response, '<span class="badge">Завершён</span>', html=True)
        self.assertFalse(any(query['sql'].lstrip().upper().startswith(('INSERT ', 'UPDATE ', 'DELETE ')) for query in queries))
        batches = list(response.context['batches'])
        with self.assertNumQueries(0):
            self.assertTrue(next(batch for batch in batches if batch.pk == self.trip.pk).is_completed)

        cancel_sale(actor=self.user, sale_id=sale.pk, comment='Отмена продажи рейса')
        self.assertFalse(self.trip.is_completed)
        self.assertEqual(self.trip.completion_label, 'В работе')
        response = self.client.get(reverse('orders:list'))
        self.assertNotContains(response, f'data-trip-id="{self.trip.pk}" class="trip-completed"')

    def test_supply_waiting_for_price_review_blocks_completion_and_cancel_reopens(self):
        sale, supply = self.sale(), self.supply()
        for status in ('assembled', 'delivered'):
            advance_order_status(actor=self.user, sale_id=sale.pk, next_status=status)
        mark_sale_paid(actor=self.user, sale_id=sale.pk)
        self.assertFalse(self.trip.is_completed)
        confirm_supply_price_review(actor=self.user, supply_id=supply.pk)
        self.assertTrue(self.trip.is_completed)
        cancel_supply(actor=self.user, supply_id=supply.pk, comment='Отмена прихода рейса')
        self.assertFalse(self.trip.is_completed)

    def test_empty_trip_and_legacy_source_orders(self):
        complete_trip(self)
        empty = SupplierOrderBatch.objects.create(created_by=self.user, price_list=self.price)
        empty.source_orders.set([self.order, self.stock_order])
        self.assertFalse(empty.is_completed)  # У рейса учитываются текущие заказы, а не старые ссылки.
        legacy = SupplierOrderBatch.objects.create(created_by=self.user)
        self.assertFalse(legacy.is_completed)
        legacy.source_orders.set([self.order, self.stock_order])
        self.assertTrue(legacy.is_completed)
        legacy.source_orders.add(self.make_order('customer', 1))
        self.assertFalse(legacy.is_completed)

    def test_hidden_stock_orders_still_block_completion_for_restricted_viewer(self):
        sale = self.sale()
        for status in ('assembled', 'delivered'):
            advance_order_status(actor=self.user, sale_id=sale.pk, next_status=status)
        mark_sale_paid(actor=self.user, sale_id=sale.pk)
        viewer = User.objects.create_user('trip-completion-viewer')
        viewer.user_permissions.set(Permission.objects.filter(codename__in=(
            'view_orders', 'generate_supplier_orders', 'view_supplier_details')))
        self.client.force_login(viewer)
        response = self.client.get(reverse('orders:list'))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(self.stock_order.pk, [order.pk for order in response.context['orders']])
        batch = next(batch for batch in response.context['batches'] if batch.pk == self.trip.pk)
        self.assertFalse(batch.is_completed)
        self.assertEqual(batch.completion_label, 'В работе')
