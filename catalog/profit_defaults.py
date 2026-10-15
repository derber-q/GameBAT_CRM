"""Начальная желаемая прибыль FBS для новых карточек товаров."""
from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist


CD_DESIRED_PROFIT = Decimal("500.00")
GAMEPAD_DESIRED_PROFIT = Decimal("1000.00")
TECH_DESIRED_PROFIT = Decimal("300.00")


def fill_new_product_desired_profit(product):
    """Выбирает прибыль по типу при создании, сохраняя введённую сумму."""
    if not product._state.adding or product.yandex_desired_profit is not None:
        return
    if product._meta.model_name == "cd":
        product.yandex_desired_profit = CD_DESIRED_PROFIT
    elif product._meta.model_name == "tech":
        product.yandex_desired_profit = TECH_DESIRED_PROFIT
        if product.product_type_id:
            try:
                type_name = product.product_type.name.strip().casefold()
            except (ObjectDoesNotExist, TypeError, ValueError):
                return
            if type_name == "геймпад":
                product.yandex_desired_profit = GAMEPAD_DESIRED_PROFIT
