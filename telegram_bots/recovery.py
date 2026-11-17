"""Постоянное переподключение одного бота под прежней блокировкой процесса."""
import logging
import time
from integrations.worker_health import BLOCKED_ERRORS
from integrations.worker_runtime import AlreadyRunning, TELEGRAM_SERVICES

logger = logging.getLogger('gamebat.business')
RETRY_DELAYS = (30, 60, 120, 240, 300)
ERRORS = BLOCKED_ERRORS | {'network', 'timeout', 'rate_limited', 'refused', 'forbidden',
                         'invalid_response', 'executor', 'database', 'restarting', 'worker_error'}


def run_autonomous(run, *, service, stop, expected, health=None, once=False, clock=time.monotonic):
    """Новая попытка перечитывает конфигурацию; старый цикл обязан закрыть клиента и аренду."""
    if service not in TELEGRAM_SERVICES:
        raise ValueError('Неизвестный Telegram-обработчик.')
    failures = 0
    while not stop.is_set() and expected() == 'required':
        started, category = clock(), ''
        try:
            run()
        except AlreadyRunning:
            raise  # Не обходим чужую аренду или блокировку второго получателя.
        except Exception as exc:
            if once:
                raise
            candidate = getattr(exc, 'category', 'configuration' if type(exc).__name__ in
                                ('ValidationError', 'ImproperlyConfigured') else 'worker_error')
            category = candidate if isinstance(candidate, str) and candidate in ERRORS else 'worker_error'
            # Никаких traceback/исходных исключений: они могут содержать токены и реквизиты.
            logger.warning('telegram_worker_cycle_failed service=%s category=%s', service, category)
        if once or stop.is_set() or expected() != 'required':
            return
        if not category and health:
            category = getattr(health, 'health_error', '')
        category = category if isinstance(category, str) and category in ERRORS else 'restarting'
        failures = 1 if clock() - started >= 300 else min(failures + 1, len(RETRY_DELAYS))
        delay = RETRY_DELAYS[failures - 1]
        logger.warning('telegram_worker_retry service=%s category=%s delay_seconds=%s retry_level=%s',
                       service, category, delay, failures)
        # Ожидание не означает готовность. Проверяем ручное выключение и SIGTERM,
        # поддерживая технический heartbeat без ложного успешного рабочего цикла.
        remaining = delay
        while remaining > 0:
            if health:
                health.progress(verified=False, error=category)
            step = min(15, remaining)
            if stop.wait(step) or expected() != 'required':
                return
            remaining -= step
