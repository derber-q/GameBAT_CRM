"""Ключ задаётся отдельно; потерянный ключ никогда не заменяется автоматически."""
import json
import os
from pathlib import Path
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.views.decorators.debug import sensitive_variables


def key_path():
    return Path(getattr(settings, 'DIGITAL_SALES_KEY_FILE', settings.BASE_DIR / '.digital-sales-key'))


def cipher():
    try:
        value = os.environ.get('GAMEBAT_DIGITAL_SALES_KEY', '').encode('ascii') or key_path().read_bytes().strip()
        return Fernet(value)
    except (OSError, ValueError, TypeError, UnicodeError):
        raise ImproperlyConfigured('Ключ цифровых товаров не настроен или недоступен. Восстановите исходный ключ.') from None


@sensitive_variables()
def encrypt(value):
    return cipher().encrypt(json.dumps(value, ensure_ascii=False).encode('utf-8')).decode('ascii')


@sensitive_variables()
def decrypt(value):
    try:
        return json.loads(cipher().decrypt(value.encode('ascii')))
    except (InvalidToken, ValueError, UnicodeError):
        raise ImproperlyConfigured('Данные цифрового товара не расшифрованы. Нужен исходный ключ.') from None
