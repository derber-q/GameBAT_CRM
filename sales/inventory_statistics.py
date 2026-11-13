"""Текущая стоимость физического остатка, отдельно от исторических продаж."""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from catalog.product_ordering import normalized_order_name, platform_order_key
from warehouse.models import CDWarehouseStock, TechWarehouseStock, Warehouse


@transaction.atomic
def build_inventory_statistics():
    """Один согласованный снимок; суммы считаются Decimal без SQLite REAL и N+1."""
    zero = Decimal('0.00')
    warehouses = {warehouse.pk: {
        'id': warehouse.pk, 'name': warehouse.name, 'units': 0,
        'cd_units': 0, 'tech_units': 0, 'cd_cost': zero, 'tech_cost': zero,
        'total_cost': zero, 'platforms': {}, 'product_types': {},
    } for warehouse in Warehouse.objects.all()}
    for model, product, category, groups in (
        (CDWarehouseStock, 'cd', 'platform', 'platforms'),
        (TechWarehouseStock, 'tech', 'product_type', 'product_types'),
    ):
        stocks = model.objects.filter(quantity__gt=0).values(
            'warehouse_id', 'quantity', f'{product}__cost',
            f'{product}__{category}_id', f'{product}__{category}__name',
        )
        for stock in stocks:
            warehouse = warehouses[stock['warehouse_id']]
            quantity = stock['quantity']
            cost = stock[f'{product}__cost'] * quantity
            category_id = stock[f'{product}__{category}_id']
            name = stock[f'{product}__{category}__name'] or ('Без платформы' if product == 'cd' else 'Без типа')
            group = warehouse[groups].setdefault(category_id, {'name': name, 'units': 0, 'cost': zero})
            group['units'] += quantity
            group['cost'] += cost
            warehouse[f'{product}_units'] += quantity
            warehouse[f'{product}_cost'] += cost
            warehouse['units'] += quantity
            warehouse['total_cost'] += cost
    for warehouse in warehouses.values():
        warehouse['platforms'] = sorted(warehouse['platforms'].values(), key=lambda row: platform_order_key(row['name']))
        warehouse['product_types'] = sorted(warehouse['product_types'].values(), key=lambda row: normalized_order_name(row['name']))
    return {
        'as_of': timezone.now(), 'warehouses': list(warehouses.values()),
        'units': sum(row['units'] for row in warehouses.values()),
        'cd_cost': sum((row['cd_cost'] for row in warehouses.values()), zero),
        'tech_cost': sum((row['tech_cost'] for row in warehouses.values()), zero),
        'total_cost': sum((row['total_cost'] for row in warehouses.values()), zero),
    }
