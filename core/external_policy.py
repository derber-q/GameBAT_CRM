"""Одна политика перед реальным внешним эффектом, включая клиент с подменённым transport."""
from django.conf import settings
from django.core.exceptions import ValidationError

MESSAGE = 'ТЕСТОВЫЙ РЕЖИМ: реальное внешнее действие заблокировано. Используйте фиктивный сценарий.'


def require_live_operation(operation):
    if settings.GAMEBAT_ENV == 'local_test':
        raise ValidationError(MESSAGE, code='test_environment_blocked')
