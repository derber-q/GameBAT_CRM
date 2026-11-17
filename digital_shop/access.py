"""Проверка настоящего участника группы, действующей привязки и выключателей."""
from dataclasses import dataclass
from django.core.exceptions import PermissionDenied
from digital_sales.models import BuyerBalanceChat, Supplier, DigitalBot
from .models import ShopConfig, ShopChat


@dataclass(frozen=True)
class Access:
    chat_id: int
    buyer_id: int
    user_id: int


def binding(access):
    config = ShopConfig.objects.filter(pk=1, enabled=True).first()
    row = BuyerBalanceChat.objects.filter(pk=access.chat_id, buyer_id=access.buyer_id).first()
    if (not config or not DigitalBot.objects.filter(pk=1, enabled=True).exists() or not row or
            not ShopChat.objects.filter(binding=row, enabled=True).exists() or
            any(access.chat_id in s.chat_ids for s in Supplier.objects.all())):
        raise PermissionDenied('Магазин в этой группе недоступен. Обратитесь к администратору.')
    return row


def member(client, *, chat, sender, sender_chat=None):
    if (not isinstance(chat, dict) or chat.get('type') not in ('group', 'supergroup') or sender_chat or
            not isinstance(sender, dict) or sender.get('is_bot') is not False or
            type(sender.get('id')) is not int or sender['id'] <= 0 or type(chat.get('id')) is not int):
        raise PermissionDenied('Откройте магазин от личного аккаунта участника группы.')
    row = BuyerBalanceChat.objects.filter(pk=chat['id']).first()
    if row is None:
        raise PermissionDenied('Группа не подключена к магазину.')
    access = Access(row.pk, row.buyer_id, sender['id'])
    binding(access)
    response = client.call('getChatMember', {'chat_id': row.pk, 'user_id': sender['id']})
    if not isinstance(response, dict) or response.get('status') not in ('creator', 'administrator', 'member'):
        raise PermissionDenied('Не удалось подтвердить участие в группе.')
    return access
