import logging
import re


class RetailTokenFilter(logging.Filter):
    """Скрывает токен даже в строке запроса журнала runserver и ошибках Django."""
    def filter(self, record):
        record.msg = re.sub(r"(/retailer/)[A-Za-z0-9_-]{43,}(/|(?=[?\s\"']))", r"\1[скрыто]\2", record.getMessage())
        record.args = ()
        return True
