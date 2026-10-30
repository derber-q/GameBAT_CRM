"""Единый расчёт фактической доставки; изменения сериализуются на уровне рейса."""
from decimal import Decimal
from django import forms
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from core.allocation import allocate_amount
from core.db_retry import retry_database_lock
from .models import SupplierOrderBatch, TripOrderOperation
from .arrival_models import TripArrival, TripCostRow
from .arrival_math import purchase_cost
from .trips import _assert_balances, _record_trip_change


class ArrivalForm(forms.Form):
    actual_delivery = forms.DecimalField(label='Фактическая доставка, RUB', min_value=0, max_digits=20, decimal_places=2)
    usdt_aed = forms.DecimalField(label='USDT/AED — дирхамов за 1 USDT', min_value=Decimal('.000001'), max_digits=20, decimal_places=6)
    usdt_rub = forms.DecimalField(label='USDT/RUB — рублей за 1 USDT', min_value=Decimal('.000001'), max_digits=20, decimal_places=6)


def require_arrival_permissions(actor, *, finalization=False):
    required = ['orders.view_order_detail', 'orders.generate_supplier_orders', 'price.view_supplier_prices']
    if finalization:
        required.append('supplies.finalize_supply')
    if not all(actor.has_perm(name) for name in required):
        raise PermissionDenied('Недостаточно прав для работы с фактическими затратами рейса.')


def _parameters(values):
    form = ArrivalForm(values)
    if not form.is_valid():
        raise ValidationError([str(message) for messages in form.errors.values() for message in messages])
    return form.cleaned_data


def assert_document_finalized(document):
    if document_waits_finalization(document):
        raise ValidationError('Сначала подтвердите итоговую финализацию всего рейса. Проведение документа пока недоступно.')


def document_waits_finalization(document):
    if not document.pk:
        return False
    key = 'sale' if document._meta.label_lower == 'sales.sale' else 'supply'
    operation = TripOrderOperation.objects.filter(**{key: document}, active=True).first()
    return bool(operation and TripArrival.objects.filter(trip__trip_orders=operation.order,
            arrived_at__isnull=False, finalized_at__isnull=True).exists())


def lock_document_trip(kind, document_id):
    operation = TripOrderOperation.objects.filter(**{kind+'_id':document_id},active=True).first()
    if operation and operation.calculation.get('arrival_id'):
        return lock_arrival(operation.calculation['arrival_id'],finalized_allowed=True)
    return None


def _revision(actual, expected):
    try:
        valid = int(expected) == actual
    except (ValueError, TypeError):
        valid = False
    if not valid:
        raise ValidationError('Рейс изменён другим действием. Обновите страницу и проверьте расчёт.')


def lock_arrival(arrival_id, expected_revision=None, *, finalized_allowed=False):
    trip_id = TripArrival.objects.values_list('trip_id', flat=True).get(pk=arrival_id)
    SupplierOrderBatch.objects.select_for_update().get(pk=trip_id)
    arrival = TripArrival.objects.select_for_update().get(pk=arrival_id)
    if not arrival.arrived:
        raise ValidationError('Сначала подтвердите «Рейс приехал».')
    if arrival.finalized and not finalized_allowed:
        raise ValidationError('Итоговая финализация рейса уже подтверждена.')
    if expected_revision is not None:
        _revision(arrival.revision, expected_revision)
    return arrival


def arrival_preview(*, actor, batch_id, **parameters):
    require_arrival_permissions(actor)
    values = _parameters(parameters)
    trip = SupplierOrderBatch.objects.get(pk=batch_id)
    if not trip.is_trip:
        raise ValidationError('Фактическое прибытие доступно для рейса заказов.')
    if (TripOrderOperation.objects.filter(order__trip=trip,active=True).exists()
            or trip.trip_orders.filter(supply__isnull=False).exists()
            or trip.trip_orders.filter(status='completed').exists()):
        raise ValidationError('В рейсе уже есть ранее созданные документы. Их история сохраняется; первую фиксацию прибытия выполнить нельзя.')
    _assert_balances(trip)
    from .fulfillment import calculation
    rows = []
    for order in trip.trip_orders.order_by('pk'):
        if not order.total_units:
            continue
        items = {item.pk: item for item in order.items.select_related('cd', 'tech')}
        for row in calculation(order, usd_rub=values['usdt_rub'], usd_aed=values['usdt_aed'],_delivery_weights=True)['rows']:
            item = items[row['order_item_id']]
            if not item.product.weight_grams or item.product.weight_grams <= 0:
                raise ValidationError(f'Заполните вес товара «{item.product.name}».')
            rows.append({**row, 'order_id': order.pk, 'weight_grams': item.product.weight_grams,
                'purchase_unit_cost': purchase_cost(row['supplier_price_aed'], values['usdt_aed'], values['usdt_rub'])})
    if not rows:
        raise ValidationError('В рейсе нет фактически поступающих товаров.')
    allocations = allocate_amount(values['actual_delivery'], [Decimal(row['delivery_rub']) * row['quantity'] for row in rows])
    for row, allocated in zip(rows, allocations):
        row['delivery_total'] = allocated
        row['final_total'] = row['purchase_unit_cost'] * row['quantity'] + allocated
    forms.DecimalField(min_value=0,max_digits=20,decimal_places=2).clean(sum(row['final_total'] for row in rows))
    return {**values, 'rows': rows, 'purchase_total': sum(row['purchase_unit_cost'] * row['quantity'] for row in rows),
            'control_total': sum(row['final_total'] for row in rows)}


@retry_database_lock
@transaction.atomic
def confirm_arrival(*, actor, batch_id, expected_revision, **parameters):
    trip = SupplierOrderBatch.objects.select_for_update().get(pk=batch_id)
    _revision(trip.revision, expected_revision)
    existing = TripArrival.objects.select_for_update().filter(trip=trip).first()
    if existing and existing.arrived:
        raise ValidationError('Прибытие рейса уже зафиксировано.')
    preview = arrival_preview(actor=actor, batch_id=batch_id, **parameters)
    values = {key: preview[key] for key in ('usdt_aed', 'usdt_rub', 'actual_delivery', 'purchase_total', 'control_total')}
    values.update(arrived_at=timezone.now(), arrived_by=actor, reviewed_orders=[])
    if existing:
        for name, value in values.items():
            setattr(existing, name, value)
        existing.revision += 1
        existing.save()
        existing.rows.all().delete()
        arrival = existing
    else:
        arrival = TripArrival.objects.create(trip=trip, **values)
    for row in preview['rows']:
        TripCostRow.objects.create(arrival=arrival, order_id=row['order_id'], order_item_id=row['order_item_id'],
            allocation_id=row['allocation_id'], supplier_id=row['supplier_id'], portion=row['portion'],
            product_kind=row['product_type'], **{row['product_type'] + '_id': row['product_id']},
            original_quantity=row['quantity'], actual_quantity=row['quantity'], price_aed=row['supplier_price_aed'],
            weight_grams_snapshot=row['weight_grams'], preliminary_delivery=row['delivery_rub'],
            tariff_snapshot=row['delivery_parameters'], purchase_unit_cost=row['purchase_unit_cost'],
            delivery_total=row['delivery_total'], final_total=row['final_total'], customer_price=row['unit_price'] or None)
    audit={key:str(value) for key,value in values.items() if key!='arrived_by'}
    audit['rows']=[{'row_id':row.pk,'allocation_id':row.allocation_id,'order_id':row.order_id,
        'product_kind':row.product_kind,'product_id':row.product_id,'quantity':row.original_quantity,
        'price_aed':str(row.price_aed),'preliminary_delivery':str(row.preliminary_delivery),
        'weight_grams':row.weight_grams_snapshot,'tariff_snapshot':row.tariff_snapshot} for row in arrival.rows.all()]
    _record_trip_change(trip, actor, 'Зафиксировано фактическое прибытие рейса',audit)
    return arrival


@retry_database_lock
@transaction.atomic
def unconfirm_arrival(*, actor, arrival_id, expected_revision):
    require_arrival_permissions(actor)
    arrival = lock_arrival(arrival_id, expected_revision)
    if TripOrderOperation.objects.filter(order__trip_id=arrival.trip_id,calculation__arrival_id=arrival.pk).exists():
        raise ValidationError('После создания первой продажи или прихода нельзя снять прибытие рейса.')
    arrival.arrived_at = None
    arrival.revision += 1
    arrival.save(update_fields=['arrived_at', 'revision'])
    _record_trip_change(arrival.trip, actor, 'Снята отметка фактического прибытия', {'arrival_id': arrival.pk})
    return arrival


def recalculate_arrival(arrival, *, actor=None):
    rows = list(arrival.rows.select_for_update().order_by('pk'))
    if not sum(row.actual_quantity for row in rows):
        raise ValidationError('В рейсе должна остаться хотя бы одна фактически поступившая единица.')
    allocations = allocate_amount(arrival.actual_delivery,
        [row.preliminary_delivery * row.actual_quantity for row in rows])
    for row, allocated in zip(rows, allocations):
        row.delivery_total = allocated
        row.final_total = row.purchase_total + allocated
        row.save(update_fields=['delivery_total', 'final_total'])
    arrival.purchase_total = sum(row.purchase_total for row in rows)
    arrival.control_total = arrival.purchase_total + arrival.actual_delivery
    arrival.revision += 1
    arrival.save(update_fields=['purchase_total', 'control_total', 'revision', 'reviewed_orders'])
    if TripOrderOperation.objects.filter(order__trip_id=arrival.trip_id, active=True).exists():
        from .arrival_documents import refresh_documents
        refresh_documents(arrival, actor=actor)


@retry_database_lock
@transaction.atomic
def reduce_received(*, actor, arrival_id, order_id, quantities, expected_revision):
    arrival = lock_arrival(arrival_id, expected_revision)
    from .fulfillment import require_permissions
    order = arrival.trip.trip_orders.filter(pk=order_id).first()
    if order is None:raise ValidationError('Заказ не относится к этому рейсу.')
    require_permissions(actor, order)
    rows = list(arrival.rows.select_for_update().filter(order=order))
    try:
        quantities = {int(key): int(value) for key, value in quantities.items()}
    except (ValueError, TypeError) as exc:
        raise ValidationError('Проверьте фактически поступившие количества.') from exc
    if set(quantities) != {row.pk for row in rows}:
        raise ValidationError('Состав заказа изменён. Обновите форму сверки.')
    changes = []
    for row in rows:
        quantity = quantities[row.pk]
        if quantity < 0 or quantity > row.actual_quantity:
            raise ValidationError('Допустимо только уменьшение фактического количества, без увеличения исходного заказа.')
        if quantity != row.actual_quantity:
            changes.append({'row_id': row.pk, 'before': row.actual_quantity, 'after': quantity})
            row.actual_quantity = quantity
            row.save(update_fields=['actual_quantity'])
    arrival.reviewed_orders = sorted(set(arrival.reviewed_orders) | {order.pk})
    recalculate_arrival(arrival, actor=actor)
    _record_trip_change(arrival.trip, actor, f'Сверено поступление по заказу №{order.pk}', {'changes': changes})
    return arrival
