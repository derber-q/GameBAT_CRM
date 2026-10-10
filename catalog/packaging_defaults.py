"""Стандартная упаковка CD и геймпадов, заданная пользователем CRM."""
from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist


CD_DIMENSIONS = {"length_cm": Decimal("23"), "width_cm": Decimal("15"), "height_cm": Decimal("4")}
GAMEPAD_DIMENSIONS = {"length_cm": Decimal("21"), "width_cm": Decimal("20"), "height_cm": Decimal("11")}


def default_dimensions_for(product):
    if product._meta.model_name == "cd":
        return CD_DIMENSIONS
    if product._meta.model_name == "tech" and product.product_type_id:
        try:
            type_name = product.product_type.name.strip().casefold()
        except (ObjectDoesNotExist, TypeError, ValueError):
            return {}
        if type_name == "геймпад":
            return GAMEPAD_DIMENSIONS
    return {}


def fill_new_product_dimensions(product):
    """Заполняет пустые размеры при создании, сохраняя указанные вручную."""
    if not product._state.adding:
        return
    for field, value in default_dimensions_for(product).items():
        if getattr(product, field) is None:
            setattr(product, field, value)
