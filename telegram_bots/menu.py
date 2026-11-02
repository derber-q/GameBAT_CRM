"""Компактный реестр: добавление функции не меняет авторизацию или транспорт."""
from dataclasses import dataclass


@dataclass(frozen=True)
class BotFunction:
    code: str
    title: str
    permission: str


WHOLESALE = BotFunction('wholesale_stock_price', 'Скачать оптовый прайс наличия', 'price.generate_wholesale_price')
FUNCTIONS = {WHOLESALE.code: WHOLESALE}


def main_menu(user):
    # Постоянная клавиатура находится у поля ввода и остаётся после нажатия.
    return {'keyboard': [[{'text': item.title}]
        for item in FUNCTIONS.values() if user.has_perm(item.permission)],
        'is_persistent': True, 'resize_keyboard': True, 'one_time_keyboard': False}


def warehouse_menu(warehouses):
    rows = [[{'text': row.name, 'callback_data': f'{WHOLESALE.code}:{row.pk}'}] for row in warehouses]
    return {'inline_keyboard': rows + [[{'text': 'Назад', 'callback_data': 'menu'}]]}
