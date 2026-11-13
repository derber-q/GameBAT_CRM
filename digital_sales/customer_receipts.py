"""Публичный чек: разрешены только клиентские названия, количества, итог и баланс."""
import re
import unicodedata
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import BuyerBalanceChat, BalanceChatPublication, DigitalOrder

# При подозрительном названии не удаляем лишь слово, оставляя рядом секретную сумму:
# вся такая строка заменяется нейтральным названием. Комментарии/исходник не используются.
PRIVATE_TITLE = re.compile(
    r'pan[\W_]*yan(?:[\W_]*store)?|yan[\W_]*store|пан[\W_]*ян|ян[\W_]*стор|'
    r'себес|закуп|поставщик|(?<![a-z])(?:cost|cogs|supplier|password|login|token)(?![a-z])|'
    r'парол|логин|https?://|www\.|@', re.IGNORECASE)


def public_title(value):
    value = unicodedata.normalize('NFKC', str(value or ''))
    value = ' '.join(''.join(' ' if ch.isspace() else ch for ch in value
                             if ch.isspace() or unicodedata.category(ch)[0] != 'C').split())
    if not value or PRIVATE_TITLE.search(value):
        return 'Цифровой товар'
    return value[:255]


def receipt_parts(*, sale, balance, at):
    """Не читаем артикулы поставщика, распределённые цены строк и снимки себестоимости."""
    from .chat_balances import balance_text
    header = f'✅ Продажа SALE-{sale.pk:06d} завершена\nСостав заказа:'
    total = f'{sale.total_amount:,.2f}'.replace(',', ' ').replace('.', ',')
    footer = f'Сумма продажи: {total} ₽\n{balance_text(balance, at)}'
    groups, lines, size = [], [], 0
    for number, item in enumerate(sale.custom_items.only('product_name_snapshot', 'quantity').order_by('pk'), 1):
        line = f'{number}. {public_title(item.product_name_snapshot)} × {item.quantity}'
        length = len(line.encode('utf-16-le')) // 2 + 1
        if lines and size + length > 3300:
            groups.append(lines)
            lines, size = [], 0
        lines.append(line)
        size += length
    groups.append(lines or ['Цифровой товар'])
    result = []
    for number, group in enumerate(groups, 1):
        page = f'\nЧасть {number}/{len(groups)}' if len(groups) > 1 else ''
        text = header + page + '\n' + '\n'.join(group) + '\n\n' + footer
        if len(text.encode('utf-16-le')) // 2 > 4096:
            raise ValueError('Публичный чек превышает размер сообщения.')
        result.append(text)
    return result


@transaction.atomic
def enqueue_sale_receipt(buyer, *, sale):
    """Тот же ключ события и outbox: повтор завершения не дублирует чек или списание."""
    if not sale.is_completed or not DigitalOrder.objects.filter(
            sale=sale, buyer=buyer, is_retail=False, state=DigitalOrder.State.COMPLETED).exists():
        raise ValidationError('Завершённая цифровая продажа не принадлежит этому покупателю.')
    chat = BuyerBalanceChat.objects.filter(buyer=buyer).first()
    if chat is None:
        return
    base_key = f'buyer:{buyer.pk}:sale:{sale.pk}'
    existing = BalanceChatPublication.objects.filter(event_key=base_key).first()
    if existing is not None:
        return existing
    at = timezone.now()
    first = None
    for number, text in enumerate(receipt_parts(sale=sale, balance=buyer.balance, at=at), 1):
        key = base_key
        if number > 1:
            key += f':part:{number}'
        row, _ = BalanceChatPublication.objects.get_or_create(event_key=key, defaults={
            'chat': chat, 'buyer': buyer, 'text': text, 'generated_at': at})
        first = first or row
    return first
