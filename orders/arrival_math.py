"""Расчёт закупки через USDT и точное представление строк в копейках."""
from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError
from price.services import decimal_value


def purchase_cost(aed, usdt_aed, usdt_rub):
    try:
        aed, usdt_aed, usdt_rub = map(lambda value: Decimal(str(value)), (aed, usdt_aed, usdt_rub))
        if any(not value.is_finite() or value <= 0 for value in (aed, usdt_aed, usdt_rub)):
            raise ValueError()
        return decimal_value(aed / usdt_aed * usdt_rub, nonnegative=True, label='Закупочная себестоимость')
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValidationError('Проверьте цену AED и положительные курсы USDT/AED и USDT/RUB.') from exc


def unit_cohorts(amount, quantity):
    if not isinstance(quantity, int) or quantity <= 0:
        raise ValidationError('В закупочной позиции должно быть положительное количество.')
    amount = Decimal(str(amount))
    if not amount.is_finite() or amount < 0 or amount != amount.quantize(Decimal('.01')):
        raise ValidationError('Стоимость позиции должна быть неотрицательной суммой в копейках.')
    cents, remainder = divmod(int(amount * 100), quantity)
    return [(count, Decimal(cost) / 100) for count, cost in
            ((quantity - remainder, cents), (remainder, cents + 1)) if count]


def preliminary_delivery(source):
    """Сохранённые тарифы задают пропорции; актуальные курсы их не изменяют."""
    from price.services import weighted_procurement_delivery
    weight,tariff=source.weight_grams_snapshot,source.delivery_usdt_per_kg_snapshot
    original_rate=source.price_list.exchange_rate_usdt_rub
    delivery=decimal_value(source.delivery_rub,nonnegative=True,label='Сохранённый тариф доставки')
    algorithm='fixed_unit' if source.product_kind=='cd' else 'legacy_saved_delivery'
    if source.product_kind=='tech' and weight and tariff is not None:
        if original_rate is not None and original_rate.is_finite() and original_rate>0:
            delivery=weighted_procurement_delivery(weight_grams=weight,tariff=tariff,dollar_rate=original_rate)
            algorithm='weight_tariff'
        elif tariff>0 and delivery==0:
            raise ValidationError(f'{source.product_name_snapshot}: нет исторической рублёвой стоимости тарифа доставки.')
    return delivery,{'algorithm':algorithm,'weight_grams':weight,
        'tariff_per_kg':str(tariff) if tariff is not None else None,
        'original_usd_rub':str(original_rate) if original_rate is not None else None,
        'original_delivery_rub':str(source.delivery_rub),'group':source.delivery_group_snapshot}
