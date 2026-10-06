from collections import defaultdict

from django.core.exceptions import ValidationError
from .client import CONTRACTS
from .content import validate_schema


def validate_boxes(order, boxes):
    validate_schema({"boxes": boxes}, CONTRACTS["setOrderBoxLayout"]["request"], "Коробки")
    expected = {item["id"]: item["count"] for item in order.items}
    counts = defaultdict(int)
    partials = defaultdict(list)
    for box in boxes:
        for item in box["items"]:
            if item["id"] not in expected:
                raise ValidationError("В коробке указан товар другого заказа.")
            if bool(item.get("fullCount")) == bool(item.get("partialCount")):
                raise ValidationError("Укажите целое количество либо часть крупного товара.")
            if item.get("fullCount"):
                counts[item["id"]] += item["fullCount"]
            else:
                partials[item["id"]].append(item["partialCount"])
    # Крупные товары требуют полной и непротиворечивой нумерации частей.
    for item_id, parts in partials.items():
        if counts[item_id] or expected[item_id] != 1:
            raise ValidationError("Разделение на части поддерживается для одной единицы товара.")
        totals = {part["total"] for part in parts}
        if len(totals) != 1 or sorted(part["current"] for part in parts) != list(range(1, next(iter(totals)) + 1)):
            raise ValidationError("Укажите все части крупного товара без повторов.")
        counts[item_id] = 1
    if dict(counts) != expected:
        raise ValidationError("Состав коробок должен точно соответствовать всем товарам заказа.")
    return boxes
