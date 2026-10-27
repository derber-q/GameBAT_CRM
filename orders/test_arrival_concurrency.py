"""Версия рейса и сериализация конкурентных сверок количества."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import connections
from django.test import TransactionTestCase
from .test_arrival import ArrivalFixture
from .arrival import reduce_received


class ArrivalConcurrencyTests(ArrivalFixture, TransactionTestCase):
    def test_parallel_reductions_cannot_silently_overwrite_global_distribution(self):
        arrival=self.arrive();revision=arrival.revision
        rows=list(arrival.rows.order_by('order_id'))
        barrier=Barrier(2)
        def work(row):
            try:
                barrier.wait(timeout=10)
                reduce_received(actor=self.user,arrival_id=arrival.pk,order_id=row.order_id,
                    quantities={row.pk:row.actual_quantity-1},expected_revision=revision)
                return 'saved'
            except ValidationError:return 'stale'
            finally:connections['default'].close()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(work,rows))
        self.assertCountEqual(results,['saved','stale'])
        arrival.refresh_from_db()
        self.assertEqual(sum(arrival.rows.values_list('actual_quantity',flat=True)),11)
        self.assertEqual(sum(arrival.rows.values_list('delivery_total',flat=True)),Decimal('1200'))
        self.assertEqual(sum(row.final_total for row in arrival.rows.all()),arrival.control_total)
