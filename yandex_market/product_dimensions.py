"""Общие размеры товара. Маркет дополняет пустые поля, ручные значения сохраняет."""
import logging
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction

from catalog.audit import changed_snapshots, field_change, product_snapshot, record_product_changes
from catalog.models import ProductChangeEvent
from .models import OfferConnection

logger = logging.getLogger("gamebat.business")
SIZE_KEYS = {"length_cm": "length", "width_cm": "width", "height_cm": "height"}


def dimensions_payload(product, fallback=None):
    values = {key: getattr(product, field) for field, key in SIZE_KEYS.items()}
    if all(value is None for value in values.values()) and fallback:
        values = {key: fallback.get(key) for key in SIZE_KEYS.values()}
    if any(value is None for value in values.values()):
        raise ValidationError("Укажите длину, ширину и высоту упаковки в карточке товара CRM.")
    if not product.weight_grams:
        raise ValidationError("Укажите вес с упаковкой в карточке товара CRM.")
    values["weight"] = Decimal(product.weight_grams) / 1000
    if any(Decimal(str(value)) <= 0 for value in values.values()):
        raise ValidationError("Вес и размеры должны быть больше нуля.")
    return values


@transaction.atomic
def save_dimensions(product, dimensions, *, actor, only_missing, source):
    product = type(product).objects.active().select_for_update().get(pk=product.pk)
    updates = {}
    for field, key in SIZE_KEYS.items():
        if only_missing and getattr(product, field) is not None:
            continue
        value = dimensions.get(key)
        if value is None:
            continue
        try:
            updates[field] = product._meta.get_field(field).clean(Decimal(str(value)), product)
        except (ValidationError, InvalidOperation, ValueError, TypeError):
            if not only_missing:
                raise ValidationError(f"Некорректное значение {field}. Размеры должны быть больше нуля.")
            logger.warning("Габарит Маркета пропущен: product_id=%s kind=%s field=%s source=%s", product.pk, product._meta.model_name, field, source)
    if only_missing and product.weight_grams is None and dimensions.get("weight") is not None:
        try:
            grams = Decimal(str(dimensions["weight"])) * 1000
            if grams <= 0 or grams != grams.to_integral_value():
                raise ValueError
            updates["weight_grams"] = product._meta.get_field("weight_grams").clean(int(grams), product)
        except (ValidationError, InvalidOperation, ValueError, TypeError):
            logger.warning("Вес Маркета пропущен: product_id=%s source=%s", product.pk, source)
    before = product_snapshot(product, updates)
    for field, value in updates.items():
        setattr(product, field, value)
    changes = changed_snapshots(product, before, updates)
    if changes:
        product.save(update_fields=[change["field_name"] for change in changes])
        record_product_changes(actor=actor, instance=product, changes=[*changes, field_change(
            field_name="dimensions_source", field_label="Источник габаритов", old_value="", new_value=source,
        )], source=ProductChangeEvent.Source.CRM)
        logger.info("Габариты товара обновлены: kind=%s product_id=%s source=%s fields=%s", product._meta.model_name, product.pk, source, list(updates))
    return bool(changes)


def fill_remote_dimensions(remote, *, actor=None):
    count = 0
    for connection in remote.connections.filter(active=True).select_related("cd", "tech", "integration__operator"):
        product = connection.product
        if product.is_archived:
            continue
        dimensions = remote.snapshot.get("offer", {}).get("weightDimensions") or {}
        count += int(save_dimensions(product, dimensions, actor=actor or connection.integration.operator,
                     only_missing=True, source=f"Яндекс Маркет · {remote.offer_id}"))
    return count


def fill_integration_dimensions(integration, *, actor):
    count = 0
    for connection in integration.connections.filter(active=True).select_related("cd", "tech", "remote_offer"):
        if connection.product.is_archived:
            continue
        dimensions = connection.content.get("weightDimensions") or connection.remote_offer.snapshot.get("offer", {}).get("weightDimensions") or {}
        count += int(save_dimensions(connection.product, dimensions, actor=actor, only_missing=True,
                     source=f"Яндекс Маркет · {connection.remote_offer.offer_id}"))
    return count
