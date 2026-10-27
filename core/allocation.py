"""Детерминированное распределение денежной суммы методом наибольших остатков."""
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from django.core.exceptions import ValidationError

CENT = Decimal('.01')


def allocate_amount(amount, weights):
    try:
        amount = Decimal(str(amount))
        weights = [Decimal(str(value)) for value in weights]
        if (not amount.is_finite() or amount < 0 or amount != amount.quantize(CENT)
                or not weights or any(not weight.is_finite() or weight < 0 for weight in weights)):
            raise ValueError()
        total = sum(weights)
        if total == 0:
            if amount:
                raise ValueError()
            return [Decimal('0.00')] * len(weights)
        cents = int(amount / CENT)
        exact = [Decimal(cents) * weight / total for weight in weights]
        allocated = [int(value.to_integral_value(rounding=ROUND_DOWN)) for value in exact]
        order = sorted(range(len(weights)), key=lambda index: (exact[index] - allocated[index], -index), reverse=True)
        for index in order[:cents - sum(allocated)]:
            allocated[index] += 1
        result = [Decimal(value) * CENT for value in allocated]
        if sum(result) != amount:
            raise ValueError()
        return result
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValidationError('Нельзя распределить сумму: проверьте деньги и исходные тарифы доставки.') from exc
