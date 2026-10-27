"""Пользовательский путь без повторного ввода курсов и индивидуальной финализации."""
from django.test import TestCase
from django.urls import reverse
from .test_arrival import ArrivalFixture
from .arrival_models import TripArrival
from .arrival_finalization import finalization_rows
from sales.models import Sale
from supplies.models import Supply


class ArrivalHTTPTests(ArrivalFixture, TestCase):
    def confirm(self):
        response=self.client.post(reverse('orders:trip_arrival',args=[self.trip.pk]),{
            'action':'confirm','revision':self.trip.revision,'actual_delivery':'1200','usdt_aed':'3.66','usdt_rub':'88.06'})
        self.assertRedirects(response,reverse('orders:trip_detail',args=[self.trip.pk]))
        return TripArrival.objects.get(trip=self.trip)

    def create_document(self, order):
        response=self.client.get(reverse('orders:operation_prepare',args=[order.pk]))
        if response.status_code==200:
            self.assertNotContains(response,'Курсы для этой операции')
            response=self.client.post(reverse('orders:operation_prepare',args=[order.pk]),{})
        self.assertEqual(response.status_code,302)
        page=self.client.get(response.url)
        self.assertEqual(page.status_code,200)
        self.assertNotContains(page,'Курсы для этой операции')
        draft=page.context['trip_draft']; rows=page.context['initial_supply_lines'] if order.is_stock_order else page.context['initial_items']
        payload={'trip_draft':draft['key'],'warehouse':self.warehouse.pk,'warehouse_id':self.warehouse.pk,
            'payment_method':'cash_postpay','weight_transport_cost':'0','product_type':[r['product_type'] for r in rows],
            'product_id':[r['product_id'] for r in rows],'quantity':[r['quantity'] for r in rows],
            'trip_row':[r['trip_row'] for r in rows],'unit_discount':['0']*len(rows),
            'supplier_id':[r['supplier_id'] for r in rows], 'purchase_unit_cost':[r['unit_cost'] for r in rows]}
        result=self.client.post(response.url,payload)
        self.assertEqual(result.status_code,302,result.content[:200])
        return result

    def test_before_arrival_prepare_redirects_to_trip_without_creating_documents(self):
        page=self.client.get(reverse('orders:trip_detail',args=[self.trip.pk]))
        self.assertContains(page,'Фактическое прибытие и доставка')
        self.assertNotContains(page,'>Создать продажу</a>')
        response=self.client.get(reverse('orders:operation_prepare',args=[self.order.pk]))
        self.assertRedirects(response,reverse('orders:trip_detail',args=[self.trip.pk]))
        self.assertFalse(Sale.objects.exists()); self.assertFalse(Supply.objects.exists())

    def test_arrival_documents_joint_finalization_and_separate_posting(self):
        arrival=self.confirm()
        self.create_document(self.order)
        self.create_document(self.stock_order)
        page=self.client.get(reverse('orders:trip_detail',args=[self.trip.pk]))
        self.assertContains(page,'Итоговая финализация рейса')
        supply=Supply.objects.get()
        self.assertEqual(supply.status,Supply.Status.WAITING_TRIP_FINALIZATION)
        self.assertNotContains(self.client.get(reverse('supplies:detail',args=[supply.pk])),'>Финализация</a>')
        rejected=self.client.post(reverse('orders:arrival_supply_post',args=[supply.pk]),{'revision_number':supply.revision_number})
        self.assertEqual(rejected.status_code,302)
        self.no_stock_change()
        arrival.refresh_from_db()
        rows=finalization_rows(arrival)
        payload={'revision_number':arrival.revision}
        for field,values in {
            'product_type':[r.product_type for r in rows],'product_id':[r.product_id for r in rows],
            'baseline_quantity':[r.global_quantity for r in rows],'baseline_cost':[str(r.current_cost) for r in rows],
            'corrected_cost':[str(r.current_cost) for r in rows],'change_source':['unchanged']*len(rows)}.items():payload[field]=values
        url=reverse('orders:arrival_finalization',args=[self.trip.pk])
        self.assertContains(self.client.get(url),'Подтвердить финализацию рейса')
        self.assertEqual(self.client.post(url,payload).status_code,302)
        arrival.refresh_from_db();self.assertTrue(arrival.finalized)
        self.no_stock_change()
        supply.refresh_from_db()
        self.assertEqual(self.client.post(reverse('orders:arrival_supply_post',args=[supply.pk]),{'revision_number':supply.revision_number}).status_code,302)
        self.stock.refresh_from_db();self.assertEqual(self.stock.quantity,5)
        review=self.client.get(reverse('supplies:price_review',args=[supply.pk]))
        self.assertContains(review,'Подтвердить цены и поставить на баланс')
        supply.refresh_from_db()
        self.client.post(reverse('supplies:price_review',args=[supply.pk]),{'expected_revision_number':supply.revision_number})
        self.stock.refresh_from_db();self.assertEqual(self.stock.quantity,7)

    def test_price_proposals_from_old_finalization_form_are_rejected(self):
        from uuid import uuid4
        from .trips import create_trip
        first,second=self.make_order('stock',2),self.make_order('stock',3)
        self.trip=create_trip(actor=self.user,order_ids=[first.pk,second.pk],creation_key=uuid4())
        arrival=self.confirm();self.create_document(first);self.create_document(second);arrival.refresh_from_db()
        rows=finalization_rows(arrival)
        payload={'revision_number':arrival.revision,'product_type':[r.product_type for r in rows],
            'product_id':[r.product_id for r in rows],'baseline_quantity':[r.global_quantity for r in rows],
            'baseline_cost':[str(r.current_cost) for r in rows],'corrected_cost':[str(r.current_cost) for r in rows],
            'change_source':['unchanged']*len(rows),f'price_cd_{self.cd.pk}_wholesale_price':['4800','4900']}
        response=self.client.post(reverse('orders:arrival_finalization',args=[self.trip.pk]),payload,follow=True)
        self.assertContains(response,'подтверждаются при приёмке прихода')
        arrival.refresh_from_db();self.assertFalse(arrival.finalized)
