"""Готовность подтверждает рабочий цикл текущего процесса, а не его heartbeat-поток."""
from datetime import timedelta
from .worker_runtime import STALE_SECONDS

DEADLINES = {'telegram_staff': 120, 'telegram_digital': 180, 'telegram_opt': 180,
             'avito': 600, 'yandex': 600, 'google': 600, 'print': 600, 'digital_prices': 900}
BLOCKED_ERRORS = frozenset(('unauthorized', 'wrong_bot', 'webhook', 'conflict', 'configuration'))


def fresh(at, now, seconds):
    return at is not None and timedelta(0) <= now - at <= timedelta(seconds=seconds)


def process_health(process, code, now):
    if process is None or not fresh(process.heartbeat_at, now, STALE_SECONDS):
        return 'unknown', 'unconfirmed'
    deadline = DEADLINES[code]
    if process.health_error in BLOCKED_ERRORS:
        return 'blocked', process.health_error
    if not fresh(process.progress_at or process.started_at, now, deadline):
        return 'degraded', 'stalled'
    if process.health_error:
        return 'degraded', process.health_error
    if process.verified_at is None:
        return 'recovering', 'checking'
    if not fresh(process.verified_at, now, deadline) or not process.ready:
        return 'degraded', 'not_verified'
    if code == 'telegram_staff' and not fresh(process.executor_at, now, 900):
        if process.executor_at is None and fresh(process.started_at, now, 120):
            return 'recovering', 'checking'
        return 'degraded', 'executor_stalled'
    return 'running', ''
