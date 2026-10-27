"""Отличия документа от заказа требуют точного подтверждения до любых проводок."""
from copy import deepcopy
from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError
from catalog.models import CD
from sales.models import Sale
from supplies.models import Supply
from .test_fulfillment import FulfillmentFixture
from .fulfillment import _create_legacy_direct_sale as create_direct_sale, _create_legacy_order_supply as create_order_supply
from .operation_changes import ChangesConfirmationRequired, draft_rows
from django.urls import reverse


class OperationChangesTests(FulfillmentFixture, TestCase):
    def arguments(self, draft, lines):
        return dict(actor=self.user,draft=draft,warehouse_id=self.warehouse.pk,lines=lines,
            price_type='wholesale',sale_type='wholesale',payment_method='cash_postpay',note='Изменён состав')

    def added_product(self):
        return CD.objects.create(name='Дополнительная игра',sku='ADDED',platform=self.cd.platform,
            wholesale_price=4500,cost=3100,weight_grams=120,cusa_ppsa_code='PPSA-00099')

    def test_quantity_discount_and_addition_require_confirmation_and_keep_original_order(self):
        draft=self.draft();lines=draft_rows(draft);lines[0].update(quantity=7,unit_discount='100')
        product=self.added_product()
        lines.append({'product_type':'cd','product_id':product.pk,'quantity':2,'trip_row':''})
        args=self.arguments(draft,lines)
        original=list(self.order.items.values())
        with self.assertRaises(ChangesConfirmationRequired) as first:create_direct_sale(**args)
        self.assertFalse(Sale.objects.exists());self.assertFalse(self.order.operations.exists())
        self.assertTrue(any('10 → 7' in value for value in first.exception.changes))
        self.assertTrue(any('скидка' in value for value in first.exception.changes))
        sale=create_direct_sale(**args,changes_confirmation=first.exception.token)
        self.assertEqual(sale.cd_items.get(cd=self.cd).unit_price,3500)
        self.assertEqual(sale.cd_items.get(cd=self.cd).unit_cost_snapshot,2720)
        self.assertEqual(sale.cd_items.get(cd=product).unit_price,4500)
        self.assertEqual(sale.cd_items.get(cd=product).unit_cost_snapshot,3100)
        self.assertEqual(sale.total_amount,32800)
        self.assertEqual(list(self.order.items.values()),original)
        self.assertEqual(sale.trip_operation.calculation['source_rows'][0]['quantity'],10)
        self.assertEqual(sale.trip_operation.calculation['rows'][0]['quantity'],7)
        self.assertTrue(sale.trip_operation.calculation['confirmed_changes'])
        self.no_stock_change()

    def test_changed_payload_cannot_reuse_confirmation(self):
        draft=self.draft();lines=draft_rows(draft);lines[0]['quantity']=6
        args=self.arguments(draft,lines)
        with self.assertRaises(ChangesConfirmationRequired) as first:create_direct_sale(**args)
        lines[0]['quantity']=5
        with self.assertRaises(ChangesConfirmationRequired):create_direct_sale(**args,changes_confirmation=first.exception.token)
        with self.assertRaises(ChangesConfirmationRequired):create_direct_sale(**args,changes_confirmation='yes')
        self.assertFalse(Sale.objects.exists());self.no_stock_change()

    def test_supply_quantity_cost_added_product_and_removal_confirmed_before_receipt(self):
        draft=self.draft(self.stock_order);lines=draft_rows(draft)
        lines[0].update(quantity=1,purchase_unit_cost='2800')
        product=self.added_product()
        lines.append({'product_type':'cd','product_id':product.pk,'quantity':3,'supplier_id':self.supplier.pk,
            'purchase_unit_cost':'3000','trip_row':''})
        args=dict(actor=self.user,draft=draft,warehouse_id=self.warehouse.pk,lines=lines)
        with self.assertRaises(ChangesConfirmationRequired) as first:create_order_supply(**args)
        self.assertFalse(Supply.objects.exists())
        supply=create_order_supply(**args,changes_confirmation=first.exception.token)
        self.assertEqual(supply.total_units,4);self.assertEqual(supply.grand_total,11800)
        self.assertEqual(supply.status,'price_review');self.no_stock_change()
        self.assertEqual(self.stock_order.items.get().quantity,2)

    def test_original_party_reference_cannot_be_duplicated_or_redirected(self):
        draft=self.draft();rows=draft_rows(draft)
        for lines in ([rows[0],rows[0]],[{**rows[0],'product_id':self.added_product().pk}]):
            with self.assertRaises(ValidationError):create_direct_sale(**self.arguments(draft,lines))
        self.assertFalse(Sale.objects.exists())

    def test_http_review_lists_changes_and_requires_current_confirmation(self):
        arrival=self.arrive_for_http()
        response=self.client.post(reverse('orders:operation_prepare',args=[self.order.pk]),{'usd_rub':'90','usd_aed':'3.673469'})
        url=response.url;draft_key=url.split('trip_draft=')[1]
        data={'trip_draft':draft_key,'warehouse':self.warehouse.pk,'payment_method':'cash_postpay','note':'Изменение',
            'product_type':['cd'],'product_id':[self.cd.pk],'quantity':['8'],
            'trip_row':[str(arrival.rows.get(order=self.order).pk)],
            'unit_discount':['100'],'line_note':[''],'avito_commission_enabled':['0']}
        response=self.client.post(url,data)
        self.assertEqual(response.status_code,200);self.assertContains(response,'Подтвердить изменения заказа?')
        self.assertFalse(Sale.objects.exists())
        token=response.context['operation_confirmation']['token']
        data['operation_confirmation']=token;data['quantity']=['7']
        response=self.client.post(url,data);self.assertEqual(response.status_code,200)
        self.assertFalse(Sale.objects.exists())
        data['operation_confirmation']=response.context['operation_confirmation']['token']
        response=self.client.post(url,data);self.assertEqual(response.status_code,302)
        self.assertEqual(Sale.objects.get().cd_items.get().quantity,7)

    def test_sale_form_shows_current_game_codes_before_and_after_changes(self):
        arrival=self.arrive_for_http()
        prepared = self.client.post(reverse('orders:operation_prepare', args=[self.order.pk]), {
            'usd_rub': '90', 'usd_aed': '3.673469',
        })
        response = self.client.get(prepared.url)
        self.assertEqual(response.context['initial_items'][0]['cusa_ppsa_code'], 'PPSA-00001')
        self.cd.cusa_ppsa_code = '036923, PPSA-00002'
        self.cd.save(update_fields=['cusa_ppsa_code'])
        response = self.client.post(prepared.url, {
            'trip_draft': prepared.url.split('trip_draft=')[1],
            'warehouse': self.warehouse.pk, 'payment_method': 'cash_postpay',
            'product_type': ['cd'], 'product_id': [self.cd.pk],
            'quantity': ['8'], 'trip_row': ['1'], 'unit_discount': ['0'],
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['initial_items'][0]['cusa_ppsa_code'], '036923, PPSA-00002')
        self.assertFalse(Sale.objects.exists())

    def test_http_supply_preserves_edited_rows_until_confirmation(self):
        arrival=self.arrive_for_http()
        response=self.client.post(reverse('orders:operation_prepare',args=[self.stock_order.pk]),{'usd_rub':'90','usd_aed':'3.673469'})
        url=response.url;draft_key=url.split('trip_draft=')[1]
        data={'trip_draft':draft_key,'warehouse_id':self.warehouse.pk,'weight_transport_cost':'0',
            'product_type':['cd'],'product_id':[self.cd.pk],'supplier_id':[self.supplier.pk],
            'quantity':['1'],'purchase_unit_cost':['2800'],'trip_row':[str(arrival.rows.get(order=self.stock_order).pk)]}
        response=self.client.post(url,data);self.assertEqual(response.status_code,200)
        self.assertFalse(Supply.objects.exists())
        self.assertEqual(response.context['initial_supply_lines'][0]['quantity'],1)
        data['operation_confirmation']=response.context['operation_confirmation']['token']
        response=self.client.post(url,data);self.assertEqual(response.status_code,302)
        supply=Supply.objects.get()
        self.assertEqual(supply.cd_items.get().quantity,1)
        self.assertEqual(supply.status,Supply.Status.WAITING_TRIP_FINALIZATION)
        self.assertNotEqual(supply.cd_items.get().purchase_unit_cost,2800)

    def test_stages_follow_all_invoices_pending_document_completion_and_cancel(self):
        from .trip_invoices import set_invoice_accepted
        from sales.services import cancel_sale
        from supplies.services import confirm_supply_price_review
        self.assertEqual(self.order.fulfillment_label,'Принят')
        set_invoice_accepted(actor=self.user,batch_id=self.trip.pk,supplier_id=self.supplier.pk,accepted=True)
        self.assertEqual(self.order.fulfillment_label,'Отфильтрован')
        sale=self.sale();self.order.refresh_from_db()
        self.assertEqual(self.order.fulfillment_label,'Привезён на склад')
        response=self.client.get(reverse('orders:trip_detail',args=[self.trip.pk]))
        self.assertContains(response,'<th>Статус</th>');self.assertContains(response,'order-operation-processing')
        cancel_sale(actor=self.user,sale_id=sale.pk,comment='Проверка')
        self.order.refresh_from_db();self.assertEqual(self.order.fulfillment_label,'Отфильтрован')
        sale=self.sale(payment_method='cash');self.order.refresh_from_db()
        self.assertEqual(self.order.fulfillment_label,'Выполнен');self.assertTrue(self.order.fulfillment_completed)
        response=self.client.get(reverse('orders:trip_detail',args=[self.trip.pk]))
        self.assertContains(response,'order-operation-completed')
        supply=self.supply();self.stock_order.refresh_from_db()
        self.assertEqual(self.stock_order.fulfillment_label,'Привезён на склад')
        confirm_supply_price_review(actor=self.user,supply_id=supply.pk)
        self.stock_order.refresh_from_db();self.assertEqual(self.stock_order.fulfillment_label,'Выполнен')

    def test_search_direct_sale_includes_catalog_products_without_stock_and_requires_price_access(self):
        from accounts.models import User
        from django.contrib.auth.models import Permission
        product=self.added_product()
        url=reverse('supplies:autocomplete')
        response=self.client.get(url,{'q':'ADDED','context':'trip_sale','warehouse':self.warehouse.pk})
        row=response.json()['results'][0]
        self.assertEqual(row['id'],product.pk);self.assertEqual(row['prices']['wholesale'],'4500.00')
        self.assertEqual(row['cost'],'3100.00')
        viewer=User.objects.create_user('only-sale-search')
        viewer.user_permissions.add(Permission.objects.get(content_type__app_label='sales',codename='create_sale'))
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(url,{'q':'ADDED','context':'trip_sale'}).status_code,403)
