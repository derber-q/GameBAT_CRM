"""Отправка outbox через существующий бот сотрудников вне учётной транзакции."""
from datetime import timedelta
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from telegram_bots.client import TelegramError
from telegram_bots.models import StaffBot
from .models import Notification
from .notifications import notification_allowed
from .telegram import card
from .reconciliation import card as balance_card


def deliver_one(client, *, bot_id, owner):
    with transaction.atomic():
        bot = StaffBot.objects.select_for_update().get(pk=bot_id)
        if not bot.enabled or bot.lease_owner != owner or not bot.lease_until or bot.lease_until <= timezone.now():
            return False
        row = Notification.objects.select_for_update().filter(access__bot_id=bot_id, state='queued').filter(
            Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=timezone.now())).order_by('pk').first()
        if not row:
            return False
        if not notification_allowed(row):
            row.state = 'revoked'
            row.save(update_fields=['state'])
            return True
        row.state, row.attempts = 'sending', row.attempts + 1
        row.save(update_fields=['state', 'attempts'])
        target = ({'order_id': row.order_id} if row.order_id else
                  {'observation_id': row.observation_id} if row.observation_id else None)
        previous = Notification.objects.filter(**target, access=row.access, state='done',
                    telegram_message_id__isnull=False).order_by('-pk').first() if target else None
        if row.observation_id and row.event_key.startswith(f'balance:{row.observation_id}:resend:'):
            previous = None  # Явный повтор владельца должен появиться новым сообщением в конце чата.
        payload = (card(row.order) if row.order_id else balance_card(row.observation)
                   if row.observation_id else {'text': row.text})
        chat_id = row.access.telegram_user_id
    try:
        if not notification_allowed(row):
            result, state, error = None, 'revoked', ''
        else:
            if previous:
                result = client.call('editMessageText', {'chat_id': chat_id, 'message_id': previous.telegram_message_id, **payload})
            else:
                result = client.message(chat_id, payload['text'], payload.get('reply_markup'))
            if not isinstance(result, dict) or type(result.get('message_id')) is not int:
                raise TelegramError('invalid_response', uncertain=True)
            state, error = 'done', ''
    except TelegramError as exc:
        error = exc.category
        uncertain = exc.uncertain or exc.category in ('network', 'timeout', 'invalid_response')
        state = 'uncertain' if uncertain else 'queued' if row.attempts < 5 and exc.category == 'rate_limited' else 'error'
        result = None
    with transaction.atomic():
        stored = Notification.objects.select_for_update().get(pk=row.pk)
        stored.state, stored.error_category = state, error
        stored.telegram_message_id = result['message_id'] if result else None
        stored.next_attempt_at = timezone.now() + timedelta(seconds=min(300, 30 * row.attempts)) if state == 'queued' else None
        stored.save(update_fields=['state', 'error_category', 'telegram_message_id', 'next_attempt_at'])
    return True
