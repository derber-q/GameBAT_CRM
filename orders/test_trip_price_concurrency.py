"""Одновременная корректировка и передача закупки не переписывают историю."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
import time

from django.core.exceptions import ValidationError
from django.db import OperationalError, connections
from django.test import TransactionTestCase

from accounts.models import User
from warehouse.models import Warehouse
from .models import CustomerProcurementOrder, SupplierOrderBatchLine, SupplierTripChange
from .services import advance_order_status
from .fulfillment_test_helpers import receive_with_test_rates as receive_stock_order
from . import test_trip_prices as price_fixtures
from .trip_prices import change_trip_price


class TripPriceConcurrencyTests(TransactionTestCase):
    order = classmethod(price_fixtures.TripPurchasePriceTests.order.__func__)

    def setUp(self):
        price_fixtures.TripPurchasePriceTests.setUpTestData.__func__(type(self))

    def change(self, value):
        actor = User.objects.get(pk=self.user.pk)
        try:
            change_trip_price(actor=actor, batch_id=self.trip.pk, line_id=self.line.pk,
                revision=self.trip.revision, price_aed=value)
            return 'saved'
        except ValidationError:
            return 'blocked'

    def parallel(self, first, second):
        barrier = Barrier(2)
        def run(action):
            try:
                barrier.wait(timeout=10)
                # SQLite shared-memory сразу возвращает SQLITE_LOCKED. Повторяем
                # запрос после отката, как при штатном HTTP 503, сохраняя проверки
                # единственного изменения цены, ревизии и согласованного прихода.
                for attempt in range(20):
                    try:
                        return action()
                    except OperationalError as exc:
                        if 'locked' not in str(exc).lower() or attempt == 19:
                            raise
                        time.sleep(.025)
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(run, (first, second)))

    def test_same_revision_only_one_different_price_wins(self):
        result = self.parallel(lambda: self.change('110'), lambda: self.change('120'))
        self.assertCountEqual(result, ['saved', 'blocked'])
        self.assertEqual(SupplierTripChange.objects.filter(batch=self.trip, details__action='purchase_price').count(), 1)
        price = SupplierOrderBatchLine.objects.get(pk=self.line.pk).supplier_price_aed_snapshot
        self.assertIn(price, (Decimal('110'), Decimal('120')))

    def test_race_with_supply_either_uses_new_price_or_blocks_correction(self):
        warehouse = Warehouse.objects.create(name='Конкурентный приход')
        advance_order_status(actor=self.user, order_id=self.stock.pk, next_status='confirmed')
        advance_order_status(actor=self.user, order_id=self.stock.pk, next_status='receiving')
        def receive():
            actor = User.objects.get(pk=self.user.pk)
            return receive_stock_order(actor=actor, order_id=self.stock.pk, warehouse_id=warehouse.pk).supply_id
        result = self.parallel(lambda: self.change('110'), receive)
        order = CustomerProcurementOrder.objects.select_related('supply').get(pk=self.stock.pk)
        price = SupplierOrderBatchLine.objects.get(pk=self.line.pk).supplier_price_aed_snapshot
        self.assertEqual(order.supply.cd_items.get().purchase_unit_cost, price * 25 + 17)
        self.assertEqual(result[1], order.supply_id)
        self.assertEqual(self.change('120'), 'blocked')
