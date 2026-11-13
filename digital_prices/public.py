"""Единственная граница внутренних цен: рендереру недоступны ORM и закупочные поля."""
from dataclasses import dataclass, asdict, replace
from datetime import timedelta
import re
from django.db import transaction
from django.utils import timezone
from .models import CatalogState, Product, Integration, ManualPriceEntry
from .services import product_price, selling_price, require
from .classification import characteristics, region_code, COUNTRIES, clean_caption


@dataclass(frozen=True)
class PublicRow:
    name: str
    category: str
    section: str
    region: str
    price: str
    availability: str
    family: str = ''
    subgroup: str = ''
    label: str = ''
    region_label: str = ''
    order: int = 0
    has_markup: bool = False


@dataclass(frozen=True)
class PublicCatalog:
    revision: int
    generated_at: str
    source_at: str | None
    stale: bool
    rows: tuple[PublicRow, ...]


def safe_text(value):
    value = re.sub(r'https?://\S+|@[\w]+|pv2_[A-Za-z0-9]+|(?:pan\s*yan(?:\s*store)?|yan\s*store)', '', str(value), flags=re.I)
    value = ''.join(char for char in value if char >= ' ' and char != '\x7f')
    return ' '.join(value.split()).strip(' ·-|')


def product_row(product):
    """Один и тот же публичный вариант используется в таблице и изображении."""
    price = product_price(product)
    family, subgroup, label = characteristics(product.source_type, product.source_name, product.attributes)
    if product.category_manual:
        family, subgroup, label = safe_text(product.category), '', clean_caption(product.display_name or product.source_name)
    elif product.display_name:
        label = clean_caption(product.display_name)
    variable = product.source_type == 'steam_topup' and product.purchase_cost is None
    if variable:
        subgroup = 'Валюты API'
    code = region_code(product.region)
    if product.source_type == 'empty':
        label = ('PS ' + COUNTRIES[code]) if code in ('tr', 'sng', 'in', 'pl', 'id', 'us') else clean_caption(product.source_name)
        if product.region == 'xbox_usa':
            label = 'Xbox'
    return PublicRow(safe_text(clean_caption(product.display_name or product.source_name)) or 'Цифровое предложение',
        safe_text(product.category) or 'Другие цифровые предложения', product.section,
        safe_text(code), 'По расчёту' if variable else 'Цена уточняется' if price is None else f'{price:,.0f} ₽'.replace(',', ' '),
        'no' if product.availability == 'no' else 'unknown' if product.requires_review else product.availability,
        safe_text(family), safe_text(subgroup), safe_text(label), COUNTRIES.get(code, safe_text(product.region)), product.position,
        product.markup is not None)


def coefficient_text(value):
    if value is None:
        return None
    whole, _, fraction = format(value, '.4f').partition('.')
    return whole + '.' + fraction.rstrip('0').ljust(3, '0')


def manual_row(entry):
    # Старые value/unit сохранены как исторические данные, но больше не задают цену.
    price = selling_price(entry.manual_cost, 'RUB', entry.markup, Product.Rule.OTHER)
    text = 'Цена уточняется' if price is None else f'{price:,.0f} ₽'.replace(',', ' ')
    if entry.pricing_mode == ManualPriceEntry.PricingMode.PERCENT:
        if entry.cost_percent is None or entry.markup_percent is None:
            text = 'Цена уточняется'
        else:
            number = format(entry.cost_percent + entry.markup_percent, '.2f').rstrip('0').rstrip('.') or '0'
            text = '+' + number + '%'
    elif entry.pricing_mode == ManualPriceEntry.PricingMode.COEFFICIENT:
        if entry.cost_coefficient is None or entry.markup_coefficient is None:
            text = 'Цена уточняется'
        else:
            text = coefficient_text(entry.cost_coefficient + entry.markup_coefficient)
    code = region_code(entry.region)
    family = 'Игры' if entry.kind == 'game_tariff' else 'Пополнение Steam'
    return PublicRow(safe_text(entry.label), family, 'services', code, text, 'unknown' if entry.sheet_issue else 'yes', family,
                     '' if entry.kind == 'game_tariff' else 'Ручные тарифы', safe_text(entry.label),
                     COUNTRIES.get(code, safe_text(entry.region)), entry.position,
                     getattr(entry, {'percent':'markup_percent','coefficient':'markup_coefficient'}.get(entry.pricing_mode,'markup')) is not None)


def populated_blocks(catalog):
    """Весь блок сохраняется, если хоть у одной строки задана эффективная наценка.

    Проверяем наценку, а не наличие API: недоступные товары и строки с ещё
    неизвестным себесом не должны исчезать из заполненного блока.
    """
    from .layout import group_key
    populated = {(row.section, group_key(row)) for row in catalog.rows if row.has_markup}
    return replace(catalog, rows=tuple(row for row in catalog.rows if (row.section, group_key(row)) in populated))


@transaction.atomic
def snapshot(*, actor, buyer=None):
    require(actor, 'download_prices')
    state = CatalogState.objects.select_for_update().get(pk=1)
    now, rows, review = timezone.now(), [], False
    from .buyer_pricing import profile_rows
    for row in profile_rows(Product.objects.all(), ManualPriceEntry.objects.filter(source_archived=False), buyer):
        is_product = isinstance(row, Product)
        review = review or (row.requires_review if is_product else bool(row.sheet_issue))
        rows.append(product_row(row) if is_product else manual_row(row))
    config = Integration.objects.filter(pk=1).first()
    return PublicCatalog(state.revision, now.isoformat(), state.source_at.isoformat() if state.source_at else None,
        review or bool(config and (config.error_category or config.manual_sheet_enabled and config.manual_sheet_error_category))
        or not state.source_at or now - state.source_at > timedelta(days=1), tuple(rows))


def serialize(catalog):
    data = asdict(catalog)
    # Флаг нужен только для отбора блоков; в сохранённом публичном DTO нет даже
    # служебной отметки о наличии наценки, тем более её значений или себестоимости.
    for row in data['rows']:
        row.pop('has_markup', None)
    return data
