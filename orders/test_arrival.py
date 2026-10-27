"""Прибытие, сверка и общая финализация фактических затрат рейса."""
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.test import TestCase
from .test_fulfillment import FulfillmentFixture
from .arrival import confirm_arrival, unconfirm_arrival, arrival_preview, reduce_received
from .arrival_models import TripArrival
from .models import SupplierOrderBatch


class ArrivalFixture(FulfillmentFixture):
    def arrive(self, **changes):
        values = dict(actor=self.user, batch_id=self.trip.pk, expected_revision=self.trip.revision,
                      usdt_rub='88.06', usdt_aed='3.66', actual_delivery='1200')
        values.update(changes)
        result = confirm_arrival(**values)
        self.trip.refresh_from_db()
        return result


class TripArrivalTests(ArrivalFixture, TestCase):
    def test_arrival_freezes_sources_and_preserves_original_order(self):
        before = list(self.order.items.values())
        arrival = self.arrive()
        self.assertTrue(arrival.arrived)
        self.assertFalse(arrival.finalized)
        self.assertEqual(sum(arrival.rows.values_list('delivery_total', flat=True)), Decimal('1200'))
        self.assertEqual(arrival.rows.count(), 2)
        self.assertEqual(arrival.control_total, Decimal('30072.12'))
        self.assertEqual(list(self.order.items.values()), before)
        self.no_stock_change()

    def test_missing_weight_rejects_arrival_without_partial_data(self):
        from .test_fulfillment import TripFulfillmentTests
        _, order = TripFulfillmentTests.tech_order(self)
        batch = SupplierOrderBatch.objects.get(pk=order.trip_id)
        with self.assertRaisesMessage(ValidationError, 'вес'):
            self.arrive(batch_id=batch.pk, expected_revision=batch.revision)
        self.assertFalse(TripArrival.objects.exists())

    def test_preview_is_read_only_and_delivery_has_no_lost_kopecks(self):
        preview = arrival_preview(actor=self.user, batch_id=self.trip.pk,
            usdt_rub='88.06', usdt_aed='3.66', actual_delivery='0.01')
        self.assertEqual(sum(row['delivery_total'] for row in preview['rows']), Decimal('.01'))
        self.assertFalse(TripArrival.objects.exists())

    def test_reduction_preserves_original_quantity_and_whole_delivery(self):
        arrival = self.arrive()
        row = arrival.rows.get(order=self.order)
        reduce_received(actor=self.user, arrival_id=arrival.pk, order_id=self.order.pk,
            quantities={row.pk: 8}, expected_revision=arrival.revision)
        row.refresh_from_db()
        arrival.refresh_from_db()
        self.assertEqual((row.original_quantity, row.actual_quantity, row.missing_quantity), (10, 8, 2))
        self.assertEqual(sum(arrival.rows.values_list('delivery_total', flat=True)), Decimal('1200'))
        self.assertEqual(self.order.items.get().quantity, 10)
        self.assertEqual(arrival.control_total, Decimal('25260.10'))

    def test_over_order_and_stale_changes_are_rejected(self):
        arrival = self.arrive()
        row = arrival.rows.get(order=self.order)
        for quantity, revision in ((11, arrival.revision), (9, arrival.revision - 1)):
            with self.subTest(quantity=quantity), self.assertRaises(ValidationError):
                reduce_received(actor=self.user, arrival_id=arrival.pk, order_id=self.order.pk,
                    quantities={row.pk: quantity}, expected_revision=revision)
        row.refresh_from_db()
        self.assertEqual(row.actual_quantity, 10)

    def test_arrival_can_be_unset_before_documents(self):
        arrival = self.arrive()
        unconfirm_arrival(actor=self.user, arrival_id=arrival.pk, expected_revision=arrival.revision)
        arrival.refresh_from_db()
        self.assertFalse(arrival.arrived)
