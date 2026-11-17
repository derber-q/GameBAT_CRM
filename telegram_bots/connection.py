"""Повтор начальной проверки Telegram: только чтение API, без повторов отправки."""
from .client import TelegramError
from integrations.worker_health import BLOCKED_ERRORS


def initialize_connection(client, username, stop, *, once=False, renew=None, health=None, keep_running=None):
    failures = 0
    while not stop.is_set() and (keep_running is None or keep_running()):
        if renew:
            renew()
        try:
            me = client.call('getMe')
            if not isinstance(me, dict) or str(me.get('username', '')).lower() != username.lower():
                raise TelegramError('wrong_bot')
            webhook = client.call('getWebhookInfo')
            if not isinstance(webhook, dict) or webhook.get('url'):
                raise TelegramError('webhook')
            return me
        except TelegramError as exc:
            if health:
                health.progress(verified=False, error=exc.category)
            # Отказы безопасных getMe/getWebhookInfo, включая HTTP 5xx,
            # не превращают временный сбой Telegram в постоянную остановку.
            if once or exc.category in BLOCKED_ERRORS:
                raise
            failures = min(failures + 1, 6)
            stop.wait(min(60, 5 * 2**failures))
    return None
