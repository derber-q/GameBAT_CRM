"""Документы фактического состава рейса; складские дополнения учитываются отдельно."""
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4
from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction
from core.db_retry import retry_database_lock
from catalog.models import CD, Tech
from catalog.game_codes import validate_supply_game_codes
from price.services import decimal_value, RATE_PRECISION
from .arrival import lock_arrival, reduce_received
from .arrival_math import unit_cohorts
from .arrival_models import TripArrival
from .models import TripOrderOperation


def cohort_rows(arrival, order_id):
    rows = []
    for source in arrival.rows.filter(order_id=order_id).select_related('cd', 'tech', 'supplier'):
        if not source.actual_quantity:
            continue
        for slot, (quantity, cost) in enumerate(unit_cohorts(source.final_total, source.actual_quantity)):
            rows.append({'product_type':source.product_kind, 'product_id':source.product_id,
                'label':source.product.name, 'quantity':quantity, 'supplier_id':source.supplier_id,
                'unit_cost':str(cost), 'unit_price':str(source.customer_price) if source.customer_price is not None else '',
                'unit_discount':str(source.unit_discount), 'line_note':source.line_note, 'origin':'trip',
                'trip_row':str(source.pk), 'trip_cost_row_id':source.pk, 'trip_cost_slot':slot})
    return rows


def form_rows(arrival, order_id):
    return [{'product_type':row.product_kind, 'product_id':row.product_id, 'label':row.product.name,
        'quantity':row.actual_quantity, 'supplier_id':row.supplier_id, 'unit_cost':str(
            (row.final_total / row.actual_quantity).quantize(Decimal('.01'), rounding=ROUND_HALF_UP) if row.actual_quantity else 0),
        'unit_price':str(row.customer_price) if row.customer_price is not None else '',
        'trip_row':str(row.pk), 'trip_cost_row_id':row.pk, 'origin':'trip',
        'weight_grams':row.weight_grams_snapshot,
        'unit_discount':str(row.unit_discount), 'line_note':row.line_note,
        'cusa_ppsa_code':getattr(row.product,'cusa_ppsa_code','')}
        for row in arrival.rows.filter(order_id=order_id).select_related('cd','tech')]


def operation_snapshot(arrival, order, rows):
    return {'arrival_id':arrival.pk, 'arrival_revision':arrival.revision, 'order_id':order.pk,
        'trip_id':arrival.trip_id, 'usd_rub':str(arrival.usdt_rub), 'usd_aed':str(arrival.usdt_aed),
        'aed_rub':str(decimal_value(arrival.usdt_rub/arrival.usdt_aed, precision=RATE_PRECISION, positive=True)),
        'partner_id':order.partner_id, 'partner_name':order.partner_name_snapshot or order.recipient,
        'purpose':order.purpose, 'rows':rows, 'control_total':str(arrival.control_total)}


def build_draft(*, actor, order):
    from .fulfillment import require_permissions, prepaid_amount
    require_permissions(actor, order)
    arrival = TripArrival.objects.filter(trip_id=order.trip_id, arrived_at__isnull=False).first()
    if not arrival:
        raise ValidationError('Сначала подтвердите «Рейс приехал» на странице рейса.')
    snapshot = operation_snapshot(arrival, order, form_rows(arrival, order.pk))
    snapshot.update(prepaid=str(prepaid_amount(order)), payment_warehouse_id=order.payment_warehouse_id)
    return {'key':str(uuid4()), 'order_id':order.pk, 'arrival_id':arrival.pk,
            'arrival_revision':arrival.revision, 'calculation':snapshot}


def _prior(actor, order_id, draft_key, kind):
    prior = TripOrderOperation.objects.filter(draft_key=draft_key).first()
    if not prior:
        return None
    if prior.order_id != order_id or prior.created_by_id!=actor.pk or not prior.active or not getattr(prior, kind + '_id'):
        raise ValidationError('Эта форма уже использована. Откройте заказ заново.')
    from .fulfillment import require_permissions
    require_permissions(actor,prior.order)
    return getattr(prior, kind)


def _order(actor, arrival, order_id, stock):
    from .fulfillment import require_permissions
    order = arrival.trip.trip_orders.filter(pk=order_id).first()
    if order is None:raise ValidationError('Заказ не относится к этому рейсу.')
    require_permissions(actor, order)
    if order.is_stock_order != stock:
        raise ValidationError('Назначение документа не соответствует заказу рейса.')
    if order.operations.filter(active=True).exists():
        raise ValidationError('Для заказа уже существует действующий документ.')
    return order


def _prepare(actor, arrival, order, lines, *, stock=False):
    sources = {row.pk:row for row in arrival.rows.select_for_update().filter(order=order)}
    lines = form_rows(arrival, order.pk) if lines is None else lines
    quantities = {key:0 for key in sources}
    configs, extras, changes = {}, [], []
    for raw in lines:
        try:
            quantity = int(raw.get('quantity',0))
            product_id = int(raw.get('product_id'))
            reference = int(raw['trip_row']) if raw.get('trip_row') else None
        except (ValueError, TypeError) as exc:
            raise ValidationError('Данные товарной строки повреждены.') from exc
        if reference:
            source = sources.get(reference)
            if (reference in configs or not source or source.product_kind != raw.get('product_type')
                    or source.product_id != product_id):
                raise ValidationError('Источник закупочной строки изменён или повторяется.')
            quantities[reference] = quantity
            discount = forms.DecimalField(max_digits=20, decimal_places=2).clean(raw.get('unit_discount') or 0)
            if source.customer_price is not None and discount > source.customer_price:
                raise ValidationError('Скидка превышает согласованную цену покупателя.')
            configs[reference] = (discount, str(raw.get('line_note') or '').strip())
        else:
            if stock:
                raise ValidationError('В приходе допускаются только закупочные позиции этого заказа рейса.')
            if quantity <= 0:
                continue
            model = {'cd':CD, 'tech':Tech}.get(raw.get('product_type'))
            product = model.objects.active().select_for_update().filter(pk=product_id).first() if model else None
            if not product or product.wholesale_price is None:
                raise ValidationError('Выберите складской товар с оптовой ценой.')
            extras.append({**raw, 'quantity':quantity, 'origin':'warehouse', 'label':product.name,
                'unit_price':str(product.wholesale_price), 'unit_cost':str(product.cost),
                'cusa_ppsa_code':getattr(product,'cusa_ppsa_code','')})
            changes.append(f'Добавлен товар со склада «{product.name}»: {quantity} шт.')
    if arrival.finalized:
        if any(quantities[key] != row.actual_quantity for key,row in sources.items()):
            raise ValidationError('Фактические количества финализированного рейса зафиксированы.')
    else:
        for key,row in sources.items():
            if quantities[key] != row.actual_quantity:
                changes.append(f'«{row.product.name}»: количество {row.actual_quantity} → {quantities[key]} шт.')
        arrival = reduce_received(actor=actor, arrival_id=arrival.pk, order_id=order.pk,
            quantities=quantities, expected_revision=arrival.revision)
    for key,(discount,note) in configs.items():
        source = sources[key]
        if discount and not note:
            # Общее примечание формы также может объяснять скидку; его проверяет сервис Sale.
            note = ''
        source.unit_discount, source.line_note = discount, note
        source.save(update_fields=['unit_discount','line_note'])
    return arrival, cohort_rows(arrival, order.pk) + extras, changes


def _confirm(actor, arrival, order, rows, changes, key, confirmation, details):
    from .operation_changes import confirm_changes
    draft = {'key':str(key)}
    confirm_changes(actor=actor, draft=draft, rows=form_rows(arrival, order.pk) + [r for r in rows if r['origin']=='warehouse'],
        changes=changes, details=details, token=confirmation)


@retry_database_lock
@transaction.atomic
def create_arrival_sale(*, actor, arrival_id, order_id, expected_revision, warehouse_id, lines=None,
        draft_key=None, payment_method='cash_postpay', note='', changes_confirmation=''):
    from sales.models import Sale
    from sales.services import _create_sale
    from .fulfillment import _link, prepaid_amount
    key = draft_key or uuid4()
    prior = _prior(actor,order_id,key,'sale')
    if prior:
        return prior
    arrival = lock_arrival(arrival_id, expected_revision, finalized_allowed=True)
    order = _order(actor, arrival, order_id, False)
    if payment_method not in (Sale.PaymentMethod.CASH_POSTPAY, Sale.PaymentMethod.BANK_TRANSFER_POSTPAY):
        raise ValidationError('Продажа из рейса создаётся с постоплатой; оплату подтвердите после общей финализации.')
    arrival, rows, changes = _prepare(actor,arrival,order,lines)
    _confirm(actor,arrival,order,rows,changes,key,changes_confirmation,{'warehouse_id':str(warehouse_id),'note':note,'payment_method':payment_method})
    if not rows:
        return None
    sale = _create_sale(actor=actor, warehouse_id=warehouse_id, price_type='wholesale', sale_type='wholesale',
        payment_method=payment_method, lines=rows, partner_id=order.partner_id,
        partner_name='' if order.partner_id else order.partner_name_snapshot or order.recipient,
        note=note, creation_key=key, _direct_rows=rows, _prepaid=prepaid_amount(order))
    if sale.total_amount < sale.procurement_prepaid_amount:
        raise ValidationError('Стоимость продажи меньше уже внесённого аванса. Сначала урегулируйте предоплату заказа.')
    snapshot = operation_snapshot(arrival,order,rows)
    _link(actor,order,{'key':str(key),'calculation':snapshot},sale=sale)
    return sale


@retry_database_lock
@transaction.atomic
def create_arrival_supply(*, actor, arrival_id, order_id, expected_revision, warehouse_id, lines=None,
        draft_key=None, changes_confirmation=''):
    from supplies.services import accept_supply
    from supplies.models import Supply
    from .fulfillment import _link
    key = draft_key or uuid4()
    prior = _prior(actor,order_id,key,'supply')
    if prior:
        return prior
    arrival = lock_arrival(arrival_id,expected_revision,finalized_allowed=True)
    order = _order(actor,arrival,order_id,True)
    arrival, rows, changes = _prepare(actor,arrival,order,lines,stock=True)
    _confirm(actor,arrival,order,rows,changes,key,changes_confirmation,{'warehouse_id':str(warehouse_id)})
    if not rows:
        return None
    validate_supply_game_codes([row.product for row in arrival.rows.filter(order=order) if row.actual_quantity])
    supply = accept_supply(accepted_by=actor,warehouse_id=warehouse_id,defer_balance=True,
        lines=[{**row,'purchase_unit_cost':row['unit_cost']} for row in rows])
    for kind in ('cd','tech'):
        for item,row in zip(getattr(supply,kind+'_items').order_by('pk'),[r for r in rows if r['product_type']==kind]):
            item.trip_cost_row_id, item.trip_cost_slot = row['trip_cost_row_id'],row['trip_cost_slot']
            item.save(update_fields=['trip_cost_row','trip_cost_slot'])
    supply.status = Supply.Status.WAITING_TRIP_FINALIZATION
    supply.save(update_fields=['status'])
    snapshot = operation_snapshot(arrival,order,rows)
    _link(actor,order,{'key':str(key),'calculation':snapshot},supply=supply)
    return supply


def refresh_supply_calculations(supply, *, rebase=False):
    """Переиспользует штатный средневзвешенный расчёт без движения товара."""
    from supplies.models import SupplyCostCalculation
    from supplies.services import _calculation_values
    from warehouse.valuation import warehouse_owned_quantity
    existing = {(c.product_kind,c.cd_id or c.tech_id):c for c in supply.cost_calculations.select_for_update()}
    wanted = set()
    for kind in ('cd','tech'):
        items = list(getattr(supply,kind+'_items').select_related('product'))
        for product_id in sorted({item.product_id for item in items}):
            key = kind,product_id
            wanted.add(key)
            product = (CD if kind=='cd' else Tech).objects.select_for_update().get(pk=product_id)
            current = existing.get(key)
            old_quantity = warehouse_owned_quantity(kind,product_id) if rebase or not current else current.old_owned_quantity
            old_cost = product.cost if rebase or not current else current.old_unit_cost
            values, _, _ = _calculation_values(supply=supply,product_type=kind,product=product,
                old_quantity=old_quantity,old_cost=old_cost,incoming={
                    'quantity':sum(item.quantity for item in items if item.product_id==product_id),
                    'value':sum(item.final_line_total for item in items if item.product_id==product_id)})
            if current:
                for name,value in values.items():
                    setattr(current,name,value)
                current.save()
            else:
                SupplyCostCalculation.objects.create(**values)
    for key,current in existing.items():
        if key not in wanted:
            current.delete()


def _refresh_sale(sale, rows):
    from sales.models import SaleCDItem, SaleTechItem
    if sale.is_completed:
        raise ValidationError('Завершённая продажа не может участвовать в перерасчёте рейса.')
    for kind,model in (('cd',SaleCDItem),('tech',SaleTechItem)):
        existing = {(item.trip_cost_row_id,item.trip_cost_slot):item
                    for item in model.objects.select_for_update().filter(sale=sale,trip_cost_row__isnull=False)}
        wanted = set()
        for row in [row for row in rows if row['product_type']==kind]:
            key = row['trip_cost_row_id'],row['trip_cost_slot']
            wanted.add(key)
            item = existing.get(key)
            product = (CD if kind=='cd' else Tech).objects.get(pk=row['product_id'])
            values = {'quantity':row['quantity'],'unit_cost_snapshot':Decimal(row['unit_cost']),
                'unit_price':Decimal(row['unit_price']),'unit_discount':Decimal(row['unit_discount']),
                'line_total':(Decimal(row['unit_price'])-Decimal(row['unit_discount']))*row['quantity'],
                'note':row['line_note']}
            if item:
                for name,value in values.items():
                    setattr(item,name,value)
                item._pending_trip_cost_write = True
                item.save(update_fields=list(values))
            else:
                model.objects.create(sale=sale,**{kind:product},**values,is_direct_delivery=True,
                    trip_cost_row_id=key[0],trip_cost_slot=key[1],product_name_snapshot=product.name,article_snapshot=product.sku)
        for key,item in existing.items():
            if key not in wanted:
                item.delete()
    sale.total_amount = sum(item.line_total for manager in (sale.cd_items,sale.tech_items) for item in manager.all())
    if sale.total_amount < sale.procurement_prepaid_amount:
        raise ValidationError('Стоимость продажи меньше уже внесённой предоплаты. Сначала урегулируйте аванс заказа.')
    sale.save(update_fields=['total_amount','updated_at'])


def _refresh_supply(supply, rows):
    from supplies.models import Supply, SupplyCDItem, SupplyTechItem
    if supply.status != Supply.Status.WAITING_TRIP_FINALIZATION:
        raise ValidationError('Приход должен ждать общей финализации рейса.')
    for kind,model in (('cd',SupplyCDItem),('tech',SupplyTechItem)):
        existing = {(item.trip_cost_row_id,item.trip_cost_slot):item for item in model.objects.select_for_update().filter(supply=supply)}
        wanted = set()
        for row in [r for r in rows if r['product_type']==kind]:
            key = row['trip_cost_row_id'],row['trip_cost_slot']
            wanted.add(key)
            source = supply.procurement_order.arrival_rows.select_related('supplier','cd','tech').get(pk=key[0])
            product, supplier = source.product,source.supplier
            item = existing.get(key) or model(supply=supply,product=product,trip_cost_row=source,trip_cost_slot=key[1])
            item.supplier = supplier
            item.quantity = row['quantity']
            item.purchase_unit_cost = item.effective_unit_cost = Decimal(row['unit_cost'])
            item.allocated_expense_per_unit = item.allocated_transport_cost = item.transport_cost_per_unit = 0
            item.weight_grams_snapshot = source.weight_grams_snapshot
            item.line_weight_grams = source.weight_grams_snapshot * item.quantity
            item.base_line_total = item.final_line_total = item.effective_unit_cost * item.quantity
            item.product_name_snapshot, item.product_sku_snapshot = product.name,product.sku
            item.supplier_name_snapshot, item.supplier_letter_snapshot, item.supplier_color_snapshot = supplier.name,supplier.letter,supplier.highlight_color
            item.save()
        for key,item in existing.items():
            if key not in wanted:
                item.delete()
    items = list(supply.cd_items.all()) + list(supply.tech_items.all())
    supply.total_units = sum(item.quantity for item in items)
    supply.goods_total_before_expenses = supply.grand_total = sum(item.final_line_total for item in items)
    supply.total_weight_grams = sum(item.line_weight_grams for item in items)
    supply.revision_number += 1
    supply.save(update_fields=['total_units','goods_total_before_expenses','grand_total','total_weight_grams','revision_number'])
    refresh_supply_calculations(supply)


def refresh_documents(arrival, *, actor=None):
    for operation in TripOrderOperation.objects.select_for_update().filter(order__trip_id=arrival.trip_id,active=True).select_related('order','sale','supply'):
        rows = cohort_rows(arrival,operation.order_id)
        actor = actor or operation.created_by
        if operation.sale_id:
            sale = operation.sale
            warehouse = warehouse_rows(sale)
            if not rows and not warehouse:
                from sales.services import cancel_sale
                cancel_sale(actor=actor,sale_id=sale.pk,comment='Все товары заказа не поступили')
                continue
            _refresh_sale(sale,rows)
            rows += warehouse
        else:
            if not rows:
                from supplies.services import cancel_supply
                cancel_supply(actor=actor,supply_id=operation.supply_id,comment='Все товары заказа не поступили')
                continue
            _refresh_supply(operation.supply,rows)
        operation.calculation = operation_snapshot(arrival,operation.order,rows)
        operation._pending_trip_cost_write = True
        operation.save(update_fields=['calculation'])


def warehouse_rows(sale):
    return [{'product_type':kind,'product_id':getattr(item,kind+'_id'),'quantity':item.quantity,
        'unit_cost':str(item.unit_cost_snapshot),'unit_price':str(item.unit_price),'unit_discount':str(item.unit_discount),
        'line_note':item.note,'origin':'warehouse'}
        for kind in ('cd','tech') for item in getattr(sale,kind+'_items').filter(is_direct_delivery=False)]


def synchronize_sale_discounts(*, actor, sale):
    operation=TripOrderOperation.objects.select_related('order').filter(sale=sale,active=True).first()
    if not operation or not operation.calculation.get('arrival_id'):
        return
    arrival=lock_arrival(operation.calculation['arrival_id'],finalized_allowed=True)
    configs={}
    for kind in ('cd','tech'):
        for item in getattr(sale,kind+'_items').filter(trip_cost_row__isnull=False):
            value=(item.unit_discount,item.note)
            if item.trip_cost_row_id in configs and configs[item.trip_cost_row_id]!=value:
                raise ValidationError('У копеечных групп одной закупочной позиции должны совпадать скидка и примечание.')
            configs[item.trip_cost_row_id]=value
    changes=[]
    for source in arrival.rows.select_for_update().filter(pk__in=configs):
        discount,note=configs[source.pk]
        if (source.unit_discount,source.line_note)!=(discount,note):
            changes.append({'row_id':source.pk,'before':str(source.unit_discount),'after':str(discount),'note':note})
            source.unit_discount,source.line_note=discount,note
            source.save(update_fields=['unit_discount','line_note'])
    if changes:
        from .trips import _record_trip_change
        if not arrival.finalized:
            arrival.revision+=1
            arrival.save(update_fields=['revision'])
            operation.calculation=operation_snapshot(arrival,operation.order,cohort_rows(arrival,operation.order_id)+warehouse_rows(sale))
            operation._pending_trip_cost_write=True
            operation.save(update_fields=['calculation'])
        _record_trip_change(arrival.trip,actor,f'Согласованы скидки продажи {sale.visible_id}',{'changes':changes})
