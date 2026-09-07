"""Изменение текущих продажных и поставщицких цен."""
import logging
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction

from catalog.models import CD, Tech
from catalog.audit import changed_snapshots, product_snapshot, record_product_changes
from catalog.models import ProductChangeEvent
from partners.models import Supplier
from .models import SupplierCDPrice, SupplierTechPrice

logger = logging.getLogger("gamebat.business")


def _price(value, *, nullable, precision):
    if nullable and value in (None, ""):
        return None
    try:
        result = Decimal(str(value)).quantize(precision, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError("Укажите корректную цену.") from exc
    if result < 0:
        raise ValidationError("Цена не может быть отрицательной.")
    return result


def product_configuration(product_type):
    if product_type == "cd":
        return CD, SupplierCDPrice, "cd"
    if product_type == "tech":
        return Tech, SupplierTechPrice, "tech"
    raise ValidationError("Выберите существующий товар.")


@transaction.atomic
def update_product_prices(*, actor, product_type, product_id, changes, record_audit=True):
    product_model, _, _ = product_configuration(product_type)
    try:
        product = product_model.objects.select_for_update().get(pk=product_id)
    except (product_model.DoesNotExist, TypeError, ValueError) as exc:
        raise ValidationError("Товар не найден.") from exc
    allowed = {"retail_price", "wholesale_price", "yandex_market_price"}
    updates = {}
    for field, value in changes.items():
        if field not in allowed:
            raise ValidationError("Неизвестный тип цены.")
        updates[field] = _price(value, nullable=True, precision=Decimal("0.01"))
    if not updates:
        raise ValidationError("Не выбраны цены для изменения.")
    before = product_snapshot(product, updates)
    for field, value in updates.items():
        setattr(product, field, value)
    # Legacy catalog rows may legitimately have blank fields (for example, a
    # barcode).  Editing prices must not revalidate and block the whole old
    # product card; validate only the fields changed by this operation.  Model
    # validators and the relevant price constraints are still applied.
    excluded_fields = [
        field.name
        for field in product._meta.fields
        if field.name not in updates
    ]
    product.full_clean(exclude=excluded_fields)
    product.save(update_fields=tuple(updates))
    if record_audit:
        try:
            record_product_changes(
                actor=actor,
                instance=product,
                changes=changed_snapshots(product, before, updates),
                source=ProductChangeEvent.Source.CRM,
            )
        except Exception:
            logger.exception(
                "Ошибка сохранения истории цен товара: user_id=%s type=%s product_id=%s",
                actor.pk, product_type, product.pk,
            )
            raise
    logger.info(
        "Продажные цены изменены: user_id=%s type=%s product_id=%s fields=%s",
        actor.pk, product_type, product.pk, ",".join(updates),
    )
    return product


@transaction.atomic
def update_supplier_price(*, actor, product_type, product_id, supplier_id, value):
    product_model, price_model, product_field = product_configuration(product_type)
    try:
        product = product_model.objects.get(pk=product_id)
        supplier = Supplier.objects.get(pk=supplier_id)
    except (product_model.DoesNotExist, Supplier.DoesNotExist, TypeError, ValueError) as exc:
        raise ValidationError("Товар или поставщик не найден.") from exc
    price = _price(value, nullable=False, precision=Decimal("0.000001"))
    lookup = {"supplier": supplier, product_field: product}
    result, _ = price_model.objects.update_or_create(**lookup, defaults={"price": price})
    logger.info(
        "Цена поставщика изменена: user_id=%s supplier_id=%s type=%s product_id=%s value=%s",
        actor.pk, supplier.pk, product_type, product.pk, price,
    )
    return result
