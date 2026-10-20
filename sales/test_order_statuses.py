"""Удаление промежуточного статуса сохраняет денежные снимки и историю продаж."""
import importlib
from types import SimpleNamespace

from django.apps import apps
from django.db import connection
from django.test import TestCase

from accounts.models import User
from catalog.models import CD, Platform
from warehouse.models import Warehouse, CDWarehouseStock
from cash.models import CashTransaction
from .models import Sale, SaleCDItem
from .services import create_sale, mark_sale_paid, cancel_sale, next_order_status


class RemovedShippedStatusTests(TestCase):
    def test_legacy_migration_preserves_finances_dates_items_and_cancellation(self):
        actor = User.objects.create_superuser('removed-status')
        warehouse = Warehouse.objects.create(name='Склад')
        product = CD.objects.create(platform=Platform.objects.create(name='PS5'), name='Игра', avito_price='100.01', cost='70')
        stock = CDWarehouseStock.objects.create(warehouse=warehouse, cd=product, quantity=10)
        sales = []
        for _ in range(4):
            sales.append(create_sale(actor=actor, warehouse_id=warehouse.pk, price_type='retail',
                sale_type='retail', payment_method='bank_transfer_postpay',
                lines=[{'product_type': 'cd', 'product_id': product.pk, 'quantity': 1}]))
        for sale in sales[:3]:
            # Историческое значение намеренно имитируется до применения миграции.
            sale.order_status = 'shipped'
            sale.save(update_fields=['order_status'])
        mark_sale_paid(actor=actor, sale_id=sales[0].pk)
        cancel_sale(actor=actor, sale_id=sales[2].pk, comment='Историческая отмена')
        before = list(Sale.objects.order_by('pk').values())
        items = list(SaleCDItem.objects.order_by('pk').values())
        stock.refresh_from_db()
        quantity = stock.quantity
        migrate = importlib.import_module('sales.migrations.0021_remove_shipped_status').remove_shipped_status
        editor = SimpleNamespace(connection=connection)
        migrate(apps, editor)
        after = list(Sale.objects.order_by('pk').values())
        for old, new in zip(before, after):
            self.assertEqual(new['order_status'], 'assembled' if old['order_status'] == 'shipped' else old['order_status'])
            self.assertEqual({k: v for k, v in old.items() if k != 'order_status'},
                             {k: v for k, v in new.items() if k != 'order_status'})
        self.assertEqual(list(SaleCDItem.objects.order_by('pk').values()), items)
        stock.refresh_from_db()
        self.assertEqual(stock.quantity, quantity)
        self.assertFalse(CashTransaction.objects.exists())
        paid = Sale.objects.get(pk=sales[0].pk)
        self.assertFalse(paid.is_completed)
        self.assertIsNone(paid.completed_at)
        self.assertEqual(next_order_status(paid), Sale.OrderStatus.DELIVERED)
        self.assertTrue(Sale.objects.get(pk=sales[2].pk).is_cancelled)
        migrate(apps, editor)
        self.assertEqual(list(Sale.objects.order_by('pk').values()), after)
        self.assertEqual(Sale.OrderStatus.values, ['created', 'assembled', 'delivered'])
