"""Единый расчёт FBS: Decimal, объём упаковки и отдельная рекомендуемая цена."""
import copy
import logging
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_HALF_UP, localcontext

from django.core.exceptions import ValidationError

logger = logging.getLogger("gamebat.business")
CENT = Decimal("0.01")
DEFAULTS = {
    "tax_rate": None, "payment_rate": None, "packaging": "30.00",
    "delivery_rate": "5.00", "delivery_max": "1000.00",
    "fixed_payment": "0.00", "other_fbs": "0.00",
    "middle_first_l": "1", "middle_first_fee": "92.00", "middle_max": "5500.00",
    "middle_bands": [{"until_l": "200", "per_l": "8.00"}, {"until_l": None, "per_l": "5.00"}],
}
DIMENSIONS = ("length_cm", "width_cm", "height_cm")
INPUT_FIELDS = (*DIMENSIONS, "weight_grams", "yandex_desired_profit", "yandex_pricing_integration", "yandex_pricing_category")


def pricing_configuration(integration):
    values = copy.deepcopy(DEFAULTS)
    values.update((integration.configuration or {}).get("fbs_pricing", {}))
    return values


def number(value, label, *, positive=False, percent=False):
    if value in (None, ""):
        raise ValidationError(f"Не указано: {label}.")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValidationError(f"{label}: укажите число.") from exc
    if not result.is_finite() or result < 0 or (positive and result == 0):
        raise ValidationError(f"{label}: значение должно быть {'больше 0' if positive else 'не меньше 0'}.")
    if percent and (result >= 100 or result != result.quantize(CENT)):
        raise ValidationError(f"{label}: укажите процент от 0 до 99,99 с двумя знаками после запятой.")
    return result / 100 if percent else result


def middle_mile(volume, config):
    first = number(config.get("middle_first_l"), "Первый диапазон средней мили", positive=True)
    if first != first.to_integral_value():
        raise ValidationError("Граница первого диапазона должна быть целым числом литров.")
    fee = number(config.get("middle_first_fee"), "Стоимость первого диапазона")
    maximum = number(config.get("middle_max"), "Максимальная стоимость средней мили")
    previous = first
    bands = config.get("middle_bands")
    if not isinstance(bands, list) or not bands or len(bands) > 20:
        raise ValidationError("Укажите диапазоны средней мили, последний — без верхней границы.")
    for index, band in enumerate(bands):
        if not isinstance(band, dict):
            raise ValidationError("Некорректный диапазон средней мили.")
        rate = number(band.get("per_l"), "Стоимость дополнительного литра")
        bound = band.get("until_l")
        if bound in (None, ""):
            if index != len(bands) - 1:
                raise ValidationError("Только последний диапазон может быть без верхней границы.")
            upper = max(previous, volume)
        else:
            upper = number(bound, "Граница диапазона", positive=True)
            if upper <= previous or upper != upper.to_integral_value():
                raise ValidationError("Границы средней мили должны возрастать и быть целыми литрами.")
        fee += max(Decimal(0), min(volume, upper) - previous) * rate
        previous = upper
    if bands[-1].get("until_l") not in (None, ""):
        raise ValidationError("Последний диапазон средней мили должен быть без верхней границы.")
    return min(fee, maximum).quantize(CENT, rounding=ROUND_HALF_UP)


def calculate_fbs_price(*, cost_price, desired_profit, length_cm, width_cm, height_cm, weight_g, placement_rate, configuration):
    with localcontext() as context:
        context.prec = 50
        return _calculate(cost_price, desired_profit, length_cm, width_cm, height_cm, weight_g, placement_rate, configuration)


def _calculate(cost, profit, length, width, height, weight, placement, config):
    if any(value in (None, "") for value in (length, width, height)):
        raise ValidationError("Цена не рассчитана: укажите габариты товара для расчёта FBS.")
    cost = number(cost, "Себестоимость", positive=True)
    profit = number(profit, "Желаемая чистая прибыль")
    sizes = [number(value, label, positive=True) for value, label in zip((length, width, height), ("Длина", "Ширина", "Высота"))]
    if weight is not None:
        numeric_weight = number(weight, "Вес с упаковкой", positive=True)
        if numeric_weight != numeric_weight.to_integral_value():
            raise ValidationError("Вес укажите целым числом граммов.")
    if placement is None:
        raise ValidationError("Цена Яндекс Маркета не рассчитана: не указан тариф категории.")
    rates = [number(value, label, percent=True) for value, label in (
        (placement, "Тариф категории"), (config.get("tax_rate"), "Налоговая ставка"),
        (config.get("payment_rate"), "Тариф перевода денежных средств"),
    )]
    delivery_rate = number(config.get("delivery_rate"), "Процент доставки", percent=True)
    delivery_max = number(config.get("delivery_max"), "Максимальная стоимость доставки")
    denominator = Decimal(1) - sum(rates)
    if denominator <= 0:
        raise ValidationError("Цена не рассчитана: сумма тарифов размещения, налога и перевода должна быть меньше 100%.")
    raw_volume = sizes[0] * sizes[1] * sizes[2] / 1000
    billing_volume = raw_volume.to_integral_value(rounding=ROUND_CEILING)
    fixed = {
        "middle_mile_fee": middle_mile(billing_volume, config),
        "packaging_fee": number(config.get("packaging"), "Стоимость упаковки"),
        "fixed_payment_fee": number(config.get("fixed_payment"), "Фиксированная комиссия за приём платежа"),
        "other_fbs_fee": number(config.get("other_fbs"), "Дополнительные расходы FBS"),
    }
    base = cost + profit + sum(fixed.values())

    def expenses(price):
        fees = dict(zip(("placement_fee", "tax_fee", "payment_transfer_fee"),
                        ((price * rate).quantize(CENT, rounding=ROUND_HALF_UP) for rate in rates)))
        fees["delivery_fee"] = min(price * delivery_rate, delivery_max).quantize(CENT, rounding=ROUND_HALF_UP)
        actual = price - cost - sum(fixed.values()) - sum(fees.values())
        return fees, actual

    # Проценты имеют два десятичных знака. Через каждые 100 целых рублей
    # округления комиссий повторяются; рассматриваем все классы остатков.
    # Это даёт минимальную целую цену даже при ставках, близких к 100%.
    threshold = delivery_max / delivery_rate if delivery_rate else Decimal(0)
    cap_start = threshold.to_integral_value(rounding=ROUND_CEILING)
    branches = [(base + delivery_max, denominator, cap_start, None)] if delivery_rate else [(base, denominator, Decimal(0), None)]
    if delivery_rate and cap_start > 0:
        branches.append((base, denominator - delivery_rate, Decimal(0), cap_start - 1))
    best = None
    for branch_base, divisor, minimum, maximum in branches:
        lower = max(minimum, Decimal(1))
        if divisor > 0:
            lower = max(lower, ((branch_base - Decimal("0.02")) / divisor).to_integral_value(rounding=ROUND_CEILING))
        for offset in range(100):
            price = lower + offset
            if maximum is not None and price > maximum:
                break
            _, actual = expenses(price)
            # При нулевой/отрицательной марже новые периоды не улучшают
            # результат, но округления могут дать подходящую малую цену.
            periods = max(Decimal(0), ((profit - actual) / (100 * divisor)).to_integral_value(rounding=ROUND_CEILING)) if divisor > 0 else Decimal(0)
            price += 100 * periods
            if maximum is not None and price > maximum:
                continue
            fees, actual = expenses(price)
            if actual >= profit and (best is None or price < best[0]):
                best = (price, fees, actual)
    if best is None or best[0] >= Decimal("1e18"):
        raise ValidationError("Цена не рассчитана: результат превышает допустимую сумму. Проверьте ставки и расходы.")
    price, fees, actual = best
    return {
        "final_price": price, "desired_profit": profit, "actual_profit": actual,
        "cost_price": cost, "raw_volume_l": raw_volume, "billing_volume_l": billing_volume,
        "weight_g": weight, "delivery_cap_price": threshold, **fixed, **fees,
    }


def product_context(product, integration=None, category=None):
    from .models import CategorySchema, Integration
    if integration is None:
        integration = product.yandex_pricing_integration
    connections = product.yandex_connections.filter(active=True).select_related("integration", "remote_offer")
    if integration is None:
        linked = list(connections[:2])
        if len(linked) == 1:
            integration = linked[0].integration
        elif len(linked) > 1:
            raise ValidationError("Выберите подключение Яндекс Маркета для расчёта.")
        elif Integration.objects.count() == 1:
            integration = Integration.objects.first()
    if integration is None:
        raise ValidationError("Выберите подключение Яндекс Маркета и настройте тарифы FBS.")
    connection = connections.filter(integration=integration).first()
    if connection:
        category_id = connection.category_id or connection.remote_offer.category_id
        if category is not None and category.category_id != category_id:
            raise ValidationError("Категория связанного товара задаётся в карточке Маркета. Для расчёта выберите ту же категорию.")
        category = CategorySchema.objects.filter(category_id=category_id).first()
    elif category is None:
        category = product.yandex_pricing_category
    return integration, category


def product_calculation(product, *, integration=None, category=None, overrides=None, log_errors=True):
    overrides = overrides or {}
    if overrides:
        # Предпросмотр учитывает и явную очистку полей, не изменяя карточку.
        product = copy.copy(product)
        for field in INPUT_FIELDS:
            if field in overrides:
                setattr(product, field, overrides[field])
    try:
        integration, category = product_context(product, integration, category)
        result = calculate_fbs_price(
            cost_price=product.cost, desired_profit=overrides.get("yandex_desired_profit", product.yandex_desired_profit),
            placement_rate=category.placement_rate if category else None,
            configuration=pricing_configuration(integration),
            weight_g=overrides.get("weight_grams", product.weight_grams),
            **{field: overrides.get(field, getattr(product, field)) for field in DIMENSIONS},
        )
        return {"ok": True, **result, "integration_id": integration.pk, "category_id": category.category_id, "category_name": str(category)}
    except (ValidationError, InvalidOperation) as exc:
        message = " ".join(exc.messages) if isinstance(exc, ValidationError) else "Некорректные значения расчёта."
        if log_errors:
            logger.warning("Ошибка расчёта FBS: kind=%s product_id=%s name=%s category=%s dimensions=%s cost=%s reason=%s",
                           product._meta.model_name, product.pk, product.name, getattr(category, "category_id", None),
                           [overrides.get(field, getattr(product, field)) for field in DIMENSIONS], product.cost, message)
        return {"ok": False, "message": message}


def refresh_recommendation(product):
    result = product_calculation(product) if product.yandex_desired_profit is not None else {"ok": False}
    value = result.get("final_price") if result["ok"] else None
    if product.yandex_calculated_price != value:
        product.yandex_calculated_price = value
        product.save(update_fields=["yandex_calculated_price"])
    return result


def refresh_recommendations(*, integration_id=None, category_id=None):
    from catalog.models import CD, Tech
    from django.db.models import Q
    for model in (CD, Tech):
        products = model.objects.active().filter(yandex_desired_profit__isnull=False)
        if integration_id is not None:
            products = products.filter(Q(yandex_pricing_integration_id=integration_id) | Q(yandex_pricing_integration__isnull=True))
        if category_id is not None:
            products = products.filter(Q(yandex_pricing_category__category_id=category_id)
                | Q(yandex_connections__active=True, yandex_connections__category_id=category_id)
                | Q(yandex_connections__active=True, yandex_connections__category_id__isnull=True, yandex_connections__remote_offer__category_id=category_id)).distinct()
        for product in products.select_related("yandex_pricing_integration", "yandex_pricing_category").iterator():
            refresh_recommendation(product)


def save_product_inputs(*, actor, product, changes, version=None):
    from django.db import transaction
    from catalog.audit import changed_snapshots, product_snapshot, record_product_changes
    from catalog.models import ProductChangeEvent
    from catalog.nomenclature_forms import product_version
    from catalog.product_fields import field_permissions_for
    with transaction.atomic():
        product = type(product).objects.active().select_for_update().get(pk=product.pk)
        if version is not None and version != product_version(product):
            raise ValidationError("Товар изменён другим пользователем. Обновите расчёт.")
        permissions = field_permissions_for(type(product))
        for field in changes:
            if field not in INPUT_FIELDS or not (actor.is_superuser or actor.has_perm(permissions[field])):
                raise ValidationError("Нет права изменять параметры расчёта или габариты товара.")
        before = product_snapshot(product, changes)
        for field, value in changes.items():
            model_field = product._meta.get_field(field)
            if model_field.is_relation:
                model_field.clean(value.pk if value is not None else None, product)
                setattr(product, field, value)
            else:
                setattr(product, field, model_field.clean(value, product))
        # Категория существующей связи является источником истины для расчёта.
        if product.yandex_pricing_integration or product.yandex_pricing_category:
            product_context(product, category=product.yandex_pricing_category if "yandex_pricing_category" in changes else None)
        changed = changed_snapshots(product, before, changes)
        if changed:
            product.save(update_fields=[item["field_name"] for item in changed])
            record_product_changes(actor=actor, instance=product, changes=changed, source=ProductChangeEvent.Source.CRM)
        result = refresh_recommendation(product)
        return product, result
