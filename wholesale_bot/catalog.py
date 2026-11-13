"""Просмотр техники из того же склада, что XLSX; без создания заказа и резерва."""
from collections import OrderedDict
import re

from django.core.exceptions import ValidationError
from django.db import transaction

from catalog.product_ordering import normalized_order_name, tech_price_order
from warehouse.models import TechWarehouseStock
from .services import operator

ROOT = 'wc:r:0'
GROUP_PAGE = 16
PRODUCT_PAGE = 8
SECTIONS = {'sony': 'SONY', 'nintendo': 'NINTENDO'}


def _button(text, callback):
    return {'text': text, 'callback_data': callback}


def _money(value):
    return f'{value:,.2f}'.replace(',', ' ').replace('.', ',')


def _icon(name):
    name = name.casefold()
    for token, icon in (('геймпад', '🎮'), ('консол', '🕹'), ('гарнитур', '🎧'),
                        ('науш', '🎧'), ('заряд', '🔌'), ('vr', '🥽'), ('чехол', '🧳')):
        if token in name:
            return icon
    return '📦'


def _parse(callback):
    if not isinstance(callback, str) or len(callback.encode('utf-8')) > 64:
        raise ValidationError('Откройте актуальное меню техники под прайсом.')
    section = re.fullmatch(r'wc:s:(sony|nintendo):([0-9]{1,5})', callback)
    if section:
        return 's', [section[1], int(section[2])]
    match = re.fullmatch(r'wc:(r|g|p):([0-9]{1,19})(?::([0-9]{1,19}))?(?::([0-9]{1,19}))?', callback)
    if not match:
        raise ValidationError('Откройте актуальное меню техники под прайсом.')
    action, *numbers = match.groups()
    values = [int(value) for value in numbers if value is not None]
    if (len(values) != {'r':1, 'g':3, 'p':2}[action]
            or any(value >= 2**63 for value in values) or values[-1] > 99999
            or any(value <= 0 for value in values[:-1])):
        raise ValidationError('Откройте актуальное меню техники под прайсом.')
    return action, values


def _page_buttons(page, pages, callback):
    buttons = []
    if page:
        buttons.append(_button('← Назад', callback(page - 1)))
    if page + 1 < pages:
        buttons.append(_button('Далее →', callback(page + 1)))
    return [buttons] if buttons else []


def _section(product):
    brand = normalized_order_name(product.brand.name).replace(' ', '')
    kind = normalized_order_name(product.product_type.name)
    if brand in ('sony', 'powera'):
        return 'sony'
    if brand == 'nintendo' or ('защитн' in kind and 'стекл' in kind):
        return 'nintendo'
    if ('подставк' in kind and 'консол' in kind or 'охлажд' in kind and 'консол' in kind
            or 'переходник' in kind):
        return 'sony'
    return None


def _category_name(product, section=None):
    brand = product.brand.name
    if normalized_order_name(brand) in ('без бренда', 'no brand', 'unbranded') or normalized_order_name(brand) == section:
        return product.product_type.name
    return f'{brand} · {product.product_type.name}'


def _group_button(key, stocks, section=None):
    product = stocks[0].tech
    title = f'{_icon(product.product_type.name)} {_category_name(product, section)}'
    return _button(title[:100], f'wc:g:{key[0]}:{key[1]}:0')


def _root(groups, page=0, *, notice=''):
    entries = []
    for section, title in SECTIONS.items():
        if any(_section(stocks[0].tech) == section for stocks in groups.values()):
            entries.append(_button(title, f'wc:s:{section}:0'))
    entries += [_group_button(key, stocks) for key, stocks in groups.items() if _section(stocks[0].tech) is None]
    if not entries:
        return {'text':'Сейчас техники с оптовой ценой в наличии нет. Позже запросите новый прайс.', 'markup':{}}
    pages = (len(entries) + GROUP_PAGE - 1) // GROUP_PAGE
    page = min(page, pages - 1)
    buttons = entries[page * GROUP_PAGE:(page + 1) * GROUP_PAGE]
    keyboard = [buttons[index:index + 2] for index in range(0, len(buttons), 2)]
    keyboard += _page_buttons(page, pages, lambda p: f'wc:r:{p}')
    return {'text': (notice + '\n\n' if notice else '') + '🛍 Техника в наличии\nВыберите категорию — покажу оптовые цены и остатки.'
            + (f'\nСтраница {page + 1} из {pages}' if pages > 1 else ''),
            'markup': {'inline_keyboard': keyboard}}


def _section_menu(groups, section, page):
    entries = [(key, stocks) for key, stocks in groups.items() if _section(stocks[0].tech) == section]
    if not entries:
        return _root(groups, notice='В этом разделе больше нет доступных товаров. Выберите другую категорию.')
    pages = (len(entries) + GROUP_PAGE - 1) // GROUP_PAGE
    page = min(page, pages - 1)
    buttons = [_group_button(key, stocks, section) for key, stocks in entries[page * GROUP_PAGE:(page + 1) * GROUP_PAGE]]
    keyboard = [buttons[index:index + 2] for index in range(0, len(buttons), 2)]
    keyboard += _page_buttons(page, pages, lambda p: f'wc:s:{section}:{p}')
    keyboard.append([_button('🛍 Все категории', ROOT)])
    return {'text':f'{SECTIONS[section]}\nВыберите категорию техники в наличии.', 'markup':{'inline_keyboard':keyboard}}


@transaction.atomic
def catalog_view(callback=ROOT):
    """Вызывается после проверки покупателя; сеть и финансовые сервисы не используются."""
    action, values = _parse(callback)
    config, _actor = operator()
    # Те же условия включения техники, что price.excel._tech_rows. Нулей,
    # архивных карточек и товаров без оптовой цены в кнопках быть не должно.
    stocks = list(TechWarehouseStock.objects.filter(warehouse_id=config.warehouse_id,
        quantity__gt=0, tech__is_archived=False, tech__wholesale_price__isnull=False)
        .select_related('tech__brand', 'tech__product_type')
        .only('quantity', 'tech__name', 'tech__wholesale_price', 'tech__brand__name', 'tech__product_type__name'))
    stocks.sort(key=lambda stock: tech_price_order(stock.tech, for_excel=True)[0])
    groups = OrderedDict()
    for stock in stocks:
        groups.setdefault((stock.tech.brand_id, stock.tech.product_type_id), []).append(stock)
    if action == 'r':
        return _root(groups, values[0])
    if action == 's':
        return _section_menu(groups, values[0], values[1])
    if action == 'p':
        product_id, page = values
        stock = next((stock for stock in stocks if stock.tech_id == product_id), None)
        if stock is None:
            return _root(groups, notice='Этот товар больше недоступен. Выберите технику из актуального списка.')
        product = stock.tech
        return {'text': f'{product.name}\n\n{_category_name(product)}\n'
                f'Оптовая цена: {_money(product.wholesale_price)} ₽\nВ наличии: {stock.quantity} шт.',
                'markup': {'inline_keyboard': [
                    [_button('← К товарам', f'wc:g:{product.brand_id}:{product.product_type_id}:{page}')],
                    [_button('🛍 Все категории', ROOT)],
                ]}}
    brand, kind, page = values
    selected = groups.get((brand, kind))
    if not selected:
        return _root(groups, notice='В этом разделе больше нет доступных товаров. Выберите другую категорию.')
    pages = (len(selected) + PRODUCT_PAGE - 1) // PRODUCT_PAGE
    page = min(page, pages - 1)
    product = selected[0].tech
    section = _section(product)
    lines = [f'{_icon(product.product_type.name)} {_category_name(product)}', '']
    keyboard = []
    for stock in selected[page * PRODUCT_PAGE:(page + 1) * PRODUCT_PAGE]:
        product = stock.tech
        price = _money(product.wholesale_price)
        lines.append(f'• {product.name}\n  {price} ₽ · В наличии: {stock.quantity} шт.')
        keyboard.append([_button(f'{product.name[:65]} · {price} ₽ · {stock.quantity} шт.', f'wc:p:{product.pk}:{page}')])
    keyboard += _page_buttons(page, pages, lambda p: f'wc:g:{brand}:{kind}:{p}')
    keyboard.append([_button(f'← {SECTIONS[section]}', f'wc:s:{section}:0') if section else _button('🛍 Все категории', ROOT)])
    if pages > 1:
        lines.append(f'\nСтраница {page + 1} из {pages}')
    return {'text':'\n'.join(lines), 'markup':{'inline_keyboard':keyboard}}


def price_markup():
    return catalog_view()['markup']
