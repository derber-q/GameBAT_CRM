"""Атомарные операции передачи и возврата товара."""
import logging
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction

from catalog.models import CD, Tech
from partners.models import SalesPlatform
from .models import CDConsignmentStock, TechConsignmentStock

logger = logging.getLogger("gamebat.business")


def _configuration(product_type):
    if product_type == "cd":
        return CD, CDConsignmentStock, "cd"
    if product_type == "tech":
        return Tech, TechConsignmentStock, "tech"
    raise ValidationError("Выберите существующий товар из списка.")


def _positive_quantity(value):
    try:
        quantity = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Количество должно быть целым числом.") from exc
    if quantity <= 0:
        raise ValidationError("Количество должно быть больше нуля.")
    return quantity


def transfer_to_consignment(*, actor, platform_id, product_type, product_id, quantity, reward_per_unit):
    quantity = _positive_quantity(quantity)
    try:
        reward = Decimal(str(reward_per_unit)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError("Укажите корректное вознаграждение.") from exc
    if reward < 0:
        raise ValidationError("Вознаграждение не может быть отрицательным.")
    product_model, stock_model, product_field = _configuration(product_type)

    with transaction.atomic():
        platform = SalesPlatform.objects.get(pk=platform_id)
        try:
            product = product_model.objects.select_for_update().get(pk=product_id)
        except product_model.DoesNotExist as exc:
            raise ValidationError("Выберите существующий товар из списка.") from exc
        if product.quantity < quantity:
            raise ValidationError("Недостаточно товара на складе.")

        lookup = {"platform": platform, product_field: product}
        stock = stock_model.objects.select_for_update().filter(**lookup).first()
        if stock is None:
            stock = stock_model(**lookup, quantity=0, reward_per_unit=reward)
        elif stock.quantity > 0 and stock.reward_per_unit != reward:
            raise ValidationError("Для этого товара на данной площадке уже задано другое вознаграждение.")
        elif stock.quantity == 0:
            stock.reward_per_unit = reward

        product.quantity -= quantity
        product.quantity_on_consignment += quantity
        stock.quantity += quantity
        product.full_clean()
        stock.full_clean()
        product.save(update_fields=("quantity", "quantity_on_consignment"))
        stock.save()
        logger.info(
            "Товар передан на реализацию: user_id=%s platform_id=%s type=%s product_id=%s quantity=%s",
            actor.pk, platform_id, product_type, product_id, quantity,
        )
        return stock


def return_from_consignment(*, actor, platform_id, product_type, product_id, quantity):
    quantity = _positive_quantity(quantity)
    product_model, stock_model, product_field = _configuration(product_type)

    with transaction.atomic():
        try:
            product = product_model.objects.select_for_update().get(pk=product_id)
            stock = stock_model.objects.select_for_update().get(
                platform_id=platform_id, **{f"{product_field}_id": product_id}
            )
        except (product_model.DoesNotExist, stock_model.DoesNotExist) as exc:
            raise ValidationError("На выбранной площадке такого товара нет.") from exc
        if stock.quantity < quantity:
            raise ValidationError(f"На выбранной площадке находится только {stock.quantity} единиц товара.")

        stock.quantity -= quantity
        product.quantity_on_consignment -= quantity
        product.quantity += quantity
        product.full_clean()
        stock.full_clean()
        stock.save(update_fields=("quantity",))
        product.save(update_fields=("quantity", "quantity_on_consignment"))
        logger.info(
            "Товар возвращён с реализации: user_id=%s platform_id=%s type=%s product_id=%s quantity=%s",
            actor.pk, platform_id, product_type, product_id, quantity,
        )
        return stock
