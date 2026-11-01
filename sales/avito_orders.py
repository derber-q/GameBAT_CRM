"""Подготовка заказа из расширения не проводит продажу и не меняет наличие."""
from decimal import Decimal, InvalidOperation
import re
from django.core.exceptions import ValidationError
from django.db import transaction
from integrations.models import AvitoListingConnection
from .models import AvitoBrowserOrder


def order_id(value):
    # ID Avito длиннее безопасного JS Number — всегда только строка.
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]{1,64}', value):
        raise ValidationError('Некорректный номер заказа Avito.')
    return value


@transaction.atomic
def prepare_order(data, actor):
    key = order_id(data.get('order_id'))
    if 'отмен' in str(data.get('status', '')).lower():
        raise ValidationError('Отменённый заказ нельзя импортировать как новую продажу.')
    titles = data.get('titles', [])
    if not isinstance(titles, list) or not 1 <= len(titles) <= 100 or any(
            not isinstance(t, str) or not 1 <= len(t.strip()) <= 500 for t in titles):
        raise ValidationError('Не удалось прочитать названия товаров заказа.')
    carrier = str(data.get('carrier', '')).strip()
    if len(carrier) > 100:
        raise ValidationError('Слишком длинное название службы доставки.')
    raw = data.get('amount')
    try:
        amount = Decimal(str(raw)) if raw else None
        if amount is not None and (not amount.is_finite() or amount < 0 or amount > Decimal('999999999999999999.99') or amount.as_tuple().exponent < -2):
            raise ValueError
    except (InvalidOperation, ValueError):
        raise ValidationError('Некорректная сумма заказа.') from None
    order, _ = AvitoBrowserOrder.objects.get_or_create(external_id=key, defaults={
        'titles':[t.strip() for t in titles], 'carrier':carrier, 'displayed_amount':amount, 'created_by':actor})
    return order


def initial_lines(order):
    rows = []
    for title in order.titles:
        matches = list(AvitoListingConnection.objects.select_related('profile__cd', 'profile__tech').filter(
            remote_listing__title__iexact=title)[:2])
        if len(matches) != 1:
            continue
        profile = matches[0].profile
        product = profile.product
        if not product.is_archived:
            rows.append(dict(product_type=profile.product_kind, product_id=product.pk, quantity=1,
                             label=f'{profile.product_kind.upper()} — {product.name}',
                             prices={'retail':str(product.avito_price) if product.avito_price is not None else None}))
    return rows
