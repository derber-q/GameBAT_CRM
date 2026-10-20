"""Печать официального PDF 58×40 мм на локальный принтер Windows без диалогов."""
from contextlib import contextmanager
import json
from pathlib import Path
import sys

from django.conf import settings
from django.core.exceptions import ValidationError
from PIL import Image, ImageWin
import pymupdf


def printer_configuration():
    try:
        config = json.loads(Path(settings.LABEL_PRINTER_CONFIG_PATH).read_text('utf-8'))
        name = config['printer_name']
        if not isinstance(name, str) or not name.strip() or len(name) > 200:
            raise ValueError
    except (OSError, ValueError, KeyError, TypeError):
        raise ValidationError('Принтер этикеток не настроен на компьютере CRM.') from None
    if sys.platform != 'win32':
        raise ValidationError('Прямая печать этикеток настроена для Windows.')
    return name.strip()


def render_label_pages(data, *, dpi):
    try:
        if len(data) > 30 * 1024 * 1024 or not data.startswith(b'%PDF-'):
            raise ValueError
        with pymupdf.open(stream=data, filetype='pdf') as pdf:
            if pdf.needs_pass or not 1 <= len(pdf) <= 100:
                raise ValueError
            pages = []
            for page in pdf:
                if abs(page.rect.width * 25.4 / 72 - 58) > 0.5 or abs(page.rect.height * 25.4 / 72 - 40) > 0.5:
                    raise ValueError
                pixmap = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB, alpha=False)
                pages.append(Image.frombytes('RGB', (pixmap.width, pixmap.height), pixmap.samples))
            return pages
    except (ValueError, RuntimeError, pymupdf.FileDataError):
        raise ValidationError('Для печати нужен корректный PDF Яндекса размером 58×40 мм.') from None


@contextmanager
def _windows_printer(name):
    import win32con
    import win32gui
    import win32print
    import win32ui

    printer = win32print.OpenPrinter(name)
    dc = None
    try:
        info = win32print.GetPrinter(printer, 2)
        blocked = (win32print.PRINTER_STATUS_OFFLINE | win32print.PRINTER_STATUS_ERROR |
                   win32print.PRINTER_STATUS_PAPER_OUT | win32print.PRINTER_STATUS_PAUSED)
        if info['Status'] & blocked:
            raise ValidationError('Принтер этикеток недоступен: проверьте бумагу и подключение.')
        mode = info['pDevMode']
        mode.PaperSize, mode.PaperWidth, mode.PaperLength, mode.Orientation = 0, 580, 400, win32con.DMORIENT_PORTRAIT
        mode.Fields = ((mode.Fields & ~win32con.DM_PAPERSIZE) | win32con.DM_PAPERWIDTH |
                       win32con.DM_PAPERLENGTH | win32con.DM_ORIENTATION)
        if win32print.DocumentProperties(0, printer, name, mode, mode,
                win32con.DM_IN_BUFFER | win32con.DM_OUT_BUFFER) != 1:
            raise ValidationError('Драйвер принтера не принял размер 58×40 мм.')
        dc = win32ui.CreateDCFromHandle(win32gui.CreateDC('WINSPOOL', name, mode))
        width = dc.GetDeviceCaps(win32con.PHYSICALWIDTH) * 25.4 / dc.GetDeviceCaps(win32con.LOGPIXELSX)
        height = dc.GetDeviceCaps(win32con.PHYSICALHEIGHT) * 25.4 / dc.GetDeviceCaps(win32con.LOGPIXELSY)
        if abs(width - 58) > 1 or abs(height - 40) > 1:
            raise ValidationError('Принтер использует другой размер бумаги. Нужен 58×40 мм.')
        yield dc
    finally:
        if dc is not None:
            dc.DeleteDC()
        win32print.ClosePrinter(printer)


def print_pdf(data, *, printer_name, title):
    with _windows_printer(printer_name) as dc:
        dpi = dc.GetDeviceCaps(88)
        pages = render_label_pages(data, dpi=dpi)
        width, height = dc.GetDeviceCaps(8), dc.GetDeviceCaps(10)
        job_id = _start_document(dc, title)
        if job_id <= 0:
            raise ValidationError('Windows не приняла задание печати.')
        try:
            _control_job(printer_name, job_id, 8)  # JOB_CONTROL_RETAIN: не терять результат после удаления из обычной очереди.
            for page in pages:
                scale = min(width / page.width, height / page.height)
                w, h = round(page.width * scale), round(page.height * scale)
                x, y = (width - w) // 2, (height - h) // 2
                dc.StartPage()
                ImageWin.Dib(page).draw(dc.GetHandleOutput(), (x, y, x + w, y + h))
                dc.EndPage()
            dc.EndDoc()
        except Exception:
            dc.AbortDoc()
            raise
        return job_id


def _start_document(dc, title):
    import win32print
    # PyCDC.StartDoc возвращает None; StartDoc Win32 возвращает нужный ID задания.
    return win32print.StartDoc(dc.GetHandleOutput(), (title, None, None, 0))


def _control_job(printer_name, job_id, command):
    import win32print
    printer = win32print.OpenPrinter(printer_name)
    try:
        win32print.SetJob(printer, job_id, 0, None, command)
    finally:
        win32print.ClosePrinter(printer)


def _printer_job_info(printer_name, job_id):
    import win32print
    printer = win32print.OpenPrinter(printer_name)
    try:
        return win32print.GetJob(printer, job_id, 2)
    finally:
        win32print.ClosePrinter(printer)


def print_job_completed(printer_name, job_id):
    import win32print
    try:
        info = _printer_job_info(printer_name, job_id)
    except OSError:
        raise ValidationError('Не удалось подтвердить завершение печати. Готовность не отправлена.') from None
    blocked = (win32print.JOB_STATUS_ERROR | win32print.JOB_STATUS_OFFLINE | win32print.JOB_STATUS_PAPEROUT |
               win32print.JOB_STATUS_DELETED | win32print.JOB_STATUS_DELETING | win32print.JOB_STATUS_PAUSED |
               win32print.JOB_STATUS_USER_INTERVENTION | win32print.JOB_STATUS_BLOCKED_DEVQ)
    if info['Status'] & blocked:
        raise ValidationError('Ошибка печати стикера. Готовность не отправлена; проверьте принтер.')
    # COMPLETE сам по себе означает только отправку. Xprinter сообщает напечатанные
    # страницы сохранённого задания вместо флага PRINTED — требуем весь счётчик.
    printed = bool(info['Status'] & win32print.JOB_STATUS_PRINTED)
    retained = bool(info['Status'] & 0x2000)  # JOB_STATUS_RETAINED
    total, completed = info.get('TotalPages', 0), info.get('PagesPrinted', 0)
    return printed or (retained and total > 0 and completed >= total)


def release_print_job(printer_name, job_id):
    _control_job(printer_name, job_id, 9)  # JOB_CONTROL_RELEASE — после сохранения подтверждённого результата.
