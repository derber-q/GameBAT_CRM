"""Создание штатных продаж/приходов из рейса без повторного складского и денежного учёта."""
import hashlib
import json
from decimal import Decimal
from uuid import UUID

from django import forms
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Sum

from core.db_retry import retry_database_lock
from catalog.game_codes import validate_supply_game_codes
from .models import CustomerProcurementOrder, CustomerOrderStatusEvent, TripOrderOperation

class FulfillmentRatesForm(forms.Form):
    usd_rub = forms.DecimalField(label='Курс USDT → RUB', help_text='Рублей за 1 USDT, например 87,43.',
        max_digits=20, decimal_places=6, min_value=Decimal('0.000001'))
    usd_aed = forms.DecimalField(label='Курс USDT → AED', help_text='Дирхамов за 1 USDT, например 3,66.',
        max_digits=20, decimal_places=6, min_value=Decimal('0.000001'))


def require_permissions(actor, order):
    required = ('orders.view_order_detail', 'orders.complete_order', 'price.view_supplier_prices',
                'supplies.add_supply' if order.is_stock_order else 'sales.create_sale')
    if not all(actor.has_perm(name) for name in required):
        raise PermissionDenied('Недостаточно прав для создания операции из заказа рейса.')


def available(order):
    return bool(order.trip_id and order.total_units and order.status != order.Status.COMPLETED and not order.supply_id
                and not any(operation.active for operation in order.operations.all()))


def operation_actions(actor, orders):
    """Одинаковые права и доступность кнопок для списка, рейса и карточки заказа."""
    from collections import defaultdict
    from .models import SupplierOrderBatchLine, SupplierTripInvoice
    orders = list(orders)
    trip_ids = {order.trip_id for order in orders if order.trip_id}
    from .arrival_models import TripArrival
    arrivals = {arrival.trip_id:arrival for arrival in TripArrival.objects.filter(trip_id__in=trip_ids,arrived_at__isnull=False)}
    suppliers, accepted = defaultdict(set), defaultdict(set)
    for batch_id, supplier_id in SupplierOrderBatchLine.objects.filter(batch_id__in=trip_ids, quantity__gt=0).values_list('batch_id','supplier_id'):
        suppliers[batch_id].add(supplier_id)
    for batch_id, supplier_id in SupplierTripInvoice.objects.filter(batch_id__in=trip_ids, accepted=True).values_list('batch_id','supplier_id'):
        accepted[batch_id].add(supplier_id)
    for order in orders:
        order._all_trip_invoices_accepted = bool(suppliers[order.trip_id]) and suppliers[order.trip_id].issubset(accepted[order.trip_id])
        order.current_operation = next((operation for operation in order.operations.all() if operation.active), None)
        order._trip_arrival = arrivals.get(order.trip_id)
        order.can_review_arrival = bool(order._trip_arrival)
        try:
            require_permissions(actor,order)
        except PermissionDenied:
            order.can_review_arrival=False
        missing = bool(order._trip_arrival and order.pk in order._trip_arrival.reviewed_orders
            and not order.arrival_rows.filter(actual_quantity__gt=0).exists())
        order.can_create_operation = available(order) and bool(order._trip_arrival) and not missing
        if order.can_create_operation:
            try:
                require_permissions(actor, order)
            except PermissionDenied:
                order.can_create_operation = False
    return orders


def require_available(order):
    if not available(order):
        raise ValidationError('Заказ не входит в рейс, уже выполняется или выполнен. Откройте связанную операцию.')


def _rate(value, label):
    field = forms.DecimalField(label=label, max_digits=20, decimal_places=6, min_value=Decimal('0.000001'))
    return field.clean(value)


def _round(value):
    from price.services import decimal_value
    result = decimal_value(value, label='Сумма операции')
    forms.DecimalField(max_digits=20, decimal_places=2, min_value=0).clean(result)
    return result


def _delivery(source, usd_rub):
    """Тот же тариф × вес; рублёвый тариф диска переводится через сохранённый курс прайса."""
    weight = source.weight_grams_snapshot
    tariff = source.delivery_usdt_per_kg_snapshot
    if source.product_kind == 'tech' and weight and tariff is not None:
        from price.services import weighted_procurement_delivery
        dollars = Decimal(weight) / Decimal('1000') * tariff
        delivery = weighted_procurement_delivery(weight_grams=weight, tariff=tariff, dollar_rate=usd_rub)
        algorithm = 'weight_tariff'
    else:
        # Старый прайс мог сохранить только итог доставки. Не берём сегодняшние тарифы/вес.
        old_rate = source.price_list.exchange_rate_usdt_rub
        if source.delivery_rub and (old_rate is None or old_rate <= 0):
            raise ValidationError(f'{source.product_name_snapshot}: нет исторического долларового курса доставки. Нельзя достоверно пересчитать доставку.')
        dollars = source.delivery_rub / old_rate if source.delivery_rub else Decimal('0')
        delivery = _round(dollars * usd_rub)
        algorithm = 'fixed_unit' if source.product_kind == 'cd' else 'legacy_saved_delivery'
    return _round(delivery), {
        'algorithm': algorithm, 'weight_grams': weight,
        'tariff_per_kg': str(tariff) if tariff is not None else None,
        'dollar_amount': str(dollars), 'original_delivery_rub': str(source.delivery_rub),
        'original_usd_rub': str(source.price_list.exchange_rate_usdt_rub),
        'group': source.delivery_group_snapshot,
    }


def calculation(order, *, usd_rub, usd_aed=None, aed_rub=None, _delivery_weights=False):
    order = CustomerProcurementOrder.objects.get(pk=order.pk)
    usd_rub = _rate(usd_rub, 'Курс USDT → RUB')
    if usd_aed is not None:
        if aed_rub is not None:
            raise ValidationError('Укажите одну пару курсов: USDT/RUB и USDT/AED.')
        from price.services import decimal_value, RATE_PRECISION
        usd_aed = _rate(usd_aed, 'Курс USDT → AED')
        aed_rub = _rate(decimal_value(usd_rub / usd_aed, precision=RATE_PRECISION, positive=True,
            label='Расчётный курс AED → RUB'), 'Расчётный курс AED → RUB')
    else:
        # Прежние снимки содержат именно AED/RUB: их суммы и подписи не меняются.
        aed_rub = _rate(aed_rub, 'Курс AED → RUB')
    rows = []
    items = order.items.select_related('price_list_item__price_list', 'cd__platform', 'tech').prefetch_related('trip_allocations__line').order_by('pk')
    for item in items:
        if not item.quantity:
            continue
        if item.product.is_archived:
            raise ValidationError(f'{item.product_name_snapshot}: товар удалён из активной номенклатуры.')
        allocations = [a for a in item.trip_allocations.all() if a.quantity and a.line.batch_id == order.trip_id]
        if sum(a.quantity for a in allocations) != item.quantity:
            raise ValidationError(f'{item.product_name_snapshot}: количество не совпадает с распределением рейса.')
        if (sum(a.prepayment_quantity for a in allocations) != item.prepayment_quantity
                or sum(a.postpayment_quantity for a in allocations) != item.postpayment_quantity):
            raise ValidationError(f'{item.product_name_snapshot}: предоплата и постоплата не совпадают с распределением рейса.')
        if _delivery_weights:
            from .arrival_math import preliminary_delivery
            delivery, parameters = preliminary_delivery(item.price_list_item)
        else:
            delivery, parameters = _delivery(item.price_list_item, usd_rub)
        for allocation in sorted(allocations, key=lambda a: a.pk):
            line = allocation.line
            aed = line.supplier_price_aed_snapshot
            if not aed.is_finite() or aed <= 0:
                raise ValidationError(f'{item.product_name_snapshot}: отсутствует закупочная цена рейса.')
            base = _round(aed / usd_aed * usd_rub) if usd_aed is not None else _round(aed * aed_rub)
            # Не усредняем разные цены предоплаты/постоплаты и разные партии поставщиков.
            portions = ((allocation.quantity, None, 'stock'),) if order.is_stock_order else (
                (allocation.prepayment_quantity, item.prepayment_unit_price, 'prepayment'),
                (allocation.postpayment_quantity, item.postpayment_unit_price, 'postpayment'))
            for qty, customer_price, portion in portions:
                if not qty:
                    continue
                rows.append({'product_type': item.product_kind, 'product_id': item.product_id,
                    'label': item.product_name_snapshot, 'quantity': qty, 'supplier_id': line.supplier_id,
                    'order_item_id': item.pk, 'allocation_id': allocation.pk, 'trip_line_id': line.pk,
                    'supplier_price_aed': str(aed), 'base_rub': str(base), 'delivery_rub': str(delivery),
                    'unit_cost': str(_round(base + delivery)),
                    'unit_price': str(customer_price) if customer_price is not None else '',
                    'portion': portion, 'delivery_parameters': parameters})
    if not rows:
        raise ValidationError('В заказе нет ненулевых позиций.')
    _round(sum((Decimal(row['unit_cost']) * row['quantity'] for row in rows), Decimal('0')))
    return {'order_id': order.pk, 'trip_id': order.trip_id, 'purpose': order.purpose,
            'partner_id': order.partner_id, 'partner_name': order.partner_name_snapshot or order.recipient,
            'usd_rub': str(usd_rub), 'aed_rub': str(aed_rub), 'rows': rows,
            **({'usd_aed': str(usd_aed)} if usd_aed is not None else {}),
            'prepaid': str(prepaid_amount(order)), 'payment_warehouse_id': order.payment_warehouse_id}


def fingerprint(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def prepaid_amount(order):
    from cash.models import CashTransaction
    totals = dict(order.cash_transactions.values('operation_type').annotate(total=Sum('amount')).values_list('operation_type', 'total'))
    return (totals.get(CashTransaction.OperationType.CUSTOMER_ORDER_PREPAYMENT, Decimal('0'))
            + totals.get(CashTransaction.OperationType.CUSTOMER_ORDER_POSTPAYMENT, Decimal('0'))
            - totals.get(CashTransaction.OperationType.CUSTOMER_ORDER_REFUND, Decimal('0')))


def _locked_draft(actor, draft):
    try:
        order = CustomerProcurementOrder.objects.select_for_update().get(pk=draft['order_id'])
        UUID(draft['key'])
    except (KeyError, ValueError, TypeError, CustomerProcurementOrder.DoesNotExist) as exc:
        raise ValidationError('Расчёт заказа отсутствует. Откройте заказ и введите курсы заново.') from exc
    require_permissions(actor, order)
    prior = TripOrderOperation.objects.filter(draft_key=draft['key']).first()
    if prior:
        if prior.order_id != order.pk or prior.created_by_id != actor.pk or not prior.active:
            raise ValidationError('Эта форма уже использована. Откройте заказ заново.')
        return order, prior
    require_available(order)
    snapshot = draft['calculation']
    rates = {'usd_aed': snapshot['usd_aed']} if 'usd_aed' in snapshot else {'aed_rub': snapshot['aed_rub']}
    actual = calculation(order, usd_rub=snapshot['usd_rub'], **rates)
    if fingerprint(actual) != fingerprint(draft['calculation']):
        raise ValidationError('Состав, цена, доставка или оплата заказа изменились. Откройте заказ и проверьте расчёт заново.')
    return order, None


def _link(actor, order, draft, *, sale=None, supply=None, snapshot=None):
    operation = TripOrderOperation.objects.create(order=order, sale=sale, supply=supply,
        usd_rub=Decimal(draft['calculation']['usd_rub']), aed_rub=Decimal(draft['calculation']['aed_rub']),
        calculation=snapshot or draft['calculation'], draft_key=UUID(draft['key']), created_by=actor)
    synchronize(operation)
    return operation


@retry_database_lock
@transaction.atomic
def _create_legacy_direct_sale(*, actor, draft, changes_confirmation='', **kwargs):
    from sales.models import Sale
    from sales.services import _create_sale
    from .operation_changes import resolve_rows, confirm_changes, operation_snapshot
    order, prior = _locked_draft(actor, draft)
    if order.is_stock_order:
        raise ValidationError('Для складского заказа создаётся приход.')
    if prior:
        return prior.sale
    rows, changes = resolve_rows(draft=draft, lines=kwargs['lines'])
    prepaid = Decimal(draft['calculation']['prepaid'])
    total = _round(sum(((Decimal(row['unit_price']) - Decimal(row['unit_discount'])) * row['quantity']
                        for row in rows), Decimal('0')))
    if total < prepaid:
        raise ValidationError('Стоимость документа меньше уже внесённого аванса заказа. Сначала урегулируйте предоплату.')
    if prepaid and str(kwargs['warehouse_id']) != str(order.payment_warehouse_id):
        raise ValidationError('Выберите склад, в кассу которого была внесена предоплата заказа.')
    kwargs.update(price_type=Sale.PriceType.WHOLESALE, sale_type=Sale.SaleType.WHOLESALE,
        partner_id=order.partner_id, partner_name='' if order.partner_id else draft['calculation']['partner_name'],
        creation_key=draft['key'])
    details = {key: str(value) for key, value in kwargs.items() if key not in ('lines', 'settlement_confirmation')}
    confirm_changes(actor=actor, draft=draft, rows=rows, changes=changes, details=details, token=changes_confirmation)
    kwargs['lines'] = rows
    sale = _create_sale(actor=actor, **kwargs, _direct_rows=rows, _prepaid=prepaid)
    _link(actor, order, draft, sale=sale, snapshot=operation_snapshot(draft, rows, changes))
    return sale


@retry_database_lock
@transaction.atomic
def _create_legacy_order_supply(*, actor, draft, warehouse_id, lines=None, changes_confirmation='', **unused):
    from supplies.services import accept_supply
    from .operation_changes import draft_rows, resolve_rows, confirm_changes, operation_snapshot
    order, prior = _locked_draft(actor, draft)
    if not order.is_stock_order:
        raise ValidationError('Для клиентского заказа создаётся продажа.')
    if prior:
        return prior.supply
    if lines is None:
        lines = [{**row, 'purchase_unit_cost': row['unit_cost']} for row in draft_rows(draft)]
    rows, changes = resolve_rows(draft=draft, lines=lines, supply=True)
    _round(sum((Decimal(row['unit_cost']) * row['quantity'] for row in rows), Decimal('0')))
    products = []
    from catalog.models import CD, Tech
    for kind, model in (('cd', CD), ('tech', Tech)):
        products.extend(model.objects.filter(pk__in={row['product_id'] for row in rows if row['product_type'] == kind}))
    validate_supply_game_codes(products)
    lines = [{'product_type': r['product_type'], 'product_id': r['product_id'], 'supplier_id': r['supplier_id'],
              'quantity': r['quantity'], 'purchase_unit_cost': r['unit_cost']} for r in rows]
    confirm_changes(actor=actor, draft=draft, rows=rows, changes=changes,
                    details={'warehouse_id': str(warehouse_id)}, token=changes_confirmation)
    supply = accept_supply(accepted_by=actor, warehouse_id=warehouse_id, lines=lines, defer_balance=True)
    _link(actor, order, draft, supply=supply, snapshot=operation_snapshot(draft, rows, changes))
    return supply


def validate_supply_snapshot(supply, lines, expenses, weight_transport_cost):
    operation = TripOrderOperation.objects.filter(supply=supply).first()
    if not operation:
        return
    from supplies.services import _normalise_lines, _normalise_expenses, _normalise_weight_transport_cost
    expected = sorted((r['product_type'], r['product_id'], r['supplier_id'], r['quantity'], Decimal(r['unit_cost']))
                      for r in operation.calculation['rows'])
    actual = sorted((r.product_type, r.product_id, r.supplier_id, r.quantity, r.purchase_unit_cost)
                    for r in _normalise_lines(lines))
    if expected != actual or _normalise_expenses(expenses) or _normalise_weight_transport_cost(weight_transport_cost):
        raise ValidationError('Состав и себестоимость прихода фиксированы заказом рейса. Доставка уже включена. Для нового расчёта отмените приход и создайте его из заказа заново.')


@transaction.atomic
def synchronize(operation, *, actor=None):
    """Вызывается в транзакции штатного сервиса после фактического изменения документа."""
    order = CustomerProcurementOrder.objects.select_for_update().get(pk=operation.order_id)
    if operation.sale_id:
        document = operation.sale
        cancelled, completed = document.is_cancelled, document.is_completed
        actor = actor or document.cancelled_by or document.paid_by or document.created_by
    else:
        document = operation.supply
        cancelled = document.is_cancelled
        completed = document.status == document.Status.ACCEPTED
        actor = actor or document.cancelled_by or document.price_reviewed_by or document.accepted_by
    if not operation.active:
        return
    if cancelled:
        operation.active = False
        operation.save(update_fields=('active',))
    old = order.status
    order.status = order.Status.CREATED if cancelled else order.Status.COMPLETED if completed else order.Status.RECEIVING
    if operation.supply_id:
        order.supply = None if cancelled else operation.supply
    order.save(update_fields=('status', 'supply', 'updated_at'))
    if old != order.status:
        CustomerOrderStatusEvent.objects.create(order=order, actor=actor, old_status=old, new_status=order.status)


def edit_direct_sale(*, actor, sale, lines, note, partner_id, partner_name):
    from sales.services import _sale_product_lines
    if ((partner_name not in (None, '') and str(partner_name).strip() != sale.partner_name_snapshot)
            or (partner_id is not None and str(partner_id or '') != str(sale.partner_id or ''))):
        raise ValidationError('Заказчик прямой продажи фиксирован заказом рейса.')
    if any(r.get('product_type') not in ('cd', 'tech') for r in lines):
        raise ValidationError('Прямая продажа содержит только товары заказа рейса.')
    existing = {('cd', i.pk): i for i in sale.cd_items.select_for_update()}
    existing.update({('tech', i.pk): i for i in sale.tech_items.select_for_update()})
    prepared = _sale_product_lines(lines)
    seen = set()
    resulting_note = sale.note if note is None else str(note).strip()
    for row in prepared:
        try:
            identity = (row['product_type'], int(row['item_id']))
        except (ValueError, TypeError) as exc:
            raise ValidationError('Обновите форму продажи: необходим ID каждой строки.') from exc
        item = existing.get(identity)
        if (identity in seen or not item or getattr(item, row['product_type'] + '_id') != row['product_id']
                or item.quantity != row['quantity']):
            raise ValidationError('Товары и количества прямой продажи фиксированы заказом. Можно изменить скидку и примечание.')
        seen.add(identity)
        if row['unit_discount'] > item.unit_price:
            raise ValidationError('Скидка превышает цену товара.')
        if row['unit_discount'] and not resulting_note:
            raise ValidationError('При скидке или доплате укажите примечание.')
        item.unit_discount, item.note = row['unit_discount'], row['note']
        item.line_total = _round((item.unit_price - item.unit_discount) * item.quantity)
        item.full_clean()
        item.save()
    if seen != set(existing):
        raise ValidationError('Нельзя удалить товары прямой продажи: состав фиксирован заказом.')
    sale.total_amount = sum((i.line_total for i in existing.values()), Decimal('0'))
    if sale.total_amount < sale.procurement_prepaid_amount:
        raise ValidationError('Стоимость продажи меньше уже внесённой предоплаты.')
    sale.note = resulting_note
    sale.full_clean()
    sale.save(update_fields=('note', 'total_amount', 'updated_at'))
    from .arrival_documents import synchronize_sale_discounts
    synchronize_sale_discounts(actor=actor,sale=sale)
    return sale


def create_direct_sale(*, actor, draft, changes_confirmation='', **kwargs):
    """Новые документы используют только общие зафиксированные затраты рейса."""
    if not draft.get('arrival_id'):
        raise ValidationError('Сначала зафиксируйте прибытие рейса. Отдельные курсы документа больше не используются.')
    if kwargs.get('price_type','wholesale')!='wholesale' or kwargs.get('sale_type','wholesale')!='wholesale':
        raise ValidationError('Продажа из заказа рейса должна быть оптовой.')
    from .arrival_documents import create_arrival_sale
    return create_arrival_sale(actor=actor,arrival_id=draft['arrival_id'],order_id=draft['order_id'],
        expected_revision=draft['arrival_revision'],draft_key=draft['key'],
        warehouse_id=kwargs.get('warehouse_id'),lines=kwargs.get('lines'),note=kwargs.get('note',''),
        payment_method=kwargs.get('payment_method','cash_postpay'),changes_confirmation=changes_confirmation)


def create_order_supply(*, actor, draft, warehouse_id, lines=None, changes_confirmation=''):
    if not draft.get('arrival_id'):
        raise ValidationError('Сначала зафиксируйте прибытие рейса. Отдельные курсы документа больше не используются.')
    from .arrival_documents import create_arrival_supply
    return create_arrival_supply(actor=actor,arrival_id=draft['arrival_id'],order_id=draft['order_id'],
        expected_revision=draft['arrival_revision'],draft_key=draft['key'],warehouse_id=warehouse_id,
        lines=lines,changes_confirmation=changes_confirmation)
