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
    """Старая клавиатура удаляется отдельно; главное меню остаётся одним inline-сообщением."""
    cleanup_id = None
    if reply and reply.get('remove_reply_keyboard'):
        chat_id = reply.get('chat_id')
        if type(chat_id) is not int or chat_id <= 0:
            raise ValueError('Удаление старой клавиатуры доступно только в личном чате.')
        cleanup = client.message(chat_id, 'Открываю меню…', {'remove_keyboard': True})
        if isinstance(cleanup, dict) and type(cleanup.get('message_id')) is int and cleanup['message_id'] > 0:
            cleanup_id = cleanup['message_id']
    try:
        return _dispatch_reply(client, reply)
    finally:
        if cleanup_id is not None:
            try:
                client.call('deleteMessage', {'chat_id': reply['chat_id'], 'message_id': cleanup_id})
            except TelegramError:
                pass  # Не повторяем отправку меню из-за ошибки удаления своего служебного ответа.


def _dispatch_reply(client, reply):
    if not reply:
        return
    if reply.get('callback_id'):
        try:
            client.call('answerCallbackQuery', {'callback_query_id': reply['callback_id']})
        except TelegramError:
            pass
    if not reply.get('screen'):
        client.message(reply['chat_id'], reply['text'], reply.get('reply_markup'))
        return
    chat_id, text = reply['chat_id'], reply['text']
    markup = reply.get('reply_markup') or {'inline_keyboard': []}
    message_id = reply.get('message_id')
    has_photo = reply.get('message_has_photo', False)
    caption_fits = len(text.encode('utf-16-le')) // 2 <= 1024
    if message_id:
        method = 'editMessageCaption' if has_photo else 'editMessageText'
        # Финансовые карточки не сокращаются ради ограничения подписи Telegram.
        long_card = has_photo and not caption_fits
        data = {'chat_id': chat_id, 'message_id': message_id,
            'caption' if has_photo else 'text': 'Подробная карточка открыта ниже.' if long_card else text,
            'reply_markup': {'inline_keyboard': []} if long_card else markup}
        try:
            client.call(method, data)
        except TelegramError as exc:
            if exc.category != 'message_missing':
                raise
        else:
            if long_card:
                client.message(chat_id, text, markup)
            return
    if caption_fits:
        client.menu_photo(chat_id, text, markup)
    else:
        client.message(chat_id, text, markup)


def job_loop(bot_id, stop, owner, client_factory, health=None):
    client = client_factory(read_token())
    try:
        while not stop.is_set():
            close_old_connections()
            try:
                # При утрате аренды старый экземпляр не начинает следующее задание.
                current = StaffBot.objects.get(pk=bot_id)
                if not current.enabled or current.lease_owner != owner or current.lease_until <= timezone.now():
                    return
                from digital_sales.delivery import deliver_one
                deliver_one(client, bot_id=bot_id, owner=owner)
                job = claim_job(bot_id)
                if job:
                    run_job(job, client, owner=owner)
                if health:
                    health.executor_progress()
            except OperationalError:
                job = None
            finally:
                connections.close_all()
            if not job:
                stop.wait(1)
    finally:
        client.close()
        connections.close_all()


def _initialize_connection(client, bot_id, owner, stop, *, once=False, health=None):
    """Повторяем только безопасные проверки API, не отправки сообщений/документов."""
    failures = 0
    while not stop.is_set() and expected_status() == 'required':
        lease(bot_id, owner)
        try:
            me = client.call('getMe')
            bot = StaffBot.objects.get(pk=bot_id)
            if not isinstance(me, dict) or str(me.get('username', '')).lower() != bot.username.lower():
                raise TelegramError('wrong_bot')
            webhook = client.call('getWebhookInfo')
            if not isinstance(webhook, dict) or webhook.get('url'):
                raise TelegramError('webhook')
        except TelegramError as exc:
            connection_state(bot_id, exc.category)
            if health:
                health.progress(verified=False, error=exc.category)
            if once or exc.category not in ('timeout', 'network', 'rate_limited'):
                raise
            failures = min(failures + 1, 6)
            stop.wait(min(60, 5 * 2**failures))
        else:
            connection_state(bot_id)
            return True
    return False


def run_polling(bot_id, owner, stop, *, client_factory=TelegramClient, once=False, health=None):
    require_live_operation('telegram_polling')
    if expected_status() != 'required':
        return
    lease(bot_id, owner)
    client = client_factory(read_token())
    executor_stop = threading.Event()
    executor = None
    try:
        recovered = recover_interrupted(bot_id)
        from digital_sales.models import Notification
        for interrupted in Notification.objects.filter(access__bot_id=bot_id, state='sending'):
            interrupted.state = 'uncertain'
            interrupted.error_category = 'interrupted'
            interrupted.save(update_fields=['state', 'error_category'])
        # Никаких deleteWebhook: существующий webhook требует решения администратора.
        if not _initialize_connection(client, bot_id, owner, stop, once=once, health=health):
            return
        notify_recovered_jobs(recovered, client)
        executor = threading.Thread(target=job_loop, args=(bot_id, executor_stop, owner, client_factory, health), name='telegram-documents')
        executor.start()
        failures, blocked = 0, False
        while not stop.is_set() and expected_status() == 'required':
            close_old_connections()
            lease(bot_id, owner)
            if executor and not executor.is_alive() and not blocked:
                connection_state(bot_id, 'executor')
                if health:
                    health.progress(verified=False, error='executor')
                return  # Штатный supervisor запустит новый единственный исполнитель.
            if blocked:
                if health:
                    health.progress(verified=False, error=StaffBot.objects.get(pk=bot_id).error_category)
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
                if health:
                    health.progress()
                failures = 0
            except TelegramError as exc:
                connection_state(bot_id, exc.category)
                if health:
                    health.progress(verified=False, error=exc.category)
                failures = min(failures + 1, 6)
                # Временный сбой polling не останавливает доставку outbox.
                # Неопределённые отправки защищены от повторов в delivery/jobs.
                transient = exc.category in ('timeout', 'network', 'rate_limited')
                blocked = exc.category in ['unauthorized', 'conflict', 'wrong_bot', 'webhook'] or (failures >= 3 and not transient)
                if blocked:
                    executor_stop.set()
                elif not once:
                    stop.wait(min(60, 5 * 2**failures))
            except OperationalError:
                if health:
                    health.progress(verified=False, error='database')
                if not once:
                    stop.wait(2)
            finally:
                connections.close_all()
            if once:
                break
    except TelegramError as exc:
        connection_state(bot_id, exc.category)
        if health:
            health.progress(verified=False, error=exc.category)
        # Процесс жив, но готовность отсутствует: токен/webhook требует исправления.
        while not once and not stop.wait(15) and expected_status() == 'required':
            lease(bot_id, owner)
            if health:
                health.progress(verified=False, error=exc.category)
    finally:
        executor_stop.set()
        if executor:
            executor.join()  # Запрос имеет конечный HTTP timeout, отправку не обрываем.
        client.close()
        lease(bot_id, owner, release=True)
        connections.close_all()
