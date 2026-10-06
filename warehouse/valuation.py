"""Расчёт средней себестоимости только по физическому складскому остатку."""
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Sum

from .models import CDWarehouseStock, TechWarehouseStock


CENT = Decimal("0.01")


def warehouse_owned_quantity(product_type, product_id):
    """Возвращает суммарный остаток товара на всех физических складах."""
    if product_type == "cd":
        stock_model, product_field = CDWarehouseStock, "cd"
    elif product_type == "tech":
        stock_model, product_field = TechWarehouseStock, "tech"
    else:
        raise ValueError(f"Неизвестный тип товара: {product_type}")
    return stock_model.objects.filter(
        **{f"{product_field}_id": product_id}
    ).aggregate(total=Sum("quantity"))["total"] or 0


def weighted_warehouse_cost(*, old_quantity, old_unit_cost, incoming_quantity, incoming_unit_cost):
    """Смешивает складской остаток с поступающей партией и округляет до копеек."""
    old_quantity = int(old_quantity)
    incoming_quantity = int(incoming_quantity)
    resulting_quantity = old_quantity + incoming_quantity
    if old_quantity < 0 or incoming_quantity <= 0 or resulting_quantity <= 0:
        raise ValueError("Количество для расчёта складской себестоимости некорректно.")
    resulting_value = (
        Decimal(old_quantity) * Decimal(old_unit_cost)
        + Decimal(incoming_quantity) * Decimal(incoming_unit_cost)
    )
    return (resulting_value / Decimal(resulting_quantity)).quantize(
        CENT, rounding=ROUND_HALF_UP
    )
