"""Оригинальное оформление и динамическое тело без данных чужой отправки."""
import json
from pathlib import Path
from io import BytesIO
from copy import copy
from django.test import SimpleTestCase
from django.core.exceptions import ValidationError
from openpyxl import load_workbook
from .customs_excel import TEMPLATE,EXCEL_FIELDS,build_workbook
from scripts.prepare_customs_template import layout_snapshot


class CustomsExcelTests(SimpleTestCase):
    def row(self,**changes):
        return dict(number='',hs_code='0123456789',marking='',ru_description='Проверенный контроллер',
            en_description='Verified controller',material='МЕТАЛЛ / ПЛАСТИК',country='CHINA',
            manufacturer='TEST MAKER',quantity=3,unit='ШТ',**changes)

    def test_original_headers_styles_widths_and_print_setup_for_all_lengths(self):
        expected=json.loads(TEMPLATE.with_name('customs_manifest_layout.json').read_text('utf-8'))
        template=load_workbook(TEMPLATE)
        self.assertEqual(layout_snapshot(template),expected)
        for count in (1,2,25,50,100):
            with self.subTest(count=count):
                rows=[self.row() for _ in range(count)]
                output=BytesIO();build_workbook(rows).save(output);book=load_workbook(BytesIO(output.getvalue()))
                self.assertEqual(book.sheetnames,['ОПИСАНИЕ']);sheet=book.active
                self.assertEqual(layout_snapshot(book),expected)
                self.assertEqual(sheet.max_row,count+5);self.assertEqual(sheet.max_column,10)
                self.assertEqual({str(m) for m in sheet.merged_cells.ranges},{'A5:J5'})
                self.assertEqual(sum(sheet.cell(r,9).value for r in range(6,count+6)),count*3)
                self.assertTrue(all(sheet.cell(r,1).value in (None,'') for r in range(6,count+6)))
                for index in range(count):
                    for col in range(1,11):
                        reference=template.active.cell(index+6 if index<25 else 8,col)
                        self.assertEqual(copy(sheet.cell(index+6,col).font),copy(reference.font))
                        self.assertEqual(copy(sheet.cell(index+6,col).border),copy(reference.border))
                        self.assertEqual(copy(sheet.cell(index+6,col).fill),copy(reference.fill))
                self.assertEqual(sheet['B6'].value,'0123456789');self.assertEqual(sheet['B6'].data_type,'s')

    def test_formula_prefixes_remain_literal_text_in_all_text_columns(self):
        for prefix in ('=SUM(1,2)','+cmd','-cmd','@cmd'):
            row={field:prefix for field in EXCEL_FIELDS if field!='quantity'};row['quantity']=1
            output=BytesIO();build_workbook([row]).save(output);sheet=load_workbook(BytesIO(output.getvalue())).active
            for col in (1,2,3,4,5,6,7,8,10):
                self.assertEqual(sheet.cell(6,col).data_type,'s');self.assertEqual(sheet.cell(6,col).value,prefix)

    def test_long_text_wraps_and_zero_quantity_rows_are_not_exported(self):
        row=self.row();row['ru_description']='Длинное русское описание '*20
        zero=self.row();zero['quantity']=0
        book=build_workbook([zero,row]);sheet=book.active
        self.assertEqual(sheet.max_row,6);self.assertTrue(sheet['D6'].alignment.wrap_text)
        self.assertGreater(sheet.row_dimensions[6].height,15)
        self.assertEqual(sheet['D6'].value,row['ru_description'])
        with self.assertRaises(ValidationError):build_workbook([zero])
