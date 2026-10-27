"""Дополнительная закупка: новые заказы и партии без перерасчёта прежнего состава."""
import hashlib
import json
from uuid import UUID
from decimal import Decimal

from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from catalog.models import CD, Tech
from catalog.supplier_exclusions import validate_supplier_assignments
from partners.models import Partner, Supplier
from price.models import ProcurementPriceList, ProcurementPriceListItem, ProcurementSupplierOffer
from price.services import decimal_value, procurement_delivery
from .models import SupplierOrderBatch, SupplierTripAllocation, TripAdditionReceipt
from .services import _quantity, create_customer_procurement_order
from .trip_prices import validated_aed
from .trips import _require_manage, _line_for, _record_trip_change, _assert_balances

FIXED_FIELDS = ('exchange_rate_usdt_aed', 'exchange_rate_usdt_rub', 'exchange_rate_aed_rub',
                'delivery_general_usdt_per_kg', 'delivery_devices_usdt_per_kg',
                'delivery_storage_usdt_per_kg', 'delivery_cd_rub')


def _fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def prepare_addition(*, batch, lines, partner_ids=(), allocations=None, require_partners=True):
    from .arrival_models import TripArrival
    if TripArrival.objects.filter(trip=batch,arrived_at__isnull=False).exists():
        raise ValidationError('После прибытия нельзя добавлять закупочные позиции в этот рейс. Создайте отдельный заказ.')
    if not batch.price_list_id:
        raise ValidationError('У рейса нет сохранённого прайса.')
    price_list = batch.price_list
    rate = price_list.exchange_rate_aed_rub
    if rate is None or not rate.is_finite() or rate <= 0:
        raise ValidationError('У рейса отсутствует сохранённый курс AED/RUB. Текущий курс не подставляется.')
    if not lines or len(lines) > 100:
        raise ValidationError('Укажите от 1 до 100 дополнительных товаров.')
    rows, seen = [], set()
    for source in lines:
        try:
            kind, pk = str(source['product']).split(':')
            model = {'cd': CD, 'tech': Tech}[kind]
            product = model.objects.active().select_related('platform' if kind == 'cd' else 'product_type').get(pk=int(pk))
            supplier = Supplier.objects.get(pk=source['supplier'])
        except (KeyError, ValueError, TypeError, CD.DoesNotExist, Tech.DoesNotExist, Supplier.DoesNotExist) as exc:
            raise ValidationError('Выберите существующий товар и поставщика.') from exc
        if (kind, product.pk) in seen:
            raise ValidationError('В дополнительной закупке товар указан дважды.')
        seen.add((kind, product.pk))
        validate_supplier_assignments([(kind, product.pk, supplier.pk, product.name)])
        aed = validated_aed(source['aed'])
        price = decimal_value(source['customer_price'], nonnegative=True, label='Цена заказчика')
        stock_qty = _quantity(source['stock_qty'], 'Количество на склад')
        customer_qty = _quantity(source['customer_qty'], 'Количество заказчикам')
        if stock_qty + customer_qty <= 0 or stock_qty + customer_qty > 2147483647:
            raise ValidationError(f'{product.name}: укажите положительное итоговое количество.')
        delivery, group, tariff = procurement_delivery(product=product, kind=kind, price_list=price_list)
        base = decimal_value(aed * rate, nonnegative=True)
        cost = base + delivery
        row = dict(product=product, kind=kind, supplier=supplier, aed=aed, customer_price=price,
                   stock_qty=stock_qty, customer_qty=customer_qty, delivery=delivery, group=group,
                   tariff=tariff, base=base, cost=cost, quantity=stock_qty + customer_qty,
                   weight=product.weight_grams, name=product.name)
        row.update(purchase_total=aed * row['quantity'], delivery_total=delivery * row['quantity'],
                   cost_total=cost * row['quantity'], customer_total=price * customer_qty,
                   unit_profit=price - cost, expected_profit=(price - cost) * customer_qty)
        rows.append(row)
    try:
        ids = sorted({int(pk) for pk in partner_ids})
    except (ValueError, TypeError) as exc:
        raise ValidationError('Выберите партнёров из справочника.') from exc
    partners = list(Partner.objects.filter(pk__in=ids, is_archived=False).order_by('pk'))
    if len(partners) != len(ids):
        raise ValidationError('Один из партнёров недоступен.')
    if require_partners and any(row['customer_qty'] for row in rows) and not partners:
        raise ValidationError('Выберите хотя бы одного заказчика.')
    if allocations is not None:
        expected_keys = {f'{index}:{pk}' for index, row in enumerate(rows) if row['customer_qty'] for pk in ids}
        if set(allocations) != expected_keys:
            raise ValidationError('Матрица распределения изменена. Повторите заполнение.')
        for index, row in enumerate(rows):
            row['distribution'] = {pk: _quantity(allocations[f'{index}:{pk}'], 'Распределение') for pk in ids} if row['customer_qty'] else {}
            if sum(row['distribution'].values()) != row['customer_qty']:
                raise ValidationError(f"{row['name']}: распределено {sum(row['distribution'].values())}, нужно {row['customer_qty']} шт.")
    snapshots = [{k: (v.pk if k in ('product', 'supplier') else v) for k, v in row.items()} for row in rows]
    fingerprint = _fingerprint({'rows': snapshots, 'partners': ids, 'rates': {field: getattr(price_list, field) for field in FIXED_FIELDS}})
    totals = {key: sum((row[key] for row in rows), Decimal('0')) for key in
              ('purchase_total', 'delivery_total', 'cost_total', 'customer_total', 'expected_profit')}
    return rows, partners, totals, fingerprint


@transaction.atomic
def commit_addition(*, actor, batch_id, key, lines, partner_ids, allocations, preview_fingerprint, revision):
    _require_manage(actor)
    if not actor.has_perm('orders.create_order'):
        raise PermissionDenied('Нет права создавать заказы.')
    try:
        key = UUID(str(key))
    except (ValueError, TypeError) as exc:
        raise ValidationError('Откройте новую форму дополнительных товаров.') from exc
    batch = SupplierOrderBatch.objects.select_for_update().select_related('price_list').get(pk=batch_id)
    request_fingerprint = _fingerprint({'lines': lines, 'partners': partner_ids, 'allocations': allocations,
                                        'preview': preview_fingerprint, 'revision': revision})
    existing = TripAdditionReceipt.objects.filter(pk=key).first()
    if existing:
        if existing.actor_id != actor.pk or existing.batch_id != batch.pk or existing.fingerprint != request_fingerprint:
            raise ValidationError('Этот запрос уже использован для другой закупки.')
        return list(existing.orders.all())
    if batch.revision != revision:
        raise ValidationError('Рейс изменился. Вернитесь к итоговой проверке дополнительных товаров.')
    _assert_balances(batch)
    rows, partners, totals, fingerprint = prepare_addition(batch=batch, lines=lines, partner_ids=partner_ids, allocations=allocations)
    if fingerprint != preview_fingerprint:
        raise ValidationError('Вес, тарифы или товары изменились. Проверьте новый итоговый расчёт.')
    receipt = TripAdditionReceipt.objects.create(key=key, batch=batch, actor=actor, fingerprint=request_fingerprint)
    # Отдельная версия хранит исключительно новую партию; исходный прайс не меняется.
    price_list = ProcurementPriceList.objects.create(created_by=actor, supplier_offers_complete=True, is_trip_addition=True,
                            **{field: getattr(batch.price_list, field) for field in FIXED_FIELDS})
    sources = []
    for row in rows:
        source = ProcurementPriceListItem.objects.create(price_list=price_list, product_kind=row['kind'],
            **{row['kind']: row['product']}, product_name_snapshot=row['name'], article_snapshot=row['product'].sku,
            selected_supplier=row['supplier'], supplier_price_aed=row['aed'], exchange_rate_aed_rub=price_list.exchange_rate_aed_rub,
            base_price_rub=row['base'], delivery_rub=row['delivery'], weight_grams_snapshot=row['weight'],
            delivery_group_snapshot=row['group'], delivery_usdt_per_kg_snapshot=row['tariff'],
            markup_rub=row['customer_price'] - row['cost'], original_markup_rub=row['customer_price'] - row['cost'],
            prepayment_price_rub=row['customer_price'], postpayment_price_rub=row['customer_price'], postpayment_surcharge_rub=0)
        ProcurementSupplierOffer.objects.create(price_list_item=source, supplier=row['supplier'], price_aed=row['aed'])
        sources.append(source)
    orders = []
    for partner in [None, *partners]:
        order_lines = []
        for row, source in zip(rows, sources):
            quantity = row['stock_qty'] if partner is None else row['distribution'].get(partner.pk, 0)
            if quantity:
                order_lines.append({'price_list_item_id': source.pk, 'prepayment_quantity': quantity if partner is None else 0,
                                    'postpayment_quantity': quantity if partner is not None else 0})
        if not order_lines:
            continue
        order = create_customer_procurement_order(actor=actor, price_list_id=price_list.pk,
            recipient=partner.name if partner else 'На склад', partner_id=partner.pk if partner else None,
            purpose='customer' if partner else 'stock', comment=f'Дополнительные товары рейса №{batch.pk}', lines=order_lines)
        order.trip = batch
        order.save(update_fields=('trip', 'updated_at'))
        batch.source_orders.add(order)
        for item in order.items.select_related('price_list_item__cd', 'price_list_item__tech'):
            line = _line_for(batch, item.price_list_item, item.selected_supplier_id, item.selected_supplier_id, item.supplier_price_aed_snapshot)
            line.quantity += item.quantity
            line.save(update_fields=('quantity',))
            SupplierTripAllocation.objects.create(line=line, order_item=item, prepayment_quantity=item.prepayment_quantity,
                                                 postpayment_quantity=item.postpayment_quantity, prepayment_cap=item.prepayment_quantity)
        orders.append(order)
    receipt.orders.set(orders)
    _assert_balances(batch)
    _record_trip_change(batch, actor, 'Добавлены дополнительные товары отдельными заказами',
                        {'action': 'additional_goods', 'order_ids': [order.pk for order in orders], 'request_key': str(key)})
    return orders
