"""Только личные сообщения. Внешние User ID и callback не дают прав сотрудника CRM."""
from datetime import timedelta
import json
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from .models import BotConfig, Customer, Event, Delivery, Audit
from .services import (active_customer, enqueue, confirm, receive_order, require_accepting,
                       PAUSED_MESSAGE, RESUMED_MESSAGE)

PRICE = 'Скачать оптовый прайс'
AUTHORIZE = 'Авторизоваться'


def menu(customer, *, accepting=None):
    if accepting is None:
        accepting = BotConfig.objects.filter(pk=1).values_list('accepting_orders', flat=True).first()
    if accepting is False:
        return {'remove_keyboard': True}
    label = PRICE if customer.status == Customer.Status.AUTHORIZED else AUTHORIZE
    return {'keyboard': [[{'text': label}]],
            'resize_keyboard': True, 'is_persistent': True}


@transaction.atomic
def ingest(update):
    """Сохраняем необходимый минимум и offset вместе; секреты и исходный файл здесь не читаются."""
    config = BotConfig.objects.select_for_update().get(pk=1)
    uid = update.get('update_id')
    if type(uid) is not int or uid < 0:
        return
    config.next_update_id = max(config.next_update_id, uid + 1)
    config.save(update_fields=['next_update_id'])
    if Event.objects.filter(update_id=uid).exists():
        return
    callback = update.get('callback_query') or {}
    message = callback.get('message') or update.get('message') or {}
    profile = callback.get('from') or message.get('from') or {}
    chat = message.get('chat') or {}
    identity = profile.get('id')
    if (type(identity) is not int or not 0 < identity < 2**63 or chat.get('type') != 'private'
            or chat.get('id') != identity or profile.get('is_bot')):
        return
    customer, _ = Customer.objects.get_or_create(telegram_id=identity)
    if Event.objects.filter(customer=customer, created_at__gte=timezone.now() - timedelta(minutes=1)).count() >= 30:
        return
    customer.username = str(profile.get('username') or '')[:64]
    customer.first_name = str(profile.get('first_name') or '')[:128]
    customer.last_name = str(profile.get('last_name') or '')[:128]
    customer.save(update_fields=['username', 'first_name', 'last_name', 'last_seen_at'])
    document = message.get('document') or {}
    payload = {'text': str(message.get('text') or '')[:200], 'message_id': message.get('message_id'),
        'callback': str(callback.get('data') or '')[:64], 'callback_id': str(callback.get('id') or '')[:200],
        'service_revision': config.service_revision, 'paused': not config.accepting_orders}
    if document:
        payload['document'] = {'file_id': str(document.get('file_id') or '')[:512],
            'file_name': str(document.get('file_name') or '')[:255], 'file_size': document.get('file_size')}
    Event.objects.create(update_id=uid, customer=customer, payload=payload)


def process_event(event, client):
    if event.state != 'pending':
        return
    customer = Customer.objects.get(pk=event.customer_id)
    payload = event.payload
    key = f'event:{event.pk}'
    try:
        config = BotConfig.objects.get(pk=1)
        if (not config.accepting_orders or payload.get('paused')
                or payload.get('service_revision', config.service_revision) != config.service_revision):
            text = PAUSED_MESSAGE if not config.accepting_orders else (
                RESUMED_MESSAGE + '\n\n🔁 Ваш предыдущий запрос пришёл до смены режима. Повторите его, пожалуйста.')
            enqueue(customer, key, text=text, markup=menu(customer), public=True)
            event.state, event.error = 'done', ''
            event.save(update_fields=['state', 'error'])
            return
        if payload.get('callback'):
            active_customer(customer.pk)
            if payload['callback'].startswith('wc:'):
                from .catalog import catalog_view
                view = catalog_view(payload['callback'])
                enqueue(customer, f"catalog:{event.pk}:{payload['callback']}", **view)
                event.state, event.error = 'done', ''
                event.save(update_fields=['state', 'error'])
                return
            parts = payload['callback'].split(':')
            if len(parts) != 4 or parts[0] != 'w' or parts[3] not in ('confirm', 'cancel', 'repeat'):
                raise ValidationError('Откройте актуальное сообщение заказа.')
            confirm(customer_id=customer.pk, intent_id=parts[1], revision=parts[2],
                    cancel=parts[3] == 'cancel', repeat=parts[3] == 'repeat')
        elif payload.get('document'):
            from .documents import MAX_FILE
            active_customer(customer.pk)
            file = payload['document']
            if (not str(file.get('file_name') or '').lower().endswith('.xlsx')
                    or type(file.get('file_size')) is not int or not 0 < file['file_size'] <= MAX_FILE
                    or not isinstance(file.get('file_id'), str) or len(file['file_id']) > 512):
                raise ValidationError('Отправьте XLSX из этого бота размером не больше 5 МБ.')
            content = client.download(file['file_id'])
            receive_order(customer_id=customer.pk, message_id=payload['message_id'], content=content)
        elif payload.get('text') == AUTHORIZE:
            with transaction.atomic():
                require_accepting()
                customer = Customer.objects.select_for_update().get(pk=customer.pk)
                if customer.status != Customer.Status.AUTHORIZED:
                    # Повтор кнопки сохраняет ту же заявку, а не новый объект/авторизацию.
                    if customer.status != Customer.Status.PENDING:
                        customer.status, customer.requested_at = Customer.Status.PENDING, timezone.now()
                        customer.save(update_fields=['status', 'requested_at', 'last_seen_at'])
                        Audit.objects.create(customer=customer, kind='access_requested')
                    text = 'Заявка на авторизацию отправлена. Ожидайте подтверждения сотрудником ReSOURCE.'
                else:
                    text = f'Вы уже авторизованы: {customer.partner.display_name}.'
                enqueue(customer, key, text=text, markup=menu(customer), public=True)
        elif payload.get('text') == PRICE:
            from .documents import issue_price
            from .catalog import price_markup
            active_customer(customer.pk)
            if not Delivery.objects.filter(key=key).exists():
                issue = issue_price(customer.pk)
                enqueue(customer, key, text='Изменяйте только количества. Готовый XLSX отправьте в этот чат.',
                        issue=issue, document=bytes(issue.content), filename='ReSOURCE-Опт.xlsx', markup=price_markup())
        else:
            if customer.status == Customer.Status.AUTHORIZED:
                active_customer(customer.pk)
                text = f'ReSOURCE — оптовые заказы.\nВаш партнёр: {customer.partner.display_name}.\nСкачайте именной прайс, заполните количества и отправьте XLSX обратно.'
            else:
                text = ('Ваша заявка ожидает подтверждения сотрудником ReSOURCE.' if customer.status == 'pending'
                        else 'ReSOURCE — оптовые заказы. Для получения прайса и оформления заказов необходимо пройти авторизацию.')
            enqueue(customer, key, text=text, markup=menu(customer), public=True)
    except ValidationError as exc:
        enqueue(customer, key, text='; '.join(exc.messages), markup=menu(customer), public=True)
    event.state = 'done'
    event.error = ''
    event.save(update_fields=['state', 'error'])


@transaction.atomic
def claim_delivery():
    config = BotConfig.objects.select_for_update().get(pk=1)
    pending = Delivery.objects.select_for_update().filter(state='pending')
    if not config.accepting_orders:
        # Уведомления и накладные уже созданных продаж не блокируются паузой.
        pending = pending.filter(Q(key__startswith='service:') | Q(requires_authorization=False) | Q(intent__sale__isnull=False))
    row = pending.order_by('pk').first()
    if row:
        # Отзыв или перепривязка блокируют ранее подготовленные частные документы.
        customer = Customer.objects.select_for_update().get(pk=row.customer_id)
        try:
            if row.requires_authorization:
                active_customer(customer.pk, revision=row.customer_revision)
            elif row.customer_revision != customer.revision:
                raise ValidationError('Уведомление об авторизации уже устарело.')
        except ValidationError:
            row.state, row.error = 'cancelled', 'authorization_changed'
            row.save(update_fields=['state', 'error'])
            return None
        row.state, row.attempts = 'sending', row.attempts + 1
        row.save(update_fields=['state', 'attempts'])
    return row


def deliver_one(client):
    from telegram_bots.client import TelegramError
    row = claim_delivery()
    if not row:
        return
    try:
        config = BotConfig.objects.get(pk=1)
        if (not config.accepting_orders and row.requires_authorization
                and not row.key.startswith('service:') and not (row.intent_id and row.intent.sale_id)):
            row.state, row.error = 'pending', 'service_paused'
            row.save(update_fields=['state', 'error'])
            return
        if row.intent_id and row.intent.sale_id and row.intent.sale.is_cancelled:
            row.state, row.error = 'cancelled', 'sale_cancelled'
            row.save(update_fields=['state', 'error'])
            return
        if row.intent_id and not row.text and row.document is None:
            from .documents import invoice
            row.filename, row.document = invoice(row.intent)
            # Снимок документа сохраняется ДО сетевой отправки.
            row.save(update_fields=['filename', 'document'])
        if row.requires_authorization:
            try:
                active_customer(row.customer_id, revision=row.customer_revision)
            except ValidationError:
                row.state, row.error = 'cancelled', 'authorization_changed'
                row.save(update_fields=['state', 'error'])
                return
        # Остатки могли измениться за время ожидания outbox: строим кнопки и цены
        # непосредственно перед отправкой. XLSX остаётся неизменным снимком прайса.
        if row.key.startswith('catalog:') or row.issue_id:
            from .catalog import catalog_view, price_markup
            if row.key.startswith('catalog:'):
                view = catalog_view(row.key.split(':', 2)[2])
                row.text, row.markup = view['text'], view['markup']
            else:
                row.markup = price_markup()
            row.save(update_fields=['text', 'markup'])
        if row.document is not None:
            payload = {'chat_id': row.customer.telegram_id, 'caption': row.text[:900]}
            if row.markup:
                payload['reply_markup'] = json.dumps(row.markup)
            client.call('sendDocument', payload,
                files={'document': (row.filename, bytes(row.document), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')})
        else:
            client.message(row.customer.telegram_id, row.text, row.markup)
        row.state, row.sent_at, row.error = 'sent', timezone.now(), ''
    except TelegramError as exc:
        # Для sendMessage также возможен неизвестный результат. Безопасного idempotency key у Telegram нет.
        row.state = 'uncertain' if exc.category in ('timeout', 'network') or exc.uncertain else 'error'
        row.error = exc.category
    except Exception:
        row.state, row.error = 'error', 'document_generation'
    row.save(update_fields=['state', 'sent_at', 'error'])
