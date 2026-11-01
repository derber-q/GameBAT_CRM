"""Тонкий адаптер существующего Windows-механизма; ORM/БД CRM не загружаются."""
class WindowsDriver:
    def __init__(self,printer_name):
        import os
        import sys
        if os.environ.get('GAMEBAT_ENV')=='local_test':
            raise RuntimeError('local_test: настоящий Print Agent запрещён.')
        if sys.platform!='win32':
            raise RuntimeError('Агент печати устанавливается на Windows-компьютере принтера.')
        from django.conf import settings
        if settings.configured and getattr(settings,'GAMEBAT_ENV','')=='local_test':
            raise RuntimeError('local_test: настоящий Print Agent запрещён.')
        if not settings.configured:
            settings.configure(GAMEBAT_ENV='local_live')
        from sales import label_printing
        self.printing=label_printing
        self.printer_name=printer_name

    def available(self):
        import win32print
        handle=win32print.OpenPrinter(self.printer_name)
        try:
            info=win32print.GetPrinter(handle,2)
            blocked=(win32print.PRINTER_STATUS_OFFLINE|win32print.PRINTER_STATUS_ERROR|
                     win32print.PRINTER_STATUS_PAPER_OUT|win32print.PRINTER_STATUS_PAUSED)
            return not bool(info['Status']&blocked)
        finally:
            win32print.ClosePrinter(handle)

    def validate(self,data):
        self.printing.render_label_pages(data,dpi=203)

    def submit(self,data,title):
        return self.printing.print_pdf(data,printer_name=self.printer_name,title=title)

    def completed(self,spool,title):
        return self.printing.print_job_completed(self.printer_name,spool,expected_title=title)

    def release(self,spool,title):
        return self.printing.release_print_job(self.printer_name,spool,expected_title=title)
