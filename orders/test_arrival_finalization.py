"""Общая финализация сохраняет сумму рейса и не проводит его документы."""
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.test import TestCase
from .test_arrival_documents import ArrivalDocumentFixture
from .arrival_finalization import finalization_rows, finalize_arrival, readiness
from .arrival import reduce_received
from supplies.services import confirm_supply_price_review
from sales.services import cancel_sale, advance_order_status, mark_sale_paid


class ArrivalFinalizationFixture(ArrivalDocumentFixture):
    def prepare(self):
        self.arrival = self.arrive()
        sale, supply = self.sale(), self.supply()
        self.arrival.refresh_from_db()
        return sale, supply

    def inputs(self):
        return [dict(product_type=row.product_type, product_id=row.product_id,
            baseline_quantity=row.global_quantity, baseline_cost=str(row.current_cost),
            corrected_cost=str(row.current_cost), change_source='unchanged')
            for row in finalization_rows(self.arrival)]

    def finalize(self, rows=None, prices=None):
        return finalize_arrival(actor=self.user, arrival_id=self.arrival.pk,
            expected_revision=self.arrival.revision, raw_rows=rows or self.inputs(), proposed_prices=prices or {})

    def post_reviewed_supply(self, supply, prices=None, expenses=None):
        from .arrival_finalization import prepare_supply_price_review
        prepare_supply_price_review(actor=self.user,supply_id=supply.pk,independent_expenses=expenses)
        supply.refresh_from_db()
        return confirm_supply_price_review(actor=self.user,supply_id=supply.pk,
            expected_revision_number=supply.revision_number,price_changes=prices)


class ArrivalFinalizationTests(ArrivalFinalizationFixture, TestCase):
    def test_readiness_requires_each_order_document(self):
        self.arrival = self.arrive()
        self.assertFalse(readiness(self.arrival)['ready'])
        self.sale()
        self.arrival.refresh_from_db()
        self.assertFalse(readiness(self.arrival)['ready'])
        self.supply()
        self.arrival.refresh_from_db()
        self.assertTrue(readiness(self.arrival)['ready'])

    def test_finalization_preserves_total_and_defers_stock_and_prices(self):
        sale, supply = self.prepare()
        self.finalize()
        self.arrival.refresh_from_db(); sale.refresh_from_db(); supply.refresh_from_db()
        self.assertTrue(self.arrival.finalized)
        self.assertFalse(sale.is_completed)
        self.assertEqual(sale.total_amount, Decimal('35000'))
        self.assertEqual(supply.status, supply.Status.WAITING_TRIP_FINALIZATION)
        self.no_stock_change()
        self.assertEqual(self.cd.wholesale_price, Decimal('9999'))
        self.post_reviewed_supply(supply,prices={('cd',self.cd.pk):{'wholesale_price':'4800','avito_price':'5000'}})
        self.cd.refresh_from_db(); self.stock.refresh_from_db()
        self.assertEqual((self.stock.quantity,self.cd.wholesale_price,self.cd.avito_price),(7,Decimal('4800'),Decimal('5000')))

    def test_cost_can_move_between_customer_and_warehouse_without_changing_total(self):
        sale, supply = self.prepare()
        rows = self.inputs()
        # 10 клиентских единиц × +10 ₽ и 2 складских × -50 ₽ сохраняют 100 ₽.
        sources = {row.product_id:row.cost_row for row in finalization_rows(self.arrival)}
        for row in rows:
            delta = Decimal('10') if sources[row['product_id']].order_id==self.order.pk else Decimal('-50')
            row['corrected_cost'] = str(Decimal(row['baseline_cost'])+delta)
            row['change_source'] = 'manual'
        self.finalize(rows)
        self.assertEqual(sale.cd_items.get().unit_cost_snapshot,Decimal('2516.01'))
        supply.refresh_from_db()
        self.assertEqual(supply.grand_total,Decimal('4912.02'))
        self.arrival.refresh_from_db()
        self.assertEqual(sum(self.arrival.rows.values_list('final_total',flat=True)),self.arrival.control_total)

    def test_unbalanced_and_stale_forms_cannot_be_finalized(self):
        self.prepare()
        rows = self.inputs(); rows[0]['corrected_cost']='0'
        with self.assertRaises(ValidationError): self.finalize(rows)
        rows=self.inputs(); source=self.arrival.rows.get(order=self.order)
        reduce_received(actor=self.user,arrival_id=self.arrival.pk,order_id=self.order.pk,
            quantities={source.pk:9},expected_revision=self.arrival.revision)
        with self.assertRaises(ValidationError): self.finalize(rows)

    def test_cancel_and_recreate_after_finalization_reuses_fixed_costs(self):
        sale, _ = self.prepare()
        self.finalize()
        original_cost = sale.cd_items.get().unit_cost_snapshot
        self.arrival.refresh_from_db(); before=self.arrival.control_total
        cancel_sale(actor=self.user,sale_id=sale.pk,comment='Повторное оформление')
        replacement=self.sale()
        self.assertEqual(replacement.cd_items.get().unit_cost_snapshot,original_cost)
        self.arrival.refresh_from_db()
        self.assertEqual(self.arrival.control_total,before)
        self.assertTrue(self.arrival.finalized)
        advance_order_status(actor=self.user,sale_id=replacement.pk,next_status='assembled')
        advance_order_status(actor=self.user,sale_id=replacement.pk,next_status='delivered')
        mark_sale_paid(actor=self.user,sale_id=replacement.pk)
        replacement.refresh_from_db(); self.assertTrue(replacement.is_completed)
