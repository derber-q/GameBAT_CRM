"""Согласованные условия покупателя, общие для подписей прайса и магазина."""
from decimal import Decimal


def new_account_fee(buyer_name):
    """Действующие доплаты; неизвестному покупателю доплата не назначается автоматически."""
    fees = {'gns': '150', 'подписки gns': '150', 'играть': '100', 'подписки играть': '100'}
    value = fees.get(' '.join(str(buyer_name).casefold().split()))
    return Decimal(value) if value is not None else None
