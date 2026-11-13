"""Редактирование только ручных тарифов, в отдельной транзакции и с аудитом."""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from core.db_retry import retry_database_lock
from .models import ManualPriceEntry, CatalogState, AuditEvent
from .services import require

FIELDS = ('kind', 'region', 'label', 'position')


@retry_database_lock
@transaction.atomic
def edit_amounts(*, actor, entry_id, revision, values):
    """Проценты складываются в п. п.; переключение не конвертирует рубли."""
    if not values or set(values) - {'manual_cost', 'markup', 'cost_percent', 'markup_percent', 'cost_coefficient', 'markup_coefficient', 'pricing_mode'}:
        raise ValidationError('Недопустимые поля изменения тарифа.')
    if {'manual_cost', 'cost_percent', 'cost_coefficient'} & set(values):
        require(actor, 'view_cost')
        require(actor, 'edit_cost')
    if {'markup', 'markup_percent', 'markup_coefficient'} & set(values):
        require(actor, 'view_cost')
        require(actor, 'edit_markup')
    if 'pricing_mode' in values:
        require(actor, 'view_cost')
        require(actor, 'edit_cost')
        require(actor, 'edit_markup')
    state = CatalogState.objects.select_for_update().get(pk=1)
    row = ManualPriceEntry.objects.select_for_update().get(pk=entry_id)
    if row.source_archived:
        raise ValidationError('Диапазон больше не используется поставщиком. Обновите страницу.', code='conflict')
    if str(row.revision) != str(revision):
        raise ValidationError('Тариф уже изменился. Обновите страницу перед сохранением.', code='conflict')
    from .api import amount, APIError
    for field, raw in values.items():
        if field == 'pricing_mode':
            if raw not in ManualPriceEntry.PricingMode.values:
                raise ValidationError('Выберите рубли, проценты или коэффициент.')
            value = raw
        elif raw in ('', None):
            value = None
        elif field in ('cost_coefficient', 'markup_coefficient'):
            from django import forms
            from decimal import Decimal
            if isinstance(raw, (bool, float)):
                raise ValidationError('Коэффициент должен быть точным десятичным числом.')
            value = forms.DecimalField(max_digits=20, decimal_places=4, min_value=Decimal(0)).clean(raw)
        else:
            try:
                value = amount(raw)
            except APIError:
                raise ValidationError('Себестоимость и наценка должны быть неотрицательными числами с точностью до двух знаков.') from None
        setattr(row, field, value)
    row.revision += 1
    row.edited_by, row.edited_at = actor, timezone.now()
    row.full_clean()
    row.save()
    state.revision += 1
    state.save(update_fields=['revision'])
    AuditEvent.objects.create(actor=actor, kind='manual_amounts', detail={'entry': row.pk, 'fields': sorted(values), 'revision': row.revision})
    return row


@retry_database_lock
@transaction.atomic
def save_rows(*, actor, changes):
    actor = require(actor, 'edit_manual_prices')
    state = CatalogState.objects.select_for_update().get(pk=1)
    seen = set()
    for values in changes:
        if set(values) - {*FIELDS, 'pk', 'revision'}:
            raise ValidationError('Здесь изменяется только структура тарифов. Итоговая цена рассчитывается автоматически.')
        pk = values.get('pk')
        if pk is not None:
            if pk in seen:
                raise ValidationError('Повтор строки ручного тарифа.')
            seen.add(pk)
            row = ManualPriceEntry.objects.select_for_update().get(pk=pk)
            if row.source_archived:
                raise ValidationError('Диапазон поставщика архивирован. Обновите страницу.')
            if row.revision != values.get('revision'):
                raise ValidationError('Ручные тарифы изменились. Обновите страницу перед сохранением.')
        else:
            row = ManualPriceEntry()
        from .public import safe_text
        for field in FIELDS:
            value = values[field]
            setattr(row, field, safe_text(value) if field in ('region', 'label') else value)
        row.revision += 1
        row.edited_by, row.edited_at = actor, timezone.now()
        row.full_clean()
        row.save()
    if changes:
        state.revision += 1
        state.save(update_fields=['revision'])
        AuditEvent.objects.create(actor=actor, kind='manual_tariffs', detail={'rows': len(changes)})
