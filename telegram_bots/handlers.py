"""Приём update сохраняет квитанцию и задание до сетевого ответа; XLSX здесь не строится."""
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from core.db_retry import retry_database_lock
from warehouse.models import Warehouse
from .access import BotDenied, authorize, consume_link
from .menu import WHOLESALE, main_menu, warehouse_menu
from .models import StaffBot, StaffBotUpdate, StaffBotJob


def _positive_id(value):
    return isinstance(value, int) and not isinstance(value, bool) and 0 < value < 2**63


def _private_context(update):
    callback = update.get('callback_query')
    if callback is not None and not isinstance(callback, dict):
        return None
    message = callback.get('message', {}) if callback else update.get('message', {})
    if not isinstance(message, dict):
        return None
    sender = callback.get('from', {}) if callback else message.get('from', {})
    chat = message.get('chat', {})
    if (not isinstance(sender, dict) or not isinstance(chat, dict) or chat.get('type') != 'private'
            or not _positive_id(sender.get('id')) or chat.get('id') != sender['id'] or sender.get('is_bot')):
        return None
    return message, sender, callback or {}


def _request_price(bot, access, warehouse_id, receipt, chat_id):
    if not Warehouse.objects.filter(pk=warehouse_id).exists():
        raise BotDenied('warehouse_missing', 'Склад не найден. Откройте меню заново.')
    if StaffBotJob.objects.filter(access=access, state__in=['queued', 'generating', 'sending']).exists():
        raise BotDenied('busy', 'Ваш прайс уже формируется или отправляется. Дождитесь результата.')
    if StaffBotJob.objects.filter(access=access,
            created_at__gt=timezone.now() - timedelta(seconds=bot.cooldown_seconds)).exists():
        raise BotDenied('rate_limited', 'Слишком частые запросы. Повторите немного позже.')
    StaffBotJob.objects.create(bot=bot, access=access, warehouse_id=warehouse_id, update=receipt, chat_id=chat_id)
    return {'text': 'Формирую актуальный оптовый прайс…'}


def _dispatch(bot, update, receipt):
    context = _private_context(update)
    if not context:
        return None  # Никаких ответов или документов в группы и каналы.
    message, sender, callback = context
    chat_id = sender['id']
    text = message.get('text', '')
    text = text if isinstance(text, str) else ''
    if not callback and text.startswith('/start '):
        consume_link(bot, text.split(' ', 1)[1].strip(), chat_id, sender.get('username', ''))
    access, user = authorize(bot, chat_id)
    data = callback.get('data') if callback else None
    if data == 'menu' or (not callback and text.split(' ', 1)[0] in ['/start', '/menu', '/help']):
        return {'text': 'Добро пожаловать в ReSOURCE.\nВыберите необходимую функцию.', 'reply_markup': main_menu(user)}
    if data == WHOLESALE.code or (not callback and text == WHOLESALE.title):
        warehouses = list(Warehouse.objects.order_by('name', 'pk'))
        if not warehouses:
            raise BotDenied('no_warehouse', 'В CRM пока нет доступных складов.')
        if len(warehouses) == 1:
            return _request_price(bot, access, warehouses[0].pk, receipt, chat_id)
        return {'text': 'Выберите склад:', 'reply_markup': warehouse_menu(warehouses)}
    if isinstance(data, str) and data.startswith(WHOLESALE.code + ':'):
        value = data.split(':', 1)[1]
        if value.isascii() and value.isdecimal() and len(value) <= 18:
            return _request_price(bot, access, int(value), receipt, chat_id)
    raise BotDenied('unknown_command', 'Откройте /menu и выберите доступную функцию.')


@retry_database_lock
@transaction.atomic
def accept_update(bot_id, update):
    if (not isinstance(update, dict) or not isinstance(update.get('update_id'), int)
            or isinstance(update['update_id'], bool) or not 0 <= update['update_id'] < 2**63):
        return None
    bot = StaffBot.objects.select_for_update().get(pk=bot_id)
    if not bot.enabled or bot.code != 'staff':
        return None
    receipt, new = StaffBotUpdate.objects.get_or_create(bot=bot, update_id=update['update_id'])
    if not new:
        return None
    bot.next_update_id = max(bot.next_update_id, update['update_id'] + 1)
    bot.save(update_fields=['next_update_id'])
    try:
        reply = _dispatch(bot, update, receipt)
        receipt.result = 'accepted' if reply else 'ignored'
    except BotDenied as exc:
        receipt.result = exc.category
        reply = {'text': exc.messages[0]} if _private_context(update) else None
    receipt.save(update_fields=['result'])
    if not reply:
        return None
    message, sender, callback = _private_context(update)
    reply['chat_id'] = message['chat']['id']
    if isinstance(callback.get('id'), str):
        reply['callback_id'] = callback['id']
    return reply
