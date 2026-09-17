"""Транзакционные операции приёмки поставок."""
import logging
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_HALF_UP, localcontext

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from catalog.audit import field_change, record_product_changes, stock_change
from catalog.models import CD, ProductChangeEvent, Tech
from partners.models import Supplier
from consignment.models import CDConsignmentStock, TechConsignmentStock
from warehouse.models import (
    CDWarehouseStock, CDWarehouseTransferItem, TechWarehouseStock, TechWarehouseTransferItem,
    Warehouse, WarehouseTransfer,
)
from warehouse.storage_services import clear_storage_locations_if_zero
from .models import (
    Supply, SupplyCDItem, SupplyCostCalculation, SupplyExpense, SupplyFinalization,
    SupplyRevision, SupplyRevisionExpense, SupplyRevisionItem, SupplyTechItem,
)

logger = logging.getLogger("gamebat.business")
CENT = Decimal("0.01")
UNIT = Decimal("0.000001")


@dataclass(frozen=True)
class SupplyLineInput:
    product_type: str
    product_id: int
    supplier_id: int
    quantity: int
    purchase_unit_cost: Decimal


@dataclass(frozen=True)
class SupplyExpenseInput:
    name: str
    amount: Decimal


@dataclass(frozen=True)
class SupplyCancellationResult:
    supply: Supply
    cancelled: bool
    costs: dict


@dataclass(frozen=True)
class SupplyRevisionResult:
    supply: Supply
    revision: SupplyRevision
    costs: dict


def _decimal(value, label):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError(f"Поле «{label}» содержит некорректное число.") from exc


def _normalise_lines(raw_lines):
    lines = []
    for raw in raw_lines:
        try:
            product_id = int(raw["product_id"])
            supplier_id = int(raw["supplier_id"])
            quantity = int(raw["quantity"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValidationError("Заполните все поля товарной позиции.") from exc
        product_type = str(raw.get("product_type", "")).lower()
        if product_type not in {"cd", "tech"}:
            raise ValidationError("Выберите существующий товар из списка.")
        if quantity <= 0:
            raise ValidationError("Количество должно быть больше нуля.")
        cost = _decimal(raw.get("purchase_unit_cost"), "Себестоимость")
        if cost < 0:
            raise ValidationError("Себестоимость не может быть отрицательной.")
        lines.append(SupplyLineInput(product_type, product_id, supplier_id, quantity, cost))
    if not lines:
        raise ValidationError("Добавьте хотя бы один товар.")
    return lines


def _normalise_expenses(raw_expenses):
    expenses = []
    for raw in raw_expenses:
        name = str(raw.get("name", "")).strip()
        amount_raw = raw.get("amount", "")
        if not name and amount_raw in ("", None):
            continue
        if not name:
            raise ValidationError("Укажите название дополнительного расхода.")
        amount = _decimal(amount_raw, "Стоимость расхода")
        if amount < 0:
            raise ValidationError("Дополнительный расход не может быть отрицательным.")
        expenses.append(SupplyExpenseInput(name, amount.quantize(CENT, rounding=ROUND_HALF_UP)))
    return expenses


def _normalise_weight_transport_cost(value):
    if value in (None, ""):
        raise ValidationError("Введите транспортные расходы по весу, даже если они равны нулю.")
    amount = _decimal(value, "Транспортные расходы по весу")
    if amount < 0:
        raise ValidationError("Транспортные расходы по весу не могут быть отрицательными.")
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def allocate_weight_transport_cost(*, lines, products, total_transport_cost):
    """Распределяет целые копейки по весу строк методом наибольших остатков."""
    line_weights = [
        products[(line.product_type, line.product_id)].weight_grams * line.quantity
        for line in lines
    ]
    total_weight = sum(line_weights)
    if total_weight <= 0:
        raise ValidationError("Общий вес поставки должен быть больше нуля.")
    total_cents = int((total_transport_cost * 100).to_integral_value())
    exact_cents = [
        Decimal(total_cents) * Decimal(line_weight) / Decimal(total_weight)
        for line_weight in line_weights
    ]
    allocated_cents = [
        int(value.to_integral_value(rounding=ROUND_DOWN)) for value in exact_cents
    ]
    residual = total_cents - sum(allocated_cents)
    order = sorted(
        range(len(lines)),
        key=lambda index: (exact_cents[index] - Decimal(allocated_cents[index]), -index),
        reverse=True,
    )
    for index in order[:residual]:
        allocated_cents[index] += 1
    allocations = [Decimal(cents) / Decimal(100) for cents in allocated_cents]
    if sum(allocations, Decimal("0")) != total_transport_cost:
        raise ValidationError("Не удалось точно распределить транспортные расходы.")
    return total_weight, line_weights, allocations


def global_owned_quantity(product_type, product_id):
    """Считает все единицы GameBAT без двойного учёта склада, реализации и transit."""
    if product_type == "cd":
        stock_model, consignment_model, transfer_item_model, product_field = (
            CDWarehouseStock, CDConsignmentStock, CDWarehouseTransferItem, "cd"
        )
    else:
        stock_model, consignment_model, transfer_item_model, product_field = (
            TechWarehouseStock, TechConsignmentStock, TechWarehouseTransferItem, "tech"
        )
    warehouse_total = stock_model.objects.filter(**{f"{product_field}_id": product_id}).aggregate(
        total=Sum("quantity")
    )["total"] or 0
    consignment_total = consignment_model.objects.filter(**{f"{product_field}_id": product_id}).aggregate(
        total=Sum("quantity")
    )["total"] or 0
    transit_total = transfer_item_model.objects.filter(
        **{
            f"{product_field}_id": product_id,
            "transfer__status__in": (
                WarehouseTransfer.Status.CREATED,
                WarehouseTransfer.Status.ASSEMBLED,
                WarehouseTransfer.Status.SHIPPED,
            ),
        }
    ).aggregate(total=Sum("quantity"))["total"] or 0
    return warehouse_total + consignment_total + transit_total


# Совместимое внутреннее имя для существующего moving-average replay.
_old_owned_quantity = global_owned_quantity


def accept_supply(*, accepted_by, warehouse_id, lines, expenses=(), weight_transport_cost=0):
    """Принимает поставку целиком и пересчитывает среднюю стоимость товаров.

    Расходы делятся на физические единицы, а вес старого товара включает и
    склад, и реализацию. Все изменяемые товары блокируются до конца транзакции.
    """
    prepared_lines = _normalise_lines(lines)
    prepared_expenses = _normalise_expenses(expenses)
    weight_transport_cost = _normalise_weight_transport_cost(weight_transport_cost)
    total_units = sum(line.quantity for line in prepared_lines)
    expenses_total = sum((expense.amount for expense in prepared_expenses), Decimal("0"))

    try:
        with transaction.atomic():
            try:
                warehouse = Warehouse.objects.select_for_update().get(pk=warehouse_id)
            except (Warehouse.DoesNotExist, TypeError, ValueError) as exc:
                raise ValidationError("Выберите склад поступления.") from exc
            cd_ids = {line.product_id for line in prepared_lines if line.product_type == "cd"}
            tech_ids = {line.product_id for line in prepared_lines if line.product_type == "tech"}
            supplier_ids = {line.supplier_id for line in prepared_lines}
            products = {
                **{("cd", p.pk): p for p in CD.objects.active().select_for_update().filter(pk__in=cd_ids).order_by("pk")},
                **{("tech", p.pk): p for p in Tech.objects.active().select_for_update().filter(pk__in=tech_ids).order_by("pk")},
            }
            suppliers = Supplier.objects.in_bulk(supplier_ids)
            if len(products) != len(cd_ids) + len(tech_ids):
                raise ValidationError("Выберите существующий товар из списка.")
            if len(suppliers) != len(supplier_ids):
                raise ValidationError("Выберите существующего поставщика.")

            missing_weight = [
                product.name for product in products.values()
                if not product.weight_grams or product.weight_grams <= 0
            ]
            if missing_weight:
                raise ValidationError(
                    "Нельзя принять товар без веса. Заполните вес: " + "; ".join(missing_weight)
                )

            with localcontext() as context:
                context.prec = 28
                total_weight, line_weights, transport_allocations = allocate_weight_transport_cost(
                    lines=prepared_lines,
                    products=products,
                    total_transport_cost=weight_transport_cost,
                )
                expense_per_unit = expenses_total / Decimal(total_units)
                goods_total = sum(
                    (line.purchase_unit_cost * line.quantity for line in prepared_lines), Decimal("0")
                )
                supply = Supply.objects.create(
                    accepted_by=accepted_by,
                    warehouse=warehouse,
                    total_units=total_units,
                    goods_total_before_expenses=goods_total.quantize(CENT, rounding=ROUND_HALF_UP),
                    expenses_total=expenses_total.quantize(CENT, rounding=ROUND_HALF_UP),
                    weight_transport_cost=weight_transport_cost,
                    total_weight_grams=total_weight,
                    grand_total=(goods_total + expenses_total + weight_transport_cost).quantize(
                        CENT, rounding=ROUND_HALF_UP
                    ),
                )
                SupplyExpense.objects.bulk_create(
                    [SupplyExpense(supply=supply, name=e.name, amount=e.amount) for e in prepared_expenses]
                )

                inventory_additions = defaultdict(lambda: {"quantity": 0, "value": Decimal("0")})
                cd_items, tech_items = [], []
                for index, line in enumerate(prepared_lines):
                    product = products[(line.product_type, line.product_id)]
                    supplier = suppliers[line.supplier_id]
                    line_transport_cost = transport_allocations[index]
                    transport_per_unit = line_transport_cost / Decimal(line.quantity)
                    effective_cost = line.purchase_unit_cost + expense_per_unit + transport_per_unit
                    incoming_line_value = (
                        line.purchase_unit_cost * line.quantity
                        + expense_per_unit * line.quantity
                        + line_transport_cost
                    )
                    common = dict(
                        supply=supply,
                        product=product,
                        supplier=supplier,
                        quantity=line.quantity,
                        purchase_unit_cost=line.purchase_unit_cost.quantize(UNIT, rounding=ROUND_HALF_UP),
                        allocated_expense_per_unit=expense_per_unit.quantize(UNIT, rounding=ROUND_HALF_UP),
                        weight_grams_snapshot=product.weight_grams,
                        line_weight_grams=line_weights[index],
                        allocated_transport_cost=line_transport_cost,
                        transport_cost_per_unit=transport_per_unit.quantize(UNIT, rounding=ROUND_HALF_UP),
                        effective_unit_cost=effective_cost.quantize(UNIT, rounding=ROUND_HALF_UP),
                        base_line_total=(line.purchase_unit_cost * line.quantity).quantize(CENT, rounding=ROUND_HALF_UP),
                        final_line_total=incoming_line_value.quantize(CENT, rounding=ROUND_HALF_UP),
                        product_name_snapshot=product.name,
                        product_sku_snapshot=product.sku,
                        supplier_letter_snapshot=supplier.letter,
                        supplier_color_snapshot=supplier.highlight_color,
                        supplier_name_snapshot=supplier.name,
                    )
                    (cd_items if line.product_type == "cd" else tech_items).append(
                        SupplyCDItem(**common) if line.product_type == "cd" else SupplyTechItem(**common)
                    )
                    bucket = inventory_additions[(line.product_type, line.product_id)]
                    bucket["quantity"] += line.quantity
                    bucket["value"] += incoming_line_value

                SupplyCDItem.objects.bulk_create(cd_items)
                SupplyTechItem.objects.bulk_create(tech_items)

                cost_calculations = []
                for key, addition in inventory_additions.items():
                    product = products[key]
                    old_owned_quantity = _old_owned_quantity(*key)
                    new_quantity = addition["quantity"]
                    old_cost = product.cost
                    old_inventory_value = Decimal(old_owned_quantity) * old_cost
                    resulting_quantity = old_owned_quantity + new_quantity
                    resulting_value = old_inventory_value + addition["value"]
                    new_average = resulting_value / Decimal(resulting_quantity)
                    product.cost = new_average.quantize(CENT, rounding=ROUND_HALF_UP)
                    # Старые импортированные карточки могут иметь пустые обязательные
                    # идентификаторы. Приход меняет только себестоимость и не должен
                    # блокироваться из-за, например, незаполненного штрихкода.
                    product.full_clean(exclude=[
                        field.name for field in product._meta.fields if field.name != "cost"
                    ])
                    product.save(update_fields=("cost",))
                    product_type, product_id = key
                    cost_calculations.append(SupplyCostCalculation(
                        supply=supply,
                        product_kind=product_type,
                        product_name_snapshot=product.name,
                        product_sku_snapshot=product.sku,
                        old_owned_quantity=old_owned_quantity,
                        old_unit_cost=old_cost,
                        old_inventory_value=old_inventory_value.quantize(UNIT, rounding=ROUND_HALF_UP),
                        incoming_quantity=new_quantity,
                        incoming_value=addition["value"].quantize(UNIT, rounding=ROUND_HALF_UP),
                        resulting_quantity=resulting_quantity,
                        resulting_value=resulting_value.quantize(UNIT, rounding=ROUND_HALF_UP),
                        resulting_unit_cost=product.cost,
                        **{product_type: product},
                    ))
                    stock_model = CDWarehouseStock if product_type == "cd" else TechWarehouseStock
                    product_field = "cd" if product_type == "cd" else "tech"
                    stock = stock_model.objects.select_for_update().filter(
                        warehouse=warehouse, **{f"{product_field}_id": product_id}
                    ).first()
                    if stock is None:
                        stock = stock_model(warehouse=warehouse, **{f"{product_field}_id": product_id})
                    old_stock_quantity = stock.quantity
                    stock.quantity += new_quantity
                    stock.full_clean()
                    stock.save()
                    changes = [stock_change(
                        warehouse=warehouse,
                        old_quantity=old_stock_quantity,
                        new_quantity=stock.quantity,
                    )]
                    if old_cost != product.cost:
                        changes.append(field_change(
                            field_name="cost",
                            field_label="Средняя себестоимость",
                            old_value=f"{old_cost:.2f}",
                            new_value=f"{product.cost:.2f}",
                        ))
                    record_product_changes(
                        actor=accepted_by,
                        instance=product,
                        source=ProductChangeEvent.Source.CRM,
                        action_kind=ProductChangeEvent.ActionKind.SUPPLY,
                        action_object_id=supply.pk,
                        action_label=f"Поставка №{supply.pk}",
                        changes=changes,
                    )
                SupplyCostCalculation.objects.bulk_create(cost_calculations)

            logger.info(
                "Поставка принята: user_id=%s supply_id=%s units=%s",
                accepted_by.pk, supply.pk, total_units,
            )
            return supply
    except Exception:
        logger.exception("Ошибка приёмки поставки: user_id=%s", getattr(accepted_by, "pk", None))
        raise


def _supply_configuration(product_type):
    if product_type == "cd":
        return CD, CDWarehouseStock, SupplyCDItem, "cd"
    if product_type == "tech":
        return Tech, TechWarehouseStock, SupplyTechItem, "tech"
    raise ValidationError("Неизвестный тип товара в поставке.")


def _revision_item_values(item, product_type):
    values = {
        "product_kind": product_type,
        "supplier_id": item.supplier_id,
        "quantity": item.quantity,
        "purchase_unit_cost": item.purchase_unit_cost,
        "allocated_expense_per_unit": item.allocated_expense_per_unit,
        "weight_grams_snapshot": item.weight_grams_snapshot,
        "line_weight_grams": item.line_weight_grams,
        "allocated_transport_cost": item.allocated_transport_cost,
        "transport_cost_per_unit": item.transport_cost_per_unit,
        "effective_unit_cost": item.effective_unit_cost,
        "base_line_total": item.base_line_total,
        "final_line_total": item.final_line_total,
        "product_name_snapshot": item.product_name_snapshot,
        "product_sku_snapshot": item.product_sku_snapshot,
        "supplier_letter_snapshot": item.supplier_letter_snapshot,
        "supplier_color_snapshot": item.supplier_color_snapshot,
        "supplier_name_snapshot": item.supplier_name_snapshot,
    }
    values[product_type] = item.product
    return values


def _snapshot_supply_revision(*, supply, actor, reason, diff_summary):
    accepted_by_name = supply.accepted_by.full_name or supply.accepted_by.username
    revision = SupplyRevision.objects.create(
        supply=supply,
        revision_number=supply.revision_number,
        created_by=actor,
        reason=reason,
        warehouse=supply.warehouse,
        accepted_at_snapshot=supply.accepted_at,
        accepted_by_name_snapshot=accepted_by_name,
        total_units=supply.total_units,
        goods_total_before_expenses=supply.goods_total_before_expenses,
        expenses_total=supply.expenses_total,
        weight_transport_cost=supply.weight_transport_cost,
        total_weight_grams=supply.total_weight_grams,
        grand_total=supply.grand_total,
        diff_summary=diff_summary,
    )
    revision_items = []
    for product_type, item_model in (("cd", SupplyCDItem), ("tech", SupplyTechItem)):
        for item in item_model.objects.select_for_update().select_related("product").filter(supply=supply):
            revision_items.append(SupplyRevisionItem(
                revision=revision, **_revision_item_values(item, product_type)
            ))
    SupplyRevisionItem.objects.bulk_create(revision_items)
    SupplyRevisionExpense.objects.bulk_create([
        SupplyRevisionExpense(revision=revision, name=expense.name, amount=expense.amount)
        for expense in SupplyExpense.objects.select_for_update().filter(supply=supply)
    ])
    return revision


def _supersede_supply_finalizations(*, supply, new_revision_number):
    """Сохраняет историю, но не переносит старую финализацию на новый состав прихода."""
    finalizations = SupplyFinalization.objects.select_for_update().filter(
        supply=supply, status=SupplyFinalization.Status.APPLIED,
    )
    return finalizations.update(
        status=SupplyFinalization.Status.SUPERSEDED,
        superseded_at=timezone.now(),
        superseded_by_revision_number=new_revision_number,
    )


def _external_owned_quantity_delta(*, product_type, product_id, after, through):
    """Returns audited non-supply changes to owned quantity in (after, through]."""
    product_filter = {f"{product_type}_id": product_id}
    events = ProductChangeEvent.objects.filter(
        created_at__gt=after, created_at__lte=through, **product_filter,
    ).exclude(
        action_kind__in=(
            ProductChangeEvent.ActionKind.SUPPLY,
            ProductChangeEvent.ActionKind.WAREHOUSE_TRANSFER,
            ProductChangeEvent.ActionKind.CONSIGNMENT,
        )
    ).prefetch_related("field_changes").order_by("created_at", "id")
    delta = 0
    for event in events:
        changes = list(event.field_changes.all())
        consignment_quantity = next(
            (change for change in changes if change.field_name == "quantity_on_consignment"), None
        )
        candidates = [consignment_quantity] if consignment_quantity is not None else [
            change for change in changes if change.field_name.startswith("warehouse_stock_")
        ]
        for change in candidates:
            try:
                delta += int(change.new_value) - int(change.old_value)
            except (TypeError, ValueError) as exc:
                raise ValidationError(
                    "История количества товара повреждена: невозможно выполнить точный пересчёт себестоимости."
                ) from exc
    return delta


def _calculation_values(*, supply, product_type, product, old_quantity, old_cost, incoming):
    incoming_quantity = incoming["quantity"]
    incoming_value = incoming["value"]
    old_value = Decimal(old_quantity) * old_cost
    resulting_quantity = old_quantity + incoming_quantity
    if resulting_quantity <= 0:
        raise ValidationError("Историческое количество товара при пересчёте стало неположительным.")
    resulting_value = old_value + incoming_value
    resulting_cost = (resulting_value / Decimal(resulting_quantity)).quantize(
        CENT, rounding=ROUND_HALF_UP
    )
    return {
        "supply": supply,
        "product_kind": product_type,
        "product_name_snapshot": product.name,
        "product_sku_snapshot": product.sku,
        "old_owned_quantity": old_quantity,
        "old_unit_cost": old_cost,
        "old_inventory_value": old_value.quantize(UNIT, rounding=ROUND_HALF_UP),
        "incoming_quantity": incoming_quantity,
        "incoming_value": incoming_value.quantize(UNIT, rounding=ROUND_HALF_UP),
        "resulting_quantity": resulting_quantity,
        "resulting_value": resulting_value.quantize(UNIT, rounding=ROUND_HALF_UP),
        "resulting_unit_cost": resulting_cost,
        product_type: product,
    }, resulting_cost, resulting_quantity


def _replay_product_valuation(*, supply, product_type, product, incoming, old_target_calculation):
    """Replays one product from the edited supply's original historical position."""
    product_filter = {f"{product_type}_id": product.pk}
    _, _, item_model, _ = _supply_configuration(product_type)
    later_calculations = list(
        SupplyCostCalculation.objects.select_for_update().select_related("supply")
        .filter(product_kind=product_type, supply__accepted_at__gt=supply.accepted_at, **product_filter)
        .order_by("supply__accepted_at", "supply_id", "id")
    )
    later_supply_ids = set(item_model.objects.filter(
        product_id=product.pk, supply__accepted_at__gt=supply.accepted_at,
    ).values_list("supply_id", flat=True))
    calculation_supply_ids = {row.supply_id for row in later_calculations}
    if later_supply_ids - calculation_supply_ids:
        raise ValidationError(
            "История себестоимости товара неполна: один из последующих приходов не имеет расчётного снимка."
        )
    if old_target_calculation is not None:
        replay_quantity = old_target_calculation.old_owned_quantity
        replay_cost = old_target_calculation.old_unit_cost.quantize(CENT, rounding=ROUND_HALF_UP)
    elif later_calculations:
        first = later_calculations[0]
        replay_quantity = first.old_owned_quantity - _external_owned_quantity_delta(
            product_type=product_type, product_id=product.pk,
            after=supply.accepted_at, through=first.supply.accepted_at,
        )
        replay_cost = first.old_unit_cost.quantize(CENT, rounding=ROUND_HALF_UP)
    else:
        now = timezone.now()
        replay_quantity = _old_owned_quantity(product_type, product.pk) - _external_owned_quantity_delta(
            product_type=product_type, product_id=product.pk,
            after=supply.accepted_at, through=now,
        )
        if incoming is not None:
            replay_quantity -= incoming["quantity"]
        replay_cost = product.cost.quantize(CENT, rounding=ROUND_HALF_UP)
    if replay_quantity < 0:
        raise ValidationError(
            "Невозможно восстановить количество товара перед приходом по имеющейся истории."
        )

    SupplyCostCalculation.objects.filter(supply=supply, **product_filter).delete()
    if incoming is not None:
        values, replay_cost, replay_quantity = _calculation_values(
            supply=supply, product_type=product_type, product=product,
            old_quantity=replay_quantity, old_cost=replay_cost, incoming=incoming,
        )
        SupplyCostCalculation.objects.create(**values)

    previous_time = supply.accepted_at
    for calculation in later_calculations:
        replay_quantity += _external_owned_quantity_delta(
            product_type=product_type, product_id=product.pk,
            after=previous_time, through=calculation.supply.accepted_at,
        )
        if replay_quantity < 0:
            raise ValidationError(
                "Историческое количество товара стало отрицательным при пересчёте себестоимости."
            )
        if not calculation.supply.is_cancelled:
            later_incoming = {
                "quantity": calculation.incoming_quantity,
                "value": calculation.incoming_value,
            }
            values, replay_cost, replay_quantity = _calculation_values(
                supply=calculation.supply, product_type=product_type, product=product,
                old_quantity=replay_quantity, old_cost=replay_cost, incoming=later_incoming,
            )
            for field_name, value in values.items():
                if field_name not in {"supply", "product_kind", "cd", "tech"}:
                    setattr(calculation, field_name, value)
            calculation.save(update_fields=(
                "product_name_snapshot", "product_sku_snapshot", "old_owned_quantity",
                "old_unit_cost", "old_inventory_value", "incoming_quantity", "incoming_value",
                "resulting_quantity", "resulting_value", "resulting_unit_cost",
            ))
        previous_time = calculation.supply.accepted_at

    expected_current_quantity = replay_quantity + _external_owned_quantity_delta(
        product_type=product_type, product_id=product.pk,
        after=previous_time, through=timezone.now(),
    )
    actual_current_quantity = _old_owned_quantity(product_type, product.pk)
    if expected_current_quantity != actual_current_quantity:
        raise ValidationError(
            "История движения товара неполна: точный пересчёт себестоимости отклонён "
            f"(ожидалось {expected_current_quantity}, фактически {actual_current_quantity})."
        )
    old_cost = product.cost
    product.cost = replay_cost
    product.full_clean(exclude=[field.name for field in product._meta.fields if field.name != "cost"])
    product.save(update_fields=("cost",))
    return old_cost, replay_cost


@transaction.atomic
def revise_supply(
    *, actor, supply_id, expected_revision_number, warehouse_id, lines, expenses,
    weight_transport_cost, reason,
):
    reason = str(reason or "").strip()
    if not reason:
        raise ValidationError("Укажите причину изменения принятого прихода.")
    prepared_lines = _normalise_lines(lines)
    prepared_expenses = _normalise_expenses(expenses)
    weight_transport_cost = _normalise_weight_transport_cost(weight_transport_cost)
    try:
        expected_revision_number = int(expected_revision_number)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Обновите страницу прихода перед сохранением изменений.") from exc

    supply = Supply.objects.select_for_update().select_related(
        "warehouse", "accepted_by"
    ).get(pk=supply_id)
    if supply.status != Supply.Status.ACCEPTED or supply.is_cancelled:
        raise ValidationError("Редактировать можно только действующий принятый приход.")
    if supply.revision_number != expected_revision_number:
        raise ValidationError("Приход был изменён другим пользователем. Обновите страницу.")
    try:
        new_warehouse = Warehouse.objects.select_for_update().get(pk=warehouse_id)
    except (Warehouse.DoesNotExist, TypeError, ValueError) as exc:
        raise ValidationError("Выберите склад поступления.") from exc
    Warehouse.objects.select_for_update().filter(pk=supply.warehouse_id).get()

    logger.info(
        "Начато редактирование принятого прихода: user_id=%s supply_id=%s old_warehouse_id=%s new_warehouse_id=%s",
        actor.pk, supply.pk, supply.warehouse_id, new_warehouse.pk,
    )
    old_items = []
    old_quantities = defaultdict(int)
    for product_type, item_model in (("cd", SupplyCDItem), ("tech", SupplyTechItem)):
        items = list(
            item_model.objects.select_for_update().select_related("product", "supplier")
            .filter(supply=supply).order_by("product_id", "id")
        )
        old_items.extend((product_type, item) for item in items)
        for item in items:
            old_quantities[(product_type, item.product_id)] += item.quantity

    cd_ids = {line.product_id for line in prepared_lines if line.product_type == "cd"}
    tech_ids = {line.product_id for line in prepared_lines if line.product_type == "tech"}
    affected_cd_ids = cd_ids | {product_id for kind, product_id in old_quantities if kind == "cd"}
    affected_tech_ids = tech_ids | {product_id for kind, product_id in old_quantities if kind == "tech"}
    products = {
        **{("cd", p.pk): p for p in CD.objects.active().select_for_update().filter(pk__in=affected_cd_ids).order_by("pk")},
        **{("tech", p.pk): p for p in Tech.objects.active().select_for_update().filter(pk__in=affected_tech_ids).order_by("pk")},
    }
    if len(products) != len(affected_cd_ids) + len(affected_tech_ids):
        raise ValidationError("Один из товаров прихода больше не существует.")
    supplier_ids = {line.supplier_id for line in prepared_lines}
    suppliers = Supplier.objects.in_bulk(supplier_ids)
    if len(suppliers) != len(supplier_ids):
        raise ValidationError("Выберите существующего поставщика.")
    missing_weight = [
        products[(line.product_type, line.product_id)].name for line in prepared_lines
        if not products[(line.product_type, line.product_id)].weight_grams
    ]
    if missing_weight:
        raise ValidationError(
            "Нельзя сохранить товар без веса. Заполните вес: " + "; ".join(sorted(set(missing_weight)))
        )

    total_units = sum(line.quantity for line in prepared_lines)
    expenses_total = sum((expense.amount for expense in prepared_expenses), Decimal("0"))
    with localcontext() as context:
        context.prec = 28
        total_weight, line_weights, transport_allocations = allocate_weight_transport_cost(
            lines=prepared_lines, products=products, total_transport_cost=weight_transport_cost,
        )
        expense_per_unit = expenses_total / Decimal(total_units)
        goods_total = sum(
            (line.purchase_unit_cost * line.quantity for line in prepared_lines), Decimal("0")
        )
        incoming_additions = defaultdict(lambda: {"quantity": 0, "value": Decimal("0")})
        new_cd_items, new_tech_items = [], []
        new_quantities = defaultdict(int)
        for index, line in enumerate(prepared_lines):
            key = (line.product_type, line.product_id)
            product = products[key]
            supplier = suppliers[line.supplier_id]
            line_transport_cost = transport_allocations[index]
            transport_per_unit = line_transport_cost / Decimal(line.quantity)
            effective_cost = line.purchase_unit_cost + expense_per_unit + transport_per_unit
            incoming_line_value = (
                line.purchase_unit_cost * line.quantity
                + expense_per_unit * line.quantity
                + line_transport_cost
            )
            common = dict(
                supply=supply, product=product, supplier=supplier, quantity=line.quantity,
                purchase_unit_cost=line.purchase_unit_cost.quantize(UNIT, rounding=ROUND_HALF_UP),
                allocated_expense_per_unit=expense_per_unit.quantize(UNIT, rounding=ROUND_HALF_UP),
                weight_grams_snapshot=product.weight_grams,
                line_weight_grams=line_weights[index],
                allocated_transport_cost=line_transport_cost,
                transport_cost_per_unit=transport_per_unit.quantize(UNIT, rounding=ROUND_HALF_UP),
                effective_unit_cost=effective_cost.quantize(UNIT, rounding=ROUND_HALF_UP),
                base_line_total=(line.purchase_unit_cost * line.quantity).quantize(CENT, rounding=ROUND_HALF_UP),
                final_line_total=incoming_line_value.quantize(CENT, rounding=ROUND_HALF_UP),
                product_name_snapshot=product.name, product_sku_snapshot=product.sku,
                supplier_letter_snapshot=supplier.letter,
                supplier_color_snapshot=supplier.highlight_color,
                supplier_name_snapshot=supplier.name,
            )
            if line.product_type == "cd":
                new_cd_items.append(SupplyCDItem(**common))
            else:
                new_tech_items.append(SupplyTechItem(**common))
            new_quantities[key] += line.quantity
            incoming_additions[key]["quantity"] += line.quantity
            incoming_additions[key]["value"] += incoming_line_value

    affected_keys = set(old_quantities) | set(new_quantities)
    old_line_data = {
        (kind, item.product_id, item.supplier_id): (item.quantity, item.purchase_unit_cost)
        for kind, item in old_items
    }
    new_line_data = {
        (line.product_type, line.product_id, line.supplier_id): (line.quantity, line.purchase_unit_cost)
        for line in prepared_lines
    }
    diff_summary = {
        "old_warehouse": supply.warehouse.name,
        "new_warehouse": new_warehouse.name,
        "added_positions": len(set(new_line_data) - set(old_line_data)),
        "removed_positions": len(set(old_line_data) - set(new_line_data)),
        "changed_quantities": sum(
            1 for key in set(old_line_data) & set(new_line_data)
            if old_line_data[key][0] != new_line_data[key][0]
        ),
        "changed_prices": sum(
            1 for key in set(old_line_data) & set(new_line_data)
            if old_line_data[key][1] != new_line_data[key][1]
        ),
        "old_transport": str(supply.weight_transport_cost),
        "new_transport": str(weight_transport_cost),
        "old_expenses": str(supply.expenses_total),
        "new_expenses": str(expenses_total.quantize(CENT, rounding=ROUND_HALF_UP)),
    }

    old_calculations = {
        (row.product_kind, row.cd_id if row.product_kind == "cd" else row.tech_id): row
        for row in SupplyCostCalculation.objects.select_for_update().filter(supply=supply)
    }

    stocks = {}
    warehouse_ids = {supply.warehouse_id, new_warehouse.pk}
    for product_type in ("cd", "tech"):
        _, stock_model, _, product_field = _supply_configuration(product_type)
        ids = sorted(product_id for kind, product_id in affected_keys if kind == product_type)
        stocks.update({
            (warehouse_id, product_type, getattr(stock, f"{product_field}_id")): stock
            for stock in stock_model.objects.select_for_update().filter(
                warehouse_id__in=warehouse_ids, **{f"{product_field}_id__in": ids}
            ).order_by("warehouse_id", product_field)
            for warehouse_id in [stock.warehouse_id]
        })

    insufficient = []
    if supply.warehouse_id == new_warehouse.pk:
        for key in affected_keys:
            delta = new_quantities.get(key, 0) - old_quantities.get(key, 0)
            stock = stocks.get((supply.warehouse_id, *key))
            if delta < 0 and (stock is None or stock.quantity < -delta):
                insufficient.append(
                    f"{products[key].name}: требуется {-delta}, доступно {stock.quantity if stock else 0}"
                )
    else:
        for key, quantity in old_quantities.items():
            stock = stocks.get((supply.warehouse_id, *key))
            if stock is None or stock.quantity < quantity:
                insufficient.append(
                    f"{products[key].name}: требуется {quantity}, доступно {stock.quantity if stock else 0}"
                )
    if insufficient:
        logger.warning(
            "Редактирование прихода отклонено: недостаточно товара: user_id=%s supply_id=%s positions=%s",
            actor.pk, supply.pk, len(insufficient),
        )
        raise ValidationError(
            "На исходном складе недостаточно товара для изменения прихода. " + "; ".join(insufficient)
        )

    revision = _snapshot_supply_revision(
        supply=supply, actor=actor, reason=reason, diff_summary=diff_summary,
    )
    stock_changes = defaultdict(list)

    def change_stock(warehouse, key, delta):
        if not delta:
            return
        product_type, product_id = key
        _, stock_model, _, product_field = _supply_configuration(product_type)
        stock_key = (warehouse.pk, product_type, product_id)
        stock = stocks.get(stock_key)
        if stock is None:
            stock = stock_model(warehouse=warehouse, **{product_field: products[key]})
            stocks[stock_key] = stock
        old_quantity = stock.quantity
        stock.quantity += delta
        stock.full_clean()
        stock.save()
        stock_changes[key].append(stock_change(
            warehouse=warehouse, old_quantity=old_quantity, new_quantity=stock.quantity,
        ))
        clear_storage_locations_if_zero(
            stock=stock, actor=actor,
            action_kind=ProductChangeEvent.ActionKind.SUPPLY,
            action_object_id=supply.pk,
            action_label=f"Редактирование поставки №{supply.pk}",
        )

    if supply.warehouse_id == new_warehouse.pk:
        for key in affected_keys:
            change_stock(new_warehouse, key, new_quantities.get(key, 0) - old_quantities.get(key, 0))
    else:
        for key, quantity in old_quantities.items():
            change_stock(supply.warehouse, key, -quantity)
        for key, quantity in new_quantities.items():
            change_stock(new_warehouse, key, quantity)

    SupplyCDItem.objects.filter(supply=supply).delete()
    SupplyTechItem.objects.filter(supply=supply).delete()
    SupplyExpense.objects.filter(supply=supply).delete()
    SupplyCDItem.objects.bulk_create(new_cd_items)
    SupplyTechItem.objects.bulk_create(new_tech_items)
    SupplyExpense.objects.bulk_create([
        SupplyExpense(supply=supply, name=expense.name, amount=expense.amount)
        for expense in prepared_expenses
    ])

    supply.warehouse = new_warehouse
    supply.total_units = total_units
    supply.goods_total_before_expenses = goods_total.quantize(CENT, rounding=ROUND_HALF_UP)
    supply.expenses_total = expenses_total.quantize(CENT, rounding=ROUND_HALF_UP)
    supply.weight_transport_cost = weight_transport_cost
    supply.total_weight_grams = total_weight
    supply.grand_total = (goods_total + expenses_total + weight_transport_cost).quantize(
        CENT, rounding=ROUND_HALF_UP
    )
    supply.revision_number += 1
    supply.last_revised_at = timezone.now()
    supply.last_revised_by = actor
    supply.full_clean()
    supply.save(update_fields=(
        "warehouse", "total_units", "goods_total_before_expenses", "expenses_total",
        "weight_transport_cost", "total_weight_grams", "grand_total", "revision_number",
        "last_revised_at", "last_revised_by",
    ))
    superseded_finalizations = _supersede_supply_finalizations(
        supply=supply, new_revision_number=supply.revision_number,
    )

    recalculated_costs = {}
    for key in sorted(affected_keys):
        product = products[key]
        try:
            old_cost, new_cost = _replay_product_valuation(
                supply=supply, product_type=key[0], product=product,
                incoming=incoming_additions.get(key),
                old_target_calculation=old_calculations.get(key),
            )
        except Exception:
            logger.exception(
                "Ошибка пересчёта исторической себестоимости: "
                "user_id=%s supply_id=%s product_type=%s product_id=%s",
                actor.pk, supply.pk, key[0], key[1],
            )
            raise
        recalculated_costs[key] = new_cost
        changes = list(stock_changes[key])
        if old_cost != new_cost:
            changes.append(field_change(
                field_name="cost", field_label="Средняя себестоимость",
                old_value=f"{old_cost:.2f}", new_value=f"{new_cost:.2f}",
            ))
        if not changes:
            changes.append(field_change(
                field_name="supply_revision", field_label="Редакция прихода",
                old_value=supply.revision_number - 1, new_value=supply.revision_number,
            ))
        record_product_changes(
            actor=actor, instance=product, source=ProductChangeEvent.Source.CRM,
            action_kind=ProductChangeEvent.ActionKind.SUPPLY,
            action_object_id=supply.pk,
            action_label=f"Редактирование поставки №{supply.pk}", changes=changes,
        )
    logger.info(
        "Принятый приход отредактирован: user_id=%s supply_id=%s old_warehouse_id=%s new_warehouse_id=%s changed_products=%s revision=%s",
        actor.pk, supply.pk, revision.warehouse_id, supply.warehouse_id,
        len(affected_keys), supply.revision_number,
    )
    if superseded_finalizations:
        logger.info(
            "Финализации прихода помечены утратившими актуальность: supply_id=%s count=%s revision=%s",
            supply.pk, superseded_finalizations, supply.revision_number,
        )
    return SupplyRevisionResult(supply=supply, revision=revision, costs=recalculated_costs)


def _recalculated_cost(*, product_type, product_id, excluded_supply_id):
    """Повторяет сохранённую moving-average историю, исключая отменённые поставки."""
    product_filter = {f"{product_type}_id": product_id}
    calculations = list(
        SupplyCostCalculation.objects.select_for_update().select_related("supply")
        .filter(product_kind=product_type, **product_filter)
        .order_by("supply__accepted_at", "supply_id", "id")
    )
    target = next((row for row in calculations if row.supply_id == excluded_supply_id), None)
    if target is None:
        raise ValidationError(
            "Невозможно отменить приход: для товара отсутствует исторический расчёт себестоимости."
        )
    first = calculations[0]
    _, _, item_model, _ = _supply_configuration(product_type)
    historical_supply_ids = set(
        item_model.objects.filter(
            product_id=product_id,
            supply__accepted_at__gte=first.supply.accepted_at,
        ).values_list("supply_id", flat=True)
    )
    calculation_supply_ids = {row.supply_id for row in calculations}
    if historical_supply_ids - calculation_supply_ids:
        raise ValidationError(
            "Невозможно отменить приход: история себестоимости товара неполна."
        )
    replay_quantity = first.old_owned_quantity
    replay_cost = first.old_unit_cost.quantize(CENT, rounding=ROUND_HALF_UP)
    original_quantity = first.old_owned_quantity
    previous_time = None

    for calculation in calculations:
        if previous_time is not None:
            cancellation_adjustment = sum(
                row.incoming_quantity
                for row in calculations
                if row.supply.cancelled_at
                and previous_time < row.supply.cancelled_at <= calculation.supply.accepted_at
            )
            replay_quantity += calculation.old_owned_quantity - original_quantity + cancellation_adjustment
            if replay_quantity < 0:
                raise ValidationError(
                    "Невозможно точно пересчитать себестоимость: без отменяемого прихода "
                    "исторический остаток стал бы отрицательным."
                )
        skip = calculation.supply.is_cancelled or calculation.supply_id == excluded_supply_id
        if not skip:
            replay_value = Decimal(replay_quantity) * replay_cost + calculation.incoming_value
            replay_quantity += calculation.incoming_quantity
            replay_cost = (
                replay_value / Decimal(replay_quantity)
            ).quantize(CENT, rounding=ROUND_HALF_UP)
        original_quantity = calculation.resulting_quantity
        previous_time = calculation.supply.accepted_at
    return replay_cost


@transaction.atomic
def cancel_supply(*, actor, supply_id, comment):
    """Полностью откатывает принятый приход, его stock и moving-average cost."""
    comment = str(comment or "").strip()
    if not comment:
        raise ValidationError("Укажите причину отмены прихода.")
    supply = Supply.objects.select_for_update().select_related("warehouse").get(pk=supply_id)
    if supply.is_cancelled:
        return SupplyCancellationResult(supply=supply, cancelled=False, costs={})
    if supply.status != Supply.Status.ACCEPTED:
        raise ValidationError("Отменить можно только принятый приход.")
    Warehouse.objects.select_for_update().get(pk=supply.warehouse_id)

    aggregated = defaultdict(int)
    for product_type in ("cd", "tech"):
        _, _, item_model, product_field = _supply_configuration(product_type)
        items = list(
            item_model.objects.select_for_update().select_related("product")
            .filter(supply=supply).order_by("product_id", "id")
        )
        for item in items:
            aggregated[(product_type, item.product_id)] += item.quantity
    if not aggregated:
        raise ValidationError("В приходе нет товарных позиций для отмены.")

    products = {}
    stocks = {}
    for product_type in ("cd", "tech"):
        product_model, stock_model, _, product_field = _supply_configuration(product_type)
        ids = sorted(product_id for kind, product_id in aggregated if kind == product_type)
        products.update({
            (product_type, product.pk): product
            for product in product_model.objects.active().select_for_update().filter(pk__in=ids).order_by("pk")
        })
        stocks.update({
            (product_type, getattr(stock, f"{product_field}_id")): stock
            for stock in stock_model.objects.select_for_update().filter(
                warehouse_id=supply.warehouse_id, **{f"{product_field}_id__in": ids}
            ).order_by(product_field)
        })
    if len(products) != len(aggregated):
        raise ValidationError("Один из товаров прихода больше не существует.")

    insufficient = []
    for key, quantity in aggregated.items():
        stock = stocks.get(key)
        if stock is None or stock.quantity < quantity:
            product = products[key]
            insufficient.append(
                f"{product.name}: требуется {quantity}, доступно {stock.quantity if stock else 0}"
            )
    if insufficient:
        logger.warning(
            "Отмена прихода отклонена: недостаточно товара: user_id=%s supply_id=%s positions=%s",
            actor.pk, supply.pk, len(insufficient),
        )
        raise ValidationError(
            "Невозможно отменить приход: на складе недостаточно товара для обратного списания. "
            + "; ".join(insufficient)
        )

    recalculated_costs = {}
    for key, product in products.items():
        product_type, product_id = key
        recalculated_costs[key] = _recalculated_cost(
            product_type=product_type,
            product_id=product_id,
            excluded_supply_id=supply.pk,
        )

    for key, quantity in aggregated.items():
        product = products[key]
        stock = stocks[key]
        old_quantity = stock.quantity
        old_cost = product.cost
        stock.quantity -= quantity
        product.cost = recalculated_costs[key]
        stock.full_clean()
        product.full_clean(exclude=[
            field.name for field in product._meta.fields if field.name != "cost"
        ])
        stock.save(update_fields=("quantity",))
        product.save(update_fields=("cost",))
        changes = [stock_change(
            warehouse=supply.warehouse,
            old_quantity=old_quantity,
            new_quantity=stock.quantity,
        )]
        if old_cost != product.cost:
            changes.append(field_change(
                field_name="cost",
                field_label="Средняя себестоимость",
                old_value=f"{old_cost:.2f}",
                new_value=f"{product.cost:.2f}",
            ))
        record_product_changes(
            actor=actor,
            instance=product,
            source=ProductChangeEvent.Source.CRM,
            action_kind=ProductChangeEvent.ActionKind.SUPPLY,
            action_object_id=supply.pk,
            action_label=f"Отмена поставки №{supply.pk}",
            changes=changes,
        )
        clear_storage_locations_if_zero(
            stock=stock,
            actor=actor,
            action_kind=ProductChangeEvent.ActionKind.SUPPLY,
            action_object_id=supply.pk,
            action_label=f"Отмена поставки №{supply.pk}",
        )
        logger.info(
            "Себестоимость после отмены прихода: supply_id=%s type=%s product_id=%s old=%s new=%s",
            supply.pk, key[0], key[1], old_cost, product.cost,
        )

    supply.status = Supply.Status.CANCELLED
    supply.cancelled_at = timezone.now()
    supply.cancelled_by = actor
    supply.cancellation_comment = comment
    supply.full_clean()
    supply.save(update_fields=("status", "cancelled_at", "cancelled_by", "cancellation_comment"))
    logger.info(
        "Приход отменён: user_id=%s supply_id=%s warehouse_id=%s positions=%s units=%s",
        actor.pk, supply.pk, supply.warehouse_id, len(aggregated), sum(aggregated.values()),
    )
    return SupplyCancellationResult(supply=supply, cancelled=True, costs=recalculated_costs)
