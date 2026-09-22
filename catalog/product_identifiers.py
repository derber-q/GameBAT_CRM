"""Атомарные операции с весом, артикулами и общим реестром штрихкодов."""
import base64
import secrets
import string
from io import BytesIO

import barcode
from barcode.writer import SVGWriter
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from .audit import field_change, record_product_changes
from .models import BarcodeRegistry, CD, ProductChangeEvent, Tech


BARCODE_LENGTH = 12
BARCODE_ATTEMPTS = 64


def product_configuration(product_kind):
    if product_kind == "cd":
        return CD, "CD"
    if product_kind == "tech":
        return Tech, "TECH"
    raise ValidationError("Неизвестный тип товара.")


def _registry_lookup(product):
    return {"cd": product} if isinstance(product, CD) else {"tech": product}


def validate_barcode_uniqueness(*, product, barcode):
    barcode = str(barcode or "").strip()
    if not barcode:
        return ""
    registry = BarcodeRegistry.objects.filter(value=barcode)
    if product.pk:
        if isinstance(product, CD):
            registry = registry.exclude(cd_id=product.pk)
        else:
            registry = registry.exclude(tech_id=product.pk)
    if registry.exists():
        raise ValidationError({
            "barcode": "Этот штрихкод уже используется другим товаром."
        })
    return barcode


def set_product_barcode(*, product, barcode):
    """Compatibility helper: replaces all product barcodes with one value."""
    barcode = validate_barcode_uniqueness(product=product, barcode=barcode)
    lookup = _registry_lookup(product)
    try:
        with transaction.atomic():
            BarcodeRegistry.objects.select_for_update().filter(**lookup).delete()
            if barcode:
                BarcodeRegistry.objects.create(
                    value=barcode,
                    product_kind=product._meta.model_name,
                    **lookup,
                )
    except (IntegrityError, ValidationError) as exc:
        raise ValidationError({
            "barcode": "Этот штрихкод уже используется другим товаром."
        }) from exc
    return product


def save_barcode_formset(*, product, formset):
    """Saves a validated barcode formset and returns audit field changes."""
    if formset is None:
        return []
    changes = []
    lookup = _registry_lookup(product)
    existing = {
        item.pk: item
        for item in BarcodeRegistry.objects.select_for_update().filter(**lookup)
    }
    # Release values marked for deletion before inserting replacements in the
    # same request; the database uniqueness constraint remains authoritative.
    for form in formset.forms:
        if not form.cleaned_data or not form.cleaned_data.get("DELETE"):
            continue
        instance = existing.pop(form.cleaned_data.get("id"), None)
        if instance:
            value = instance.value
            instance.delete()
            changes.append(field_change(
                field_name="barcode_removed", field_label="Штрихкод удалён",
                old_value=value, new_value="",
            ))
    for form in formset.forms:
        if not form.cleaned_data:
            continue
        barcode_id = form.cleaned_data.get("id")
        instance = existing.get(barcode_id) if barcode_id else None
        old_value = instance.value if instance else ""
        if form.cleaned_data.get("DELETE"):
            continue
        value = form.cleaned_data.get("value")
        if not value:
            continue
        if instance is None:
            instance = BarcodeRegistry(product_kind=product._meta.model_name, **lookup)
        if old_value != value:
            instance.value = value
            instance.save()
        if not old_value:
            changes.append(field_change(
                field_name="barcode_added",
                field_label="Штрихкод добавлен",
                old_value="",
                new_value=value,
            ))
        elif old_value != value:
            changes.append(field_change(
                field_name="barcode_changed",
                field_label="Штрихкод изменён",
                old_value=old_value,
                new_value=value,
            ))
    return changes


def ensure_product_article(product):
    """Генерирует стабильный артикул только для новой карточки с пустым значением."""
    if str(product.sku or "").strip():
        product.sku = product.sku.strip()
        return product.sku
    prefix = "CD" if isinstance(product, CD) else "TECH"
    base = f"{prefix}-{product.pk:06d}"
    candidate = base
    suffix = 2
    while CD.objects.filter(sku=candidate).exclude(pk=product.pk).exists() or Tech.objects.filter(
        sku=candidate
    ).exclude(pk=product.pk).exists():
        candidate = f"{base}-{suffix}"
        suffix += 1
    product.sku = candidate
    product.save(update_fields=("sku",))
    return candidate


def _positive_weight(value):
    raw = str(value or "").strip()
    if not raw.isdecimal():
        raise ValidationError("Вес должен быть целым числом граммов.")
    result = int(raw)
    if result <= 0:
        raise ValidationError("Вес должен быть не меньше 1 г.")
    return result


@transaction.atomic
def set_product_weight(*, actor, product_kind, product_id, weight_grams):
    model, _ = product_configuration(product_kind)
    try:
        product = model.objects.active().select_for_update().get(pk=product_id)
    except (model.DoesNotExist, TypeError, ValueError) as exc:
        raise ValidationError("Товар не найден.") from exc
    weight = _positive_weight(weight_grams)
    old_weight = product.weight_grams
    if old_weight == weight:
        return product
    product.weight_grams = weight
    excluded = [field.name for field in product._meta.fields if field.name != "weight_grams"]
    product.full_clean(exclude=excluded)
    product.save(update_fields=("weight_grams",))
    record_product_changes(
        actor=actor,
        instance=product,
        changes=[field_change(
            field_name="weight_grams",
            field_label="Вес, г",
            old_value=old_weight or "",
            new_value=weight,
        )],
        source=ProductChangeEvent.Source.CRM,
    )
    return product


@transaction.atomic
def generate_unique_barcode(*, actor, product_kind, product_id):
    model, _ = product_configuration(product_kind)
    try:
        product = model.objects.active().select_for_update().get(pk=product_id)
    except (model.DoesNotExist, TypeError, ValueError) as exc:
        raise ValidationError("Товар не найден.") from exc
    for _ in range(BARCODE_ATTEMPTS):
        candidate = "".join(secrets.choice(string.digits) for _ in range(BARCODE_LENGTH))
        if candidate == "0" * BARCODE_LENGTH:
            continue
        try:
            with transaction.atomic():
                BarcodeRegistry.objects.create(
                    value=candidate,
                    product_kind=product_kind,
                    **_registry_lookup(product),
                )
        except (IntegrityError, ValidationError):
            continue
        record_product_changes(
            actor=actor,
            instance=product,
            changes=[field_change(
                field_name="barcode_added",
                field_label="Штрихкод добавлен",
                old_value="",
                new_value=candidate,
            )],
            source=ProductChangeEvent.Source.NOMENCLATURE,
        )
        return product
    raise ValidationError("Не удалось сгенерировать уникальный штрихкод. Повторите попытку.")


def render_barcode_svg_data_url(value):
    """Возвращает настоящий Code 128 без человекочитаемой строки."""
    value = str(value or "").strip()
    if not value:
        raise ValidationError("У товара нет штрихкода для печати.")
    output = BytesIO()
    barcode.get("code128", value, writer=SVGWriter()).write(output, options={
        "module_width": 0.32,
        "module_height": 23,
        "quiet_zone": 2.5,
        "write_text": False,
        "font_size": 0,
        "background": "white",
        "foreground": "black",
    })
    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"
