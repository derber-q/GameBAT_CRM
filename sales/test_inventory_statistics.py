"""Согласованность складских сумм, группировки и прав; без внешних сервисов."""
from decimal import Decimal

from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from catalog.models import Brand, CD, Platform, ProductType, Tech
from warehouse.models import CDWarehouseStock, TechWarehouseStock, Warehouse
from .inventory_statistics import build_inventory_statistics


class InventoryStatisticsTests(TestCase):
    def setUp(self):
        self.warehouse = Warehouse.objects.create(name='А склад')
        self.second = Warehouse.objects.create(name='Б склад')
        self.empty = Warehouse.objects.create(name='Пустой склад')
        ps5 = Platform.objects.create(name='PlayStation 5')
        switch = Platform.objects.create(name='Nintendo Switch 2')
        self.game = CD.objects.create(name='Игра', platform=ps5, cost='100.11', wholesale_price='900')
        self.other = CD.objects.create(name='Другая игра', platform=switch, cost='200.22')
        CDWarehouseStock.objects.create(warehouse=self.warehouse, cd=self.game, quantity=3)
        CDWarehouseStock.objects.create(warehouse=self.warehouse, cd=self.other, quantity=2)
        CDWarehouseStock.objects.create(warehouse=self.second, cd=self.game, quantity=4)
        brand = Brand.objects.create(name='Sony')
        kind = ProductType.objects.create(name='Геймпад')
        pad = Tech.objects.create(name='Геймпад', brand=brand, product_type=kind, cost='50.05')
        TechWarehouseStock.objects.create(warehouse=self.warehouse, tech=pad, quantity=2)

    def test_values_use_physical_quantity_and_cost_with_empty_warehouses(self):
        data = build_inventory_statistics()
        rows = {r['id']: r for r in data['warehouses']}
        first = rows[self.warehouse.pk]
        self.assertEqual(first['cd_cost'], Decimal('700.77'))
        self.assertEqual(first['tech_cost'], Decimal('100.10'))
        self.assertEqual(first['total_cost'], Decimal('800.87'))
        self.assertEqual(first['units'], 7)
        self.assertEqual(sum((r['cost'] for r in first['platforms']), Decimal('0')), first['cd_cost'])
        self.assertEqual(sum((r['cost'] for r in first['product_types']), Decimal('0')), first['tech_cost'])
        self.assertEqual(rows[self.empty.pk]['total_cost'], Decimal('0.00'))
        self.assertEqual(rows[self.empty.pk]['platforms'], [])
        self.assertEqual(data['total_cost'], Decimal('1201.31'))
        self.assertEqual(data['units'], 11)

    def test_zero_stock_excluded_but_archived_physical_stock_counted(self):
        zero = CD.objects.create(name='Нулевой остаток', platform=self.game.platform, cost='99999')
        CDWarehouseStock.objects.create(warehouse=self.warehouse, cd=zero, quantity=0)
        self.game.is_archived = True
        self.game.save(update_fields=['is_archived'])
        self.assertEqual(build_inventory_statistics()['total_cost'], Decimal('1201.31'))

    def test_statistics_permission_and_sales_filters_do_not_hide_inventory(self):
        user = User.objects.create_user('inventory-statistics')
        self.client.force_login(user)
        url = reverse('statistics:index')
        self.assertEqual(self.client.get(url).status_code, 403)
        user.user_permissions.add(Permission.objects.get(content_type__app_label='sales', codename='view_sales_statistics'))
        response = self.client.get(url, {'date_from':'2000-01-01', 'date_to':'2000-01-02', 'warehouse':self.second.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['inventory']['total_cost'], Decimal('1201.31'))
        self.assertContains(response, 'inventory-warehouse-')
