"""Возврат уменьшенных количеств при отмене связанных документов рейса."""
from decimal import Decimal
from uuid import uuid4

from django.test import TestCase
from django.urls import reverse

from sales.services import cancel_sale
from supplies.services import cancel_supply
from .arrival import reduce_received
from .arrival_documents import create_arrival_supply
from .operation_changes import ChangesConfirmationRequired
from .test_arrival_finalization import ArrivalFinalizationFixture


class OperationQuantityRestoreTests(ArrivalFinalizationFixture, TestCase):
    def assert_delivery_balanced(self):
        self.arrival.refresh_from_db()
        self.assertEqual(sum(self.arrival.rows.values_list('delivery_total', flat=True)), Decimal('1200'))
        self.assertEqual(sum(self.arrival.rows.values_list('final_total', flat=True)), self.arrival.control_total)

    def test_sale_cancel_restores_only_document_reduction_and_only_once(self):
        self.arrival = self.arrive()
        row = self.arrival.rows.get(order=self.order)
        self.arrival = reduce_received(actor=self.user, arrival_id=self.arrival.pk,
            order_id=self.order.pk, quantities={row.pk:9}, expected_revision=self.arrival.revision)
        sale = self.sale(lines=[{'product_type':'cd', 'product_id':self.cd.pk,
            'quantity':7, 'trip_row':row.pk}])
        supply = self.supply()  # Пересчёт другого документа не должен терять снимок восстановления.
        self.assertEqual(self.arrival.rows.get(pk=row.pk).actual_quantity, 7)
        cancel_sale(actor=self.user, sale_id=sale.pk, comment='Повторная сверка')
        self.assertEqual(self.arrival.rows.get(pk=row.pk).actual_quantity, 9)
        cancel_sale(actor=self.user, sale_id=sale.pk, comment='Повторный запрос')
        self.assertEqual(self.arrival.rows.get(pk=row.pk).actual_quantity, 9)
        supply.refresh_from_db()
        self.assertEqual(supply.total_units, 2)
        self.assertEqual(self.order.items.get().quantity, 10)
        self.assert_delivery_balanced()
        self.no_stock_change()

    def test_supply_cancel_restores_reduction_with_sale_still_active(self):
        self.arrival = self.arrive()
        sale = self.sale()
        self.arrival.refresh_from_db()
        row = self.arrival.rows.get(order=self.stock_order)
        args = dict(actor=self.user, arrival_id=self.arrival.pk, order_id=self.stock_order.pk,
            expected_revision=self.arrival.revision, warehouse_id=self.warehouse.pk, draft_key=uuid4(),
            lines=[{'product_type':'cd', 'product_id':self.cd.pk, 'quantity':1, 'trip_row':row.pk}])
        with self.assertRaises(ChangesConfirmationRequired) as confirmation:
            create_arrival_supply(**args)
        self.assertEqual(self.arrival.rows.get(pk=row.pk).actual_quantity, 2)
        supply = create_arrival_supply(**args, changes_confirmation=confirmation.exception.token)
        self.assertEqual(self.arrival.rows.get(pk=row.pk).actual_quantity, 1)
        cancel_supply(actor=self.user, supply_id=supply.pk, comment='Повторная сверка')
        self.assertEqual(self.arrival.rows.get(pk=row.pk).actual_quantity, 2)
        sale.refresh_from_db()
        self.assertEqual(sum(i.quantity for i in sale.cd_items.all()), 10)
        self.assert_delivery_balanced()
        self.no_stock_change()

    def test_finalized_cancel_keeps_frozen_costs_and_quantities(self):
        self.arrival = self.arrive()
        row = self.arrival.rows.get(order=self.order)
        sale = self.sale(lines=[{'product_type':'cd', 'product_id':self.cd.pk,
            'quantity':8, 'trip_row':row.pk}])
        self.supply()
        self.arrival.refresh_from_db()
        self.finalize()
        before = list(self.arrival.rows.values('pk', 'actual_quantity', 'final_total'))
        cancel_sale(actor=self.user, sale_id=sale.pk, comment='Повторная продажа')
        self.assertEqual(list(self.arrival.rows.values('pk', 'actual_quantity', 'final_total')), before)

    def test_order_details_show_reduction_for_customer_and_stock(self):
        self.arrival = self.arrive()
        for order, quantity in ((self.order, 8), (self.stock_order, 1)):
            self.arrival.refresh_from_db()
            row = self.arrival.rows.get(order=order)
            reduce_received(actor=self.user, arrival_id=self.arrival.pk, order_id=order.pk,
                quantities={row.pk:quantity}, expected_revision=self.arrival.revision)
            response = self.client.get(reverse('orders:detail', args=[order.pk]))
            self.assertContains(response, f'Фактически в рейсе: {quantity} из {row.original_quantity} шт.')
            self.assertContains(response, f'количество уменьшено на {row.original_quantity-quantity} шт.')
