"""Отметки снижения цен не меняют числовой Excel и его обратный импорт."""
from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from openpyxl import load_workbook

from accounts.models import User
from catalog.audit import record_product_changes
from catalog.models import Brand, CD, Platform, ProductChangeEvent, ProductType, Tech
from warehouse.models import CDWarehouseStock, TechWarehouseStock, Warehouse

from .excel import MAIN_SHEET, generate_retail_price_xlsx, generate_wholesale_price_xlsx, import_wholesale_price_to_sale
from .price_changes import WHOLESALE_DECREASE_DAYS, recent_wholesale_price_decreases


class WholesalePriceDecreaseTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.user = User.objects.create_superuser('price-admin', password='Test-only-strong-password!')
        self.warehouse = Warehouse.objects.create(name='Проверка прайса')
        self.cd = CD.objects.create(name='Игра', sku='drop-cd', barcode='drop-cd',
            platform=Platform.objects.create(name='PS5'), cost=100, wholesale_price=150, avito_price=200)
        # Одинаковые ID разных моделей не должны смешивать историю CD и Tech.
        self.tech = Tech.objects.create(pk=self.cd.pk, name='Геймпад', sku='drop-tech', barcode='drop-tech',
            brand=Brand.objects.create(name='Sony'), product_type=ProductType.objects.create(name='Геймпады'),
            cost=100, wholesale_price=250, avito_price=300)
        CDWarehouseStock.objects.create(warehouse=self.warehouse, cd=self.cd, quantity=5)
        TechWarehouseStock.objects.create(warehouse=self.warehouse, tech=self.tech, quantity=2)

    def change(self, product, old, new, *, ago=1, field='wholesale_price'):
        when = self.now - timedelta(days=ago)
        with patch('django.utils.timezone.now', return_value=when):
            return record_product_changes(actor=self.user, instance=product,
                source=ProductChangeEvent.Source.CRM,
                changes=[{'field_name':field, 'field_label':'Цена', 'old_value':old, 'new_value':new}])

    def decreases(self):
        return recent_wholesale_price_decreases([('cd',self.cd),('tech',self.tech)], at=self.now)

    def test_export_marks_both_kinds_and_keeps_importable_numeric_prices(self):
        self.change(self.cd, '180.00', '150.00')
        self.change(self.tech, '300.00', '250.00')
        self.cd.newness_months = 1
        self.cd.save()
        content = generate_wholesale_price_xlsx(warehouse_id=self.warehouse.pk, actor=self.user)
        wb = load_workbook(BytesIO(content))
        sheet = wb[MAIN_SHEET]
        self.assertEqual(sheet.max_column, 4)
        self.assertIn('📉', sheet['A7'].value)
        for name, price in (('📉 🌟 Игра',150), ('📉 Геймпад',250)):
            row = next(r for r in sheet if r[0].value == name)
            self.assertEqual(row[1].value, price)
            self.assertIn('↓', row[1].number_format)
            self.assertEqual(row[1].fill.fgColor.rgb, '00FFF2CC')
            self.assertTrue(all(cell.fill.fgColor.rgb != '00FFF2CC' for cell in (row[0],row[2],row[3])))
            if '🌟' in name:
                self.assertEqual(row[0].fill.fgColor.rgb, '00E2F0D9')
            self.assertFalse(row[3].protection.locked)
            self.assertIsNone(row[1].comment)
            row[3].value = 1
        stream = BytesIO()
        wb.save(stream)
        wb.close()

        stream.seek(0)
        stream.name = 'order.xlsx'
        warehouse, lines = import_wholesale_price_to_sale(stream)
        self.assertEqual(warehouse.pk, self.warehouse.pk)
        self.assertEqual({(line['product_type'],line['product_id'],line['quantity']) for line in lines},
                         {('cd',self.cd.pk,1),('tech',self.tech.pk,1)})
        retail, _ = generate_retail_price_xlsx(warehouse_id=self.warehouse.pk, actor=self.user)
        wb = load_workbook(BytesIO(retail))
        self.assertFalse(any('↓' in cell.number_format for row in wb[MAIN_SHEET] for cell in row))
        wb.close()

    def test_new_product_without_decrease_marks_only_name_green(self):
        self.cd.newness_months = 1
        self.cd.save(update_fields=['newness_months'])
        wb = load_workbook(BytesIO(generate_wholesale_price_xlsx(warehouse_id=self.warehouse.pk, actor=self.user)))
        row = next(row for row in wb[MAIN_SHEET] if row[0].value == '🌟 Игра')
        self.assertEqual(row[0].fill.fgColor.rgb, '00E2F0D9')
        self.assertTrue(all(cell.fill.fgColor.rgb != '00E2F0D9' for cell in row[1:]))
        self.assertNotIn('↓', row[1].number_format)
        wb.close()

    def test_latest_increase_replaces_earlier_decrease(self):
        self.change(self.cd, '200', '100', ago=2)
        self.change(self.cd, '100', '150', ago=1)
        self.assertNotIn(('cd',self.cd.pk), self.decreases())

    def test_unrelated_or_identical_saves_do_not_hide_or_renew_decrease(self):
        self.change(self.cd, '180', '150', ago=2)
        self.change(self.cd, '180', '200', field='avito_price')
        self.change(self.cd, '150', '150.00', ago=0)
        with self.assertNumQueries(1):
            decrease = self.decreases()['cd',self.cd.pk]
        self.assertEqual(decrease.changed_at, self.now - timedelta(days=2))

    def test_expired_or_initial_price_is_not_marked(self):
        self.change(self.cd, '180', '150', ago=WHOLESALE_DECREASE_DAYS)
        self.change(self.tech, '', '250')
        self.assertEqual(self.decreases(), {})

    def test_mismatched_and_invalid_history_cannot_mark_current_price(self):
        self.change(self.cd, '200', '140')
        self.change(self.tech, '300', 'NaN')
        self.assertEqual(self.decreases(), {})

    def test_empty_price_has_no_history_query(self):
        with self.assertNumQueries(0):
            self.assertEqual(recent_wholesale_price_decreases([], at=self.now), {})
