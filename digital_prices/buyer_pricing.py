"""Профиль покупателя меняет только наценки, сохраняя общую себестоимость и округление."""
from copy import copy
from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction

from core.db_retry import retry_database_lock
from digital_sales.models import Buyer
from .models import BuyerMarkup, CatalogState, Product, ManualPriceEntry, AuditEvent
from .services import require

FIELDS = ('markup', 'markup_percent', 'markup_coefficient')


def selected_buyer(raw):
    if raw in ('', None):
        return None
    if not isinstance(raw, str) or not raw.isascii() or not raw.isdecimal() or len(raw) > 18:
        raise ValidationError('Выберите существующего цифрового покупателя.')
    try:
        return Buyer.objects.get(pk=int(raw))
    except Buyer.DoesNotExist:
        raise ValidationError('Цифровой покупатель не найден. Обновите страницу.') from None


def profile_rows(products, manual, buyer):
    """Две выборки каталога и одна наценок, без запросов на каждую товарную строку."""
    overrides = {} if buyer is None else {
        ('product', row.product_id) if row.product_id else ('manual', row.manual_entry_id): row
        for row in BuyerMarkup.objects.filter(buyer=buyer)
    }
    result = []
    for kind, rows in (('product', products), ('manual', manual)):
        for original in rows:
            row = copy(original)
            override = overrides.get((kind, row.pk))
            if buyer is not None:
                row.profile_revision = f'{row.revision}:{override.revision if override else 0}'
                fields = FIELDS if kind == 'manual' else ('markup',)
                row.general_markups = {field: getattr(original, field) for field in fields}
                row.buyer_markup_values = {field: getattr(override, field) if override else None for field in fields}
                active_field = ({'percent':'markup_percent', 'coefficient':'markup_coefficient'}.get(row.pricing_mode, 'markup')
                                if kind == 'manual' else 'markup')
                row.inherited_markup = row.buyer_markup_values[active_field] is None
            if override:
                for field in FIELDS if kind == 'manual' else ('markup',):
                    value = getattr(override, field)
                    if value is not None:
                        setattr(row, field, value)
            result.append(row)
    return result


@retry_database_lock
@transaction.atomic
def edit_buyer_markup(*, actor, buyer_id, product_id=None, entry_id=None, revision, values):
    actor = require(actor, 'edit_markup')
    require(actor, 'view_cost')
    fields = FIELDS if entry_id is not None else ('markup',)
    if (product_id is None) == (entry_id is None) or not values or set(values) - set(fields):
        raise ValidationError('Для покупателя здесь можно менять только наценки.')
    buyer = Buyer.objects.get(pk=buyer_id)
    state = CatalogState.objects.select_for_update().get(pk=1)
    source = (ManualPriceEntry if entry_id is not None else Product).objects.select_for_update().get(
        pk=entry_id if entry_id is not None else product_id)
    if entry_id is not None and source.source_archived:
        raise ValidationError('Диапазон больше не используется поставщиком. Обновите страницу.', code='conflict')
    target = {'manual_entry': source} if entry_id is not None else {'product': source}
    row = BuyerMarkup.objects.select_for_update().filter(buyer=buyer, **target).first()
    if str(revision) != f'{source.revision}:{row.revision if row else 0}':
        raise ValidationError('Наценка или исходная цена уже изменились. Обновите страницу перед сохранением.', code='conflict')
    if row is None:
        row = BuyerMarkup(buyer=buyer, edited_by=actor, **target)
    else:
        row.revision += 1
    for field, raw in values.items():
        if isinstance(raw, (bool, float)):
            raise ValidationError('Укажите точное неотрицательное число.')
        digits, places = (8, 2) if field == 'markup_percent' else (20, 4 if field == 'markup_coefficient' else 2)
        value = forms.DecimalField(max_digits=digits, decimal_places=places, min_value=Decimal(0), required=False).clean(raw)
        setattr(row, field, value)
    row.edited_by = actor
    row.full_clean()
    row.save()
    state.revision += 1
    state.save(update_fields=['revision'])
    AuditEvent.objects.create(actor=actor, product=source if entry_id is None else None,
        kind='buyer_markup', detail={'buyer': buyer.pk, 'entry': entry_id, 'fields': sorted(values), 'revision': row.revision})
    return profile_rows([source] if entry_id is None else [], [source] if entry_id is not None else [], buyer)[0]
