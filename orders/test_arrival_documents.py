"""Отдельные документы рейса, источники строк и запрет раннего проведения."""
from decimal import Decimal
from uuid import uuid4
from django.core.exceptions import ValidationError
from django.test import TestCase
from .test_arrival import ArrivalFixture
from .arrival_documents import create_arrival_sale, create_arrival_supply
from .arrival import reduce_received, unconfirm_arrival
from .operation_changes import ChangesConfirmationRequired
from sales.models import Sale
from sales.services import cancel_sale, advance_order_status, mark_sale_paid
from supplies.models import Supply
from supplies.services import confirm_supply_price_review


class ArrivalDocumentFixture(ArrivalFixture):
    def sale(self, **changes):
        self.arrival.refresh_from_db()
        values = dict(actor=self.user, arrival_id=self.arrival.pk, order_id=self.order.pk,
            expected_revision=self.arrival.revision, warehouse_id=self.warehouse.pk, draft_key=uuid4())
        values.update(changes)
        try:
            return create_arrival_sale(**values)
        except ChangesConfirmationRequired as exc:
            return create_arrival_sale(**values, changes_confirmation=exc.token)

    def supply(self):
        self.arrival.refresh_from_db()
        return create_arrival_supply(actor=self.user, arrival_id=self.arrival.pk, order_id=self.stock_order.pk,
            expected_revision=self.arrival.revision, warehouse_id=self.warehouse.pk)


class ArrivalDocumentTests(ArrivalDocumentFixture, TestCase):
    def test_separate_pending_documents_do_not_change_stock_or_catalog_cost(self):
        self.arrival = self.arrive()
        sale = self.sale()
        supply = self.supply()
        self.assertFalse(sale.is_completed)
        self.assertEqual(supply.status, Supply.Status.WAITING_TRIP_FINALIZATION)
        self.assertEqual(sale.cd_items.get().unit_cost_snapshot, Decimal('2506.01'))
        self.assertEqual(supply.cd_items.get().purchase_unit_cost, Decimal('2506.01'))
        self.assertEqual((Sale.objects.count(), Supply.objects.count()), (1, 1))
        self.no_stock_change()

    def test_same_product_trip_and_warehouse_have_independent_stock_and_cost(self):
        self.arrival = self.arrive()
        row = self.arrival.rows.get(order=self.order)
        sale = self.sale(lines=[{'product_type':'cd', 'product_id':self.cd.pk, 'quantity':10, 'trip_row':str(row.pk)},
            {'product_type':'cd', 'product_id':self.cd.pk, 'quantity':2, 'trip_row':''}])
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 3)
        self.assertEqual(sum(i.quantity for i in sale.cd_items.filter(is_direct_delivery=True)), 10)
        self.assertEqual(sale.cd_items.get(is_direct_delivery=False).unit_cost_snapshot, Decimal('700'))
        cancel_sale(actor=self.user, sale_id=sale.pk, comment='Проверка источников')
        self.no_stock_change()
        self.arrival.refresh_from_db()
        with self.assertRaises(ValidationError):
            unconfirm_arrival(actor=self.user, arrival_id=self.arrival.pk, expected_revision=self.arrival.revision)

    def test_premature_completion_is_rejected_on_backend(self):
        self.arrival = self.arrive()
        sale = self.sale()
        supply = self.supply()
        advance_order_status(actor=self.user, sale_id=sale.pk, next_status='assembled')
        advance_order_status(actor=self.user, sale_id=sale.pk, next_status='delivered')
        with self.assertRaisesMessage(ValidationError, 'финализац'):
            mark_sale_paid(actor=self.user, sale_id=sale.pk)
        with self.assertRaises(ValidationError):
            confirm_supply_price_review(actor=self.user, supply_id=supply.pk)
        supply.status = Supply.Status.ACCEPTED
        with self.assertRaisesMessage(ValidationError, 'финализац'):
            supply.save()
        self.no_stock_change()

    def test_quantity_reduction_updates_every_pending_document_atomically(self):
        self.arrival = self.arrive()
        sale = self.sale()
        supply = self.supply()
        self.arrival.refresh_from_db()
        row = self.arrival.rows.get(order=self.order)
        reduce_received(actor=self.user, arrival_id=self.arrival.pk, order_id=self.order.pk,
            quantities={row.pk:8}, expected_revision=self.arrival.revision)
        self.arrival.refresh_from_db()
        sale.refresh_from_db()
        supply.refresh_from_db()
        self.assertEqual(sale.total_amount, Decimal('28000'))
        self.assertEqual(sum(i.quantity for i in sale.cd_items.all()), 8)
        self.assertEqual(sum(i.unit_cost_snapshot * i.quantity for i in sale.cd_items.all()), Decimal('20208.08'))
        self.assertEqual(supply.grand_total, Decimal('5052.02'))
        self.assertEqual(supply.grand_total + sum(i.unit_cost_snapshot*i.quantity for i in sale.cd_items.all()), self.arrival.control_total)
        self.no_stock_change()
