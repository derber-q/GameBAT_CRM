"""Непоступление, партии, отложенные цены и атомарность общих затрат."""
from decimal import Decimal
from uuid import uuid4
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.test import TestCase
from .test_arrival_finalization import ArrivalFinalizationFixture
from .arrival import reduce_received
from .arrival_finalization import readiness, finalization_rows, distribute_arrival
from .models import SupplierOrderBatchLine, SupplierTripAllocation
from .trips import create_trip
from sales.models import Sale
from sales.services import edit_postpay_sale_items, cancel_sale
from supplies.models import Supply
from supplies.services import confirm_supply_price_review, cancel_supply


class ArrivalEdgeCaseTests(ArrivalFinalizationFixture, TestCase):
    def reduce(self, order, quantity):
        self.arrival.refresh_from_db()
        source=self.arrival.rows.get(order=order)
        return reduce_received(actor=self.user,arrival_id=self.arrival.pk,order_id=order.pk,
            quantities={source.pk:quantity},expected_revision=self.arrival.revision)

    def test_customer_completely_missing_does_not_create_empty_sale_or_block_finalization(self):
        self.arrival=self.arrive()
        row=self.arrival.rows.get(order=self.order)
        self.assertIsNone(self.sale(lines=[{'product_type':'cd','product_id':self.cd.pk,'quantity':0,'trip_row':row.pk}]))
        self.assertFalse(Sale.objects.exists())
        self.supply();self.arrival.refresh_from_db()
        self.assertTrue(readiness(self.arrival)['ready'])
        self.finalize();self.order.refresh_from_db()
        self.assertEqual(self.order.fulfillment_label,'Не поступил')
        self.assertNotEqual(self.order.status,self.order.Status.COMPLETED)

    def test_only_customer_documents_are_sufficient(self):
        self.arrival=self.arrive();sale=self.sale()
        self.reduce(self.stock_order,0);self.arrival.refresh_from_db()
        self.assertFalse(Supply.objects.exists())
        self.assertTrue(readiness(self.arrival)['ready'])
        self.finalize();self.no_stock_change()
        self.assertEqual(sale.cd_items.get().unit_cost_snapshot,Decimal('2526.01'))

    def test_emptying_existing_document_cancels_it_without_losing_history(self):
        sale,supply=self.prepare()
        original=sale.cd_items.get().quantity
        self.reduce(self.order,0)
        sale.refresh_from_db();supply.refresh_from_db();self.arrival.refresh_from_db()
        self.assertTrue(sale.is_cancelled)
        self.assertEqual(sale.cd_items.get().quantity,original)
        self.assertEqual(supply.grand_total,Decimal('6012.02'))
        self.assertTrue(readiness(self.arrival)['ready'])
        self.no_stock_change()

    def test_entire_trip_cannot_be_empty_and_previous_reduction_is_preserved(self):
        self.arrival=self.arrive();self.reduce(self.order,0)
        with self.assertRaises(ValidationError):self.reduce(self.stock_order,0)
        self.assertEqual(self.arrival.rows.get(order=self.stock_order).actual_quantity,2)
        self.assertEqual(sum(self.arrival.rows.values_list('delivery_total',flat=True)),Decimal('1200'))

    def test_cancel_before_finalization_requires_new_document(self):
        sale,_=self.prepare()
        cancel_sale(actor=self.user,sale_id=sale.pk,comment='Повторная сверка')
        self.assertFalse(readiness(self.arrival)['ready'])
        self.sale();self.arrival.refresh_from_db()
        self.assertTrue(readiness(self.arrival)['ready'])

    def test_exact_cent_delivery_is_split_without_lost_costs(self):
        self.arrival=self.arrive(actual_delivery='.01')
        sale,supply=self.sale(),self.supply();self.arrival.refresh_from_db()
        self.assertEqual(sale.cd_items.count(),2)
        self.assertEqual(sum(i.unit_cost_snapshot*i.quantity for i in sale.cd_items.all())+supply.grand_total,self.arrival.control_total)
        self.finalize();self.no_stock_change()

    def test_authoritative_distribution_tools_work_with_procurement_cohort_keys(self):
        self.prepare();rows=self.inputs();baseline=finalization_rows(self.arrival)
        rows[0]['corrected_cost']=str(Decimal(rows[0]['baseline_cost'])-10);rows[0]['change_source']='manual'
        result=distribute_arrival(actor=self.user,arrival_id=self.arrival.pk,expected_revision=self.arrival.revision,
            raw_rows=rows,selected_keys={baseline[-1].key})
        self.assertEqual(sum(row.row_penalty for row in result),0)
        self.assertEqual(result[-1].corrected_cost,baseline[-1].current_cost+50)

    def test_finalization_rolls_back_all_documents_if_one_update_fails(self):
        sale,supply=self.prepare();rows=self.inputs();old_sale=sale.cd_items.get().unit_cost_snapshot
        rows[0]['corrected_cost']=str(Decimal(rows[0]['baseline_cost'])+10)
        rows[-1]['corrected_cost']=str(Decimal(rows[-1]['baseline_cost'])-50)
        with patch('orders.arrival_documents._refresh_supply',side_effect=ValidationError('Проверка отката')):
            with self.assertRaises(ValidationError):self.finalize(rows)
        self.arrival.refresh_from_db();supply.refresh_from_db()
        self.assertFalse(self.arrival.finalized)
        self.assertEqual(sale.cd_items.get().unit_cost_snapshot,old_sale)
        self.assertEqual(supply.grand_total,Decimal('5012.02'))

    def test_discount_edit_survives_reallocation_of_delivery(self):
        sale,_=self.prepare();item=sale.cd_items.get()
        edit_postpay_sale_items(actor=self.user,sale_id=sale.pk,note='Согласованная скидка',lines=[{
            'product_type':'cd','product_id':self.cd.pk,'quantity':10,'item_id':item.pk,'unit_discount':'100'}])
        self.reduce(self.stock_order,1)
        sale.refresh_from_db()
        self.assertEqual(sale.total_amount,Decimal('34000'))
        self.assertTrue(all(item.unit_discount==100 for item in sale.cd_items.all()))

    def test_two_stock_orders_stay_separate_and_post_against_current_cost(self):
        first,second=self.make_order('stock',2),self.make_order('stock',3)
        self.trip=create_trip(actor=self.user,order_ids=[first.pk,second.pk],creation_key=uuid4())
        self.arrival=self.arrive();self.stock_order=first;a=self.supply();self.stock_order=second;b=self.supply()
        self.arrival.refresh_from_db();self.assertEqual(Supply.objects.count(),2)
        self.finalize()
        self.post_reviewed_supply(a,prices={('cd',self.cd.pk):{'wholesale_price':'4800'}})
        from pricing.services import update_product_prices
        update_product_prices(actor=self.user,product_type='cd',product_id=self.cd.pk,changes={'wholesale_price':Decimal('5200')})
        self.post_reviewed_supply(b)
        _,changed=confirm_supply_price_review(actor=self.user,supply_id=b.pk)
        self.stock.refresh_from_db();self.cd.refresh_from_db()
        self.assertEqual(self.stock.quantity,10)
        self.assertFalse(changed)
        self.assertEqual(self.cd.wholesale_price,Decimal('5200'))

    def test_supplier_parties_are_not_merged_by_product_id(self):
        from partners.models import Supplier
        supplier=Supplier.objects.create(name='B',letter='B',legal_entity='B',phone_1='2')
        allocation=self.order.items.get().trip_allocations.get();old_line=allocation.line
        allocation.postpayment_quantity=5;allocation.save(update_fields=['postpayment_quantity'])
        old_line.quantity-=5;old_line.save(update_fields=['quantity'])
        line=SupplierOrderBatchLine.objects.create(batch=self.trip,supplier=supplier,price_supplier=supplier,
            price_list_item=self.source,product_kind='cd',cd=self.cd,product_name_snapshot=self.cd.name,
            article_snapshot=self.cd.sku,quantity=5,supplier_price_aed_snapshot=110)
        SupplierTripAllocation.objects.create(line=line,order_item=self.order.items.get(),postpayment_quantity=5)
        self.arrival=self.arrive();sale=self.sale()
        self.assertEqual(self.arrival.rows.filter(order=self.order).count(),2)
        self.assertEqual(sale.cd_items.count(),2)
        self.assertEqual(len(set(sale.cd_items.values_list('unit_cost_snapshot',flat=True))),2)

    def test_supply_cancel_and_recreate_after_finalization_keeps_whole_trip_fixed(self):
        _,supply=self.prepare();self.finalize();self.arrival.refresh_from_db()
        total=self.arrival.control_total
        self.post_reviewed_supply(supply)
        cancel_supply(actor=self.user,supply_id=supply.pk,comment='Повторное оформление')
        replacement=self.supply()
        self.assertNotEqual(replacement.pk,supply.pk)
        self.arrival.refresh_from_db();self.assertEqual(self.arrival.control_total,total)
        self.assertTrue(self.arrival.finalized)
        self.post_reviewed_supply(replacement)
        self.stock.refresh_from_db();self.assertEqual(self.stock.quantity,7)

    def test_independent_supply_expenses_do_not_repeat_trip_delivery(self):
        _,supply=self.prepare();self.finalize();self.arrival.refresh_from_db()
        supply.refresh_from_db()
        control=self.arrival.control_total
        self.post_reviewed_supply(supply,expenses=[{'name':'Независимая упаковка','amount':'.01'}])
        supply.refresh_from_db();self.arrival.refresh_from_db()
        self.assertEqual(supply.goods_total_before_expenses,Decimal('5012.02'))
        self.assertEqual(supply.grand_total,Decimal('5012.03'))
        self.assertEqual(sum(supply.cd_items.values_list('final_line_total',flat=True)),supply.grand_total)
        self.assertEqual(self.arrival.control_total,control)
        self.assertEqual(supply.weight_transport_cost,0)
        _,changed=confirm_supply_price_review(actor=self.user,supply_id=supply.pk,
            independent_expenses=[{'name':'Независимая упаковка','amount':'.01'}])
        self.assertFalse(changed)
        self.stock.refresh_from_db();self.assertEqual(self.stock.quantity,7)

    def test_each_supply_prices_are_confirmed_separately_against_current_average(self):
        _,older=self.prepare();self.finalize()
        order=self.make_order('stock',1)
        self.trip=create_trip(actor=self.user,order_ids=[order.pk],creation_key=uuid4())
        self.stock_order=order;self.arrival=self.arrive();newer=self.supply();self.arrival.refresh_from_db()
        self.finalize()
        self.post_reviewed_supply(older,prices={('cd',self.cd.pk):{'wholesale_price':'4800'}})
        self.cd.refresh_from_db();self.assertEqual(self.cd.wholesale_price,Decimal('4800'))
        self.post_reviewed_supply(newer,prices={('cd',self.cd.pk):{'wholesale_price':'5100'}})
        self.cd.refresh_from_db();self.assertEqual(self.cd.wholesale_price,Decimal('5100'))

    def test_public_legacy_creator_cannot_bypass_arrival(self):
        from .fulfillment import create_direct_sale,create_order_supply
        with self.assertRaisesMessage(ValidationError,'прибытие'):
            create_direct_sale(actor=self.user,draft=self.draft(),warehouse_id=self.warehouse.pk)
        with self.assertRaisesMessage(ValidationError,'прибытие'):
            create_order_supply(actor=self.user,draft=self.draft(self.stock_order),warehouse_id=self.warehouse.pk)
        self.assertFalse(Sale.objects.exists());self.assertFalse(Supply.objects.exists())

    def test_stock_shortage_rolls_back_delivery_reallocation_in_other_documents(self):
        self.arrival=self.arrive();supply=self.supply();self.arrival.refresh_from_db()
        source=self.arrival.rows.get(order=self.order);before=self.arrival.control_total
        with self.assertRaises(ValidationError):
            self.sale(lines=[{'product_type':'cd','product_id':self.cd.pk,'quantity':8,'trip_row':source.pk},
                {'product_type':'cd','product_id':self.cd.pk,'quantity':6,'trip_row':''}])
        self.arrival.refresh_from_db();supply.refresh_from_db();source.refresh_from_db()
        self.assertEqual(source.actual_quantity,10)
        self.assertEqual(supply.grand_total,Decimal('5012.02'))
        self.assertEqual(self.arrival.control_total,before)
        self.no_stock_change()

    def test_emptying_pending_stock_order_cancels_without_warehouse_movement(self):
        sale,supply=self.prepare();self.reduce(self.stock_order,0)
        supply.refresh_from_db();self.arrival.refresh_from_db()
        self.assertTrue(supply.is_cancelled)
        self.assertTrue(readiness(self.arrival)['ready'])
        self.assertEqual(sale.cd_items.get().unit_cost_snapshot,Decimal('2526.01'))
        self.no_stock_change()

    def test_completed_sale_statistics_use_final_trip_cost(self):
        from sales.statistics_service import build_sales_statistics_report
        from sales.services import advance_order_status,mark_sale_paid
        sale,_=self.prepare();rows=self.inputs()
        rows[0]['corrected_cost']=str(Decimal(rows[0]['baseline_cost'])+10)
        rows[-1]['corrected_cost']=str(Decimal(rows[-1]['baseline_cost'])-50)
        self.finalize(rows)
        advance_order_status(actor=self.user,sale_id=sale.pk,next_status='assembled')
        advance_order_status(actor=self.user,sale_id=sale.pk,next_status='delivered')
        mark_sale_paid(actor=self.user,sale_id=sale.pk)
        report=build_sales_statistics_report({})
        self.assertEqual(report.sales[0].cost,Decimal('25160.10'))
        self.assertEqual(report.sales[0].profit,Decimal('9839.90'))

    def test_source_flags_and_cost_cannot_be_reassigned_by_model_save(self):
        sale,_=self.prepare();item=sale.cd_items.get()
        item.is_direct_delivery=False
        with self.assertRaises(ValidationError):item.save()
        item.refresh_from_db();item.unit_cost_snapshot=0
        with self.assertRaises(ValidationError):item.save()

    def test_global_prices_are_rejected_in_finalization_service(self):
        from accounts.models import User
        from django.contrib.auth.models import Permission
        from django.core.exceptions import PermissionDenied
        from .arrival_finalization import finalize_arrival
        self.prepare()
        actor=User.objects.create_user('finalize-no-price')
        actor.user_permissions.add(*Permission.objects.filter(content_type__app_label__in=['orders','price','supplies'],
            codename__in=['view_order_detail','generate_supplier_orders','view_supplier_prices','finalize_supply']))
        with self.assertRaises(ValidationError):
            finalize_arrival(actor=actor,arrival_id=self.arrival.pk,expected_revision=self.arrival.revision,
                raw_rows=self.inputs(),proposed_prices={('cd',self.cd.pk):{'wholesale_price':'4800'}})
        self.arrival.refresh_from_db();self.assertFalse(self.arrival.finalized)

    def test_canceled_legacy_history_does_not_block_first_arrival(self):
        from .fulfillment import _create_legacy_direct_sale
        previous=_create_legacy_direct_sale(actor=self.user,draft=self.draft(),warehouse_id=self.warehouse.pk,
            price_type='wholesale',sale_type='wholesale',payment_method='cash_postpay',
            lines=[{'product_type':'cd','product_id':self.cd.pk,'quantity':10}])
        cancel_sale(actor=self.user,sale_id=previous.pk,comment='Переход к общей финализации')
        original=previous.cd_items.get().unit_cost_snapshot
        self.arrival=self.arrive()
        self.assertTrue(self.arrival.arrived)
        self.assertEqual(previous.cd_items.get().unit_cost_snapshot,original)
        previous.trip_operation.refresh_from_db()
        self.assertFalse(previous.trip_operation.active)
        from .arrival import unconfirm_arrival
        unconfirm_arrival(actor=self.user,arrival_id=self.arrival.pk,expected_revision=self.arrival.revision)
        self.arrival.refresh_from_db()
        self.assertFalse(self.arrival.arrived)
