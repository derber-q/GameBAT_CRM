"""Собственный токен; чтение и сеть запрещены в local_test."""
import os
from pathlib import Path
from django.conf import settings
from django.db import OperationalError, ProgrammingError
from core.external_policy import require_live_operation
from telegram_bots.configuration import validate_token
from .models import BotConfig


def token_path():
    return Path(getattr(settings, 'TELEGRAM_OPT_TOKEN_FILE', settings.BASE_DIR / '.telegram-opt-bot-token'))


def read_token():
    require_live_operation('wholesale_telegram_token')
    value = os.environ.get('GAMEBAT_TELEGRAM_OPT_BOT_TOKEN', '')
    if not value:
        try:
            value = token_path().read_text(encoding='utf-8').strip()
        except OSError:
            from django.core.exceptions import ValidationError
            raise ValidationError('Токен оптового бота не настроен.') from None
    return validate_token(value)


def expected_status():
    if settings.GAMEBAT_ENV == 'local_test':
        return 'disabled'
    try:
        config = BotConfig.objects.filter(pk=1).first()
    except (OperationalError, ProgrammingError):
        return 'unconfigured'
    if not config or not config.enabled:
        return 'disabled'
    return ('required' if config.warehouse_id and config.operator_id and
        (os.environ.get('GAMEBAT_TELEGRAM_OPT_BOT_TOKEN') or token_path().is_file()) else 'unconfigured')
