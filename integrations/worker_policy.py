"""Только чтение конфигурации. Ошибка внешнего API не выключает ожидаемый worker."""
from pathlib import Path
import sys

from django.conf import settings
from django.core.exceptions import ValidationError

from .models import IntegrationCredential, GoogleSheetsIntegration
from .worker_runtime import SERVICES


def expected_services():
    if settings.GAMEBAT_ENV == 'local_test':
        # Этап A: реальные очереди запрещены; моделирование восстановления идёт
        # в существующих изолированных тестах с FakeProcesses.
        return dict.fromkeys(SERVICES, 'disabled')
    result = dict.fromkeys(SERVICES, 'unconfigured')
    from telegram_bots.configuration import expected_status
    result['telegram_staff'] = expected_status()
    avito = IntegrationCredential.objects.filter(provider='avito').first()
    if avito and avito.is_configured and avito.last_success_at:
        result['avito'] = 'required'
    from yandex_market.models import Integration
    yandex = Integration.objects.all()
    if yandex.exists():
        if not yandex.filter(enabled=True).exists():
            result['yandex'] = 'disabled'
        elif settings.YANDEX_MARKET_API_KEY or Path(settings.YANDEX_MARKET_KEY_FILE).is_file():
            result['yandex'] = 'required'
    google = GoogleSheetsIntegration.objects.first()
    if google:
        if not google.enabled:
            result['google'] = 'disabled'
        elif google.spreadsheet_id and settings.GOOGLE_SERVICE_ACCOUNT_FILE and Path(settings.GOOGLE_SERVICE_ACCOUNT_FILE).is_file():
            result['google'] = 'required'
    if getattr(settings,'LABEL_PRINT_BACKEND','native') == 'agent':
        from sales.models import PrintAgent
        result['print'] = 'required' if PrintAgent.objects.filter(enabled=True).exists() else 'unconfigured'
    elif sys.platform != 'win32':
        # Windows spooler недоступен в Linux; Print Agent подключается отдельно.
        result['print'] = 'disabled'
    else:
        from sales.label_printing import printer_configuration
        try:
            printer_configuration()
        except ValidationError:
            pass
        else:
            # Печать нужна и для ранее принятых заданий отключённого Маркета.
            result['print'] = 'required'
    return result
