"""Точный расчёт и применение финализации принятого прихода."""
import logging
from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
from functools import reduce
from math import gcd

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

from catalog.audit import field_change, record_product_changes
from catalog.models import CD, ProductChangeEvent, Tech
from consignment.models import CDConsignmentStock, TechConsignmentStock
from warehouse.models import (
    CDWarehouseStock, CDWarehouseTransferItem, TechWarehouseStock,
    TechWarehouseTransferItem, WarehouseTransfer,
)

from .models import Supply, SupplyFinalization, SupplyFinalizationItem
from .services import global_owned_quantity

logger = logging.getLogger("gamebat.business")
CENT = Decimal("0.01")


@dataclass(frozen=True)
class FinalizationRow:
    product_type: str
    product_id: int
    product: object
    global_quantity: int
    current_cost: Decimal
    corrected_cost: Decimal
    change_source: str = "unchanged"

    @property
    def key(self):
        return self.product_type, self.product_id

    @property
    def row_penalty(self):
        return (self.current_cost - self.corrected_cost) * Decimal(self.global_quantity)

    @property
    def difference_per_unit(self):
        return self.corrected_cost - self.current_cost


@dataclass(frozen=True)
class FinalizationInput:
    product_type: str
    product_id: int
    baseline_quantity: int
    baseline_cost: Decimal
    corrected_cost: Decimal
    change_source: str

    @property
    def key(self):
        return self.product_type, self.product_id


def _money(value, label):
    try:
        amount = Decimal(str(value).strip().replace(" ", "").replace(",", "."))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError(f"Поле «{label}» содержит некорректное число.") from exc
    if not amount.is_finite():
        raise ValidationError(f"Поле «{label}» содержит некорректное число.")
    rounded = amount.quantize(CENT)
    if rounded != amount:
        raise ValidationError(f"Поле «{label}» должно быть указано с точностью до копейки.")
    return rounded


def parse_finalization_inputs(raw_rows):
    """Нормализует присланные baseline и corrected cost без доверия к UI."""
    parsed = []
    seen = set()
    for raw in raw_rows:
        product_type = str(raw.get("product_type", "")).lower()
        if product_type not in {"cd", "tech"}:
            raise ValidationError("Передан неизвестный тип товара.")
        try:
            product_id = int(raw.get("product_id"))
            baseline_quantity = int(raw.get("baseline_quantity"))
        except (TypeError, ValueError) as exc:
            raise ValidationError("Данные товара в форме повреждены. Обновите расчёт.") from exc
        key = product_type, product_id
        if key in seen:
            raise ValidationError("Один товар передан в финализацию несколько раз.")
        seen.add(key)
        baseline_cost = _money(raw.get("baseline_cost"), "Исходная себестоимость")
        corrected_cost = _money(raw.get("corrected_cost"), "Откорректированная себестоимость")
        if corrected_cost < 0:
            raise ValidationError("Откорректированная себестоимость не может быть отрицательной.")
        source = str(raw.get("change_source", "manual")).lower()
        if source not in {"manual", "auto", "unchanged"}:
            source = "manual"
        parsed.append(FinalizationInput(
            product_type=product_type,
            product_id=product_id,
            baseline_quantity=baseline_quantity,
            baseline_cost=baseline_cost,
            corrected_cost=corrected_cost,
            change_source=source,
        ))
    if not parsed:
        raise ValidationError("В приходе нет товаров для финализации.")
    return parsed


def _supply_product_keys(supply):
    return sorted(
        {("cd", value) for value in supply.cd_items.values_list("product_id", flat=True)}
        | {("tech", value) for value in supply.tech_items.values_list("product_id", flat=True)}
    )


def supply_has_complete_cost_calculations(supply):
    expected = set(_supply_product_keys(supply))
    actual = {
        (
            row.product_kind,
            row.cd_id if row.product_kind == "cd" else row.tech_id,
        )
        for row in supply.cost_calculations.all()
    }
    return bool(expected) and expected == actual


def _lock_global_quantity_records(keys):
    """Блокирует все строки, из которых складывается глобальное количество."""
    cd_ids = [product_id for kind, product_id in keys if kind == "cd"]
    tech_ids = [product_id for kind, product_id in keys if kind == "tech"]
    transfer_filter = Q(cd_items__cd_id__in=cd_ids) | Q(tech_items__tech_id__in=tech_ids)
    list(
        WarehouseTransfer.objects.select_for_update()
        .filter(transfer_filter).distinct().order_by("id")
    )
    list(CDWarehouseStock.objects.select_for_update().filter(cd_id__in=cd_ids).order_by("id"))
    list(TechWarehouseStock.objects.select_for_update().filter(tech_id__in=tech_ids).order_by("id"))
    list(CDConsignmentStock.objects.select_for_update().filter(cd_id__in=cd_ids).order_by("id"))
    list(TechConsignmentStock.objects.select_for_update().filter(tech_id__in=tech_ids).order_by("id"))
    list(CDWarehouseTransferItem.objects.select_for_update().filter(cd_id__in=cd_ids).order_by("id"))
    list(TechWarehouseTransferItem.objects.select_for_update().filter(tech_id__in=tech_ids).order_by("id"))


def get_supply_finalization_context(*, supply, lock=False):
    """Возвращает уникальные товары актуальной редакции с global qty/cost."""
    if supply.status != Supply.Status.ACCEPTED or supply.is_cancelled:
        raise ValidationError("Финализировать можно только действующий принятый приход.")
    keys = _supply_product_keys(supply)
    if not keys:
        raise ValidationError("В приходе нет товаров для финализации.")
    if not supply_has_complete_cost_calculations(supply):
        raise ValidationError(
            "Обычный расчёт себестоимости этого прихода не завершён или его история неполна."
        )
    cd_ids = [product_id for kind, product_id in keys if kind == "cd"]
    tech_ids = [product_id for kind, product_id in keys if kind == "tech"]
    cd_query = CD.objects.active().filter(pk__in=cd_ids).order_by("pk")
    tech_query = Tech.objects.active().filter(pk__in=tech_ids).order_by("pk")
    if lock:
        cd_query = cd_query.select_for_update()
        tech_query = tech_query.select_for_update()
    products = {
        **{("cd", product.pk): product for product in cd_query},
        **{("tech", product.pk): product for product in tech_query},
    }
    if set(products) != set(keys):
        raise ValidationError("Один из товаров прихода больше не существует.")
    if lock:
        _lock_global_quantity_records(keys)
    rows = []
    for key in keys:
        product = products[key]
        quantity = global_owned_quantity(*key)
        current_cost = product.cost.quantize(CENT)
        rows.append(FinalizationRow(
            product_type=key[0], product_id=key[1], product=product,
            global_quantity=quantity, current_cost=current_cost,
            corrected_cost=current_cost,
        ))
    return rows


def calculate_finalization_penalty(rows):
    return sum((row.row_penalty for row in rows), Decimal("0.00")).quantize(CENT)


def _extended_gcd(a, b):
    if b == 0:
        return a, 1, 0
    divisor, x1, y1 = _extended_gcd(b, a % b)
    return divisor, y1, x1 - (a // b) * y1


def _residual_coefficients(quantities, target):
    """Находит детерминированные целые поправки в копейках для residual."""
    if target == 0:
        return [0] * len(quantities)

    total_quantity = sum(quantities)
    if total_quantity <= 20_000:
        preferred = 1 if target > 0 else -1
        states = {0: ()}
        for index, quantity in enumerate(quantities):
            next_states = {}
            for value, coefficients in states.items():
                for coefficient in (0, preferred, -preferred):
                    candidate = value + quantity * coefficient
                    if -total_quantity <= candidate <= total_quantity and candidate not in next_states:
                        next_states[candidate] = coefficients + (coefficient,)
            states = next_states
            if target in states:
                return list(states[target]) + [0] * (len(quantities) - index - 1)
        if target in states:
            return list(states[target])

    common = reduce(gcd, quantities)
    if target % common:
        raise ValidationError(
            "Точную неустойку 0,00 ₽ невозможно получить при выбранных количествах "
            "и копеечной точности себестоимости. Измените набор товаров."
        )
    coefficients = [1]
    divisor = quantities[0]
    for quantity in quantities[1:]:
        new_divisor, left, right = _extended_gcd(divisor, quantity)
        coefficients = [value * left for value in coefficients] + [right]
        divisor = new_divisor
    multiplier = target // divisor
    return [value * multiplier for value in coefficients]


def auto_distribute_penalty(*, rows, selected_keys):
    """Распределяет penalty по глобальным единицам и точно гасит residual."""
    selected_keys = set(selected_keys)
    eligible = [
        row for row in rows
        if row.key in selected_keys and row.global_quantity > 0 and row.change_source != "manual"
    ]
    penalty = calculate_finalization_penalty(rows)
    if penalty == Decimal("0.00"):
        return list(rows)
    if not eligible:
        raise ValidationError("Выберите товары для распределения неустойки.")
    selected_total_quantity = sum(row.global_quantity for row in eligible)
    penalty_cents = int(penalty / CENT)
    sign = 1 if penalty_cents > 0 else -1
    base_cents = sign * (abs(penalty_cents) // selected_total_quantity)
    residual_cents = penalty_cents - base_cents * selected_total_quantity
    residuals = _residual_coefficients(
        [row.global_quantity for row in eligible], residual_cents
    )
    corrections = {
        row.key: base_cents + residual
        for row, residual in zip(eligible, residuals)
    }
    result = []
    for row in rows:
        correction = corrections.get(row.key)
        if correction is None:
            result.append(row)
            continue
        corrected = row.corrected_cost + Decimal(correction) * CENT
        if corrected < 0:
            raise ValidationError(
                f"Автораспределение сделает себестоимость «{row.product.name}» отрицательной. "
                "Измените набор товаров."
            )
        result.append(replace(
            row, corrected_cost=corrected.quantize(CENT), change_source="auto"
        ))
    if calculate_finalization_penalty(result) != Decimal("0.00"):
        raise ValidationError(
            "Не удалось точно распределить неустойку при копеечной точности себестоимости."
        )
    return result


def rows_from_inputs(current_rows, inputs):
    current = {row.key: row for row in current_rows}
    submitted = {row.key: row for row in inputs}
    if set(current) != set(submitted):
        raise ValidationError(
            "Состав прихода изменился после открытия финализации. Обновите расчёт."
        )
    rows = []
    for key, baseline in current.items():
        posted = submitted[key]
        if (
            posted.baseline_quantity != baseline.global_quantity
            or posted.baseline_cost != baseline.current_cost
        ):
            raise ValidationError(
                "Данные товаров изменились после открытия финализации. Обновите расчёт."
            )
        source = posted.change_source
        if posted.corrected_cost == baseline.current_cost:
            source = "unchanged"
        elif source == "unchanged":
            source = "manual"
        rows.append(replace(
            baseline, corrected_cost=posted.corrected_cost, change_source=source
        ))
    return rows


def apply_supply_finalization(*, actor, supply_id, expected_revision_number, raw_rows):
    logger.info(
        "Начато применение финализации прихода: user_id=%s supply_id=%s",
        getattr(actor, "pk", None), supply_id,
    )
    try:
        inputs = parse_finalization_inputs(raw_rows)
        with transaction.atomic():
            supply = Supply.objects.select_for_update().get(pk=supply_id)
            try:
                expected_revision_number = int(expected_revision_number)
            except (TypeError, ValueError) as exc:
                raise ValidationError(
                    "Приход изменился после открытия финализации. Обновите расчёт."
                ) from exc
            if supply.revision_number != expected_revision_number:
                raise ValidationError(
                    "Приход изменился после открытия финализации. Обновите расчёт."
                )
            current_rows = get_supply_finalization_context(supply=supply, lock=True)
            rows = rows_from_inputs(current_rows, inputs)
            total_penalty = calculate_finalization_penalty(rows)
            if total_penalty != Decimal("0.00"):
                raise ValidationError(
                    f"Финализацию нельзя применить: неустойка равна {total_penalty:.2f} ₽, а должна быть 0,00 ₽."
                )
            changed = [row for row in rows if row.corrected_cost != row.current_cost]
            if not changed:
                raise ValidationError("Измените себестоимость хотя бы одного товара.")
            before_value = sum(
                (
                    Decimal(row.global_quantity) * row.current_cost
                    for row in changed if row.global_quantity > 0
                ),
                Decimal("0.00"),
            )
            after_value = sum(
                (
                    Decimal(row.global_quantity) * row.corrected_cost
                    for row in changed if row.global_quantity > 0
                ),
                Decimal("0.00"),
            )
            if (before_value - after_value).quantize(CENT) != Decimal("0.00"):
                raise ValidationError("Общая стоимость запасов не сохраняется. Обновите расчёт.")
            manual_penalty = sum(
                (row.row_penalty for row in changed if row.change_source != "auto"),
                Decimal("0.00"),
            ).quantize(CENT)
            finalization = SupplyFinalization.objects.create(
                supply=supply,
                created_by=actor,
                supply_revision_number=supply.revision_number,
                total_penalty_before_distribution=manual_penalty,
            )
            history_items = []
            for row in changed:
                difference = row.difference_per_unit.quantize(CENT)
                history_items.append(SupplyFinalizationItem(
                    finalization=finalization,
                    product_kind=row.product_type,
                    product_name_snapshot=row.product.name,
                    product_sku_snapshot=row.product.sku,
                    global_quantity_snapshot=row.global_quantity,
                    old_global_cost=row.current_cost,
                    new_global_cost=row.corrected_cost,
                    difference_per_unit=difference,
                    value_difference=(difference * Decimal(row.global_quantity)).quantize(CENT),
                    change_source=(
                        SupplyFinalizationItem.ChangeSource.AUTO_DISTRIBUTED
                        if row.change_source == "auto"
                        else SupplyFinalizationItem.ChangeSource.MANUAL
                    ),
                    **{row.product_type: row.product},
                ))
            SupplyFinalizationItem.objects.bulk_create(history_items)
            for row in changed:
                product = row.product
                product.cost = row.corrected_cost
                product.full_clean(exclude=[
                    field.name for field in product._meta.fields if field.name != "cost"
                ])
                product.save(update_fields=("cost",))
                record_product_changes(
                    actor=actor,
                    instance=product,
                    source=ProductChangeEvent.Source.CRM,
                    action_kind=ProductChangeEvent.ActionKind.SUPPLY_FINALIZATION,
                    action_object_id=supply.pk,
                    action_label=f"Финализация прихода №{supply.pk}",
                    changes=[field_change(
                        field_name="cost",
                        field_label="Средняя себестоимость",
                        old_value=f"{row.current_cost:.2f}",
                        new_value=f"{row.corrected_cost:.2f}",
                    )],
                )
            logger.info(
                "Финализация прихода применена: user_id=%s supply_id=%s "
                "finalization_id=%s products=%s penalty_before=%s",
                actor.pk, supply.pk, finalization.pk, len(changed), manual_penalty,
            )
            return finalization
    except Exception:
        logger.exception(
            "Финализация прихода отклонена: user_id=%s supply_id=%s",
            getattr(actor, "pk", None), supply_id,
        )
        raise
