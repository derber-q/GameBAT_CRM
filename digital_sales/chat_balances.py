"""Каждое изменение баланса — новое сообщение, отдельная очередь без сети в учёте."""
import re
from datetime import timedelta
from zoneinfo import ZoneInfo
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone
from telegram_bots.access import check_access, BotDenied
from telegram_bots.client import TelegramError
from telegram_bots.models import StaffBotAccess
from .models import (Buyer, BuyerBalanceChat, BalanceChatCommand, BalanceChatPublication,
                     AuditEvent, DigitalBot, Supplier)


def balance_text(amount, at):
    signed = f'{amount:+,.2f}'.replace(',', ' ').replace('.', ',')
    date = timezone.localtime(at, ZoneInfo('Europe/Moscow')).strftime('%d.%m.%Y %H:%M')
    return f'Текущий баланс на {date}: {signed} ₽'


def enqueue_balance(buyer, *, event):
    """Вызывать внутри транзакции изменения баланса; сумма и время — снимок события."""
    chat = BuyerBalanceChat.objects.filter(buyer=buyer).first()
    if chat:
        at = timezone.now()
        return BalanceChatPublication.objects.get_or_create(event_key=f'buyer:{buyer.pk}:{event}', defaults={
            'chat': chat, 'buyer': buyer, 'text': balance_text(buyer.balance, at), 'generated_at': at})[0]


def ingest_chat_update(update):
    """Только метаданные и явные команды; текст переписки покупателей не сохраняется."""
    member = update.get('my_chat_member')
    message = update.get('message')
    source = member if isinstance(member, dict) else message
    if not isinstance(source, dict):
        return False
    chat = source.get('chat')
    if not isinstance(chat, dict) or chat.get('type') not in ('group', 'supergroup'):
        return False
    chat_id = chat.get('id')
    if type(chat_id) is not int or not -2**63 < chat_id < 0:
        return False
    text = str(source.get('text') or '')
    match = re.fullmatch(r'/balance_bind(?:@[A-Za-z0-9_]+)?\s+([0-9]{1,18})\s*', text)
    if match and '@' in text.split()[0] and text.split()[0].split('@', 1)[1].lower() != DigitalBot.objects.get(pk=1).username.lower():
        return False
    if not isinstance(member, dict) and not match:
        return BuyerBalanceChat.objects.filter(chat_id=chat_id, buyer__isnull=False).exists()
    row, _ = BuyerBalanceChat.objects.get_or_create(chat_id=chat_id, defaults={'title': str(chat.get('title') or '')[:255]})
    row.title = str(chat.get('title') or '')[:255]
    fields = ['title', 'updated_at']
    if isinstance(member, dict):
        rights = member.get('new_chat_member') or {}
        if not isinstance(rights, dict):
            rights = {}
        row.can_pin = rights.get('status') == 'administrator' and rights.get('can_pin_messages') is True
        row.can_delete = rights.get('status') == 'administrator' and rights.get('can_delete_messages') is True
        fields += ['can_pin', 'can_delete']
    row.save(update_fields=fields)
    sender = source.get('from') or {}
    if not isinstance(sender, dict):
        sender = {}
    if (match and type(sender.get('id')) is int and sender['id'] > 0 and not sender.get('is_bot')
            and int(match[1]) > 0):
        try:
            _staff(sender['id'])
        except TelegramError:
            return True  # Посторонние участники не могут заполнять очередь привязки.
        BalanceChatCommand.objects.get_or_create(update_id=update['update_id'], defaults={
            'chat': row, 'sender_id': sender['id'], 'buyer_id_requested': int(match[1])})
    return True


def _staff(sender_id):
    for access in StaffBotAccess.objects.filter(telegram_user_id=sender_id, allowed=True, revoked_at__isnull=True):
        try:
            user = check_access(access)
            if user.has_perm('digital_sales.manage_digital_buyers'):
                return user
        except BotDenied:
            pass
    raise TelegramError('staff_permission')


def _rights(client, chat_id, bot_id):
    rights = client.call('getChatMember', {'chat_id': chat_id, 'user_id': bot_id})
    if not isinstance(rights, dict):
        raise TelegramError('send_permission')
    allowed = rights.get('status') in ('administrator', 'creator', 'member') or (
        rights.get('status') == 'restricted' and rights.get('is_member') is True
        and rights.get('can_send_messages') is True)
    if not allowed:
        raise TelegramError('send_permission')
    return rights


def process_command(client, bot_id):
    command = BalanceChatCommand.objects.filter(state='queued').order_by('pk').first()
    if not command:
        return False
    try:
        actor = _staff(command.sender_id)
        member = client.call('getChatMember', {'chat_id': command.chat_id, 'user_id': command.sender_id})
        if not isinstance(member, dict) or member.get('status') not in ('administrator', 'creator'):
            raise TelegramError('group_admin_permission')
        rights = _rights(client, command.chat_id, bot_id)
        if any(command.chat_id in supplier.chat_ids for supplier in Supplier.objects.all()):
            raise TelegramError('supplier_chat')
        with transaction.atomic():
            actor = _staff(command.sender_id)
            command = BalanceChatCommand.objects.select_for_update().get(pk=command.pk)
            chat = BuyerBalanceChat.objects.select_for_update().get(pk=command.chat_id)
            buyer = Buyer.objects.select_for_update().get(pk=command.buyer_id_requested)
            if (chat.buyer_id not in (None, buyer.pk) or BuyerBalanceChat.objects.filter(buyer=buyer).exclude(pk=chat.pk).exists()):
                raise TelegramError('binding_conflict')
            chat.buyer, chat.can_pin, chat.can_delete = buyer, bool(rights.get('can_pin_messages')), bool(rights.get('can_delete_messages'))
            chat.save(update_fields=['buyer', 'can_pin', 'can_delete', 'updated_at'])
            enqueue_balance(buyer, event=f'chat_binding:{chat.pk}')
            AuditEvent.objects.create(actor=actor, kind='buyer_chat_bound', detail=f'buyer={buyer.pk};chat={chat.pk}')
            command.state, command.error_category = 'done', ''
            command.save(update_fields=['state', 'error_category'])
    except (TelegramError, Buyer.DoesNotExist) as exc:
        command.state, command.error_category = 'error', getattr(exc, 'category', 'buyer_missing')
        command.save(update_fields=['state', 'error_category'])
    return True


def bind_chat_as_owner(*, actor, client, chat_id, buyer_id):
    """Явная привязка владельцем CRM; не требует его административной роли в Telegram."""
    from django.core.exceptions import PermissionDenied
    from .services import require
    actor = require(actor, 'digital_sales.configure_digital_bot', 'digital_sales.manage_digital_buyers')
    if not actor.is_superuser:
        raise PermissionDenied('Для привязки из CRM требуются права владельца.')
    chat = BuyerBalanceChat.objects.get(pk=chat_id)  # Только уже обнаруженная ботом группа.
    me = client.call('getMe')
    if not isinstance(me, dict) or me.get('username', '').lower() != DigitalBot.objects.get(pk=1).username.lower():
        raise TelegramError('wrong_bot')
    rights = _rights(client, chat.pk, me['id'])
    if any(chat.pk in supplier.chat_ids for supplier in Supplier.objects.all()):
        raise TelegramError('supplier_chat')
    with transaction.atomic():
        actor = require(actor, 'digital_sales.configure_digital_bot', 'digital_sales.manage_digital_buyers')
        if not actor.is_superuser:
            raise PermissionDenied
        chat = BuyerBalanceChat.objects.select_for_update().get(pk=chat_id)
        buyer = Buyer.objects.select_for_update().get(pk=buyer_id)
        if chat.buyer_id not in (None, buyer.pk) or BuyerBalanceChat.objects.filter(buyer=buyer).exclude(pk=chat.pk).exists():
            raise ValidationError('Этот чат или покупатель уже связан с другой записью.')
        chat.buyer, chat.can_pin, chat.can_delete = buyer, bool(rights.get('can_pin_messages')), bool(rights.get('can_delete_messages'))
        chat.save(update_fields=['buyer', 'can_pin', 'can_delete', 'updated_at'])
        enqueue_balance(buyer, event=f'chat_binding:{chat.pk}')
        for command in BalanceChatCommand.objects.select_for_update().filter(chat=chat, state__in=['queued', 'error']):
            command.state, command.error_category = 'superseded', 'owner_binding'
            command.save(update_fields=['state', 'error_category'])
        AuditEvent.objects.create(actor=actor, kind='buyer_chat_bound_by_owner', detail=f'buyer={buyer.pk};chat={chat.pk}')
    return chat


@transaction.atomic
def recover_publications():
    for row in BalanceChatPublication.objects.select_for_update().filter(state='working'):
        unknown_send = row.stage in ('create', 'copy') and row.copy_message_id is None
        row.state = 'uncertain' if unknown_send else 'queued'
        row.error_category = 'interrupted'
        row.save(update_fields=['state', 'error_category'])


@transaction.atomic
def _claim(owner):
    bot = DigitalBot.objects.select_for_update().get(pk=1)
    if not bot.enabled or bot.lease_owner != owner or not bot.lease_until or bot.lease_until <= timezone.now():
        return None
    prior = BalanceChatPublication.objects.filter(chat_id=OuterRef('chat_id'), pk__lt=OuterRef('pk')).exclude(state='done')
    row = (BalanceChatPublication.objects.select_for_update().filter(state='queued')
           .filter(Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=timezone.now()))
           .annotate(blocked=Exists(prior)).filter(blocked=False).order_by('pk').first())
    if row:
        row.state, row.attempts = 'working', row.attempts + 1
        row.save(update_fields=['state', 'attempts'])
    return row


def _message_id(result):
    if not isinstance(result, dict) or type(result.get('message_id')) is not int or result['message_id'] <= 0:
        raise TelegramError('invalid_response', uncertain=True)
    return result['message_id']


def publish_one(client, *, owner, bot_id):
    row = _claim(owner)
    if row is None:
        return False
    try:
        chat = BuyerBalanceChat.objects.get(pk=row.chat_id)
        if chat.buyer_id != row.buyer_id:
            raise TelegramError('binding_changed')
        if any(chat.pk in supplier.chat_ids for supplier in Supplier.objects.only('chat_ids')):
            raise TelegramError('supplier_chat')
        _rights(client, chat.pk, bot_id)
        # copy_message_id старой очереди означает, что сообщение уже есть в ленте.
        # При переходе со старых этапов edit/pin/copy ни редактирования, ни закрепа.
        if row.copy_message_id is None:
            row.stage, row.message_id = 'create', None
            row.save(update_fields=['stage', 'message_id'])
            result = client.call('sendMessage', {'chat_id': chat.pk, 'text': row.text})
            identity = _message_id(result)
            with transaction.atomic():
                row.message_id = row.copy_message_id = identity
                row.stage = 'sent'
                row.save(update_fields=['message_id', 'copy_message_id', 'stage'])
        row.state, row.error_category, row.next_attempt_at = 'done', '', None
        row.save(update_fields=['state', 'error_category', 'next_attempt_at'])
    except TelegramError as exc:
        uncertain = row.stage in ('create', 'copy') and (exc.uncertain or exc.category in ('network', 'timeout', 'invalid_response'))
        safe_retry = not uncertain and exc.category in ('network', 'timeout', 'rate_limited') and row.attempts < 5
        row.state = 'uncertain' if uncertain else 'queued' if safe_retry else 'error'
        row.error_category = exc.category
        row.next_attempt_at = timezone.now() + timedelta(seconds=min(300, 15 * 2**row.attempts)) if safe_retry else None
        row.save(update_fields=['state', 'stage', 'error_category', 'next_attempt_at'])
        if row.state in ('error', 'uncertain'):
            from .notifications import enqueue_alert
            enqueue_alert(f'chat_balance:{row.pk}',
                f'Не удалось отправить баланс в чат покупателя {row.buyer.name}. '
                f'Ошибка: {row.error_category}. Проверьте раздел настройки цифрового бота. Списание в CRM сохранено.')
    return True


@transaction.atomic
def retry_publication(*, actor, publication_id, checked, message_id=None):
    from .services import require, record_id
    actor = require(actor, 'digital_sales.configure_digital_bot', 'digital_sales.manage_digital_buyers')
    row = BalanceChatPublication.objects.select_for_update().get(pk=record_id(publication_id))
    if row.state not in ('error', 'uncertain'):
        return
    if not checked:
        raise ValidationError('Сначала проверьте сообщения в чате и подтвердите возможность повтора.')
    chat = BuyerBalanceChat.objects.select_for_update().get(pk=row.chat_id)
    if chat.buyer_id != row.buyer_id:
        raise ValidationError('Привязка чата изменилась. Повтор запрещён.')
    identity = record_id(message_id) if message_id else None
    if identity and row.stage in ('create', 'copy'):
        row.message_id = row.copy_message_id = identity
        row.stage = 'sent'
    row.state, row.error_category, row.next_attempt_at, row.attempts = 'queued', '', None, 0
    row.save(update_fields=['message_id', 'copy_message_id', 'stage', 'state', 'error_category', 'next_attempt_at', 'attempts'])
    AuditEvent.objects.create(actor=actor, kind='chat_balance_retry', detail=f'publication={row.pk};message={identity}')


def unpin_previous_balance(*, actor, client, chat_id):
    """Разовый переход: снимает закреп только известного сообщения нашего бота."""
    from .services import require
    actor = require(actor, 'digital_sales.configure_digital_bot', 'digital_sales.manage_digital_buyers')
    chat = BuyerBalanceChat.objects.get(pk=chat_id, buyer__isnull=False)
    identity = chat.message_id
    if not identity:
        return False
    if not BalanceChatPublication.objects.filter(chat=chat, buyer_id=chat.buyer_id,
            message_id=identity, state='done').exists():
        raise ValidationError('Нет подтверждения, что прежний закреп создан ботом. Нужна ручная проверка.')
    me = client.call('getMe')
    if not isinstance(me, dict) or me.get('username', '').lower() != DigitalBot.objects.get(pk=1).username.lower():
        raise TelegramError('wrong_bot')
    if client.call('unpinChatMessage', {'chat_id': chat.pk, 'message_id': identity}) is not True:
        raise TelegramError('invalid_response')
    with transaction.atomic():
        chat = BuyerBalanceChat.objects.select_for_update().get(pk=chat.pk)
        if chat.message_id == identity:
            chat.message_id, chat.message_at = None, None
            chat.save(update_fields=['message_id', 'message_at', 'updated_at'])
        AuditEvent.objects.create(actor=actor, kind='buyer_balance_unpinned', detail=f'chat={chat.pk};message={identity}')
    return True
