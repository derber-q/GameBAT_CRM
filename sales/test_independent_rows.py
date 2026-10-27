from decimal import Decimal
from io import BytesIO
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from openpyxl import load_workbook
from accounts.models import User
from catalog.models import CD, Platform, Tech, ProductType, Brand
from warehouse.models import Warehouse, CDWarehouseStock, TechWarehouseStock
from .models import Sale
from .services import create_sale, edit_postpay_sale_items, cancel_sale
from .statistics_service import _sale_row


class IndependentSaleRowsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('independent', password='test')
        self.warehouse = Warehouse.objects.create(name='Склад')
        self.cd = CD.objects.create(name='Игра', sku='ROWCD', platform=Platform.objects.create(name='PS5'), cost=100, avito_price=150)
        self.tech = Tech.objects.create(name='Техника', sku='ROWT', brand=Brand.objects.create(name='Sony'),
                    product_type=ProductType.objects.create(name='Геймпад'), cost=100, avito_price=150)
        self.cd_stock = CDWarehouseStock.objects.create(cd=self.cd, warehouse=self.warehouse, quantity=5)
        self.tech_stock = TechWarehouseStock.objects.create(tech=self.tech, warehouse=self.warehouse, quantity=5)
        self.client.force_login(self.user)

    def create(self, kind='cd', quantities=(4, 1), note='Скидка на повреждённую упаковку'):
        product = self.cd if kind == 'cd' else self.tech
        return create_sale(actor=self.user, warehouse_id=self.warehouse.pk, price_type='retail', sale_type='avito',
            payment_method='cash_postpay', note=note, lines=[{'product_type': kind, 'product_id': product.pk,
            'quantity': qty, 'unit_discount': index * 10, 'line_note': f'Строка {index}'} for index, qty in enumerate(quantities)])

    def test_two_cd_rows_have_independent_discount_commission_and_profit_and_cancel(self):
        sale = self.create()
        items = list(sale.cd_items.order_by('pk'))
        self.assertEqual([(x.quantity, x.unit_discount, x.line_total) for x in items], [(4, 0, 600), (1, 10, 140)])
        self.assertEqual([x.avito_commission_amount for x in items], [3, 1])
        self.assertEqual([x.unit_profit for x in _sale_row(sale).lines], [Decimal('49.25'), Decimal('39.00')])
        self.cd_stock.refresh_from_db(); self.assertEqual(self.cd_stock.quantity, 0)
        cancel_sale(actor=self.user, sale_id=sale.pk, comment='Отмена')
        self.cd_stock.refresh_from_db(); self.assertEqual(self.cd_stock.quantity, 5)
        self.assertEqual(sale.cd_items.count(), 2)

    def test_tech_repeated_rows_and_invoice_preserved(self):
        sale = self.create('tech')
        self.assertEqual(sale.tech_items.count(), 2)
        response = self.client.get(reverse('sales:invoice', args=(sale.pk,)))
        self.assertEqual(response.status_code, 200)
        book = load_workbook(BytesIO(response.content))
        self.assertEqual(sum(row[2] == self.tech.name for row in book.active.values), 2)
        book.close()

    def test_sum_stock_and_discount_note_are_validated_atomically(self):
        for quantities, note in (((4, 2), 'Скидка'), ((4, 1), '')):
            with self.assertRaises(ValidationError): self.create(quantities=quantities, note=note)
        self.cd_stock.refresh_from_db(); self.assertEqual(self.cd_stock.quantity, 5)
        self.assertFalse(Sale.objects.exists())

    def test_edit_preserves_item_ids_and_historical_prices_and_costs(self):
        sale = self.create(quantities=(2, 1))
        first, second = sale.cd_items.order_by('pk')
        self.cd.cost, self.cd.avito_price = 800, 900
        self.cd.save(update_fields=('cost', 'avito_price'))
        edit_postpay_sale_items(actor=self.user, sale_id=sale.pk, note='Скидка', lines=[
            {'product_type': 'cd', 'product_id': self.cd.pk, 'item_id': first.pk, 'quantity': 1, 'unit_discount': 5},
            {'product_type': 'cd', 'product_id': self.cd.pk, 'item_id': second.pk, 'quantity': 3, 'unit_discount': 10}])
        first.refresh_from_db(); second.refresh_from_db(); self.cd_stock.refresh_from_db()
        self.assertEqual((first.unit_price, second.unit_price, first.unit_cost_snapshot, second.unit_cost_snapshot), (150,150,100,100))
        self.assertEqual((first.quantity,second.quantity,self.cd_stock.quantity),(1,3,1))
        with self.assertRaises(ValidationError):
            edit_postpay_sale_items(actor=self.user, sale_id=sale.pk, lines=[
                {'product_type':'cd','product_id':self.cd.pk,'item_id':first.pk,'quantity':4},
                {'product_type':'cd','product_id':self.cd.pk,'item_id':second.pk,'quantity':4}])
        first.refresh_from_db(); self.assertEqual(first.quantity,1)

    def test_missing_cost_unit_profit_is_none(self):
        sale = self.create()
        item = sale.cd_items.first()
        item.unit_cost_snapshot = None
        # Исторический snapshot не редактируем: проверяем построение строки на неподтверждённом объекте.
        from .statistics_service import _line
        self.assertIsNone(_line(item, 'cd').unit_profit)
