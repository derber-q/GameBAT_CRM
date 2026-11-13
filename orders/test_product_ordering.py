"""Плоский порядок заказов и форм операций соответствует действующему оптовому XLSX."""
from uuid import uuid4
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from catalog.test_product_ordering import create_ordering_fixture
from catalog.models import BarcodeRegistry
from partners.models import Supplier
from price.excel import _warehouse_price_groups
from price.models import ProcurementPriceList, ProcurementPriceListItem
from .arrival import confirm_arrival
from .arrival_documents import form_rows
from .services import create_customer_procurement_order
from .trips import create_trip


class ImportProductOrderingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('import-ordering', password='test')
        self.client.force_login(self.user)
        self.warehouse, tech, cds = create_ordering_fixture()
        groups, _ = _warehouse_price_groups(self.warehouse, price_field='wholesale_price')
        self.expected = [(kind, product.pk) for _, rows in groups for kind, product, *_ in rows]
        supplier = Supplier.objects.create(name='Поставщик порядка', letter='A', legal_entity='A', phone_1='1')
        price = ProcurementPriceList.objects.create(created_by=self.user, exchange_rate_aed_rub=20,
            exchange_rate_usdt_aed=4, exchange_rate_usdt_rub=80, delivery_cd_rub=0)
        sources = []
        # ID и алфавит не должны случайно давать тот же порядок, что оптовый прайс.
        for kind, product in reversed([('tech', p) for p in tech] + [('cd', p) for p in cds]):
            product.weight_grams = 100
            product.save(update_fields=['weight_grams'])
            BarcodeRegistry.objects.create(product_kind=kind, **{kind: product}, value=f'ORDER-{kind}-{product.pk}')
            if kind == 'cd':
                product.cusa_ppsa_code = 'PPSA-00001'
                product.save(update_fields=['cusa_ppsa_code'])
            sources.append(ProcurementPriceListItem.objects.create(price_list=price, product_kind=kind,
                **{kind: product}, product_name_snapshot=product.name, article_snapshot=product.sku,
                selected_supplier=supplier, supplier_price_aed=10, exchange_rate_aed_rub=20,
                base_price_rub=200, delivery_rub=0, prepayment_price_rub=300, postpayment_price_rub=300))
        self.orders = []
        for purpose in ('customer', 'stock'):
            self.orders.append(create_customer_procurement_order(actor=self.user, price_list_id=price.pk,
                purpose=purpose, recipient='Покупатель' if purpose == 'customer' else 'На склад', comment='',
                lines=[{'price_list_item_id': source.pk, 'prepayment_quantity': 1, 'postpayment_quantity': 0}
                       for source in sources]))

    def test_order_details_edit_and_addition_keep_wholesale_order_and_saved_rows(self):
        for order in self.orders:
            before = list(order.items.order_by('pk').values())
            response = self.client.get(reverse('orders:detail', args=[order.pk]))
            self.assertEqual(response.status_code, 200)
            self.assertEqual([(i.product_kind, i.product_id) for i in response.context['ordered_items']], self.expected)
            for url in ('orders:edit', 'orders:add_items'):
                response = self.client.get(reverse(url, args=[order.pk]))
                self.assertEqual(response.status_code, 200)
                self.assertEqual([(r['source'].product_kind, r['source'].product_id)
                                  for r in response.context['rows']], self.expected)
            self.assertEqual(list(order.items.order_by('pk').values()), before)

    def test_arrival_sale_and_supply_forms_keep_quantities_prices_and_references(self):
        trip = create_trip(actor=self.user, order_ids=[o.pk for o in self.orders], creation_key=uuid4())
        arrival = confirm_arrival(actor=self.user, batch_id=trip.pk, expected_revision=trip.revision,
            usdt_rub='80', usdt_aed='4', actual_delivery='0')
        before = list(arrival.rows.order_by('pk').values())
        for order in self.orders:
            rows = form_rows(arrival, order.pk)
            self.assertEqual([(r['product_type'], r['product_id']) for r in rows], self.expected)
            originals = {str(r.pk): r for r in arrival.rows.filter(order=order)}
            self.assertEqual({r['trip_row'] for r in rows}, set(originals))
            for row in rows:
                self.assertEqual(row['quantity'], originals[row['trip_row']].actual_quantity)
            response = self.client.get(reverse('orders:operation_prepare', args=[order.pk]), follow=True)
            self.assertEqual(response.status_code, 200)
            key = 'initial_supply_lines' if order.is_stock_order else 'initial_items'
            self.assertEqual([(r['product_type'], r['product_id']) for r in response.context[key]], self.expected)
        self.assertEqual(list(arrival.rows.order_by('pk').values()), before)
