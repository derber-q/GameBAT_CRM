from decimal import Decimal, ROUND_HALF_UP


CENT = Decimal("0.01")
AVITO_COMMISSION_RATE = Decimal("0.005")
AVITO_COMMISSION_MINIMUM = Decimal("1.00")
ZERO = Decimal("0.00")


def calculate_avito_commission(line_total, *, enabled):
    """Рассчитать денежный снимок комиссии по итоговой сумме строки."""
    if not enabled:
        return ZERO
    amount = max(
        Decimal(line_total) * AVITO_COMMISSION_RATE,
        AVITO_COMMISSION_MINIMUM,
    )
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)
