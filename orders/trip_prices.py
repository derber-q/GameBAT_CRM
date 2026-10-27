"""Корректировка закупки рейса без изменения согласованных цен покупателей."""
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import DecimalValidator
from django.db import transaction
from django.utils import timezone

from price.services import RATE_PRECISION, decimal_value
from .models import CustomerProcurementOrder, SupplierOrderBatch, SupplierOrderBatchLine
from .order_editing import downstream_lock_reason
from .trips import _assert_balances, _quantity, _record_trip_change, _require_manage

ZERO = Decimal('0')


def validated_aed(value):
    price = decimal_value(value, precision=RATE_PRECISION, positive=True, label='Цена поставщика, AED')
    DecimalValidator(max_digits=20, decimal_places=6)(Decimal(str(value)))
    return price


def historical_rate(source):
    """Использует только сохранённые данные той же версии прайса."""
    price_list = source.price_list
    for value, label in ((source.exchange_rate_aed_rub, 'Снимок позиции прайса'),
                         (price_list.exchange_rate_aed_rub, 'Сохранённый курс версии прайса')):
        if value is not None and value.is_finite() and value > 0:
            return value, label
    aed, rub = price_list.exchange_rate_usdt_aed, price_list.exchange_rate_usdt_rub
    if all(value is not None and value.is_finite() and value > 0 for value in (aed, rub)):
        return decimal_value(rub / aed, precision=RATE_PRECISION, positive=True), 'Сохранённая пара курсов версии прайса'
    raise ValidationError(f'{source.product_name_snapshot}: исторический курс прайса №{source.price_list_id} отсутствует. Текущий курс не подставляется.')


def allocation_unit_cost(item, line=None, *, for_supply=False, price_aed=None):
    if for_supply and (line is None or line.supplier_price_updated_at is None):
        return item.prepayment_unit_price
    source = item.price_list_item
    rate, _ = historical_rate(source)
    price = price_aed if price_aed is not None else (
        line.supplier_price_aed_snapshot if line is not None else item.supplier_price_aed_snapshot)
    base = decimal_value(price * rate, nonnegative=True, label='Закупочная база')
    return base + decimal_value(source.delivery_rub, nonnegative=True, label='Сохранённая доставка')


def stock_purchase_rows(order, item):
    """Отдельные цены партий остаются отдельными строками складского документа."""
    allocations = [row for row in item.trip_allocations.all()
                   if row.line.batch_id == order.trip_id and row.quantity]
    if not any(row.line.supplier_price_updated_at for row in allocations):
        return [(item.quantity, item.prepayment_unit_price)]
    if sum(row.quantity for row in allocations) != item.quantity:
        raise ValidationError('Количество складского заказа не совпадает с распределением рейса.')
    return [(row.quantity, allocation_unit_cost(item, row.line, for_supply=True)) for row in allocations]


def order_financials(order, *, overrides=None):
    order = CustomerProcurementOrder.objects.get(pk=order.pk)
    overrides = overrides or {}
    operation = order.operations.select_related('sale').filter(active=True).first() if not overrides else None
    if operation:
        cost = sum((Decimal(row['unit_cost']) * row['quantity'] for row in operation.calculation['rows']), ZERO)
        revenue = operation.sale.total_amount if operation.sale_id else order.grand_total
        return {'cost_rub': cost, 'revenue_rub': revenue,
                'profit_rub': None if order.is_stock_order else revenue - cost}
    cost = ZERO
    items = order.items.select_related('price_list_item__price_list').prefetch_related('trip_allocations__line')
    for item in items:
        if not item.quantity:
            continue
        remaining = item.quantity
        for allocation in item.trip_allocations.all():
            if allocation.line.batch_id != order.trip_id or not allocation.quantity:
                continue
            if allocation.quantity > remaining:
                raise ValidationError('Распределение рейса превышает количество заказа.')
            cost += allocation_unit_cost(item, allocation.line,
                price_aed=overrides.get(allocation.line_id)) * allocation.quantity
            remaining -= allocation.quantity
        if remaining and order.trip_id:
            raise ValidationError('Распределение рейса не покрывает количество заказа.')
        if remaining:
            cost += allocation_unit_cost(item) * remaining
    cost = decimal_value(cost, nonnegative=True, label='Закупочные затраты')
    DecimalValidator(max_digits=20, decimal_places=2)(cost)
    return {'cost_rub': cost, 'revenue_rub': order.grand_total,
            'profit_rub': None if order.is_stock_order else order.grand_total - cost}


def trip_financials(batch):
    cost, profit, stock_cost = ZERO, ZERO, ZERO
    for order in batch.trip_orders.all():
        finance = order_financials(order)
        cost += finance['cost_rub']
        if order.is_stock_order:
            stock_cost += finance['cost_rub']
        else:
            profit += finance['profit_rub']
    return {'cost_rub': cost, 'profit_rub': profit, 'stock_cost_rub': stock_cost,
            'total_aed': sum((line.total_aed for line in batch.lines.all()), ZERO)}


def line_price_lock_reason(line, allocations=None):
    if not hasattr(line.batch,'_arrival_locked'):
        from .arrival_models import TripArrival
        line.batch._arrival_locked = TripArrival.objects.filter(trip_id=line.batch_id,arrived_at__isnull=False).exists()
    if line.batch._arrival_locked:
        return 'Рейс приехал. Исходные закупочные цены зафиксированы.'
    for allocation in line.allocations.all() if allocations is None else allocations:
        if not allocation.quantity:
            continue
        reason = downstream_lock_reason(allocation.order_item.order)
        if reason:
            return 'Закупочная цена заблокирована: ' + reason
    return ''


def _locked_context(actor, batch_id, line_id):
    if not actor.is_active:
        raise PermissionDenied
    _require_manage(actor)
    try:
        batch = SupplierOrderBatch.objects.select_for_update().get(pk=batch_id, price_list__isnull=False)
        line = SupplierOrderBatchLine.objects.select_for_update().select_related(
            'supplier', 'price_list_item__price_list').get(pk=line_id, batch=batch)
    except (SupplierOrderBatch.DoesNotExist, SupplierOrderBatchLine.DoesNotExist, ValueError, TypeError) as exc:
        raise ValidationError('Рейс или позиция поставщика не найдены.') from exc
    allocations = list(line.allocations.select_for_update().select_related(
        'order_item__order', 'order_item__price_list_item__price_list').order_by('pk'))
    locked_orders = {order.pk: order for order in CustomerProcurementOrder.objects.select_for_update().filter(
        pk__in=[row.order_item.order_id for row in allocations]).order_by('pk')}
    for allocation in allocations:
        allocation.order_item.order = locked_orders[allocation.order_item.order_id]
    reason = line_price_lock_reason(line, allocations)
    if reason:
        raise ValidationError(reason)
    _assert_balances(batch)
    if not any(row.quantity for row in allocations):
        historical_rate(line.price_list_item)
    return batch, line, allocations


def _preview(batch, line, allocations, price):
    old = line.supplier_price_aed_snapshot
    costs, profit_delta, stock_delta = ZERO, ZERO, ZERO
    rows, orders = [], {}
    for allocation in allocations:
        item, amount = allocation.order_item, allocation.quantity
        if not amount:
            continue
        rate, rate_source = historical_rate(item.price_list_item)
        before = allocation_unit_cost(item, line)
        after = allocation_unit_cost(item, line, price_aed=price)
        DecimalValidator(max_digits=20, decimal_places=6)(after)
        delta = (after - before) * amount
        costs += delta
        if item.order.is_stock_order:
            stock_delta += delta
        else:
            profit_delta -= delta
        rows.append({'order_id': item.order_id, 'recipient': item.order.recipient,
            'is_stock': item.order.is_stock_order, 'quantity': amount,
            'rate': str(rate), 'rate_source': rate_source, 'old_unit_cost_rub': str(before),
            'new_unit_cost_rub': str(after), 'cost_delta_rub': str(delta),
            'profit_delta_rub': None if item.order.is_stock_order else str(-delta)})
        if item.order_id not in orders:
            previous = order_financials(item.order)
            following = order_financials(item.order, overrides={line.pk: price})
            orders[item.order_id] = {'id': item.order_id, 'recipient': item.order.recipient,
                'is_stock': item.order.is_stock_order, 'revenue_rub': str(item.order.grand_total),
                'old_cost_rub': str(previous['cost_rub']), 'new_cost_rub': str(following['cost_rub']),
                'old_profit_rub': None if item.order.is_stock_order else str(previous['profit_rub']),
                'new_profit_rub': None if item.order.is_stock_order else str(following['profit_rub'])}
    return {'revision': batch.revision, 'line_id': line.pk, 'product': line.product_name_snapshot,
            'supplier': line.supplier.name, 'quantity': line.quantity, 'old_price_aed': str(old),
            'new_price_aed': str(price), 'unit_delta_aed': str(price - old),
            'total_delta_aed': str((price - old) * line.quantity), 'cost_delta_rub': str(costs),
            'customer_profit_delta_rub': str(profit_delta), 'stock_cost_delta_rub': str(stock_delta),
            'allocations': rows, 'orders': list(orders.values())}


@transaction.atomic
def preview_trip_price(*, actor, batch_id, line_id, revision, price_aed):
    price = validated_aed(price_aed)
    batch, line, allocations = _locked_context(actor, batch_id, line_id)
    if batch.revision != _quantity(revision, 'Версия рейса'):
        raise ValidationError('Рейс уже изменён. Обновите страницу и повторите расчёт.')
    return _preview(batch, line, allocations, price)


@transaction.atomic
def change_trip_price(*, actor, batch_id, line_id, revision, price_aed, reason=''):
    price = validated_aed(price_aed)
    batch, line, allocations = _locked_context(actor, batch_id, line_id)
    expected = _quantity(revision, 'Версия рейса')
    if price == line.supplier_price_aed_snapshot:
        return batch
    if batch.revision != expected:
        raise ValidationError('Рейс уже изменён другим запросом. Обновите страницу.')
    explanation = str(reason or '').strip()
    if len(explanation) > 2000:
        raise ValidationError('Причина изменения не должна превышать 2000 символов.')
    details = _preview(batch, line, allocations, price)
    details.update(action='purchase_price', reason=explanation, supplier_id=line.supplier_id,
                   price_list_item_id=line.price_list_item_id)
    line.supplier_price_aed_snapshot = price
    line.supplier_price_updated_at = timezone.now()
    line.full_clean()
    line.save(update_fields=('supplier_price_aed_snapshot', 'supplier_price_updated_at'))
    _record_trip_change(batch, actor,
        f'Цена AED: {details["old_price_aed"]} → {price} · {line.product_name_snapshot} · {line.supplier.name}'[:500], details)
    return batch
