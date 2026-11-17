"""Отметки недавнего снижения опта по сохранённой истории карточек."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from django.db.models import Q

from catalog.models import ProductFieldChange

WHOLESALE_DECREASE_DAYS = 7


@dataclass(frozen=True)
class WholesalePriceDecrease:
    previous_price: Decimal
    current_price: Decimal
    changed_at: datetime


def recent_wholesale_price_decreases(products, *, at):
    """Один запрос на прайс; последнее изменение опта важнее прежнего снижения.

    Создание цены из пустого значения, повышение и отсутствие достоверной
    истории не считаются снижением. Сверка с текущей ценой исключает устаревшую
    отметку при несовпадении карточки и аудита. Экспорт не меняет историю БД.
    """
    prices = {(kind, product.pk): product.wholesale_price for kind, product in products}
    if not prices:
        return {}
    ids = {kind: [pk for kind_key, pk in prices if kind_key == kind] for kind in ('cd', 'tech')}
    changes = ProductFieldChange.objects.filter(
        Q(event__cd_id__in=ids['cd']) | Q(event__tech_id__in=ids['tech']),
        field_name='wholesale_price',
        event__created_at__gt=at - timedelta(days=WHOLESALE_DECREASE_DAYS),
        event__created_at__lte=at,
    ).order_by('-event__created_at', '-event_id', '-pk').values(
        'event__product_kind', 'event__cd_id', 'event__tech_id',
        'event__created_at', 'old_value', 'new_value',
    )
    seen, result = set(), {}
    for change in changes:
        kind = change['event__product_kind']
        key = kind, change['event__' + kind + '_id']
        if key in seen or change['old_value'] == change['new_value']:
            continue
        try:
            previous = Decimal(change['old_value'])
            current = Decimal(change['new_value'])
        except (InvalidOperation, ValueError):
            seen.add(key)
            continue
        if previous.is_finite() and current.is_finite() and previous == current:
            continue
        seen.add(key)
        if (previous.is_finite() and current.is_finite() and previous > current >= 0
                and prices.get(key) == current):
            result[key] = WholesalePriceDecrease(previous, current, change['event__created_at'])
    return result
