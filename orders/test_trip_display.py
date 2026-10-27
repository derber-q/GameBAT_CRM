"""Порядок товаров внутри каждого поставщика без изменения партий рейса."""
from uuid import uuid4

from django.contrib.auth.models import Permission
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from accounts.models import User
from catalog.models import Brand, CD, Platform, ProductType, Tech
from partners.models import Supplier
from price.services import create_procurement_price_list
from pricing.models import SupplierCDPrice, SupplierTechPrice
from .services import create_customer_procurement_order
from .trips import change_trip_line, create_trip


class TripDisplayTests(TestCase):
    def test_platform_and_type_groups_repeat_for_each_supplier_without_writes(self):
        user = User.objects.create_superuser('trip-display-admin')
        suppliers = [Supplier.objects.create(name=f'Поставщик {letter}', letter=letter,
            priority=index, legal_entity=letter, phone_1='1', highlight_color='#37A7BA')
            for index, letter in enumerate('AB', 1)]
        brands = {name: Brand.objects.create(name=name) for name in ('Sony', 'Nintendo')}
        types = {name: ProductType.objects.create(name=name) for name in ('Гарнитуры', 'Геймпады')}
        products = [Tech.objects.create(name=name, brand=brands[brand], product_type=types[kind],
            sku=f'T-{index}', weight_grams=1000)
            for index, (name, brand, kind) in enumerate((
                ('Альфа геймпад', 'Sony', 'Геймпады'),
                ('Яркий геймпад', 'Nintendo', 'Геймпады'),
                ('Яркая гарнитура', 'Sony', 'Гарнитуры'),
            ))]
        platforms = {name: Platform.objects.create(name=name)
            for name in ('PS4', 'PS5', 'Nintendo Switch', 'Nintendo Switch 2')}
        products += [CD.objects.create(name=name, platform=platforms[platform], sku=f'C-{index}')
            for index, (name, platform) in enumerate((
                ('Альфа Switch', 'Nintendo Switch'), ('Яркая Switch 2', 'Nintendo Switch 2'),
                ('Яркая PS4', 'PS4'), ('Яркая PS5', 'PS5'), ('Альфа PS5', 'PS5'),
            ))]
        for product in products:
            kind = 'cd' if isinstance(product, CD) else 'tech'
            price_model = SupplierCDPrice if kind == 'cd' else SupplierTechPrice
            for index, supplier in enumerate(suppliers):
                price_model.objects.create(supplier=supplier, **{kind: product}, price=100 + index * 10)
        price = create_procurement_price_list(actor=user, exchange_rate_usdt_aed=4,
            exchange_rate_usdt_rub=80, delivery_general_usdt_per_kg=0,
            delivery_devices_usdt_per_kg=0, delivery_storage_usdt_per_kg=0, delivery_cd_rub=0,
            postpayment_surcharges={product.pk: 0 for product in products if isinstance(product, Tech)})
        order = create_customer_procurement_order(actor=user, price_list_id=price.pk,
            recipient='Заказчик', comment='', lines=[{'price_list_item_id': item.pk,
                'prepayment_quantity': 2, 'postpayment_quantity': 0} for item in price.items.all()])
        trip = create_trip(actor=user, order_ids=[order.pk], creation_key=uuid4())
        for line in list(trip.lines.all()):
            trip.refresh_from_db()
            change_trip_line(actor=user, batch_id=trip.pk, line_id=line.pk, revision=trip.revision,
                quantity=1, action='transfer', target_supplier_id=suppliers[1].pk,
                price_supplier_id=suppliers[0].pk)
        before = list(trip.lines.values())
        self.client.force_login(user)
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse('orders:trip_detail', args=(trip.pk,)))
        self.assertEqual(response.status_code, 200)
        expected = ['Яркая гарнитура', 'Альфа геймпад', 'Яркий геймпад',
            'Яркая Switch 2', 'Альфа Switch', 'Яркая PS4', 'Альфа PS5', 'Яркая PS5']
        groups = list(response.context['supplier_groups'])
        self.assertEqual([supplier.pk for supplier, _ in groups], [supplier.pk for supplier in suppliers])
        for _, lines in groups:
            self.assertEqual([line.product_name_snapshot for line in lines], expected)
            self.assertTrue(all(line.quantity == 1 for line in lines))
        self.assertContains(response, 'Техника · Геймпады', count=2)
        self.assertContains(response, 'Диски · PS5', count=2)
        self.assertContains(response, 'scope="rowgroup" colspan="7"', count=12)
        self.assertContains(response, 'css/order-trips.css?v=5')
        self.assertFalse(any(query['sql'].lstrip().upper().startswith(('INSERT ', 'UPDATE ', 'DELETE '))
            for query in queries))
        self.assertEqual(list(trip.lines.values()), before)

        viewer = User.objects.create_user('trip-display-viewer')
        viewer.user_permissions.set(Permission.objects.filter(codename__in=(
            'generate_supplier_orders', 'view_supplier_details')))
        self.client.force_login(viewer)
        response = self.client.get(reverse('orders:trip_detail', args=(trip.pk,)))
        self.assertContains(response, 'scope="rowgroup" colspan="3"', count=12)
        self.assertNotContains(response, 'data-trip-price-edit=')
