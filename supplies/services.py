"""Транзакционные операции приёмки поставок."""
import logging
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext

from django.core.exceptions import ValidationError
from django.db import transaction

from catalog.models import CD, Tech
from partners.models import Supplier
from .models import Supply, SupplyCDItem, SupplyExpense, SupplyTechItem

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


def accept_supply(*, accepted_by, lines, expenses=()):
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

                for key, addition in inventory_additions.items():
                    product = products[key]
                    old_owned_quantity = product.quantity + product.quantity_on_consignment
                    new_quantity = addition["quantity"]
                    new_average = (
                        (Decimal(old_owned_quantity) * product.cost + addition["value"])
                        / Decimal(old_owned_quantity + new_quantity)
                    )
                    product.quantity += new_quantity
                    product.cost = new_average.quantize(UNIT, rounding=ROUND_HALF_UP)
                    product.full_clean()
                    product.save(update_fields=("quantity", "cost"))

            logger.info(
                "Поставка принята: user_id=%s supply_id=%s units=%s",
                accepted_by.pk, supply.pk, total_units,
            )
            return supply
    except Exception:
        logger.exception("Ошибка приёмки поставки: user_id=%s", getattr(accepted_by, "pk", None))
        raise
