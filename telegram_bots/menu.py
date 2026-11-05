"""Компактный реестр: добавление функции не меняет авторизацию или транспорт."""
from dataclasses import dataclass


@dataclass(frozen=True)
class BotFunction:
    code: str
    title: str
    permissions: tuple[str, ...]

    def allowed(self, user):
        return user.has_perms(self.permissions)


WHOLESALE = BotFunction('wholesale_stock_price', 'Скачать оптовый прайс наличия', ('price.generate_wholesale_price',))
SUPPLIER_TEMPLATES = BotFunction('supplier_price_templates', 'Скачать шаблоны поставщиков с ценами',
    ('price.download_supplier_template', 'price.view_supplier_prices'))
FUNCTIONS = {item.code: item for item in (WHOLESALE, SUPPLIER_TEMPLATES)}


def main_menu(user):
    # Постоянная клавиатура находится у поля ввода и остаётся после нажатия.
    buttons = [[{'text': item.title}] for item in FUNCTIONS.values() if item.allowed(user)]
    if not buttons:
        return {'remove_keyboard': True}
    return {'keyboard': buttons,
        'is_persistent': True, 'resize_keyboard': True, 'one_time_keyboard': False}


def supplier_label(supplier, user):
    return supplier.name if user.has_perm('partners.view_supplier_details') else supplier.safe_label


def supplier_menu(suppliers, user):
    return {'inline_keyboard': [[{'text': supplier_label(row, user),
        'callback_data': f'{SUPPLIER_TEMPLATES.code}:{row.pk}'}] for row in suppliers]
        + [[{'text': 'Назад', 'callback_data': 'menu'}]]}


def warehouse_menu(warehouses):
    rows = [[{'text': row.name, 'callback_data': f'{WHOLESALE.code}:{row.pk}'}] for row in warehouses]
    return {'inline_keyboard': rows + [[{'text': 'Назад', 'callback_data': 'menu'}]]}
