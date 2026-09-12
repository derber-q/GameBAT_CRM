"""Транзакционные операции приёмки поставок."""
import logging
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext

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
from .models import Supply, SupplyCDItem, SupplyCostCalculation, SupplyExpense, SupplyTechItem

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


def _old_owned_quantity(product_type, product_id):
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


def accept_supply(*, accepted_by, warehouse_id, lines, expenses=()):
    """Принимает поставку целиком и пересчитывает среднюю стоимость товаров.

    Расходы делятся на физические единицы, а вес старого товара включает и
    склад, и реализацию. Все изменяемые товары блокируются до конца транзакции.
    """
    prepared_lines = _normalise_lines(lines)
    prepared_expenses = _normalise_expenses(expenses)
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
                **{("cd", p.pk): p for p in CD.objects.select_for_update().filter(pk__in=cd_ids).order_by("pk")},
                **{("tech", p.pk): p for p in Tech.objects.select_for_update().filter(pk__in=tech_ids).order_by("pk")},
            }
            suppliers = Supplier.objects.in_bulk(supplier_ids)
            if len(products) != len(cd_ids) + len(tech_ids):
                raise ValidationError("Выберите существующий товар из списка.")
            if len(suppliers) != len(supplier_ids):
                raise ValidationError("Выберите существующего поставщика.")

            with localcontext() as context:
                context.prec = 28
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
                    grand_total=(goods_total + expenses_total).quantize(CENT, rounding=ROUND_HALF_UP),
                )
                SupplyExpense.objects.bulk_create(
                    [SupplyExpense(supply=supply, name=e.name, amount=e.amount) for e in prepared_expenses]
                )

                inventory_additions = defaultdict(lambda: {"quantity": 0, "value": Decimal("0")})
                cd_items, tech_items = [], []
                for line in prepared_lines:
                    product = products[(line.product_type, line.product_id)]
                    supplier = suppliers[line.supplier_id]
                    effective_cost = line.purchase_unit_cost + expense_per_unit
                    common = dict(
                        supply=supply,
                        product=product,
                        supplier=supplier,
                        quantity=line.quantity,
                        purchase_unit_cost=line.purchase_unit_cost.quantize(UNIT, rounding=ROUND_HALF_UP),
                        allocated_expense_per_unit=expense_per_unit.quantize(UNIT, rounding=ROUND_HALF_UP),
                        effective_unit_cost=effective_cost.quantize(UNIT, rounding=ROUND_HALF_UP),
                        base_line_total=(line.purchase_unit_cost * line.quantity).quantize(CENT, rounding=ROUND_HALF_UP),
                        final_line_total=(effective_cost * line.quantity).quantize(CENT, rounding=ROUND_HALF_UP),
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
                    bucket["value"] += effective_cost * line.quantity

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
            for product in product_model.objects.select_for_update().filter(pk__in=ids).order_by("pk")
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
