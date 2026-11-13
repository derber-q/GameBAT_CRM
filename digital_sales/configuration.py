"""Чтение конфигурации не выполняет сеть; local_test не читает рабочие секреты."""
import os
from pathlib import Path
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import OperationalError, ProgrammingError
from core.external_policy import require_live_operation
from telegram_bots.configuration import validate_token
from .models import DigitalBot


def token_path():
    return Path(getattr(settings, 'TELEGRAM_DIGITAL_TOKEN_FILE', settings.BASE_DIR / '.telegram-digital-bot-token'))


def read_token():
    require_live_operation('digital_telegram_token')
    value = os.environ.get('GAMEBAT_TELEGRAM_DIGITAL_BOT_TOKEN', '')
    if not value:
        try:
            value = token_path().read_text(encoding='utf-8').strip()
        except OSError:
            raise ValidationError('Токен цифрового бота не настроен.') from None
    return validate_token(value)


def expected_status():
    if settings.GAMEBAT_ENV == 'local_test':
        return 'disabled'
    try:
        bot = DigitalBot.objects.filter(pk=1).first()
    except (OperationalError, ProgrammingError):
        return 'unconfigured'
    if not bot or not bot.enabled:
        return 'disabled'
    return 'required' if (os.environ.get('GAMEBAT_TELEGRAM_DIGITAL_BOT_TOKEN') or token_path().is_file()) else 'unconfigured'
