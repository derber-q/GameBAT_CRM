"""Long polling и исполнитель используют разные соединения; мониторинг — существующий."""
from datetime import timedelta
import threading
from django.db import close_old_connections, connections, OperationalError, transaction
from django.utils import timezone
from core.db_retry import retry_database_lock
from core.external_policy import require_live_operation
from integrations.worker_runtime import AlreadyRunning
from .client import TelegramClient, TelegramError
from .configuration import read_token, expected_status
from .handlers import accept_update
from .jobs import claim_job, run_job, recover_interrupted, notify_recovered_jobs
from .models import StaffBot


@retry_database_lock
@transaction.atomic
def lease(bot_id, owner, *, release=False):
    bot = StaffBot.objects.select_for_update().get(pk=bot_id)
    now = timezone.now()
    if bot.lease_owner and bot.lease_owner != owner and bot.lease_until and bot.lease_until > now:
        raise AlreadyRunning('Telegram уже обслуживается')
    bot.lease_owner = None if release else owner
    bot.lease_until = None if release else now + timedelta(seconds=180)
    bot.save(update_fields=['lease_owner', 'lease_until'])


def connection_state(bot_id, category=''):
    bot = StaffBot.objects.get(pk=bot_id)
    bot.error_category, bot.last_poll_at = category, timezone.now()
    fields = ['error_category', 'last_poll_at']
    if not category:
        bot.last_success_at = timezone.now()
        fields.append('last_success_at')
    bot.save(update_fields=fields)


def dispatch_reply(client, reply):
    if not reply:
        return
    if reply.get('callback_id'):
        try:
            client.call('answerCallbackQuery', {'callback_query_id': reply['callback_id']})
        except TelegramError:
            pass
    client.message(reply['chat_id'], reply['text'], reply.get('reply_markup'))


def job_loop(bot_id, stop, owner, client_factory):
    client = client_factory(read_token())
    try:
        while not stop.is_set():
            close_old_connections()
            try:
                # При утрате аренды старый экземпляр не начинает следующее задание.
                current = StaffBot.objects.get(pk=bot_id)
                if not current.enabled or current.lease_owner != owner or current.lease_until <= timezone.now():
                    return
                job = claim_job(bot_id)
                if job:
                    run_job(job, client, owner=owner)
            except OperationalError:
                job = None
            finally:
                connections.close_all()
            if not job:
                stop.wait(1)
    finally:
        client.close()
        connections.close_all()


def run_polling(bot_id, owner, stop, *, client_factory=TelegramClient, once=False):
    require_live_operation('telegram_polling')
    if expected_status() != 'required':
        return
    lease(bot_id, owner)
    client = client_factory(read_token())
    executor_stop = threading.Event()
    executor = None
    try:
        recovered = recover_interrupted(bot_id)
        # Никаких deleteWebhook: существующий webhook требует решения администратора.
        me = client.call('getMe')
        bot = StaffBot.objects.get(pk=bot_id)
        if not isinstance(me, dict) or str(me.get('username', '')).lower() != bot.username.lower():
            raise TelegramError('wrong_bot')
        webhook = client.call('getWebhookInfo')
        if not isinstance(webhook, dict) or webhook.get('url'):
            raise TelegramError('webhook')
        notify_recovered_jobs(recovered, client)
        executor = threading.Thread(target=job_loop, args=(bot_id, executor_stop, owner, client_factory), name='telegram-documents')
        executor.start()
        failures, blocked = 0, False
        while not stop.is_set() and expected_status() == 'required':
            close_old_connections()
            lease(bot_id, owner)
            if executor and not executor.is_alive() and not blocked:
                blocked = True
                connection_state(bot_id, 'executor')
            if blocked:
                if once:
                    break
                stop.wait(15)
                continue
            try:
                bot = StaffBot.objects.get(pk=bot_id)
                updates = client.call('getUpdates', {'offset': bot.next_update_id, 'timeout': 20,
                    'limit': 30, 'allowed_updates': ['message', 'callback_query']})
                if not isinstance(updates, list):
                    raise TelegramError('invalid_response')
                for update in updates:
                    if stop.is_set() or expected_status() != 'required':
                        break
                    lease(bot_id, owner)
                    dispatch_reply(client, accept_update(bot_id, update))
                connection_state(bot_id)
                failures = 0
            except TelegramError as exc:
                connection_state(bot_id, exc.category)
                failures += 1
                blocked = exc.category in ['unauthorized', 'conflict', 'wrong_bot', 'webhook'] or failures >= 3
                if blocked:
                    executor_stop.set()
                elif not once:
                    stop.wait(min(60, 5 * 2**failures))
            except OperationalError:
                if not once:
                    stop.wait(2)
            finally:
                connections.close_all()
            if once:
                break
    except TelegramError as exc:
        connection_state(bot_id, exc.category)
        # Heartbeat остаётся живым: ошибка API не провоцирует перезапуски supervisor.
        while not once and not stop.wait(15) and expected_status() == 'required':
            lease(bot_id, owner)
    finally:
        executor_stop.set()
        if executor:
            executor.join()  # Запрос имеет конечный HTTP timeout, отправку не обрываем.
        client.close()
        lease(bot_id, owner, release=True)
        connections.close_all()
