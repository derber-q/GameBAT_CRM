"""Создание рейсов, привязка прайса и распределение поставщиков/заказчиков."""
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from partners.models import Supplier
from price.models import ProcurementSupplierOffer
from catalog.supplier_exclusions import exclusion_keys
from .models import (
    CustomerProcurementOrder, CustomerProcurementOrderItem, OrderAdjustment, OrderAdjustmentChange,
    SupplierOrderBatch, SupplierOrderBatchLine, SupplierTripAllocation, SupplierTripChange,
)
from .services import _quantity, _save_totals
from .order_editing import require_untransferred_order

MANAGE_PERMISSIONS = (
    "orders.generate_supplier_orders", "orders.edit_created_order",
    "partners.view_supplier_details", "price.view_supplier_prices",
)


def can_manage_trips(user):
    return user.is_superuser or user.has_perms(MANAGE_PERMISSIONS)


def _require_manage(actor):
    if not can_manage_trips(actor):
        raise PermissionDenied("Недостаточно прав для изменения рейса и клиентских заказов.")


def trip_queryset():
    return SupplierOrderBatch.objects.select_related("price_list", "created_by").prefetch_related(
        "source_orders", "trip_orders__items", "trip_orders__operations", "lines__supplier", "lines__price_supplier",
        "lines__cd__platform", "lines__tech__product_type",
        "lines__price_list_item__supplier_offers__supplier", "lines__allocations__order_item__order",
        "lines__allocations__order_item__order__operations",
        "changes__actor",
    )


def _batch_exclusions(batch):
    # Объект рейса загружается заново внутри каждой операции. Одна выборка
    # допуска обслуживает весь состав этой транзакции, без запроса на строку.
    if not hasattr(batch, '_current_supplier_exclusions'):
        batch._current_supplier_exclusions = exclusion_keys()
    return batch._current_supplier_exclusions


def _check_supplier_admission(batch, source, *supplier_ids):
    blocked = _batch_exclusions(batch)
    if any((source.product_kind, source.product_id, supplier_id) in blocked for supplier_id in supplier_ids):
        raise ValidationError(f'{source.product_name_snapshot}: поставщик или источник цены исключён из подбора этого товара.')


def _line_for(batch, source, supplier_id, price_supplier_id, price, *, price_updated_at=None):
    _check_supplier_admission(batch, source, supplier_id, price_supplier_id)
    line, created = SupplierOrderBatchLine.objects.get_or_create(
        batch=batch, supplier_id=supplier_id, price_list_item=source, price_supplier_id=price_supplier_id,
        defaults={"product_kind": source.product_kind, source.product_kind: source.product,
                  "product_name_snapshot": source.product_name_snapshot, "article_snapshot": source.article_snapshot,
                  "quantity": 0, "supplier_price_aed_snapshot": price},
    )
    if line.supplier_price_aed_snapshot != price:
        raise ValidationError("Сохранённая цена строки изменилась. Обновите страницу.")
    if price_updated_at and line.supplier_price_updated_at is None:
        if not created:
            raise ValidationError('Нельзя объединить скорректированную закупку с другой самостоятельной партией.')
        line.supplier_price_updated_at = price_updated_at
        line.save(update_fields=('supplier_price_updated_at',))
    return line


@transaction.atomic
def create_trip(*, actor, order_ids, creation_key, name="", allow_empty=False):
    _require_manage(actor)
    try:
        ids = {int(value) for value in order_ids}
        key = UUID(str(creation_key))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValidationError("Выберите заказы и повторите создание рейса со страницы списка.") from exc
    if not ids and not allow_empty:
        raise ValidationError("Выберите хотя бы один созданный заказ.")
    name = str(name or "").strip()
    if len(name) > 255:
        raise ValidationError("Название рейса не должно превышать 255 символов.")
    existing = SupplierOrderBatch.objects.filter(creation_key=key).first()
    if existing:
        original_empty = allow_empty and not ids and existing.changes.filter(revision=0, details__empty=True).exists()
        if allow_empty and not ids and not original_empty:
            raise ValidationError('Этот запрос уже создал другой рейс. Обновите страницу.')
        if (not original_empty and set(existing.source_orders.values_list("pk", flat=True)) != ids) or existing.name != name:
            raise ValidationError("Этот запрос уже создал другой рейс. Обновите страницу.")
        return existing
    if not ids:
        batch = SupplierOrderBatch.objects.create(created_by=actor, creation_key=key, name=name)
        SupplierTripChange.objects.create(batch=batch, actor=actor, revision=0,
            description="Создан пустой рейс", details={"order_ids": [], "empty": True})
        return batch
    orders = list(CustomerProcurementOrder.objects.select_for_update().filter(pk__in=ids).order_by("pk"))
    if len(orders) != len(ids):
        raise ValidationError("Один из выбранных заказов не найден.")
    for order in orders:
        require_untransferred_order(order)
    if any(order.status != order.Status.CREATED for order in orders):
        raise ValidationError("В рейс можно включить только заказы в статусе «Создан».")
    if any(order.trip_id for order in orders):
        raise ValidationError("Один из заказов уже включён в рейс.")
    if len({order.price_list_id for order in orders}) != 1:
        raise ValidationError("Все заказы рейса должны быть из одной версии прайса.")
    items = list(CustomerProcurementOrderItem.objects.select_for_update().select_related(
        "price_list_item__cd", "price_list_item__tech", "cd", "tech",
    ).filter(order_id__in=ids).order_by("order_id", "pk"))
    if not any(item.prepayment_quantity + item.postpayment_quantity for item in items):
        raise ValidationError("В выбранных заказах нет товаров.")
    if any(item.product.is_archived for item in items):
        raise ValidationError("Архивный товар нельзя включить в новый рейс.")
    batch = SupplierOrderBatch.objects.create(
        created_by=actor, price_list_id=orders[0].price_list_id, creation_key=key, name=name,
    )
    batch.source_orders.set(orders)
    for order in orders:
        order.trip = batch
        order.save(update_fields=("trip", "updated_at"))
    for item in items:
        line = _line_for(batch, item.price_list_item, item.selected_supplier_id,
                         item.selected_supplier_id, item.supplier_price_aed_snapshot)
        line.quantity += item.prepayment_quantity + item.postpayment_quantity
        line.save(update_fields=("quantity",))
        SupplierTripAllocation.objects.create(
            line=line, order_item=item, prepayment_quantity=item.prepayment_quantity,
            postpayment_quantity=item.postpayment_quantity, prepayment_cap=item.prepayment_quantity,
        )
    SupplierTripChange.objects.create(batch=batch, actor=actor, revision=0,
                                     description="Создан рейс", details={"order_ids": sorted(ids)})
    apply_m_to_f_rule(actor=actor, batch_id=batch.pk)
    batch.refresh_from_db(fields=("revision",))
    return batch


def create_empty_trip(*, actor, creation_key, name=""):
    return create_trip(actor=actor, order_ids=(), creation_key=creation_key, name=name, allow_empty=True)


def _assert_balances(batch):
    quantities = {}
    for line in batch.lines.prefetch_related("allocations").all():
        if line.quantity != sum(row.quantity for row in line.allocations.all()):
            raise ValidationError("Количество поставщика не совпадает с распределением заказчиков.")
        for row in line.allocations.all():
            pre, post = quantities.get(row.order_item_id, (0, 0))
            quantities[row.order_item_id] = (pre + row.prepayment_quantity, post + row.postpayment_quantity)
    items = CustomerProcurementOrderItem.objects.filter(order__trip=batch)
    for item in items:
        if quantities.pop(item.pk, (0, 0)) != (item.prepayment_quantity, item.postpayment_quantity):
            raise ValidationError("Клиентский заказ изменён. Обновите рейс перед корректировкой.")
    if quantities:
        raise ValidationError("В рейсе обнаружена позиция постороннего заказа.")


def available_trips(*, price_list_id, exclude_id=None):
    from django.db.models import Q
    from .arrival_models import TripArrival
    return SupplierOrderBatch.objects.trips().filter(
        Q(price_list_id=price_list_id) | Q(price_list__isnull=True),
    ).exclude(pk=exclude_id).exclude(pk__in=TripArrival.objects.filter(
        arrived_at__isnull=False).values('trip_id')).exclude(
        trip_orders__status__in=(CustomerProcurementOrder.Status.CONFIRMED,
                                CustomerProcurementOrder.Status.RECEIVING,
                                CustomerProcurementOrder.Status.COMPLETED),
    ).order_by("pk")


def _require_editable_trip(batch):
    from .arrival_models import TripArrival
    if TripArrival.objects.filter(trip=batch,arrived_at__isnull=False).exists():
        raise ValidationError('Рейс приехал. Исходные партии зафиксированы; используйте сверку фактического поступления.')
    orders = list(batch.trip_orders.select_for_update().order_by("pk"))
    for order in orders:
        require_untransferred_order(order)
    if any(order.status != order.Status.CREATED for order in orders):
        raise ValidationError("Рейс зафиксирован: один из заказов уже подтверждён.")
    if {order.pk for order in orders} != set(batch.source_orders.values_list("pk", flat=True)):
        raise ValidationError("Связи заказов рейса изменились. Обновите страницу.")
    _assert_balances(batch)


def _record_trip_change(batch, actor, description, details):
    batch.revision += 1
    batch.save(update_fields=("revision",))
    SupplierTripChange.objects.create(batch=batch, actor=actor, revision=batch.revision,
                                     description=description, details=details)


@transaction.atomic
def assign_order_to_trip(*, actor, order_id, target_batch_id, target_revision,
                         source_batch_id=None, source_revision=None):
    """Перенести весь заказ или добавить свободный, сохранив снимки и распределение."""
    _require_manage(actor)
    try:
        target_id = int(target_batch_id)
        source_id = int(source_batch_id) if source_batch_id is not None else None
    except (TypeError, ValueError) as exc:
        raise ValidationError("Заказ или рейс не найдены.") from exc
    if target_id == source_id:
        raise ValidationError("Выберите другой рейс.")
    ids = {target_id} | ({source_id} if source_id else set())
    batches = {batch.pk: batch for batch in SupplierOrderBatch.objects.trips().select_for_update().filter(
        pk__in=ids,
    ).order_by("pk")}
    if set(batches) != ids:
        raise ValidationError("Рейс не найден.")
    try:
        order = CustomerProcurementOrder.objects.select_for_update().get(pk=order_id)
    except CustomerProcurementOrder.DoesNotExist as exc:
        raise ValidationError("Заказ не найден.") from exc
    if order.status != order.Status.CREATED:
        raise ValidationError("Перемещать можно только заказ в статусе «Создан».")
    if order.trip_id != source_id:
        raise ValidationError("Заказ уже перемещён другим запросом. Обновите страницу.")
    target = batches[target_id]
    source = batches.get(source_id)
    additional = order.price_list.is_trip_addition
    if additional and source is None:
        raise ValidationError('Дополнительный заказ должен принадлежать исходному рейсу.')
    main_price_id = source.price_list_id if additional else order.price_list_id
    for batch, revision in ((target, target_revision), (source, source_revision)):
        if batch is None:
            continue
        if batch.revision != _quantity(revision, "Версия рейса"):
            raise ValidationError("Рейс уже изменён другим запросом. Обновите страницу.")
        if batch.price_list_id is not None and batch.price_list_id != main_price_id:
            raise ValidationError("Заказ и рейс должны быть из одной версии прайса.")
        _require_editable_trip(batch)

    items = list(order.items.select_for_update().select_related(
        "price_list_item__cd", "price_list_item__tech", "selected_supplier", "cd", "tech",
    ).order_by("pk"))
    if not source and not any(item.quantity for item in items):
        raise ValidationError("В заказе нет товаров.")
    bound_price = target.price_list_id is None and not additional
    if bound_price:
        target.price_list_id = order.price_list_id
        target.save(update_fields=('price_list',))
    transfers = []
    if source:
        allocations = list(SupplierTripAllocation.objects.select_for_update().select_related(
            "line__price_list_item__cd", "line__price_list_item__tech",
        ).filter(line__batch=source, order_item__order=order).order_by("line_id", "pk"))
        source_lines = {}
        for allocation in allocations:
            old_line = source_lines.setdefault(allocation.line_id, allocation.line)
            new_line = _line_for(target, old_line.price_list_item, old_line.supplier_id,
                                 old_line.price_supplier_id, old_line.supplier_price_aed_snapshot,
                                 price_updated_at=old_line.supplier_price_updated_at)
            new_line.quantity += allocation.quantity
            if new_line.quantity > 2147483647:
                raise ValidationError("Слишком большое количество в рейсе назначения.")
            new_line.save(update_fields=("quantity",))
            old_line.quantity -= allocation.quantity
            transfers.append({"item_id": allocation.order_item_id, "source_line_id": old_line.pk,
                              "target_line_id": new_line.pk, "quantity": allocation.quantity,
                              "supplier_id": old_line.supplier_id,
                              "price_supplier_id": old_line.price_supplier_id,
                              "price_aed": str(old_line.supplier_price_aed_snapshot)})
            allocation.line = new_line
            allocation.save(update_fields=("line",))
        for line in source_lines.values():
            if line.allocations.exists():
                line.save(update_fields=("quantity",))
            else:
                line.delete()
        source.source_orders.remove(order)
    else:
        if any(item.product.is_archived for item in items):
            raise ValidationError("Архивный товар нельзя включить в рейс.")
        for item in items:
            supplier_id = item.selected_supplier_id
            if item.selected_supplier.letter == "M" and item.quantity:
                f = Supplier.objects.filter(letter="F").first()
                if f is None or not ProcurementSupplierOffer.objects.filter(
                    price_list_item=item.price_list_item, supplier_id=supplier_id,
                    price_aed=item.supplier_price_aed_snapshot,
                ).exists():
                    raise ValidationError("Для товаров M требуются поставщик F и сохранённая цена M.")
                if (item.product_kind, item.product_id, f.pk) not in _batch_exclusions(target):
                    supplier_id = f.pk
            line = _line_for(target, item.price_list_item, supplier_id,
                             item.selected_supplier_id, item.supplier_price_aed_snapshot)
            line.quantity += item.quantity
            if line.quantity > 2147483647:
                raise ValidationError("Слишком большое количество в рейсе назначения.")
            line.save(update_fields=("quantity",))
            SupplierTripAllocation.objects.create(
                line=line, order_item=item, prepayment_quantity=item.prepayment_quantity,
                postpayment_quantity=item.postpayment_quantity, prepayment_cap=item.prepayment_quantity,
            )
    order.trip = target
    order.save(update_fields=("trip", "updated_at"))
    target.source_orders.add(order)
    details = {"action": "move_order" if source else "add_order", "order_id": order.pk,
               "source_batch_id": source_id, "target_batch_id": target_id, "lines": transfers}
    if bound_price:
        details['bound_price_list_id'] = target.price_list_id
    _assert_balances(target)
    if source:
        _assert_balances(source)
        _record_trip_change(source, actor, f"Заказ №{order.pk} перенесён в рейс №{target.pk}", details)
    _record_trip_change(target, actor, f"Заказ №{order.pk} " + (
        f"перенесён из рейса №{source.pk}" if source else "добавлен в рейс"), details)
    return target


@transaction.atomic
def add_orders_to_trip(*, actor, batch_id, order_ids, revision):
    """Добавить выбранные свободные заказы одной атомарной операцией."""
    _require_manage(actor)
    try:
        ids = sorted({int(pk) for pk in order_ids})
    except (TypeError, ValueError) as exc:
        raise ValidationError('Выберите существующие заказы.') from exc
    if not ids:
        raise ValidationError('Выберите хотя бы один заказ.')
    try:
        batch = SupplierOrderBatch.objects.trips().select_for_update().get(pk=batch_id)
    except SupplierOrderBatch.DoesNotExist as exc:
        raise ValidationError('Рейс не найден.') from exc
    if batch.revision != _quantity(revision, 'Версия рейса'):
        raise ValidationError('Рейс уже изменён другим запросом. Обновите страницу.')
    for pk in ids:
        batch = assign_order_to_trip(actor=actor, order_id=pk, target_batch_id=batch.pk,
            target_revision=batch.revision)
    return batch


@transaction.atomic
def delete_empty_trip(*, actor, batch_id, revision, archive_batch_id):
    """Удалить пустой рейс, сохранив его историю в рейсе назначения."""
    _require_manage(actor)
    batches = {batch.pk: batch for batch in SupplierOrderBatch.objects.select_for_update().filter(
        pk__in=(batch_id, archive_batch_id), price_list__isnull=False,
    ).order_by("pk")}
    if batch_id == archive_batch_id or len(batches) != 2:
        raise ValidationError("Выберите другой существующий рейс для сохранения истории.")
    batch, archive = batches[batch_id], batches[archive_batch_id]
    if batch.revision != _quantity(revision, "Версия рейса"):
        raise ValidationError("Рейс уже изменён другим запросом. Обновите страницу.")
    if batch.price_list_id != archive.price_list_id:
        raise ValidationError("Рейсы должны быть из одной версии прайса.")
    if (batch.trip_orders.exists() or batch.source_orders.exists()
            or batch.lines.filter(quantity__gt=0).exists()
            or SupplierTripAllocation.objects.filter(line__batch=batch).exists()):
        raise ValidationError("Удалить можно только пустой рейс: сначала перенесите все заказы.")
    details = {"action": "delete_empty_trip", "deleted_batch_id": batch.pk,
               "name": batch.name, "created_at": batch.created_at.isoformat(),
               "created_by_id": batch.created_by_id, "creation_key": str(batch.creation_key or ""),
               "revision": batch.revision,
               "history": [{"actor_id": change.actor_id, "created_at": change.created_at.isoformat(),
                            "revision": change.revision, "description": change.description,
                            "details": change.details} for change in batch.changes.all()]}
    _record_trip_change(archive, actor, f"Удалён пустой рейс №{batch.pk}; история сохранена", details)
    batch.changes.all().delete()
    batch.lines.all().delete()
    batch.delete()
    return archive


def _record_customer_changes(actor, changes, batch):
    for order_id, entries in changes.items():
        order = CustomerProcurementOrder.objects.get(pk=order_id)
        adjustment = OrderAdjustment.objects.create(
            order=order, actor=actor, comment=f"Корректировка распределения в рейсе №{batch.pk}.", refund_amount=0,
        )
        for item, field, before, after in entries:
            OrderAdjustmentChange.objects.create(
                adjustment=adjustment, product_kind=item.product_kind, product_id_snapshot=item.product_id,
                product_name_snapshot=item.product_name_snapshot, field_name=field, old_value=before, new_value=after,
            )
        _save_totals(order, list(order.items.all()))


def trip_supplier_chains(lines, *, excluded=None):
    """Предложения, фактические получатели и допустимый получатель M по чужой цене."""
    lines = list(lines)
    if excluded is None:
        excluded = exclusion_keys((line.product_kind, line.product_id) for line in lines)
    fallback_ids = list(Supplier.objects.filter(letter='M').values_list('pk', flat=True))
    chains = {}
    for line in lines:
        suppliers = chains.setdefault(line.price_list_item_id, set())
        suppliers.add(line.supplier_id)
        suppliers.update(offer.supplier_id for offer in line.price_list_item.supplier_offers.all()
                         if (line.product_kind, line.product_id, offer.supplier_id) not in excluded)
        # M принимает запрос и без собственной цены, например по сохранённой цене A.
        suppliers.update(supplier_id for supplier_id in fallback_ids
                         if (line.product_kind, line.product_id, supplier_id) not in excluded)
    return chains


def supplier_priority_state(supplier_id, priorities):
    """При равном максимуме не выбирает последнего по букве, имени или ID."""
    maximum = max(priorities.values())
    at_maximum = [key for key, priority in priorities.items() if priority == maximum]
    return {
        "is_last_supplier": at_maximum == [supplier_id],
        "priority_ambiguous": supplier_id in at_maximum and len(at_maximum) > 1,
    }


def _automatic_reduction(allocations, quantity):
    """Сохраняет доли других поставщиков; нуль и одного получателя распределяет без выбора."""
    active = [row for row in allocations if row.quantity > 0]
    if quantity and len(active) != 1:
        return None
    return [{
        "allocation_id": row.pk,
        "final_quantity": row.order_item.quantity - row.quantity + (quantity if row.quantity else 0),
    } for row in allocations]


@transaction.atomic
def change_trip_line(*, actor, batch_id, line_id, revision, quantity, action,
                     target_supplier_id=None, price_supplier_id=None, distribution=None,
                     _allow_priority_transfer=False, _exclusions=None):
    _require_manage(actor)
    try:
        batch = SupplierOrderBatch.objects.trips().select_for_update().get(pk=batch_id)
        expected_revision = _quantity(revision, "Версия рейса")
        line = SupplierOrderBatchLine.objects.select_for_update().select_related("price_list_item__cd", "price_list_item__tech").get(pk=line_id, batch=batch)
    except (SupplierOrderBatch.DoesNotExist, SupplierOrderBatchLine.DoesNotExist, ValueError, TypeError) as exc:
        raise ValidationError("Рейс или строка не найдены.") from exc
    if _exclusions is not None:
        batch._current_supplier_exclusions = _exclusions
    if batch.revision != expected_revision:
        raise ValidationError("Рейс уже изменён другим запросом. Обновите страницу.")
    orders = list(CustomerProcurementOrder.objects.select_for_update().filter(trip=batch).order_by("pk"))
    if not orders:
        raise ValidationError("В рейсе нет заказов.")
    _assert_balances(batch)
    new_quantity = _quantity(quantity, "Количество поставщика")
    if new_quantity > 2147483647:
        raise ValidationError("Слишком большое количество.")
    old_quantity = line.quantity
    if new_quantity > old_quantity:
        _check_supplier_admission(batch, line.price_list_item, line.supplier_id, line.price_supplier_id)
    if new_quantity == old_quantity:
        raise ValidationError("Количество не изменилось.")
    allocations = list(line.allocations.select_for_update().select_related("order_item__order").order_by("order_item__order_id", "pk"))
    for allocation in allocations:
        if allocation.quantity:
            require_untransferred_order(allocation.order_item.order)
            if allocation.order_item.order.status != CustomerProcurementOrder.Status.CREATED:
                raise ValidationError("Строка рейса зафиксирована: один из связанных заказов уже подтверждён.")
    detail = {"line_id": line.pk, "before": old_quantity, "after": new_quantity, "action": action}
    if action == "transfer":
        if new_quantity >= old_quantity:
            raise ValidationError("Перенос доступен только при уменьшении количества.")
        if not _allow_priority_transfer:
            chain_lines = list(batch.lines.filter(price_list_item_id=line.price_list_item_id).select_related(
                "price_list_item",
            ).prefetch_related("price_list_item__supplier_offers"))
            chain = trip_supplier_chains(chain_lines, excluded=_batch_exclusions(batch))[line.price_list_item_id]
            priorities = dict(Supplier.objects.select_for_update().filter(pk__in=chain).values_list("pk", "priority"))
            if supplier_priority_state(line.supplier_id, priorities)["is_last_supplier"]:
                raise ValidationError("Это последний поставщик товара по приоритету. Уменьшите количество в связанных заказах без переноса.")
        try:
            supplier = Supplier.objects.get(pk=target_supplier_id)
            offer = ProcurementSupplierOffer.objects.get(price_list_item=line.price_list_item, supplier_id=price_supplier_id)
        except (Supplier.DoesNotExist, ProcurementSupplierOffer.DoesNotExist, ValueError, TypeError) as exc:
            raise ValidationError("Выберите поставщика и цену из сохранённого прайса.") from exc
        if supplier.pk == line.supplier_id:
            raise ValidationError("Для переноса выберите другого поставщика.")
        target = _line_for(batch, line.price_list_item, supplier.pk, offer.supplier_id, offer.price_aed)
        left = old_quantity - new_quantity
        # При переносе клиентские количества и цены не меняются; переносятся их доли.
        for allocation in reversed(allocations):
            moved_post = min(left, allocation.postpayment_quantity)
            left -= moved_post
            moved_pre = min(left, allocation.prepayment_quantity)
            left -= moved_pre
            if not moved_pre and not moved_post:
                continue
            destination, _ = SupplierTripAllocation.objects.get_or_create(line=target, order_item=allocation.order_item)
            destination.prepayment_quantity += moved_pre
            destination.postpayment_quantity += moved_post
            destination.prepayment_cap = max(destination.prepayment_cap, destination.prepayment_quantity)
            destination.save()
            allocation.prepayment_quantity -= moved_pre
            allocation.postpayment_quantity -= moved_post
            allocation.save(update_fields=("prepayment_quantity", "postpayment_quantity"))
        if left:
            raise ValidationError("Недостаточно распределённых клиентских позиций для переноса.")
        target.quantity += old_quantity - new_quantity
        target.save(update_fields=("quantity",))
        detail.update(target_line_id=target.pk, target_supplier_id=supplier.pk,
                      price_supplier_id=offer.supplier_id, price_aed=str(offer.price_aed))
        description = f"Перенесено {old_quantity - new_quantity} шт. поставщику {supplier.letter} по цене {offer.supplier.letter}"
    elif action == "adjust":
        if distribution is None and new_quantity < old_quantity:
            distribution = _automatic_reduction(allocations, new_quantity)
        if not isinstance(distribution, list):
            raise ValidationError("Укажите итоговое количество каждого заказчика.")
        wanted = {}
        for row in distribution:
            try:
                allocation_id = int(row["allocation_id"])
                amount = _quantity(row["final_quantity"], "Итог заказчика")
            except (KeyError, TypeError, ValueError) as exc:
                raise ValidationError("Некорректное распределение заказчиков.") from exc
            if allocation_id in wanted or amount > 2147483647:
                raise ValidationError("Некорректное распределение заказчиков.")
            wanted[allocation_id] = amount
        if set(wanted) != {row.pk for row in allocations}:
            raise ValidationError("Передайте всех заказчиков этой строки без повторов.")
        final_line_total = 0
        changes = {}
        customer_details = []
        for allocation in allocations:
            item = allocation.order_item
            elsewhere = item.prepayment_quantity + item.postpayment_quantity - allocation.quantity
            allocated = wanted[allocation.pk] - elsewhere
            if allocated < 0:
                raise ValidationError("Итог заказчика не может быть меньше количества у других поставщиков.")
            if allocated != allocation.quantity:
                require_untransferred_order(item.order)
                if item.order.status != CustomerProcurementOrder.Status.CREATED:
                    raise ValidationError("Изменять количество можно только в созданном заказе.")
            if new_quantity < old_quantity and allocated > allocation.quantity:
                raise ValidationError("При уменьшении нельзя увеличить долю другого заказчика.")
            if new_quantity > old_quantity and allocated < allocation.quantity:
                raise ValidationError("При увеличении нельзя уменьшить долю заказчика.")
            final_line_total += allocated
            cap = allocation.prepayment_quantity if allocated <= allocation.quantity else max(allocation.prepayment_cap, allocation.prepayment_quantity)
            new_pre = allocated if item.order.is_stock_order else min(allocated, cap)
            new_post = allocated - new_pre
            for field, after in (("prepayment_quantity", new_pre), ("postpayment_quantity", new_post)):
                before = getattr(allocation, field)
                item_before = getattr(item, field)
                setattr(item, field, item_before + after - before)
                if before != after:
                    changes.setdefault(item.order_id, []).append((item, field, item_before, getattr(item, field)))
                setattr(allocation, field, after)
            item.full_clean()
            item.save(update_fields=("prepayment_quantity", "postpayment_quantity"))
            allocation.save(update_fields=("prepayment_quantity", "postpayment_quantity"))
            customer_details.append({"order_id": item.order_id, "item_id": item.pk, "final_quantity": wanted[allocation.pk]})
        if final_line_total != new_quantity:
            raise ValidationError("Сумма долей заказчиков должна совпадать с новым количеством поставщика.")
        _record_customer_changes(actor, changes, batch)
        detail["customers"] = customer_details
        description = f"Количество изменено с {old_quantity} до {new_quantity}; скорректированы клиентские заказы"
    else:
        raise ValidationError("Выберите перенос или корректировку клиентских заказов.")
    line.quantity = new_quantity
    line.save(update_fields=("quantity",))
    _assert_balances(batch)
    batch.revision += 1
    batch.save(update_fields=("revision",))
    SupplierTripChange.objects.create(batch=batch, actor=actor, revision=batch.revision, description=description, details=detail)
    return batch


def is_m_order_in_f(line):
    return (line.supplier.letter == "F" and line.price_supplier_id
            and line.price_supplier.letter == "M" and line.quantity > 0)


@transaction.atomic
def apply_m_to_f_rule(*, actor, batch_id):
    """Однократно применить правило к созданному рейсу; повтор без строк M ничего не меняет."""
    _require_manage(actor)
    try:
        batch = SupplierOrderBatch.objects.trips().select_for_update().get(pk=batch_id)
    except SupplierOrderBatch.DoesNotExist as exc:
        raise ValidationError("Рейс не найден.") from exc
    suppliers = {supplier.letter: supplier for supplier in Supplier.objects.filter(letter__in=("M", "F"))}
    if "M" not in suppliers:
        return {"lines": 0, "units": 0}
    lines = list(batch.lines.filter(supplier=suppliers["M"], quantity__gt=0).order_by("pk"))
    if not lines:
        return {"lines": 0, "units": 0}
    if "F" not in suppliers:
        raise ValidationError("Для товаров M требуется поставщик с буквой F в справочнике.")
    excluded = _batch_exclusions(batch)
    lines = [line for line in lines if (line.product_kind, line.product_id, suppliers['F'].pk) not in excluded]
    if not lines:
        return {'lines': 0, 'units': 0}
    result = {"lines": len(lines), "units": sum(line.quantity for line in lines)}
    for line in lines:
        batch = change_trip_line(
            actor=actor, batch_id=batch.pk, line_id=line.pk, revision=batch.revision,
            quantity=0, action="transfer", target_supplier_id=suppliers["F"].pk,
            price_supplier_id=suppliers["M"].pk,
            _allow_priority_transfer=True,
            _exclusions=excluded,
        )
    SupplierTripChange.objects.create(
        batch=batch, actor=actor, revision=batch.revision,
        description=f"Правило M → F: перенесено {result['lines']} поз., {result['units']} шт. по ценам M",
        details={"action": "default_m_to_f", **result},
    )
    return result


@transaction.atomic
def return_line_to_m(*, actor, batch_id, line_id, revision):
    """Вернуть всю положительную строку F с ценой M, сохранив распределение заказчиков."""
    _require_manage(actor)
    try:
        line = SupplierOrderBatchLine.objects.select_related("supplier", "price_supplier").get(pk=line_id, batch_id=batch_id)
    except SupplierOrderBatchLine.DoesNotExist as exc:
        raise ValidationError("Строка рейса не найдена.") from exc
    if not is_m_order_in_f(line):
        raise ValidationError("Вернуть в M можно только товар F по сохранённой цене M с положительным количеством.")
    return change_trip_line(
        actor=actor, batch_id=batch_id, line_id=line_id, revision=revision,
        quantity=0, action="transfer", target_supplier_id=line.price_supplier_id,
        price_supplier_id=line.price_supplier_id,
        _allow_priority_transfer=True,
    )
