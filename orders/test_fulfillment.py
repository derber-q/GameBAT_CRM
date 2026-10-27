"""Стоимость, склад, жизненный цикл и повторные запросы операций из рейса."""
from decimal import Decimal
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.core.exceptions import ValidationError, PermissionDenied
from django.db import connections
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.core import signing

from accounts.models import User
from catalog.models import CD, Platform, BarcodeRegistry, Tech, Brand, ProductType
from cash.models import CashRegister, CashTransaction
from partners.models import Partner, Supplier
from price.models import ProcurementPriceList, ProcurementPriceListItem
from sales.models import Sale
from sales.services import advance_order_status, mark_sale_paid, cancel_sale, edit_postpay_sale_items
from supplies.services import confirm_supply_price_review, cancel_supply, edit_pending_supply
from supplies.models import Supply
from warehouse.models import Warehouse, CDWarehouseStock
from .models import CustomerProcurementOrder, TripOrderOperation
from .services import create_customer_procurement_order, advance_order_status as advance_procurement
from .trips import create_trip
from .fulfillment import calculation, _create_legacy_direct_sale as create_direct_sale, _create_legacy_order_supply as create_order_supply, FulfillmentRatesForm
from .fulfillment_views import DRAFTS


class FulfillmentFixture:
    def setUp(self):
        self.user = User.objects.create_superuser('fulfillment', password='test')
        self.warehouse = Warehouse.objects.create(name='Склад')
        self.supplier = Supplier.objects.create(name='A', letter='A', legal_entity='A', phone_1='1')
        self.partner = Partner.objects.create(name='Партнёр')
        self.cd = CD.objects.create(name='Игра', sku='FX-CD', platform=Platform.objects.create(name='PS5'),
            weight_grams=100, cusa_ppsa_code='PPSA-00001', cost=700, wholesale_price=9999)
        self.stock = CDWarehouseStock.objects.create(warehouse=self.warehouse, cd=self.cd, quantity=5)
        self.price = ProcurementPriceList.objects.create(created_by=self.user, exchange_rate_aed_rub=20,
            exchange_rate_usdt_aed=4, exchange_rate_usdt_rub=80, delivery_cd_rub=240)
        self.source = ProcurementPriceListItem.objects.create(price_list=self.price, product_kind='cd', cd=self.cd,
            product_name_snapshot=self.cd.name, article_snapshot=self.cd.sku, selected_supplier=self.supplier,
            supplier_price_aed=100, exchange_rate_aed_rub=20, base_price_rub=2000, delivery_rub=240,
            prepayment_price_rub=3500, postpayment_price_rub=3500)
        self.order = self.make_order('customer', 10)
        self.stock_order = self.make_order('stock', 2)
        self.trip = create_trip(actor=self.user, order_ids=[self.order.pk, self.stock_order.pk], creation_key=uuid4())
        self.order.refresh_from_db(); self.stock_order.refresh_from_db()
        self.client.force_login(self.user)

    def make_order(self, purpose, qty):
        return create_customer_procurement_order(actor=self.user, price_list_id=self.price.pk,
            purpose=purpose, recipient='На склад' if purpose == 'stock' else self.partner.name,
            partner_id=self.partner.pk if purpose == 'customer' else None, comment='',
            lines=[{'price_list_item_id': self.source.pk, 'prepayment_quantity': qty if purpose == 'stock' else 0,
                    'postpayment_quantity': 0 if purpose == 'stock' else qty}])

    def arrive_for_http(self, order=None):
        """Новый UI использует общие затраты; старые суммы ниже — исторические fixtures."""
        from .arrival import confirm_arrival
        from .arrival_models import TripArrival
        from .models import SupplierOrderBatch
        if order: order.refresh_from_db()
        batch=SupplierOrderBatch.objects.get(pk=order.trip_id if order else self.trip.pk)
        existing=TripArrival.objects.filter(trip=batch,arrived_at__isnull=False).first()
        if existing:return existing
        delivery=sum(Decimal(row['delivery_rub'])*row['quantity']
            for source_order in batch.trip_orders.all()
            for row in calculation(source_order,usd_rub='90',usd_aed='3.673469')['rows'])
        result=confirm_arrival(actor=self.user,batch_id=batch.pk,expected_revision=batch.revision,
            usdt_rub='90',usdt_aed='3.673469',actual_delivery=delivery)
        self.trip.refresh_from_db()
        return result

    def draft(self, order=None, usd='90', aed='24.5'):
        order = order or self.order
        return {'key': str(uuid4()), 'order_id': order.pk, 'calculation': calculation(order, usd_rub=usd, aed_rub=aed)}

    def sale(self, draft=None, **changes):
        draft = draft or self.draft()
        args = dict(actor=self.user, draft=draft, warehouse_id=self.warehouse.pk, price_type='wholesale',
            sale_type='wholesale', payment_method='cash_postpay', lines=[
                {'product_type': r['product_type'], 'product_id': r['product_id'], 'quantity': r['quantity']}
                for r in draft['calculation']['rows']])
        args.update(changes)
        return create_direct_sale(**args)

    def supply(self, draft=None):
        return create_order_supply(actor=self.user, draft=draft or self.draft(self.stock_order), warehouse_id=self.warehouse.pk)

    def no_stock_change(self):
        self.stock.refresh_from_db(); self.cd.refresh_from_db()
        self.assertEqual(self.stock.quantity, 5)
        self.assertEqual(self.cd.cost, 700)


class TripFulfillmentTests(FulfillmentFixture, TestCase):
    def test_cross_rates_convert_aed_before_adding_delivery(self):
        snapshot = calculation(self.order, usd_rub='87.43', usd_aed='3.66')
        self.assertEqual(snapshot['usd_aed'], '3.66')
        self.assertEqual(snapshot['aed_rub'], '23.887978')
        row = snapshot['rows'][0]
        self.assertEqual(row['base_rub'], '2388.80')
        self.assertEqual(row['delivery_rub'], '262.29')
        self.assertEqual(row['unit_cost'], '2651.09')
        self.assertEqual(row['unit_price'], '3500.00')
        sale = self.sale({'key': str(uuid4()), 'order_id': self.order.pk, 'calculation': snapshot})
        self.assertEqual(sale.cd_items.get().unit_cost_snapshot, Decimal('2651.09'))
        self.assertEqual(sale.trip_operation.calculation['usd_aed'], '3.66')
        self.assertEqual(sale.trip_operation.aed_rub, Decimal('23.887978'))
        self.no_stock_change()

    def test_cross_rates_supply_snapshot_keeps_input_rates(self):
        snapshot = calculation(self.stock_order, usd_rub='87.43', usd_aed='3.66')
        supply = self.supply({'key': str(uuid4()), 'order_id': self.stock_order.pk, 'calculation': snapshot})
        self.assertEqual(supply.cd_items.get().purchase_unit_cost, Decimal('2651.09'))
        self.assertEqual(supply.trip_operation.calculation['usd_aed'], '3.66')
        self.no_stock_change()

    def test_cross_rates_do_not_round_conversion_before_purchase_total(self):
        line = self.order.items.get().trip_allocations.get().line
        line.supplier_price_aed_snapshot = Decimal('123456.78')
        line.save(update_fields=['supplier_price_aed_snapshot'])
        snapshot = calculation(self.order, usd_rub='87.43', usd_aed='3.66')
        self.assertEqual(snapshot['rows'][0]['base_rub'], '2949132.86')

    def test_cross_rates_reject_zero_infinite_and_ambiguous_inputs(self):
        for rub, aed in (('87.43', '0'), ('87.43', 'NaN'), ('87.43', 'Infinity'),
                         ('87.43', ''), ('87.43', '-3.66'), ('0.000001', '99999999999999'),
                         ('99999999999999', '0.000001')):
            with self.subTest(rub=rub, aed=aed), self.assertRaises(ValidationError):
                calculation(self.order, usd_rub=rub, usd_aed=aed)
        with self.assertRaises(ValidationError):
            calculation(self.order, usd_rub='87.43', usd_aed='3.66', aed_rub='3.66')

    def test_prepare_uses_common_trip_rates_and_rejects_previous_rate_screen(self):
        url=reverse('orders:operation_prepare',args=[self.order.pk])
        response=self.client.post(url,{'usd_rub':'87.43','aed_rub':'3.66'})
        self.assertRedirects(response,reverse('orders:trip_detail',args=[self.trip.pk]))
        self.assertFalse(self.client.session.get(DRAFTS))
        self.client.post(reverse('orders:trip_arrival',args=[self.trip.pk]),{
            'action':'confirm','revision':self.trip.revision,'usdt_rub':'87.43','usdt_aed':'3.66','actual_delivery':'3147.48'})
        response=self.client.get(url)
        self.assertEqual(response.status_code,302)
        page=self.client.get(response.url)
        self.assertEqual(page.context['trip_draft']['calculation']['rows'][0]['unit_cost'],'2651.09')
        self.assertContains(page,'USDT/AED 3.66')
        self.assertNotContains(page,'name="usd_aed"')
        self.assertFalse(Sale.objects.exists())

    def test_required_finite_positive_precise_rates(self):
        for value in ('', '0', '-1', 'NaN', 'Infinity', '1.1234567', '100000000000000'):
            with self.subTest(value=value):
                form = FulfillmentRatesForm({'usd_rub': value, 'usd_aed': '3.6'})
                self.assertFalse(form.is_valid())
                self.assertFalse(FulfillmentRatesForm({'usd_rub': '87.43', 'usd_aed': value}).is_valid())
        self.assertTrue(FulfillmentRatesForm({'usd_rub': '90.123456', 'usd_aed': '3.6'}).is_valid())

    def test_calculation_example_customer_price_and_other_order_unchanged(self):
        original = list(self.stock_order.items.values())
        row = self.draft()['calculation']['rows'][0]
        self.assertEqual(row['unit_cost'], '2720.00')
        self.assertEqual(row['unit_price'], '3500.00')
        sale = self.sale()
        self.assertEqual(sale.cd_items.get().unit_cost_snapshot, 2720)
        self.assertEqual(sale.total_amount, 35000)
        self.assertEqual(list(self.stock_order.items.values()), original)
        self.assertEqual(self.price.exchange_rate_usdt_rub, 80)
        self.no_stock_change()

    def test_processing_then_completed_and_statistics_cost(self):
        from sales.statistics_service import build_sales_statistics_report
        sale = self.sale()
        self.order.refresh_from_db()
        self.assertEqual(self.order.fulfillment_label, 'Привезён на склад')
        self.assertTrue(self.order.fulfillment_processing)
        advance_order_status(actor=self.user, sale_id=sale.pk, next_status='assembled')
        advance_order_status(actor=self.user, sale_id=sale.pk, next_status='delivered')
        self.order.refresh_from_db(); self.assertNotEqual(self.order.status, 'completed')
        mark_sale_paid(actor=self.user, sale_id=sale.pk)
        self.order.refresh_from_db(); self.assertEqual(self.order.status, 'completed')
        report = build_sales_statistics_report({})
        self.assertEqual(report.sales[0].cost, Decimal('27200'))
        self.assertEqual(report.sales[0].profit, Decimal('7800'))
        self.no_stock_change()

    def test_cancel_unpaid_and_recreate_fresh_rates_retains_history(self):
        draft = self.draft(); sale = self.sale(draft)
        cancel_sale(actor=self.user, sale_id=sale.pk, comment='Отмена')
        self.order.refresh_from_db()
        self.assertEqual(self.order.fulfillment_label, 'Принят')
        with self.assertRaises(ValidationError): self.sale(draft)
        new = self.sale(self.draft(aed='25'))
        self.assertEqual(new.cd_items.get().unit_cost_snapshot, 2770)
        self.assertEqual(sale.cd_items.get().unit_cost_snapshot, 2720)
        self.assertEqual(self.order.operations.count(), 2)
        self.assertEqual(self.order.operations.filter(active=True).count(), 1)
        self.no_stock_change()

    def test_cancel_paid_reverses_cash_without_returning_goods(self):
        sale = self.sale(payment_method='cash')
        self.assertEqual(CashRegister.objects.get(warehouse=self.warehouse).balance, 35000)
        cancel_sale(actor=self.user, sale_id=sale.pk, comment='Отмена')
        self.assertEqual(CashRegister.objects.get(warehouse=self.warehouse).balance, 0)
        self.no_stock_change()

    def test_partial_payment_and_cancel_reverses_partner_debt(self):
        from sales.partner_payments import quote, SALT
        sale = self.sale()
        token = signing.dumps(quote(total=35000, received=30000, debt=0,
            partner_id=self.partner.pk, sale_id=sale.pk), salt=SALT)
        mark_sale_paid(actor=self.user, sale_id=sale.pk, cash_received_amount=30000, note='Остаток в долг', settlement_confirmation=token)
        self.partner.creditor.refresh_from_db(); self.assertEqual(self.partner.creditor.current_debt, 5000)
        cancel_sale(actor=self.user, sale_id=sale.pk, comment='Отмена')
        self.partner.creditor.refresh_from_db(); self.assertEqual(self.partner.creditor.current_debt, 0)
        self.no_stock_change()

    def test_direct_discount_edit_no_stock_and_no_current_catalog_price(self):
        sale = self.sale()
        item = sale.cd_items.get()
        edit_postpay_sale_items(actor=self.user, sale_id=sale.pk, lines=[{'product_type': 'cd', 'product_id': self.cd.pk,
            'item_id': item.pk, 'quantity': 10, 'unit_discount': 100}], note='Скидка')
        item.refresh_from_db(); sale.refresh_from_db()
        self.assertEqual(item.unit_price, 3500); self.assertEqual(item.unit_cost_snapshot, 2720)
        self.assertEqual(sale.total_amount, 34000)
        self.no_stock_change()

    def test_direct_composition_tampering_blocked_atomically(self):
        with self.assertRaises(ValidationError): self.sale(lines=[{'product_type': 'cd', 'product_id': self.cd.pk, 'quantity': 1}])
        self.assertFalse(Sale.objects.exists()); self.assertFalse(TripOrderOperation.objects.exists())
        sale = self.sale(); item = sale.cd_items.get()
        with self.assertRaises(ValidationError):
            edit_postpay_sale_items(actor=self.user, sale_id=sale.pk, lines=[{'product_type':'cd', 'product_id':self.cd.pk,
                'item_id':item.pk, 'quantity':1}], note='Изменение')
        self.no_stock_change()

    def test_supply_pending_then_accepted_then_cancel(self):
        supply = self.supply()
        self.assertEqual(supply.status, 'price_review')
        self.stock_order.refresh_from_db(); self.assertEqual(self.stock_order.status, 'receiving')
        self.assertEqual(supply.cd_items.get().effective_unit_cost, 2720)
        self.no_stock_change()
        confirm_supply_price_review(actor=self.user, supply_id=supply.pk)
        self.stock_order.refresh_from_db(); self.assertEqual(self.stock_order.status, 'completed')
        self.stock.refresh_from_db(); self.assertEqual(self.stock.quantity, 7)
        cancel_supply(actor=self.user, supply_id=supply.pk, comment='Отмена')
        self.stock_order.refresh_from_db()
        self.assertIsNone(self.stock_order.supply_id)
        self.assertEqual(self.stock_order.fulfillment_label, 'Принят')
        self.no_stock_change()

    def test_pending_cancel_and_duplicate_supply(self):
        draft = self.draft(self.stock_order)
        supply = self.supply(draft)
        self.assertEqual(self.supply(draft).pk, supply.pk)
        with self.assertRaises(ValidationError): self.supply()
        cancel_supply(actor=self.user, supply_id=supply.pk, comment='Отмена')
        self.stock_order.refresh_from_db()
        self.assertEqual(self.stock_order.fulfillment_label, 'Принят')
        self.assertNotEqual(self.supply().pk, supply.pk)
        self.no_stock_change()

    def test_supply_snapshot_cannot_add_delivery_twice(self):
        supply = self.supply()
        row = supply.cd_items.get()
        with self.assertRaises(ValidationError):
            edit_pending_supply(actor=self.user, supply_id=supply.pk, expected_revision_number=1,
                warehouse_id=self.warehouse.pk, lines=[{'product_type':'cd', 'product_id':self.cd.pk,
                    'supplier_id':self.supplier.pk, 'quantity':2, 'purchase_unit_cost':row.purchase_unit_cost}],
                weight_transport_cost=100)
        self.assertEqual(supply.cd_items.get().effective_unit_cost, 2720)

    def test_sale_duplicate_idempotent_and_independent_new_key_blocked(self):
        draft = self.draft(); sale = self.sale(draft)
        self.assertEqual(self.sale(draft).pk, sale.pk)
        with self.assertRaises(ValidationError): self.sale()
        self.assertEqual(Sale.objects.count(), 1)

    def test_rates_frozen_and_changed_trip_price_rejects_stale_draft(self):
        draft = self.draft(); sale = self.sale(draft)
        self.price.exchange_rate_aed_rub = 40; self.price.save(update_fields=('exchange_rate_aed_rub',))
        self.assertEqual(sale.cd_items.get().unit_cost_snapshot, 2720)
        self.assertEqual(sale.trip_operation.aed_rub, Decimal('24.5'))
        draft = self.draft(self.stock_order)
        line = self.stock_order.items.get().trip_allocations.get().line
        line.supplier_price_aed_snapshot = 110; line.save(update_fields=('supplier_price_aed_snapshot',))
        with self.assertRaises(ValidationError): self.supply(draft)
        self.assertEqual(self.supply().cd_items.get().effective_unit_cost, 2965)

    def test_separate_prepayment_postpayment_prices_and_discounts_once(self):
        item=self.order.items.get();item.prepayment_quantity=2;item.postpayment_quantity=8
        item.postpayment_unit_price=3600;item.save()
        allocation=item.trip_allocations.get();allocation.prepayment_quantity=2;allocation.postpayment_quantity=8;allocation.save()
        draft=self.draft();rows=draft['calculation']['rows']
        self.assertEqual([r['unit_price'] for r in rows],['3500.00','3600.00'])
        lines=[{'product_type':'cd','product_id':self.cd.pk,'quantity':r['quantity'],'unit_discount':100} for r in rows]
        from .operation_changes import ChangesConfirmationRequired
        with self.assertRaises(ChangesConfirmationRequired) as review:
            self.sale(draft,lines=lines,note='Скидка один раз')
        sale=self.sale(draft,lines=lines,note='Скидка один раз',changes_confirmation=review.exception.token)
        self.assertEqual(sale.total_amount,34800)
        self.assertEqual(list(sale.cd_items.values_list('unit_price','unit_discount')),
            [(Decimal('3500'),Decimal('100')),(Decimal('3600'),Decimal('100'))])
        self.no_stock_change()

    def test_prepaid_cannot_be_paid_again_as_zero_and_cost_snapshot_is_immutable(self):
        register=CashRegister.objects.get(warehouse=self.warehouse)
        register.balance=1000;register.save(update_fields=('balance',))
        CashTransaction.objects.create(cash_register=register,customer_order=self.order,amount=1000,
            operation_type=CashTransaction.OperationType.CUSTOMER_ORDER_PREPAYMENT,created_by=self.user,comment='Аванс')
        self.order.payment_warehouse=self.warehouse;self.order.save(update_fields=('payment_warehouse',))
        sale=self.sale()
        with self.assertRaises(ValidationError):mark_sale_paid(actor=self.user,sale_id=sale.pk,cash_received_amount=0)
        self.partner.creditor.refresh_from_db();self.assertEqual(self.partner.creditor.current_debt,0)
        operation=sale.trip_operation;operation.aed_rub=30
        with self.assertRaises(ValidationError):operation.save()
        sale.direct_delivery=False
        with self.assertRaises(ValidationError):sale.save()
        self.no_stock_change()

    def test_buttons_only_trip_purpose_and_yellow_links(self):
        self.assertContains(self.client.get(reverse('orders:detail', args=[self.order.pk])), 'Создать продажу')
        self.assertContains(self.client.get(reverse('orders:detail', args=[self.stock_order.pk])), 'Создать приход')
        plain = self.make_order('customer', 1)
        self.assertNotContains(self.client.get(reverse('orders:detail', args=[plain.pk])), 'operation/')
        sale = self.sale()
        response = self.client.get(reverse('orders:detail', args=[self.order.pk]))
        self.assertContains(response, 'Открыть продажу'); self.assertContains(response, 'order-operation-processing')
        self.assertNotContains(response, 'Создать продажу')
        self.assertContains(self.client.get(reverse('orders:list')), 'order-operation-processing')
        self.assertContains(self.client.get(reverse('orders:trip_detail', args=[self.trip.pk])), 'Привезён на склад')

    def test_list_and_trip_offer_create_actions_for_each_available_order(self):
        self.arrive_for_http()
        for url in (reverse('orders:list'), reverse('orders:trip_detail', args=[self.trip.pk])):
            with self.subTest(url=url):
                response=self.client.get(url)
                self.assertContains(response, f'href="{reverse("orders:operation_prepare", args=[self.order.pk])}"')
                self.assertContains(response, f'href="{reverse("orders:operation_prepare", args=[self.stock_order.pk])}"')
                self.assertContains(response, 'Создать продажу')
                self.assertContains(response, 'Создать приход')

    def test_order_list_sections_unassigned_selection_and_collapsed_all_orders(self):
        unassigned=self.make_order('customer',1)
        response=self.client.get(reverse('orders:list'))
        self.assertEqual([order.pk for order in response.context['unassigned_orders']],[unassigned.pk])
        body=response.content.decode()
        self.assertLess(body.index('id="formed-trips"'),body.index('id="unassigned-orders"'))
        self.assertLess(body.index('id="unassigned-orders"'),body.index('aria-controls="all-orders-content"'))
        self.assertContains(response,'aria-expanded="false" aria-controls="all-orders-content"')
        self.assertContains(response,'id="all-orders-content" class="collapsible-content" hidden')
        unassigned_html=body.split('id="unassigned-orders"',1)[1].split('</section>',1)[0]
        self.assertIn(reverse('orders:detail',args=[unassigned.pk]),unassigned_html)
        self.assertNotIn(reverse('orders:detail',args=[self.order.pk]),unassigned_html)
        self.assertEqual(body.count(f'name="order_id" value="{unassigned.pk}"'),1)
        self.assertNotIn('name="order_id"',body.split('id="all-orders-content"',1)[1])
        self.assertNotContains(response,'<th class="numeric">Предоплата</th>')
        self.assertNotContains(response,'<th class="numeric">Постоплата</th>')

    def test_unassigned_list_preserves_customer_only_visibility_without_supplier_price_permission(self):
        from django.contrib.auth.models import Permission
        customer=self.make_order('customer',1)
        stock=self.make_order('stock',1)
        viewer=User.objects.create_user('unassigned-viewer')
        viewer.user_permissions.add(Permission.objects.get(content_type__app_label='orders',codename='view_orders'))
        self.client.force_login(viewer)
        response=self.client.get(reverse('orders:list'))
        self.assertEqual([order.pk for order in response.context['unassigned_orders']],[customer.pk])
        self.assertNotIn(stock.pk,[order.pk for order in response.context['orders']])
        self.assertNotContains(response,'id="unassigned-trip-form"')
        self.assertNotContains(response,'id="formed-trips"')

    def test_list_replaces_create_with_current_operation_and_checks_permissions(self):
        from django.contrib.auth.models import Permission
        sale=self.sale()
        response=self.client.get(reverse('orders:list'))
        self.assertNotContains(response, f'href="{reverse("orders:operation_prepare", args=[self.order.pk])}"')
        self.assertContains(response, f'href="{reverse("sales:detail", args=[sale.pk])}"')
        viewer=User.objects.create_user('operation-list-viewer')
        viewer.user_permissions.set(Permission.objects.filter(codename__in=('view_orders','view_order_detail','view_supplier_prices')))
        self.client.force_login(viewer)
        response=self.client.get(reverse('orders:list'))
        self.assertNotContains(response,'Создать продажу')
        self.assertNotContains(response,'Создать приход')
        self.assertEqual(self.client.get(reverse('orders:operation_prepare',args=[self.stock_order.pk])).status_code,403)

    def test_metadata_all_missing_products_codes_required_barcode_optional(self):
        self.arrive_for_http()
        self.cd.cusa_ppsa_code=''; self.cd.save(update_fields=('cusa_ppsa_code',))
        url = reverse('orders:operation_prepare', args=[self.stock_order.pk])
        response = self.client.get(url)
        self.assertContains(response, 'CUSA/PPSA через запятую'); self.assertContains(response, 'Штрихкод (необязательно)')
        data = {'usd_rub':'90','usd_aed':'3.673469'}
        self.assertEqual(self.client.post(url,data).status_code,200)
        self.cd.refresh_from_db(); self.assertEqual(self.cd.cusa_ppsa_code,'')
        data[f'cd-{self.cd.pk}-codes']='ppsa00001, PPSA-00001, CUSA-00002'
        self.assertEqual(self.client.post(url,data).status_code,302)
        self.cd.refresh_from_db(); self.assertEqual(self.cd.cusa_ppsa_code,'PPSA-00001, CUSA-00002')
        self.assertEqual(self.cd.weight_grams,100)
        self.assertFalse(BarcodeRegistry.objects.filter(cd=self.cd).exists())

    def tech_order(self):
        tech=Tech.objects.create(name='Устройство', sku='FX-T', brand=Brand.objects.create(name='Марка'),
            product_type=ProductType.objects.create(name='Консоль'), weight_grams=None)
        source=ProcurementPriceListItem.objects.create(price_list=self.price,product_kind='tech',tech=tech,
            product_name_snapshot=tech.name,article_snapshot=tech.sku,selected_supplier=self.supplier,
            supplier_price_aed=100,exchange_rate_aed_rub=20,base_price_rub=2000,delivery_rub=240,
            weight_grams_snapshot=500,delivery_usdt_per_kg_snapshot=6,prepayment_price_rub=3500,postpayment_price_rub=3500)
        order=create_customer_procurement_order(actor=self.user,price_list_id=self.price.pk,purpose='stock',recipient='Склад',comment='',
            lines=[{'price_list_item_id':source.pk,'prepayment_quantity':3,'postpayment_quantity':0}])
        create_trip(actor=self.user,order_ids=[order.pk],creation_key=uuid4())
        order.refresh_from_db()
        return tech,order

    def test_tech_saved_delivery_weight_required_and_codes_exempt(self):
        from .models import SupplierOrderBatch
        from .arrival_models import TripArrival
        from .arrival_documents import create_arrival_supply
        tech,order=self.tech_order()
        self.assertEqual(self.draft(order)['calculation']['rows'][0]['unit_cost'],'2720.00')
        with self.assertRaises(ValidationError):self.supply(self.draft(order))
        batch=SupplierOrderBatch.objects.get(pk=order.trip_id)
        payload={'action':'confirm','revision':batch.revision,'actual_delivery':'810','usdt_rub':'90','usdt_aed':'3.673469'}
        response=self.client.post(reverse('orders:trip_arrival',args=[batch.pk]),payload)
        self.assertFalse(TripArrival.objects.filter(trip=batch).exists())
        payload[f'weight_tech_{tech.pk}']='2000'
        self.client.post(reverse('orders:trip_arrival',args=[batch.pk]),payload)
        arrival=TripArrival.objects.get(trip=batch)
        response=self.client.get(reverse('orders:operation_prepare',args=[order.pk]))
        self.assertNotContains(response,'CUSA/PPSA через запятую')
        tech.refresh_from_db();self.assertEqual(tech.weight_grams,2000)
        supply=create_arrival_supply(actor=self.user,arrival_id=arrival.pk,order_id=order.pk,
            expected_revision=arrival.revision,warehouse_id=self.warehouse.pk)
        self.assertEqual(supply.tech_items.get().effective_unit_cost,2720)

    def test_direct_tech_without_warehouse_stock_never_creates_stock(self):
        from warehouse.models import TechWarehouseStock
        tech,unused=self.tech_order()
        source=tech.procurement_price_items.get()
        order=create_customer_procurement_order(actor=self.user,price_list_id=self.price.pk,purpose='customer',
            partner_id=self.partner.pk,recipient=self.partner.name,comment='',
            lines=[{'price_list_item_id':source.pk,'prepayment_quantity':0,'postpayment_quantity':4}])
        create_trip(actor=self.user,order_ids=[order.pk],creation_key=uuid4())
        order.refresh_from_db();sale=self.sale(self.draft(order),payment_method='bank_account')
        self.assertEqual(sale.tech_items.get().unit_cost_snapshot,2720)
        self.assertFalse(TechWarehouseStock.objects.filter(tech=tech).exists())
        cancel_sale(actor=self.user,sale_id=sale.pk,comment='Отмена')
        tech.refresh_from_db();self.assertEqual(tech.cost,0)
        self.assertFalse(TechWarehouseStock.objects.filter(tech=tech).exists())

    def test_five_missing_codes_all_validated_and_barcode_conflict_rolls_back(self):
        products=[];lines=[]
        for number in range(5):
            product=CD.objects.create(name=f'PS4 игра {number}',sku=f'FX-{number}',platform=self.cd.platform,weight_grams=120)
            source=ProcurementPriceListItem.objects.create(price_list=self.price,product_kind='cd',cd=product,
                product_name_snapshot=product.name,article_snapshot=product.sku,selected_supplier=self.supplier,
                supplier_price_aed=100,exchange_rate_aed_rub=20,base_price_rub=2000,delivery_rub=240,
                prepayment_price_rub=3500,postpayment_price_rub=3500)
            products.append(product);lines.append({'price_list_item_id':source.pk,'prepayment_quantity':1,'postpayment_quantity':0})
        order=create_customer_procurement_order(actor=self.user,price_list_id=self.price.pk,purpose='stock',recipient='Склад',comment='',lines=lines)
        create_trip(actor=self.user,order_ids=[order.pk],creation_key=uuid4())
        self.arrive_for_http(order)
        url=reverse('orders:operation_prepare',args=[order.pk])
        response=self.client.get(url);self.assertEqual(len(response.context['metadata']),5)
        data={'usd_rub':'90','usd_aed':'3.673469'}
        for product in products[:-1]:data[f'cd-{product.pk}-codes']='PPSA-00001'
        self.assertEqual(self.client.post(url,data).status_code,200)
        self.assertEqual(CD.objects.filter(pk__in=[p.pk for p in products],cusa_ppsa_code='').count(),5)
        data[f'cd-{products[-1].pk}-codes']='PPSA-00002'
        BarcodeRegistry.objects.create(product_kind='cd',cd=self.cd,value='0001234567890')
        data[f'cd-{products[-1].pk}-barcode']='0001234567890'
        response=self.client.post(url,data);self.assertEqual(response.status_code,200)
        self.assertEqual(CD.objects.filter(pk__in=[p.pk for p in products],cusa_ppsa_code='').count(),5)
        del data[f'cd-{products[-1].pk}-barcode']
        self.assertEqual(self.client.post(url,data).status_code,302)

    def test_non_playstation_platform_needs_no_codes(self):
        self.cd.platform=Platform.objects.create(name='NS2');self.cd.cusa_ppsa_code=''
        self.cd.save(update_fields=('platform','cusa_ppsa_code'))
        self.assertIsNotNone(self.supply().pk)

    def test_barcode_global_leading_zeros_and_existing_no_prompt(self):
        self.arrive_for_http()
        url = reverse('orders:operation_prepare', args=[self.stock_order.pk])
        response = self.client.post(url, {'usd_rub':'90','usd_aed':'3.673469', f'cd-{self.cd.pk}-barcode':'0001234567890'})
        self.assertEqual(response.status_code,302)
        self.assertEqual(BarcodeRegistry.objects.get(cd=self.cd).value,'0001234567890')
        self.assertNotContains(self.client.get(url,follow=True),'Штрихкод (необязательно)')

    def test_missing_codes_backend_both_creation_and_acceptance(self):
        self.cd.cusa_ppsa_code=''; self.cd.save(update_fields=('cusa_ppsa_code',))
        with self.assertRaises(ValidationError): self.supply()
        self.assertFalse(Supply.objects.exists())
        self.cd.cusa_ppsa_code='PPSA-00001'; self.cd.save(update_fields=('cusa_ppsa_code',))
        supply=self.supply()
        self.cd.cusa_ppsa_code=''; self.cd.save(update_fields=('cusa_ppsa_code',))
        with self.assertRaises(ValidationError): confirm_supply_price_review(actor=self.user,supply_id=supply.pk)
        self.no_stock_change()

    def test_prepare_no_operation_standard_sale_and_supply_forms(self):
        arrival=self.arrive_for_http()
        response=self.client.post(reverse('orders:operation_prepare',args=[self.order.pk]),{'usd_rub':'90','usd_aed':'3.673469'})
        self.assertEqual(response.status_code,302)
        page=self.client.get(response.url); self.assertContains(page,'2720.00')
        self.assertContains(page,'data-trip-editable="true"'); self.assertFalse(Sale.objects.exists())
        draft=next(iter(self.client.session[DRAFTS].values()))
        response=self.client.post(response.url,{'trip_draft':draft['key'],'warehouse':self.warehouse.pk,
            'payment_method':'cash_postpay','product_type':['cd'],'product_id':[self.cd.pk],'quantity':[10],'trip_row':[str(arrival.rows.get(order=self.order).pk)],'unit_discount':[0], 'avito_commission_enabled':['0']})
        self.assertEqual(response.status_code,302); self.assertEqual(Sale.objects.count(),1)
        response=self.client.post(reverse('orders:operation_prepare',args=[self.stock_order.pk]),{'usd_rub':'90','usd_aed':'3.673469'})
        page=self.client.get(response.url);self.assertContains(page,'initial-supply-lines')
        draft=list(self.client.session[DRAFTS].values())[-1]
        response=self.client.post(response.url,{'trip_draft':draft['key'],'warehouse_id':self.warehouse.pk,
            'product_type':['cd'],'product_id':[self.cd.pk],'supplier_id':[self.supplier.pk],
            'quantity':['2'],'purchase_unit_cost':['2720.00'],'trip_row':[str(arrival.rows.get(order=self.stock_order).pk)],'weight_transport_cost':'0'})
        self.assertEqual(response.status_code,302);self.assertEqual(Supply.objects.count(),1)

    def test_permissions_and_no_manual_complete(self):
        viewer=User.objects.create_user('no-permissions')
        with self.assertRaises(PermissionDenied): self.sale(actor=viewer)
        self.order.status='receiving';self.order.save(update_fields=('status',))
        with self.assertRaises(ValidationError): advance_procurement(actor=self.user,order_id=self.order.pk,next_status='completed')
        self.assertEqual(Sale.objects.count(),0)

    def test_old_order_prepaid_not_credited_twice_and_retained_on_cancel(self):
        item=self.order.items.get();item.prepayment_quantity=4;item.postpayment_quantity=6
        item.save(update_fields=('prepayment_quantity','postpayment_quantity'))
        self.order.prepayment_total=14000;self.order.postpayment_total=21000;self.order.save()
        # Распределение также сохраняет две ценовые части.
        allocation=item.trip_allocations.get();allocation.prepayment_quantity=4;allocation.postpayment_quantity=6;allocation.save()
        advance_procurement(actor=self.user,order_id=self.order.pk,next_status='confirmed',warehouse_id=self.warehouse.pk)
        sale=self.sale(payment_method='cash')
        self.assertEqual(sale.procurement_prepaid_amount,14000)
        self.assertEqual(CashRegister.objects.get(warehouse=self.warehouse).balance,35000)
        self.assertEqual(sale.cash_transactions.get().amount,21000)
        cancel_sale(actor=self.user,sale_id=sale.pk,comment='Отмена')
        self.assertEqual(CashRegister.objects.get(warehouse=self.warehouse).balance,14000)
        self.order.refresh_from_db()
        new=self.sale(payment_method='cash')
        self.assertEqual(new.procurement_prepaid_amount,14000)
        self.assertEqual(CashRegister.objects.get(warehouse=self.warehouse).balance,35000)


class TripFulfillmentConcurrencyTests(FulfillmentFixture, TransactionTestCase):
    def parallel(self, actions):
        barrier=Barrier(2)
        def run(action):
            try:
                barrier.wait(timeout=10)
                try:return action()
                except ValidationError:return None
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(run, actions))

    def test_two_sales_only_one_active(self):
        a,b=self.draft(),self.draft()
        self.parallel([lambda:self.sale(a),lambda:self.sale(b)])
        self.assertEqual(Sale.objects.count(),1)
        self.assertEqual(self.order.operations.filter(active=True).count(),1)
        self.no_stock_change()

    def test_two_supplies_only_one_active(self):
        a,b=self.draft(self.stock_order),self.draft(self.stock_order)
        self.parallel([lambda:self.supply(a),lambda:self.supply(b)])
        self.assertEqual(Supply.objects.count(),1)
        self.assertEqual(self.stock_order.operations.filter(active=True).count(),1)
        self.no_stock_change()

    def test_same_draft_two_requests_return_one_sale(self):
        draft=self.draft()
        sales=self.parallel([lambda:self.sale(draft),lambda:self.sale(draft)])
        self.assertEqual({s.pk for s in sales},set(Sale.objects.values_list('pk',flat=True)))
        self.assertEqual(Sale.objects.count(),1)
