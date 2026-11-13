"""Выбор покупателя в личном CRM-боте; доставка через прежнюю цифровую очередь."""
from datetime import timedelta
import secrets
from django.db import transaction
from django.utils import timezone
from telegram_bots.access import BotDenied, check_function_access
from telegram_bots.menu import BUYER_BALANCE
from .chat_balances import balance_text
from .models import Buyer, BuyerBalanceChat, BalanceChatPublication, DigitalBot, AuditEvent, StaffConversation

PREFIX = 'buyerbalance:'
PAGE_SIZE = 20


def buyers_menu(offset=0, menu_key=None):
    # При редактировании одного сообщения каждому новому открытию нужен свой ключ.
    menu_key = menu_key or secrets.token_hex(8)
    buyers = list(Buyer.objects.select_related('balance_chat').order_by('name', 'pk')[offset:offset+PAGE_SIZE+1])
    if not buyers:
        return {'text': 'Цифровых покупателей пока нет. Добавьте покупателя и привяжите его чат в CRM.'}
    buttons = []
    for buyer in buyers[:PAGE_SIZE]:
        chat = getattr(buyer, 'balance_chat', None)
        label = buyer.name[:52] + (' · нет чата' if chat is None else '')
        buttons.append([{'text': label, 'callback_data': f'{PREFIX}send:{buyer.pk}:{menu_key}'}])
    navigation = []
    if offset:
        navigation.append({'text': '← Назад', 'callback_data': f'{PREFIX}list:{max(0,offset-PAGE_SIZE)}:{menu_key}'})
    if len(buyers) > PAGE_SIZE:
        navigation.append({'text': 'Далее →', 'callback_data': f'{PREFIX}list:{offset+PAGE_SIZE}:{menu_key}'})
    if navigation:
        buttons.append(navigation)
    buttons.append([{'text': 'В главное меню', 'callback_data': 'menu'}])
    return {'text': 'Кому отправить текущий баланс?\nПосле выбора цифровой бот отправит сообщение в привязанный чат покупателя.',
            'reply_markup': {'inline_keyboard': buttons}}


@transaction.atomic
def request_balance(*, access, buyer_id, message_id, menu_key=None):
    """Одна отправка на меню выбора; повтор Telegram или двойной клик безопасны."""
    actor = check_function_access(access, BUYER_BALANCE.code)
    if type(message_id) is not int or not 0 < message_id < 2**63:
        raise BotDenied('invalid_menu', 'Откройте список покупателей заново.')
    key = f'manual:staff:{access.bot_id}:{access.pk}:{message_id}'
    if menu_key is not None:
        if not isinstance(menu_key, str) or len(menu_key) != 16 or any(c not in '0123456789abcdef' for c in menu_key):
            raise BotDenied('invalid_menu', 'Откройте список покупателей заново.')
        key += ':' + menu_key
    previous = BalanceChatPublication.objects.select_for_update().filter(event_key=key).first()
    if previous:
        if previous.buyer_id != buyer_id:
            raise BotDenied('menu_used', 'В этом списке уже выбран другой покупатель. Нажмите «Отправить баланс покупателю» ещё раз.')
        return previous, False
    if not DigitalBot.objects.filter(pk=1, enabled=True).exists():
        raise BotDenied('digital_disabled', 'Цифровой бот выключен. Включите его в настройках CRM перед отправкой.')
    buyer = Buyer.objects.select_for_update().filter(pk=buyer_id).first()
    if not buyer:
        raise BotDenied('buyer_missing', 'Покупатель не найден. Откройте список заново.')
    chat = BuyerBalanceChat.objects.select_for_update().filter(buyer=buyer).first()
    if not chat:
        raise BotDenied('buyer_chat_missing', f'У покупателя «{buyer.name}» нет привязанного чата. Сначала привяжите чат к цифровому покупателю в CRM.')
    if BalanceChatPublication.objects.filter(chat=chat, state__in=['error','uncertain']).exists():
        raise BotDenied('publication_blocked', 'В этом чате есть неподтверждённая отправка. Проверьте её в настройках цифрового бота CRM, чтобы не продублировать сообщение.')
    if BalanceChatPublication.objects.filter(event_key__startswith=f'manual:staff:{access.bot_id}:{access.pk}:',
            created_at__gt=timezone.now()-timedelta(seconds=access.bot.cooldown_seconds)).exists():
        raise BotDenied('rate_limited', 'Баланс уже запрошен недавно. Повторите через несколько секунд.')
    at = timezone.now()
    publication = BalanceChatPublication.objects.create(event_key=key, chat=chat, buyer=buyer,
        text=balance_text(buyer.balance, at), generated_at=at)
    AuditEvent.objects.create(actor=actor, kind='buyer_balance_requested',
        detail=f'buyer={buyer.pk};chat={chat.pk};publication={publication.pk};staff_access={access.pk}')
    return publication, True


def handle(access, message, callback):
    data = callback.get('data', '') if callback else ''
    opening = data == BUYER_BALANCE.code or (not callback and message.get('text') == BUYER_BALANCE.title)
    if not opening and not (isinstance(data, str) and data.startswith(PREFIX)):
        return None
    check_function_access(access, BUYER_BALANCE.code)
    if opening:
        # Прерываем только ожидание ввода текста; цифровой заказ/черновик не меняется.
        StaffConversation.objects.filter(access=access).delete()
        return buyers_menu()
    parts = data[len(PREFIX):].split(':')
    if (len(parts) not in (2, 3) or not parts[1].isascii() or not parts[1].isdecimal()
            or len(parts[1]) > 18):
        raise BotDenied('invalid_menu', 'Откройте список покупателей заново.')
    menu_key = parts[2] if len(parts) == 3 else None
    if menu_key is not None and (len(menu_key) != 16 or any(c not in '0123456789abcdef' for c in menu_key)):
        raise BotDenied('invalid_menu', 'Откройте список покупателей заново.')
    value = int(parts[1])
    if parts[0] == 'list' and value <= 1_000_000 and value % PAGE_SIZE == 0:
        return buyers_menu(value, menu_key)
    if parts[0] != 'send' or value <= 0:
        raise BotDenied('invalid_menu', 'Откройте список покупателей заново.')
    publication, created = request_balance(access=access, buyer_id=value,
        message_id=message.get('message_id'), menu_key=menu_key)
    name = publication.buyer.name
    if not created:
        text = ('Баланс уже отправлен' if publication.state == 'done' else
                'Проверьте отправку в настройках цифрового бота CRM' if publication.state in ('error','uncertain') else
                'Отправка баланса уже стоит в очереди')
        return {'text': f'{text}: {name}. Повторное сообщение не создано.'}
    return {'text': f'Баланс покупателя «{name}» поставлен в очередь отправки в его чат.\n\n{publication.text}'}
