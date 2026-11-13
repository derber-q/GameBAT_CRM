"""CRM-бот сначала выбирает покупателя, затем ставит его прайс в штатную очередь."""
from digital_sales.models import Buyer
from telegram_bots.access import check_function_access, BotDenied
from telegram_bots.menu import DIGITAL_PRICES
from .models import BuyerPriceRequest


def handle(bot, access, receipt, chat_id, message, callback):
    data = callback.get('data', '')
    root = data == DIGITAL_PRICES.code or (not callback and message.get('text') == DIGITAL_PRICES.title)
    if not root and not (isinstance(data, str) and data.startswith(DIGITAL_PRICES.code + ':')):
        return None
    check_function_access(access, DIGITAL_PRICES.code)
    action, value = 'page', '0'
    if not root:
        parts = data.split(':')
        if len(parts) != 3 or parts[1] not in ('page', 'buyer'):
            raise BotDenied('unknown_command', 'Откройте список покупателей заново.')
        _, action, value = parts
    if not value.isascii() or not value.isdecimal() or len(value) > 18:
        raise BotDenied('unknown_command', 'Откройте список покупателей заново.')
    value = int(value)
    if action == 'buyer':
        buyer = Buyer.objects.select_for_update().filter(pk=value).first()
        if buyer is None:
            raise BotDenied('buyer_missing', 'Покупатель не найден. Откройте список заново.')
        from telegram_bots.handlers import _request_job
        job = _request_job(bot, access, receipt, chat_id, function=DIGITAL_PRICES.code)
        BuyerPriceRequest.objects.create(job=job, buyer=buyer)
        return {'text': f'Формирую полный комплект прайсов для покупателя «{buyer.name}» с его наценками…'}
    buyers = list(Buyer.objects.order_by('name', 'pk')[value:value + 21])
    rows = [[{'text': buyer.name[:60], 'callback_data': f'{DIGITAL_PRICES.code}:buyer:{buyer.pk}'}] for buyer in buyers[:20]]
    navigation = []
    if value:
        navigation.append({'text': '← Предыдущие', 'callback_data': f'{DIGITAL_PRICES.code}:page:{max(0, value - 20)}'})
    if len(buyers) > 20:
        navigation.append({'text': 'Следующие →', 'callback_data': f'{DIGITAL_PRICES.code}:page:{value + 20}'})
    if navigation:
        rows.append(navigation)
    return {'text': 'Для какого покупателя сформировать цифровой прайс?' if rows else
            'В CRM пока нет цифровых покупателей. Добавьте покупателя в CRM и откройте список заново.',
            'reply_markup': {'inline_keyboard': rows}}
