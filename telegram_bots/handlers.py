"""Приём update сохраняет квитанцию и задание до сетевого ответа; XLSX здесь не строится."""
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from core.db_retry import retry_database_lock
from warehouse.models import Warehouse
from partners.models import Supplier
from .access import BotDenied, authorize, consume_link, check_function_access
from .menu import WHOLESALE, SUPPLIER_TEMPLATES, main_menu, warehouse_menu, supplier_menu, supplier_label
from .models import StaffBot, StaffBotUpdate, StaffBotJob, StaffBotJobDocument


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


def _request_job(bot, access, receipt, chat_id, *, function, **target):
    if StaffBotJob.objects.filter(access=access, state__in=['queued', 'generating', 'sending']).exists():
        raise BotDenied('busy', 'Документы уже формируются или отправляются.')
    if StaffBotJob.objects.filter(access=access,
            created_at__gt=timezone.now() - timedelta(seconds=bot.cooldown_seconds)).exists():
        raise BotDenied('rate_limited', 'Слишком частые запросы. Повторите немного позже.')
    return StaffBotJob.objects.create(bot=bot, access=access, update=receipt, chat_id=chat_id,
        function=function, **target)


def _request_price(bot, access, warehouse_id, receipt, chat_id):
    check_function_access(access, WHOLESALE.code)
    if not Warehouse.objects.filter(pk=warehouse_id).exists():
        raise BotDenied('warehouse_missing', 'Склад не найден. Откройте меню заново.')
    _request_job(bot, access, receipt, chat_id, function=WHOLESALE.code, warehouse_id=warehouse_id)
    return {'text': 'Формирую актуальный оптовый прайс…'}


def _request_supplier_templates(bot, access, supplier_id, receipt, chat_id):
    user = check_function_access(access, SUPPLIER_TEMPLATES.code)
    supplier = Supplier.objects.select_for_update().filter(pk=supplier_id).first()
    if supplier is None:
        raise BotDenied('supplier_missing', 'Поставщик не найден. Откройте список заново.')
    job = _request_job(bot, access, receipt, chat_id, function=SUPPLIER_TEMPLATES.code, supplier_id=supplier.pk)
    for kind in ('cd', 'tech'):
        StaffBotJobDocument.objects.create(job=job, product_kind=kind)
    return {'text': f'Формирую шаблоны поставщика {supplier_label(supplier, user)} с последними сохранёнными ценами…'}


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
        menu = main_menu(user)
        return {'text': ('Добро пожаловать в ReSOURCE.\nВыберите необходимую функцию.'
            if 'keyboard' in menu else 'У вас пока нет доступных функций. Обратитесь к администратору CRM.'),
            'reply_markup': menu}
    if data == SUPPLIER_TEMPLATES.code or (not callback and text == SUPPLIER_TEMPLATES.title):
        user = check_function_access(access, SUPPLIER_TEMPLATES.code)
        suppliers = list(Supplier.objects.order_by('letter', 'pk'))
        if not suppliers:
            raise BotDenied('no_suppliers', 'В CRM пока нет доступных поставщиков.')
        return {'text': 'Выберите поставщика, для которого нужно скачать шаблоны с последними ценами:',
            'reply_markup': supplier_menu(suppliers, user)}
    if isinstance(data, str) and data.startswith(SUPPLIER_TEMPLATES.code + ':'):
        check_function_access(access, SUPPLIER_TEMPLATES.code)
        value = data.split(':', 1)[1]
        if value.isascii() and value.isdecimal() and len(value) <= 19 and _positive_id(int(value)):
            return _request_supplier_templates(bot, access, int(value), receipt, chat_id)
    if data == WHOLESALE.code or (not callback and text == WHOLESALE.title):
        check_function_access(access, WHOLESALE.code)
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
