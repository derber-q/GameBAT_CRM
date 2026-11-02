"""Секрет читается лениво только в live. Тестовая CRM не открывает файл ключа."""
import os
from pathlib import Path
import re
import tempfile
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import OperationalError, ProgrammingError
from core.external_policy import require_live_operation
from .models import StaffBot

TEST_MESSAGE = 'Тестовый режим. Взаимодействие с Telegram отключено.'


def token_path():
    return Path(getattr(settings, 'TELEGRAM_STAFF_TOKEN_FILE', settings.BASE_DIR / '.telegram-staff-bot-token'))


def token_configured():
    if settings.GAMEBAT_ENV == 'local_test':
        return False
    return bool(os.environ.get('GAMEBAT_TELEGRAM_STAFF_BOT_TOKEN') or token_path().is_file())


def read_token():
    require_live_operation('telegram_read_token')
    value = os.environ.get('GAMEBAT_TELEGRAM_STAFF_BOT_TOKEN', '')
    if not value:
        try:
            value = token_path().read_text(encoding='utf-8').strip()
        except OSError:
            raise ValidationError('Токен Telegram не настроен.') from None
    return validate_token(value)


def validate_token(value):
    value = str(value).strip()
    if not re.fullmatch(r'[0-9]{5,20}:[A-Za-z0-9_-]{30,100}', value):
        raise ValidationError('Неверный формат токена Telegram.')
    return value


def save_token(value):
    require_live_operation('telegram_save_token')
    value = validate_token(value)
    path = token_path()
    if path.is_symlink():
        raise ValidationError('Ссылка вместо файла токена запрещена.')
    # Подмена файла атомарна; открытый токен не попадает в БД, формы или журнал.
    fd, name = tempfile.mkstemp(prefix='.telegram-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(value)
        os.chmod(name, 0o600)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def expected_status():
    if settings.GAMEBAT_ENV == 'local_test':
        return 'disabled'
    try:
        bot = StaffBot.objects.filter(code='staff').first()
    except (OperationalError, ProgrammingError):
        # Обновление кода не делает отсутствие ещё не согласованной миграции аварией.
        return 'unconfigured'
    if bot and not bot.enabled:
        return 'disabled'
    return 'required' if bot and bot.username and token_configured() else 'unconfigured'
