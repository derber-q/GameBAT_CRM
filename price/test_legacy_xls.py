"""Проверка типов ячеек настоящего BIFF8-файла без тестового Excel-писателя."""
from pathlib import Path
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from .excel import load_legacy_xls, _quantity


class LegacyXlsReaderTests(TestCase):
    def upload(self):
        return SimpleUploadedFile('legacy.xls',
            Path(__file__).with_name('test_data').joinpath('legacy_cells.xls').read_bytes())

    def test_blank_cells_match_xlsx_and_identifiers_remain_strings(self):
        book = load_legacy_xls(self.upload())
        try:
            sheet = book['Example']
            self.assertEqual(sheet.cell(1, 1).value, '001234')
            self.assertEqual(_quantity(sheet.cell(1, 2).value, excel_row=1), 10)
            self.assertIsNone(sheet.cell(2, 1).value)
            self.assertIsNone(sheet.cell(10, 10).value)
            self.assertIs(sheet.cell(1, 3).value, True)
            with self.assertRaises(ValidationError):
                _quantity(sheet.cell(1, 3).value, excel_row=1)
            with self.assertRaises(KeyError):
                book['_resource_report']
        finally:
            book.close()

    def test_invalid_report_returns_validation_error(self):
        from consignment.reports import import_report
        with self.assertRaises(ValidationError):
            import_report(upload=self.upload(), platform_id=1, actor=None)
