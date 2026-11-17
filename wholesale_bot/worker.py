"""Долговечный inbox/outbox обслуживается одним независимым polling-процессом."""
from django.db import close_old_connections, connections, OperationalError
from django.utils import timezone
from core.external_policy import require_live_operation
from telegram_bots.client import TelegramError
from telegram_bots.connection import initialize_connection
from .client import WholesaleClient
from .configuration import read_token, expected_status
from .models import BotConfig, Event, Delivery
from .handlers import ingest, process_event, deliver_one
from .services import enqueue


def recover_sends():
    # Неизвестный результат сетевой отправки нельзя автоматически считать неотправленным.
    for delivery in Delivery.objects.filter(state='sending'):
        delivery.state, delivery.error = 'uncertain', 'interrupted'
        delivery.save(update_fields=['state', 'error'])


def run_polling(stop, *, client_factory=WholesaleClient, once=False, health=None):
    require_live_operation('wholesale_polling')
    if expected_status() != 'required':
        return
    client = client_factory(read_token())
    try:
        config = BotConfig.objects.get(pk=1)
        me = initialize_connection(client, config.username, stop, once=once,
            health=health, keep_running=lambda: expected_status() == 'required')
        if me is None:
            return
        recover_sends()
        while not stop.is_set() and expected_status() == 'required':
            close_old_connections()
            try:
                # Сначала очередь: авария после получения update не теряет файл/подтверждение.
                event = Event.objects.filter(state='pending').order_by('pk').first()
                if event:
                    try:
                        process_event(event, client)
                    except TelegramError as exc:
                        event.state, event.error = 'error', exc.category
                        event.save(update_fields=['state', 'error'])
                        enqueue(event.customer, f'event-error:{event.pk}', public=True,
                            text='Не удалось получить файл из Telegram. Заявка сохранена для проверки сотрудником. Дождитесь результата перед повторным оформлением.')
                    except Exception:
                        # Номер события остаётся для диагностики; исходное исключение может содержать URL/токен.
                        event.state, event.error = 'error', 'processing'
                        event.save(update_fields=['state', 'error'])
                        enqueue(event.customer, f'event-error:{event.pk}', public=True,
                            text='Не удалось завершить обработку. Статус заказа уточняется сотрудником ReSOURCE. Повторное оформление пока не выполняйте.')
                deliver_one(client)
                config.refresh_from_db()
                busy = Event.objects.filter(state='pending').exists() or Delivery.objects.filter(state='pending').exists()
                updates = client.call('getUpdates', {'offset': config.next_update_id,
                    'timeout': 1 if busy else 20, 'limit': 20, 'allowed_updates': ['message', 'callback_query']})
                if not isinstance(updates, list):
                    raise TelegramError('invalid_response')
                for update in updates:
                    if stop.is_set() or expected_status() != 'required':
                        break
                    ingest(update)
                    callback = update.get('callback_query') or {}
                    if callback.get('id'):
                        try:
                            client.call('answerCallbackQuery', {'callback_query_id': callback['id']})
                        except TelegramError:
                            pass
                config.refresh_from_db()
                config.last_success_at, config.error_category = timezone.now(), ''
                config.save(update_fields=['last_success_at', 'error_category'])
                if health:
                    health.progress()
            except TelegramError as exc:
                config = BotConfig.objects.get(pk=1)
                config.error_category = exc.category
                config.save(update_fields=['error_category'])
                if health:
                    health.progress(verified=False, error=exc.category)
                if exc.category in ('unauthorized', 'wrong_bot', 'webhook', 'conflict'):
                    return  # Повторная проверка выполнится общим автономным циклом.
                if not once:
                    stop.wait(10)
            except OperationalError:
                if health:
                    health.progress(verified=False, error='database')
                if not once:
                    stop.wait(2)
            if once:
                break
    except TelegramError as exc:
        config = BotConfig.objects.get(pk=1)
        config.error_category = exc.category
        config.save(update_fields=['error_category'])
        if health:
            health.progress(verified=False, error=exc.category)
    finally:
        client.close()
        connections.close_all()
