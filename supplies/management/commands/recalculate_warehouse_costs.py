"""Одноразовый безопасный пересчёт истории приходов по физическому складу."""
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalog.audit import field_change, record_product_changes
from catalog.models import CD, ProductChangeEvent, ProductFieldChange, Tech
from consignment.models import (
    CDConsignmentStock,
    ConsignmentMovementItem,
    TechConsignmentStock,
)
from warehouse.models import WarehouseTransfer
from warehouse.valuation import warehouse_owned_quantity, weighted_warehouse_cost

from supplies.models import Supply, SupplyCostCalculation, SupplyFinalization


CENT = Decimal("0.01")
UNIT = Decimal("0.000001")


def _product_filter(kind, product_id):
    return {f"event__{kind}_id": product_id}


def _warehouse_quantity_before(kind, product_id, moment):
    """Восстанавливает складское количество непосредственно перед операцией."""
    current = warehouse_owned_quantity(kind, product_id)
    delta_after = 0
    changes = ProductFieldChange.objects.filter(
        event__created_at__gt=moment,
        field_name__startswith="warehouse_stock_",
        **_product_filter(kind, product_id),
    ).values_list("old_value", "new_value")
    for old_value, new_value in changes:
        try:
            delta_after += int(new_value) - int(old_value)
        except (TypeError, ValueError) as exc:
            raise CommandError(
                f"Повреждена история складского количества: {kind} #{product_id}."
            ) from exc
    quantity = current - delta_after
    if quantity < 0:
        raise CommandError(
            f"Не удалось восстановить складской остаток: {kind} #{product_id}, значение {quantity}."
        )
    return quantity


def _movement_stock_id(item):
    prefix = f"consignment_stock_{item.product_kind}_"
    change = ProductFieldChange.objects.filter(
        event__action_kind=ProductChangeEvent.ActionKind.CONSIGNMENT,
        event__action_object_id=item.movement_id,
        field_name__startswith=prefix,
        **_product_filter(item.product_kind, getattr(item, f"{item.product_kind}_id")),
    ).order_by("id").first()
    if change is None:
        return None, None
    try:
        return int(change.field_name.removeprefix(prefix)), int(change.old_value)
    except (TypeError, ValueError):
        return None, None


class Command(BaseCommand):
    help = (
        "Пересчитывает текущую себестоимость и снимки приходов только по физическому "
        "складскому остатку. Без --apply выполняет проверочный прогон с откатом."
    )

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Сохранить рассчитанные значения.")

    @transaction.atomic
    def handle(self, *args, **options):
        apply_changes = options["apply"]
        if Supply.objects.filter(cancelled_at__isnull=False).exists():
            raise CommandError("Есть отменённые приходы; автоматический исторический пересчёт остановлен.")
        if Supply.objects.exclude(revision_number=1).exists():
            raise CommandError("Есть редакции приходов; автоматический исторический пересчёт остановлен.")
        if SupplyFinalization.objects.exists():
            raise CommandError("Есть финализации приходов; автоматический исторический пересчёт остановлен.")
        if WarehouseTransfer.objects.exists():
            raise CommandError("Есть межскладские перемещения; автоматический исторический пересчёт остановлен.")

        changed_products = 0
        changed_calculations = 0
        changed_lots = 0
        examples = []

        for kind, product_model, stock_model in (
            ("cd", CD, CDConsignmentStock),
            ("tech", Tech, TechConsignmentStock),
        ):
            product_field = kind
            product_ids = set(
                SupplyCostCalculation.objects.filter(product_kind=kind).values_list(
                    f"{kind}_id", flat=True
                )
            ) | set(stock_model.objects.values_list(f"{kind}_id", flat=True))

            for product in product_model.objects.select_for_update().filter(pk__in=product_ids).order_by("pk"):
                calculations = list(
                    SupplyCostCalculation.objects.select_for_update().select_related("supply")
                    .filter(product_kind=kind, **{product_field: product})
                    .order_by("supply__accepted_at", "supply_id", "id")
                )
                base_cost = (
                    calculations[0].old_unit_cost.quantize(CENT, rounding=ROUND_HALF_UP)
                    if calculations else product.cost.quantize(CENT, rounding=ROUND_HALF_UP)
                )
                current_cost = base_cost

                lot_costs = {}
                lot_quantities = {}
                lots = list(
                    stock_model.objects.select_for_update().filter(**{product_field: product}).order_by("id")
                )
                for lot in lots:
                    lot_costs[lot.pk] = base_cost
                    lot_quantities[lot.pk] = 0 if lot.lot_key == "" else lot.quantity

                events = [
                    (calculation.supply.accepted_at, 0, "supply", calculation)
                    for calculation in calculations
                ]
                movement_items = list(
                    ConsignmentMovementItem.objects.select_for_update().select_related("movement")
                    .filter(product_kind=kind, **{product_field: product})
                    .order_by("movement__created_at", "id")
                )
                events.extend(
                    (item.movement.created_at, 1, item.movement.operation_type, item)
                    for item in movement_items
                )

                for moment, _, event_type, event in sorted(events, key=lambda row: (row[0], row[1], row[3].pk)):
                    if event_type == "supply":
                        old_quantity = _warehouse_quantity_before(kind, product.pk, moment)
                        old_value = Decimal(old_quantity) * current_cost
                        resulting_quantity = old_quantity + event.incoming_quantity
                        resulting_value = old_value + event.incoming_value
                        resulting_cost = (resulting_value / Decimal(resulting_quantity)).quantize(
                            CENT, rounding=ROUND_HALF_UP
                        )
                        before = (
                            event.old_owned_quantity,
                            event.old_unit_cost,
                            event.resulting_quantity,
                            event.resulting_unit_cost,
                        )
                        event.old_owned_quantity = old_quantity
                        event.old_unit_cost = current_cost
                        event.old_inventory_value = old_value.quantize(UNIT, rounding=ROUND_HALF_UP)
                        event.resulting_quantity = resulting_quantity
                        event.resulting_value = resulting_value.quantize(UNIT, rounding=ROUND_HALF_UP)
                        event.resulting_unit_cost = resulting_cost
                        after = (
                            event.old_owned_quantity,
                            event.old_unit_cost,
                            event.resulting_quantity,
                            event.resulting_unit_cost,
                        )
                        if before != after:
                            changed_calculations += 1
                            if len(examples) < 12:
                                examples.append(
                                    f"приход №{event.supply_id}: {product.name}: "
                                    f"остаток {before[0]} -> {old_quantity}, cost {before[3]} -> {resulting_cost}"
                                )
                        event.save(update_fields=(
                            "old_owned_quantity", "old_unit_cost", "old_inventory_value",
                            "resulting_quantity", "resulting_value", "resulting_unit_cost",
                        ))
                        current_cost = resulting_cost
                        continue

                    item = event
                    stock_id, old_lot_quantity = _movement_stock_id(item)
                    if event_type == "transfer":
                        if stock_id is None:
                            matching_lot = next((
                                lot for lot in lots
                                if lot.lot_key == ""
                                and lot.platform_id == item.movement.platform_id
                                and lot.warehouse_id == item.movement.warehouse_id
                            ), None)
                            if matching_lot is not None:
                                stock_id = matching_lot.pk
                                old_lot_quantity = item.consignment_quantity_before
                        item.unit_cost_snapshot = current_cost
                        if stock_id is not None:
                            previous_quantity = old_lot_quantity or 0
                            previous_cost = lot_costs.get(stock_id, base_cost)
                            lot_costs[stock_id] = (
                                current_cost if previous_quantity == 0 else weighted_warehouse_cost(
                                    old_quantity=previous_quantity,
                                    old_unit_cost=previous_cost,
                                    incoming_quantity=item.quantity,
                                    incoming_unit_cost=current_cost,
                                )
                            )
                            lot_quantities[stock_id] = previous_quantity + item.quantity
                    else:
                        returned_cost = lot_costs.get(stock_id, base_cost)
                        item.unit_cost_snapshot = returned_cost
                        old_quantity = _warehouse_quantity_before(kind, product.pk, moment)
                        current_cost = weighted_warehouse_cost(
                            old_quantity=old_quantity,
                            old_unit_cost=current_cost,
                            incoming_quantity=item.quantity,
                            incoming_unit_cost=returned_cost,
                        )
                        if stock_id is not None:
                            lot_quantities[stock_id] = max(
                                0, lot_quantities.get(stock_id, old_lot_quantity or 0) - item.quantity
                            )
                    item.save(update_fields=("unit_cost_snapshot",))

                for lot in lots:
                    corrected = lot_costs.get(lot.pk, base_cost)
                    if lot.unit_cost != corrected:
                        lot.unit_cost = corrected
                        lot.save(update_fields=("unit_cost",))
                        changed_lots += 1

                old_product_cost = product.cost
                if old_product_cost != current_cost:
                    product.cost = current_cost
                    product.full_clean(exclude=[
                        field.name for field in product._meta.fields if field.name != "cost"
                    ])
                    product.save(update_fields=("cost",))
                    changed_products += 1
                    if apply_changes:
                        record_product_changes(
                            actor=None,
                            instance=product,
                            source=ProductChangeEvent.Source.CRM,
                            changes=[field_change(
                                field_name="cost",
                                field_label="Пересчёт себестоимости только по физическим складам",
                                old_value=f"{old_product_cost:.2f}",
                                new_value=f"{current_cost:.2f}",
                            )],
                        )

        for example in examples:
            self.stdout.write(example)
        self.stdout.write(
            f"Товаров с новой cost: {changed_products}; расчётов приходов: "
            f"{changed_calculations}; партий реализации: {changed_lots}."
        )
        if not apply_changes:
            transaction.set_rollback(True)
            self.stdout.write(self.style.WARNING("Проверочный прогон завершён; изменения отменены."))
        else:
            self.stdout.write(self.style.SUCCESS("Складские себестоимости пересчитаны и сохранены."))
