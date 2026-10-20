from io import BytesIO
from unittest.mock import patch, Mock

from django.test import SimpleTestCase
import pymupdf

from sales.label_printing import print_pdf, render_label_pages, print_job_completed


def label_pdf(width=58, height=40):
    document = pymupdf.open()
    page = document.new_page(width=width * 72 / 25.4, height=height * 72 / 25.4)
    page.insert_text((8, 20), 'TEST LABEL')
    data = document.tobytes()
    document.close()
    return data


class LabelPrintingTests(SimpleTestCase):
    def test_pdf_is_rendered_at_printer_resolution_and_other_sizes_are_rejected(self):
        pages = render_label_pages(label_pdf(), dpi=203)
        self.assertEqual(len(pages), 1)
        self.assertAlmostEqual(pages[0].width, 58 * 203 / 25.4, delta=1)
        self.assertAlmostEqual(pages[0].height, 40 * 203 / 25.4, delta=1)
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            render_label_pages(label_pdf(75, 120), dpi=203)

    @patch('sales.label_printing._windows_printer')
    def test_prints_once_and_returns_windows_job_number(self, printer):
        dc = printer.return_value.__enter__.return_value
        dc.GetDeviceCaps.side_effect = lambda cap: {88:203,90:203,8:444,10:320}[cap]
        dc.StartDoc.return_value = 77
        with patch('sales.label_printing.ImageWin.Dib') as dib, patch('sales.label_printing._control_job'), \
                patch('sales.label_printing._start_document', return_value=77) as start:
            job_id = print_pdf(label_pdf(), printer_name='Test label printer', title='Order 123')
        self.assertEqual(job_id, 77)
        start.assert_called_once_with(dc, 'Order 123')
        dc.StartPage.assert_called_once()
        dc.EndPage.assert_called_once()
        dc.EndDoc.assert_called_once()
        dib.return_value.draw.assert_called_once()

    @patch('sales.label_printing._windows_printer')
    def test_driver_error_aborts_and_never_reports_success(self, printer):
        dc = printer.return_value.__enter__.return_value
        dc.GetDeviceCaps.side_effect = lambda cap: {88:203,90:203,8:444,10:320}[cap]
        dc.StartDoc.return_value = 77
        dc.StartPage.side_effect = RuntimeError('printer failed')
        with patch('sales.label_printing._control_job'), \
                patch('sales.label_printing._start_document', return_value=77), self.assertRaises(RuntimeError):
            print_pdf(label_pdf(), printer_name='Test label printer', title='Order 123')
        dc.AbortDoc.assert_called_once()
        dc.EndDoc.assert_not_called()

    def test_start_document_uses_win32_api_job_identifier(self):
        from sales.label_printing import _start_document
        dc = Mock()
        dc.GetHandleOutput.return_value = 123
        with patch('win32print.StartDoc', return_value=77) as start:
            self.assertEqual(_start_document(dc, 'Test'), 77)
        start.assert_called_once_with(123, ('Test', None, None, 0))
        dc.StartDoc.assert_not_called()

    def test_only_printed_status_counts_as_printed_not_complete_or_disappeared(self):
        from django.core.exceptions import ValidationError
        with patch('sales.label_printing._printer_job_info', return_value={'Status': 4096}):
            self.assertFalse(print_job_completed('test', 1))
        with patch('sales.label_printing._printer_job_info', return_value={'Status': 128}):
            self.assertTrue(print_job_completed('test', 1))
        with patch('sales.label_printing._printer_job_info', return_value={'Status': 12288, 'TotalPages': 1, 'PagesPrinted': 1}):
            self.assertTrue(print_job_completed('test', 1))
        with patch('sales.label_printing._printer_job_info', return_value={'Status': 12288, 'TotalPages': 1, 'PagesPrinted': 0}):
            self.assertFalse(print_job_completed('test', 1))
        with patch('sales.label_printing._printer_job_info', side_effect=OSError), self.assertRaises(ValidationError):
            print_job_completed('test', 1)
