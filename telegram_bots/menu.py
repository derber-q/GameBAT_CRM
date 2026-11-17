"""Компактный реестр: добавление функции не меняет авторизацию или транспорт."""
from dataclasses import dataclass


@dataclass(frozen=True)
class BotFunction:
    code: str
    title: str
    permissions: tuple[str, ...]

    def allowed(self, user):
        if self.code == 'digital_price_images':
            from digital_prices.services import ready
            if not ready():
                return False
        return user.has_perms(self.permissions)


WHOLESALE = BotFunction('wholesale_stock_price', 'Скачать оптовый прайс наличия', ('price.generate_wholesale_price',))
SUPPLIER_TEMPLATES = BotFunction('supplier_price_templates', 'Скачать шаблоны поставщиков с ценами',
    ('price.download_supplier_template', 'price.view_supplier_prices'))
DIGITAL = BotFunction('digital_sales', 'Цифровые продажи',
    ('sales.create_sale', 'digital_sales.create_digital_sales', 'digital_sales.telegram_digital_sales'))
WHOLESALE_CONTROL = BotFunction('wholesale_bot_control', 'Оптовый бот: вкл / выкл',
    ('wholesale_bot.configure_wholesale_bot',))
DIGITAL_PRICES = BotFunction('digital_price_images', 'Прайс цифровых товаров', ('digital_prices.download_prices',))
BUYER_BALANCE = BotFunction('digital_buyer_balance', 'Отправить баланс покупателю',
    ('digital_sales.view_digital_sales', 'digital_sales.manage_digital_buyers', 'digital_sales.telegram_digital_sales'))
SUPPLIER_BALANCE = BotFunction('digital_supplier_balance', 'Баланс у поставщика',
    ('digital_sales.view_digital_sales', 'digital_sales.view_digital_reconciliation', 'digital_sales.telegram_digital_sales'))
FUNCTIONS = {item.code: item for item in (WHOLESALE, SUPPLIER_TEMPLATES, DIGITAL, WHOLESALE_CONTROL, DIGITAL_PRICES, BUYER_BALANCE, SUPPLIER_BALANCE)}


def main_menu(user):
    buttons = [{'text': item.title, 'callback_data': item.code}
               for item in FUNCTIONS.values() if item.allowed(user)]
    return {'inline_keyboard': [[button] for button in buttons]}


def screen_reply(reply, message, callback):
    """Добавляет навигацию к ответу; действия и проверки прав остаются в обработчиках."""
    data = callback.get('data', '') if callback else ''
    if isinstance(data, str) and data.startswith('dbal:'):
        return reply  # Отдельное уведомление сверки не становится главным меню.
    rows = [list(row) for row in reply.get('reply_markup', {}).get('inline_keyboard', [])]
    is_root = data == 'menu' or (not callback and message.get('text', '').split(' ', 1)[0]
                                in ('/start', '/menu', '/help'))
    if not is_root:
        back = None
        if isinstance(data, str):
            if data.startswith(SUPPLIER_TEMPLATES.code + ':'):
                back = SUPPLIER_TEMPLATES.code
            elif data.startswith(DIGITAL_PRICES.code + ':'):
                back = DIGITAL_PRICES.code
            elif data.startswith('buyerbalance:'):
                back = BUYER_BALANCE.code
            elif data.startswith('dg:'):
                parts = data.split(':')
                back = ':'.join(parts[:3]) + ':open' if len(parts) >= 4 and parts[3] in ('buyers', 'price') else DIGITAL.code
        present = {button.get('callback_data') for row in rows for button in row}
        navigation = []
        if back and back not in present:
            navigation.append({'text': '← Назад', 'callback_data': back})
        if 'menu' not in present:
            navigation.append({'text': 'Главное меню', 'callback_data': 'menu'})
        if navigation:
            rows.append(navigation)
    elif not callback:
        # Telegram сохраняет прежнюю ReplyKeyboard, пока бот явно не удалит её.
        reply['remove_reply_keyboard'] = True
    reply['reply_markup'] = {'inline_keyboard': rows}
    reply['screen'] = True
    if callback and type(message.get('message_id')) is int and 0 < message['message_id'] < 2**63:
        reply['message_id'] = message['message_id']
        reply['message_has_photo'] = bool(message.get('photo'))
    return reply


def supplier_label(supplier, user):
    return supplier.name if user.has_perm('partners.view_supplier_details') else supplier.safe_label


def supplier_menu(suppliers, user):
    return {'inline_keyboard': [[{'text': supplier_label(row, user),
        'callback_data': f'{SUPPLIER_TEMPLATES.code}:{row.pk}'}] for row in suppliers]
        + [[{'text': 'Назад', 'callback_data': 'menu'}]]}


def warehouse_menu(warehouses):
    rows = [[{'text': row.name, 'callback_data': f'{WHOLESALE.code}:{row.pk}'}] for row in warehouses]
    return {'inline_keyboard': rows + [[{'text': 'Назад', 'callback_data': 'menu'}]]}
