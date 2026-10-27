"""Общая финализация с переиспользованием инструментов штатного прихода."""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from core.db_retry import retry_database_lock
from supplies.finalization import (FinalizationRow, parse_finalization_inputs, rows_from_inputs,
    calculate_finalization_penalty, auto_distribute_penalty)
from .arrival import lock_arrival, require_arrival_permissions
from .arrival_math import unit_cohorts
from .arrival_documents import refresh_documents
from .models import TripOrderOperation
from .trips import _record_trip_change


@dataclass(frozen=True, kw_only=True)
class TripFinalizationRow(FinalizationRow):
    cost_row: object

    @property
    def delivery_unit(self):
        return self.cost_row.delivery_total/self.cost_row.actual_quantity


def readiness(arrival):
    errors, processed, sale_count, supply_count = [], 0, 0, 0
    if not arrival.arrived:
        errors.append('Не подтверждено фактическое прибытие рейса.')
    all_rows = list(arrival.rows.all())
    if not sum(row.actual_quantity for row in all_rows):
        errors.append('В рейсе нет фактически поступивших товаров.')
    for order in arrival.trip.trip_orders.order_by('pk'):
        operation = order.operations.filter(active=True).select_related('sale','supply').first()
        if operation:
            if operation.sale_id:
                sale_count += 1
                if operation.sale.is_completed or operation.sale.is_cancelled:
                    errors.append(f'Продажа {operation.sale.visible_id} не находится в допустимом предварительном состоянии.')
            else:
                supply_count += 1
                if operation.supply.status != operation.supply.Status.WAITING_TRIP_FINALIZATION:
                    errors.append(f'Приход №{operation.supply_id} должен ждать финализации рейса.')
            if order.pk not in arrival.reviewed_orders:
                errors.append(f'Не сверены количества заказа №{order.pk}.')
            else:
                processed += 1
        elif order.pk in arrival.reviewed_orders and not any(row.actual_quantity for row in all_rows if row.order_id==order.pk):
            processed += 1
        else:
            errors.append(f'Не создана {"поставка" if order.is_stock_order else "продажа"} по заказу №{order.pk}.')
    if sum((row.delivery_total for row in all_rows),Decimal('0')) != arrival.actual_delivery:
        errors.append('Распределённая доставка не совпадает с фактической суммой.')
    if sum((row.purchase_total+row.delivery_total for row in all_rows),Decimal('0')) != arrival.control_total:
        errors.append('Контрольная сумма рейса не совпадает с расчётом фактического состава.')
    return {'ready':not errors, 'errors':errors, 'processed':processed,
        'pending':arrival.trip.trip_orders.count()-processed,'sales':sale_count,'supplies':supply_count}


def finalization_rows(arrival):
    rows=[]
    for source in arrival.rows.select_related('order','supplier','cd','tech').order_by('order_id','supplier_id','pk'):
        if not source.actual_quantity:
            continue
        for slot,(quantity,cost) in enumerate(unit_cohorts(source.final_total,source.actual_quantity)):
            rows.append(TripFinalizationRow(product_type=source.product_kind, product_id=source.pk*2+slot,
                product=source.product, global_quantity=quantity,current_cost=cost,corrected_cost=cost,cost_row=source))
    return rows


def _checked_rows(arrival, raw_rows):
    state = readiness(arrival)
    if not state['ready']:
        raise ValidationError(state['errors'])
    return rows_from_inputs(finalization_rows(arrival),parse_finalization_inputs(raw_rows))


def distribute_arrival(*, actor, arrival_id, expected_revision, raw_rows, selected_keys):
    require_arrival_permissions(actor,finalization=True)
    with transaction.atomic():
        arrival = lock_arrival(arrival_id,expected_revision)
        return auto_distribute_penalty(rows=_checked_rows(arrival,raw_rows),selected_keys=selected_keys)


@retry_database_lock
@transaction.atomic
def finalize_arrival(*, actor, arrival_id, expected_revision, raw_rows, proposed_prices=None):
    require_arrival_permissions(actor,finalization=True)
    arrival=lock_arrival(arrival_id,finalized_allowed=True)
    if arrival.finalized:
        return arrival
    from .arrival import _revision
    _revision(arrival.revision,expected_revision)
    rows=_checked_rows(arrival,raw_rows)
    if calculate_finalization_penalty(rows)!=Decimal('0'):
        raise ValidationError('Есть нераспределённый остаток. Общая себестоимость рейса должна сохраниться.')
    if proposed_prices:
        raise ValidationError('Оптовая цена и цена Авито подтверждаются при приёмке прихода по средней себестоимости склада.')
    proposals={}
    totals={}
    for row in rows:
        totals[row.cost_row.pk]=totals.get(row.cost_row.pk,Decimal('0'))+row.corrected_cost*row.global_quantity
    if sum(totals.values(),Decimal('0'))!=arrival.control_total:
        raise ValidationError('Итоговая себестоимость не равна контрольной сумме рейса.')
    changes=[]
    for source in arrival.rows.select_for_update():
        if source.actual_quantity:
            value=totals[source.pk]
            changes.append({'row_id':source.pk,'before':str(source.final_total),'after':str(value)})
            source.final_total=value
            source.save(update_fields=['final_total'])
    refresh_documents(arrival,actor=actor)
    arrival.proposed_prices=proposals
    arrival.finalized_at=timezone.now()
    arrival.finalized_by=actor
    arrival.revision+=1
    arrival.save(update_fields=['proposed_prices','finalized_at','finalized_by','revision'])
    _record_trip_change(arrival.trip,actor,'Подтверждена итоговая финализация рейса',
        {'control_total':str(arrival.control_total),'rows':changes,'proposed_prices':proposals})
    return arrival


def prepare_supply_posting(supply, *, actor, independent_expenses=None):
    """Готовит штатную приёмку по окончательным затратам, не проводя товар."""
    from .arrival_models import TripArrival
    from .arrival import assert_document_finalized
    from .arrival_documents import refresh_supply_calculations
    from supplies.models import Supply
    operation=TripOrderOperation.objects.filter(supply=supply,active=True).first()
    if not operation or 'arrival_id' not in operation.calculation:
        return None
    assert_document_finalized(supply)
    arrival=TripArrival.objects.select_for_update().get(pk=operation.calculation['arrival_id'])
    if independent_expenses is not None:
        _independent_expenses(supply,independent_expenses,actor,arrival)
    refresh_supply_calculations(supply,rebase=True)
    supply.status=Supply.Status.PRICE_REVIEW_REQUIRED
    supply.save(update_fields=['status'])
    return {}


@retry_database_lock
@transaction.atomic
def prepare_supply_price_review(*, actor, supply_id, expected_revision_number=None, independent_expenses=None):
    """Фиксирует предпросмотр средней стоимости, оставляя приход непроведённым."""
    from django.core.exceptions import PermissionDenied
    from .arrival import lock_document_trip, assert_document_finalized
    from .arrival_documents import refresh_supply_calculations
    from supplies.models import Supply
    if not actor.has_perm('supplies.add_supply'):
        raise PermissionDenied('Недостаточно прав для проверки цен прихода.')
    arrival=lock_document_trip('supply',supply_id)
    supply=Supply.objects.select_for_update().get(pk=supply_id)
    if arrival is None or supply.status not in (Supply.Status.WAITING_TRIP_FINALIZATION,Supply.Status.PRICE_REVIEW_REQUIRED):
        raise ValidationError('Этот приход недоступен для проверки цен рейса.')
    assert_document_finalized(supply)
    if expected_revision_number is not None:
        from .arrival import _revision
        _revision(supply.revision_number,expected_revision_number)
    fields=('product_kind','cd_id','tech_id','old_owned_quantity','old_unit_cost',
            'incoming_quantity','incoming_value','resulting_unit_cost')
    def snapshot():
        return list(supply.cost_calculations.order_by('product_kind','cd_id','tech_id').values_list(*fields))
    before=snapshot()
    was_waiting=supply.status==Supply.Status.WAITING_TRIP_FINALIZATION
    if was_waiting:
        prepare_supply_posting(supply,actor=actor,independent_expenses=independent_expenses)
    else:
        if independent_expenses is not None:
            _independent_expenses(supply,independent_expenses,actor,arrival)
        refresh_supply_calculations(supply,rebase=True)
    if was_waiting or snapshot()!=before:
        supply.revision_number+=1
        supply.save(update_fields=['revision_number'])
    return supply



def _independent_expenses(supply, raw_expenses, actor, arrival):
    """Независимые расходы конкретного поступления не повторяют доставку рейса."""
    from django import forms
    from core.allocation import allocate_amount
    from supplies.models import SupplyExpense
    from supplies.services import _normalise_expenses, UNIT
    amount=forms.DecimalField(min_value=0,max_digits=20,decimal_places=2)
    validated=[]
    for raw in raw_expenses:
        if not raw.get('name') and raw.get('amount') in ('',None):continue
        validated.append({'name':str(raw.get('name') or '').strip(),'amount':amount.clean(raw.get('amount'))})
    expenses=_normalise_expenses(validated)
    total=sum((expense.amount for expense in expenses),Decimal('0'))
    items=list(supply.cd_items.order_by('pk'))+list(supply.tech_items.order_by('pk'))
    amount.clean(sum(item.base_line_total for item in items)+total)
    allocations=allocate_amount(total,[item.quantity for item in items])
    supply.expenses.all().delete()
    for expense in expenses:SupplyExpense.objects.create(supply=supply,name=expense.name,amount=expense.amount)
    for item,allocated in zip(items,allocations):
        item.allocated_expense_per_unit=(allocated/item.quantity).quantize(UNIT,rounding=ROUND_HALF_UP)
        item.final_line_total=item.base_line_total+allocated
        item.effective_unit_cost=(item.final_line_total/item.quantity).quantize(UNIT,rounding=ROUND_HALF_UP)
        item.save(update_fields=['allocated_expense_per_unit','final_line_total','effective_unit_cost'])
    supply.expenses_total=total
    supply.grand_total=sum(item.final_line_total for item in items)
    supply.revision_number+=1
    supply.save(update_fields=['expenses_total','grand_total','revision_number'])
    if expenses:
        _record_trip_change(arrival.trip,actor,f'Независимые расходы прихода №{supply.pk} вне доставки рейса',
            {'supply_id':supply.pk,'expenses':[{'name':e.name,'amount':str(e.amount)} for e in expenses]})
