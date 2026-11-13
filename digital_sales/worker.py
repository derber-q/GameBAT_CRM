"""Независимый пассивный получатель с арендой, остановкой и фиксированным transport."""
import base64
from datetime import timedelta
import re
from django.core.exceptions import ValidationError, ImproperlyConfigured
from django.db import transaction, close_old_connections, OperationalError, connections
from django.db.models import Q
from django.utils import timezone
from core.db_retry import retry_database_lock
from core.external_policy import require_live_operation
from integrations.worker_runtime import AlreadyRunning
from telegram_bots.client import TelegramClient, TelegramError
from telegram_bots.connection import initialize_connection
from .configuration import read_token, expected_status
from .models import DigitalBot, SupplierMessage
from .crypto import decrypt, encrypt
from .ingestion import accept_update, _refresh

MAX_FILE = 5 * 1024 * 1024


class SupplierClient(TelegramClient):
    def download(self, file_id):
        require_live_operation('digital_file_download')
        metadata = self.call('getFile', {'file_id': file_id})
        if not isinstance(metadata, dict):
            raise TelegramError('invalid_response')
        path = metadata.get('file_path', '')
        size = metadata.get('file_size', 0)
        if (not isinstance(path, str) or not re.fullmatch(r'[A-Za-z0-9_/.-]{1,500}', path)
                or '..' in path or path.startswith('/') or type(size) is not int or not 0 <= size <= MAX_FILE):
            raise TelegramError('file_size_or_path')
        import requests
        try:
            with self._session.get(f'https://api.telegram.org/file/bot{self._token}/{path}',
                    stream=True, timeout=(5, 30), allow_redirects=False) as response:
                if response.status_code != 200:
                    raise TelegramError('download_refused')
                content = bytearray()
                for chunk in response.iter_content(65536):
                    content.extend(chunk)
                    if len(content) > MAX_FILE:
                        raise TelegramError('file_too_large')
                return bytes(content)
        except requests.RequestException:
            raise TelegramError('download_network') from None


@retry_database_lock
@transaction.atomic
def lease(owner, *, release=False):
    bot = DigitalBot.objects.select_for_update().get(pk=1)
    if bot.lease_owner and bot.lease_owner != owner and bot.lease_until and bot.lease_until > timezone.now():
        raise AlreadyRunning('Цифровой бот уже обслуживается')
    bot.lease_owner = None if release else owner
    bot.lease_until = None if release else timezone.now() + timedelta(seconds=180)
    bot.save(update_fields=['lease_owner', 'lease_until'])


def download_one(client, owner):
    event = SupplierMessage.objects.filter(attachment_state='pending').filter(
        Q(order__isnull=True) | Q(order__ignored_at__isnull=True) & ~Q(order__state='cancelled')).order_by('pk').first()
    if not event:
        return
    payload = decrypt(event.encrypted_payload)
    file = payload.get('file', {})
    try:
        if not file.get('file_id') or file.get('file_size', 0) and file['file_size'] > MAX_FILE:
            raise TelegramError('file_too_large')
        content = client.download(file['file_id'])
        payload['attachments'] = [{'name': file.get('file_name') or 'file', 'mime': file.get('mime_type') or 'application/octet-stream',
                                   'data': base64.b64encode(content).decode('ascii')}]
        encrypted, state = encrypt(payload), 'done'
    except TelegramError:
        encrypted, state = event.encrypted_payload, 'error'
    with transaction.atomic():
        bot = DigitalBot.objects.select_for_update().get(pk=1)
        if bot.lease_owner != owner or not bot.lease_until or bot.lease_until <= timezone.now():
            return
        event = SupplierMessage.objects.select_for_update().get(pk=event.pk)
        if event.attachment_state != 'pending' or event.order_id and event.order.processing_stopped:
            return  # Отмена во время сетевого запроса не должна вернуть вложение в обработку.
        event.encrypted_payload, event.attachment_state = encrypted, state
        event.save(update_fields=['encrypted_payload', 'attachment_state'])
        if event.order_id and state == 'done':
            order = event.order
            if order.review_reason == 'Ожидается безопасное сохранение вложения':
                order.review_reason = ''
                order.save(update_fields=['review_reason'])
                _refresh(order)


def run_polling(owner, stop, *, client_factory=SupplierClient, once=False, health=None):
    require_live_operation('digital_polling')
    if expected_status() != 'required':
        return
    token = read_token()
    lease(owner)
    client = client_factory(token)
    try:
        bot = DigitalBot.objects.get(pk=1)
        me = initialize_connection(client, bot.username, stop, once=once, renew=lambda: lease(owner),
            health=health, keep_running=lambda: expected_status() == 'required')
        if me is None:
            return
        from .chat_balances import process_command, publish_one, recover_publications
        from digital_prices.dispatch import recover_dispatches, publish_one as publish_price
        failures, blocked = 0, False
        while not stop.is_set() and expected_status() == 'required':
            close_old_connections()
            lease(owner)
            if blocked:
                if health:
                    health.progress(verified=False, error=DigitalBot.objects.get(pk=1).error_category)
                if once:
                    break
                stop.wait(15)
                continue
            try:
                # Один исполнитель: незавершённый этап прошлого цикла мог остаться
                # после ошибки БД уже после сетевой отправки. Не отправляем его вслепую.
                recover_publications()
                recover_dispatches()
                bot = DigitalBot.objects.get(pk=1)
                process_command(client, me.get('id'))
                publish_one(client, owner=owner, bot_id=me.get('id'))
                publish_price(client, owner=owner, bot_id=me.get('id'), renew=lambda: lease(owner))
                from .models import BalanceChatCommand, BalanceChatPublication
                from digital_prices.models import BuyerPriceDispatch
                busy = (BalanceChatCommand.objects.filter(state='queued').exists() or BalanceChatPublication.objects.filter(state='queued').exists()
                        or BuyerPriceDispatch.objects.filter(state__in=('queued', 'pinning')).exists())
                updates = client.call('getUpdates', {'offset': bot.next_update_id, 'timeout': 1 if busy else 20, 'limit': 30,
                                                     'allowed_updates': ['message', 'edited_message', 'my_chat_member']})
                if not isinstance(updates, list):
                    raise TelegramError('invalid_response')
                for update in updates:
                    if stop.is_set():
                        break
                    lease(owner)
                    accept_update(update, owner=owner)
                download_one(client, owner)
                bot.refresh_from_db()
                bot.last_poll_at = bot.last_success_at = timezone.now()
                bot.error_category = ''
                bot.save(update_fields=['last_poll_at', 'last_success_at', 'error_category'])
                if health:
                    health.progress()
                failures = 0
            except (TelegramError, ImproperlyConfigured, ValidationError) as exc:
                bot = DigitalBot.objects.get(pk=1)
                bot.error_category = getattr(exc, 'category', 'configuration')
                bot.last_poll_at = timezone.now()
                bot.save(update_fields=['error_category', 'last_poll_at'])
                if health:
                    health.progress(verified=False, error=bot.error_category)
                failures = min(failures + 1, 6)
                # Продолжаем пассивный приём после временного сбоя сети, сохраняя offset.
                transient = bot.error_category in ('timeout', 'network', 'rate_limited')
                blocked = bot.error_category in ('wrong_bot', 'unauthorized', 'conflict', 'webhook', 'configuration') or (failures >= 3 and not transient)
                if not once and not blocked:
                    stop.wait(min(60, 5 * 2**failures))
            except OperationalError:
                if health:
                    health.progress(verified=False, error='database')
                if not once:
                    stop.wait(2)
            if once:
                break
    except TelegramError as exc:
        bot = DigitalBot.objects.get(pk=1)
        bot.error_category = exc.category
        bot.save(update_fields=['error_category'])
        if health:
            health.progress(verified=False, error=exc.category)
        while not once and expected_status() == 'required' and not stop.wait(15):
            lease(owner)
            if health:
                health.progress(verified=False, error=exc.category)
    finally:
        client.close()
        lease(owner, release=True)
        connections.close_all()
