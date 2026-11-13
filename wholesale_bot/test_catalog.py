"""Каталог использует оптовый остаток и авторизацию, не проводит продажи."""
from decimal import Decimal
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from catalog.models import Brand, ProductType, Tech
from partners.models import Partner
from sales.models import Sale
from warehouse.models import Warehouse, TechWarehouseStock
from .catalog import ROOT, catalog_view
from .handlers import PRICE, process_event, deliver_one
from .models import BotConfig, Customer, Delivery, Event


class CatalogTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_superuser(username='catalog-operator')
        self.warehouse = Warehouse.objects.create(name='Оптовый склад')
        self.config = BotConfig.objects.create(enabled=True, operator=self.actor, warehouse=self.warehouse)
        self.customer = Customer.objects.create(telegram_id=123, status=Customer.Status.AUTHORIZED,
            partner=Partner.objects.create(name='Покупатель каталога'))
        self.brand = Brand.objects.create(name='Sony')
        self.kind = ProductType.objects.create(name='Геймпад')
        self.product = Tech.objects.create(name='PS5 DualSense White', brand=self.brand, product_type=self.kind,
            wholesale_price='900.10', cost='137.89')
        self.stock = TechWarehouseStock.objects.create(warehouse=self.warehouse, tech=self.product, quantity=3)

    def group_callback(self):
        return f'wc:g:{self.brand.pk}:{self.kind.pk}:0'

    def event(self, **payload):
        return Event.objects.create(update_id=Event.objects.count() + 1, customer=self.customer,
            payload={'service_revision':self.config.service_revision, **payload})

    def test_empty_unpriced_archived_and_other_warehouse_items_are_absent(self):
        for name, quantity, price, archived in [('Нет остатка',0,10,False), ('Нет цены',1,None,False), ('Архив',1,10,True)]:
            item = Tech.objects.create(name=name, brand=self.brand, product_type=self.kind,
                wholesale_price=price, is_archived=archived)
            TechWarehouseStock.objects.create(warehouse=self.warehouse, tech=item, quantity=quantity)
        other = Warehouse.objects.create(name='Другой склад')
        item = Tech.objects.create(name='Только другой склад', brand=self.brand, product_type=self.kind, wholesale_price=20)
        TechWarehouseStock.objects.create(warehouse=other, tech=item, quantity=10)
        root = catalog_view()
        self.assertEqual(root['markup']['inline_keyboard'][0][0]['callback_data'], 'wc:s:sony:0')
        submenu = catalog_view('wc:s:sony:0')
        self.assertEqual(submenu['markup']['inline_keyboard'][0][0]['callback_data'], self.group_callback())
        group = catalog_view(self.group_callback())
        buttons = group['markup']['inline_keyboard']
        self.assertEqual(len(buttons), 2)  # Товар и действующий возврат к категориям.
        self.assertIn('900,10', group['text'])
        self.assertIn('3 шт.', group['text'])
        self.assertNotIn('137,89', group['text'])

    def test_price_file_has_inline_catalog_and_delivery_refreshes_empty_stock(self):
        event = self.event(text=PRICE)
        process_event(event, Mock())
        delivery = Delivery.objects.get(key=f'event:{event.pk}')
        self.assertIsNotNone(delivery.document)
        self.assertIn('inline_keyboard', delivery.markup)
        self.stock.quantity = 0
        self.stock.save(update_fields=['quantity'])
        client = Mock()
        deliver_one(client)
        delivery.refresh_from_db()
        self.assertEqual(delivery.state, 'sent')
        self.assertEqual(delivery.markup, {})
        self.assertNotIn('reply_markup', client.call.call_args.args[1])
        self.assertEqual(Sale.objects.count(), 0)

    def test_old_product_button_returns_current_menu_and_current_prices(self):
        self.product.wholesale_price = Decimal('950.00')
        self.product.save(update_fields=['wholesale_price'])
        callback = f'wc:p:{self.product.pk}:0'
        self.assertIn('950,00', catalog_view(callback)['text'])
        self.stock.quantity = 0
        self.stock.save(update_fields=['quantity'])
        self.assertEqual(catalog_view(callback)['markup'], {})
        self.assertEqual(catalog_view(self.group_callback())['markup'], {})

    def test_revocation_and_pause_prevent_private_catalog_responses(self):
        self.customer.status = Customer.Status.REVOKED
        self.customer.save(update_fields=['status'])
        process_event(self.event(callback=ROOT), Mock())
        self.assertFalse(Delivery.objects.filter(key__startswith='catalog:').exists())
        self.config.accepting_orders = False
        self.config.save(update_fields=['accepting_orders'])
        with self.assertRaises(ValidationError):
            catalog_view()

    def test_malformed_callbacks_are_rejected_before_catalog_lookup(self):
        for callback in ['wc:s:other:0', 'wc:s:sony:-1', 'wc:g:1:1:-1', 'wc:p:9999999999999999999:0', 'wc:r:0:1', 'wc:p:1:0:1', 'wc:r:' + '9'*65]:
            with self.subTest(callback=callback), patch('wholesale_bot.catalog.operator', side_effect=AssertionError('No catalog lookup')), self.assertRaises(ValidationError):
                catalog_view(callback)

    def test_sony_nintendo_accessories_and_unbranded_labels(self):
        definitions = [('PowerA','Зарядная станция','sony'), ('Без бренда','Переходник','sony'),
            ('Без бренда','Подставка для игровой консоли','sony'),
            ('Без бренда','Охлаждающая подставка для консоли','sony'),
            ('Nintendo','MicroSD-карта','nintendo'), ('Без бренда','Защитное стекло','nintendo')]
        for brand_name, type_name, section in definitions:
            brand, _ = Brand.objects.get_or_create(name=brand_name)
            kind, _ = ProductType.objects.get_or_create(name=type_name)
            item = Tech.objects.create(name=type_name, brand=brand, product_type=kind, wholesale_price=100)
            stock = TechWarehouseStock.objects.create(warehouse=self.warehouse, tech=item, quantity=1)
            menu = catalog_view(f'wc:s:{section}:0')
            buttons = [b for row in menu['markup']['inline_keyboard'] for b in row]
            self.assertIn(f'wc:g:{brand.pk}:{kind.pk}:0', [b['callback_data'] for b in buttons])
            self.assertTrue(all('Без бренда' not in b['text'] for b in buttons))
            stock.quantity = 0
            stock.save(update_fields=['quantity'])
            after = catalog_view(f'wc:s:{section}:0')
            self.assertNotIn(f'wc:g:{brand.pk}:{kind.pk}:0', [b['callback_data']
                for row in after['markup'].get('inline_keyboard', []) for b in row])
