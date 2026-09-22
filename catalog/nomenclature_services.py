"""Атомарное редактирование карточек номенклатуры."""
import logging
from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from pricing.services import update_product_prices
from warehouse.models import CDWarehouseStock, TechWarehouseStock, Warehouse
from warehouse.storage_services import clear_storage_locations_if_zero, update_storage_locations

from .audit import changed_snapshots, field_change, product_snapshot, record_product_changes, stock_change
from .models import CD, ProductChangeEvent, Tech
from .nomenclature_forms import CDCardForm, TechCardForm, barcode_formset, product_version
from .product_identifiers import ensure_product_article, save_barcode_formset
from .product_fields import CD_CARD_FIELDS, PRICE_FIELDS, TECH_CARD_FIELDS

logger = logging.getLogger("gamebat.business")


CREATE_FIELDS = {
    "cd": (
        "platform", "game_series", "name", "description", "sku", "cusa_ppsa_code",
        "weight_grams", "comment",
    ),
    "tech": (
        "brand", "product_type", "name", "description", "sku",
        "weight_grams", "comment",
    ),
}


@dataclass
class ProductUpdateResult:
    product: object
    form: object
    saved: bool = False
    stale: bool = False
    barcode_formset: object = None


def product_configuration(product_kind):
    if product_kind == "cd":
        return CD, CDCardForm, CD_CARD_FIELDS, ("platform", "game_series"), CDWarehouseStock, "cd"
    if product_kind == "tech":
        return Tech, TechCardForm, TECH_CARD_FIELDS, ("brand", "product_type"), TechWarehouseStock, "tech"
    raise ValueError("Неизвестный тип товара.")


@transaction.atomic
def create_product(*, actor, product_kind, data, barcode_formset_instance=None):
    """Атомарно создаёт номенклатурную карточку с нулевым системным состоянием и audit."""
    if product_kind not in CREATE_FIELDS:
        raise ValueError("Неизвестный тип товара.")
    model = CD if product_kind == "cd" else Tech
    values = {
        field: data[field]
        for field in CREATE_FIELDS[product_kind]
        if field in data
    }
    product = model(**values)
    product.full_clean()
    product.save()
    ensure_product_article(product)
    barcode_changes = save_barcode_formset(product=product, formset=barcode_formset_instance)
    legacy_barcode = str(data.get("barcode") or "").strip()
    if barcode_formset_instance is None and legacy_barcode:
        from .models import BarcodeRegistry

        try:
            BarcodeRegistry.objects.create(
                value=legacy_barcode,
                product_kind=product_kind,
                **({"cd": product} if product_kind == "cd" else {"tech": product}),
            )
        except IntegrityError as exc:
            raise ValidationError({
                "barcode": "Этот штрихкод уже используется другим товаром."
            }) from exc
        barcode_changes.append(field_change(
            field_name="barcode_added", field_label="Штрихкод добавлен",
            old_value="", new_value=legacy_barcode,
        ))
    changes = [field_change(
        field_name="created",
        field_label="Товар создан",
        old_value="",
        new_value="CD" if product_kind == "cd" else "Tech",
    )]
    snapshot = product_snapshot(product, CREATE_FIELDS[product_kind])
    changes.extend(
        field_change(
            field_name=field_name,
            field_label=str(product._meta.get_field(field_name).verbose_name),
            old_value="",
            new_value=value,
        )
        for field_name, value in snapshot.items()
        if value
    )
    changes.extend(barcode_changes)
    record_product_changes(
        actor=actor,
        instance=product,
        changes=changes,
        source=ProductChangeEvent.Source.NOMENCLATURE,
    )
    logger.info(
        "Товар создан: user_id=%s type=%s product_id=%s",
        actor.pk, product_kind, product.pk,
    )
    return product


@transaction.atomic
def update_product_card(*, actor, product_kind, product_id, data, barcode_data=None):
    model, form_class, audited_fields, related_fields, stock_model, stock_product_field = product_configuration(
        product_kind
    )
    location_warehouse_ids = sorted({
        int(field_name.removeprefix("storage_location_"))
        for field_name in data
        if field_name.startswith("storage_location_")
        and field_name.removeprefix("storage_location_").isdigit()
    })
    if location_warehouse_ids:
        # Общий порядок блокировок: Warehouse → Product → WarehouseStock.
        list(
            Warehouse.objects.select_for_update().filter(
                pk__in=location_warehouse_ids
            ).order_by("pk")
        )
    product = model.objects.select_for_update().select_related(*related_fields).get(pk=product_id)
    if product.is_archived:
        raise ValidationError("Удалённый товар нельзя изменять.")
    locked_stocks = list(
        stock_model.objects.select_for_update().filter(
            **{stock_product_field: product}
        ).select_related("warehouse")
    )
    stocks_by_warehouse = {stock.warehouse_id: stock for stock in locked_stocks}
    current_version = product_version(product)
    before = product_snapshot(product, audited_fields)
    form_data = data.copy()
    if barcode_data is not None:
        for key in list(form_data.keys()):
            if key.startswith("barcodes-"):
                del form_data[key]
    form = form_class(form_data, instance=product, user=actor)
    barcode_formset_instance = barcode_formset(data=barcode_data, product=product) if barcode_data is not None else None
    form_valid = form.is_valid()
    barcodes_valid = barcode_formset_instance is None or barcode_formset_instance.is_valid()
    if not form_valid or not barcodes_valid:
        if form.forbidden_fields:
            logger.warning(
                "Отклонена попытка изменения защищённых полей: user_id=%s type=%s product_id=%s fields=%s",
                actor.pk,
                product_kind,
                product.pk,
                ",".join(form.forbidden_fields),
            )
        return ProductUpdateResult(product=product, form=form, barcode_formset=barcode_formset_instance)
    if form.cleaned_data["version"] != current_version:
        form.add_error(
            None,
            "Карточка уже была изменена другим пользователем. Обновите страницу и повторите изменения.",
        )
        return ProductUpdateResult(product=product, form=form, stale=True, barcode_formset=barcode_formset_instance)

    changed_fields = [field for field in form.changed_data if field in form.allowed_fields]
    stock_fields = [field for field in changed_fields if field.startswith("stock_")]
    storage_location_fields = [
        field for field in changed_fields if field.startswith("storage_location_")
    ]
    product_fields = [field for field in changed_fields if field in audited_fields]
    barcodes_changed = bool(barcode_formset_instance and barcode_formset_instance.has_changed())
    if not product_fields and not stock_fields and not storage_location_fields and not barcodes_changed:
        return ProductUpdateResult(product=product, form=form, barcode_formset=barcode_formset_instance)

    for field_name in storage_location_fields:
        warehouse_id = int(field_name.removeprefix("storage_location_"))
        stock = stocks_by_warehouse.get(warehouse_id)
        current_quantity = stock.quantity if stock is not None else 0
        final_quantity = form.cleaned_data.get(f"stock_{warehouse_id}", current_quantity)
        if form.cleaned_data[field_name] and final_quantity <= 0:
            form.add_error(
                field_name,
                "Место хранения можно указать только для товара с положительным остатком на складе.",
            )
    if form.errors:
        return ProductUpdateResult(product=product, form=form)

    product = form.save(commit=False)
    card_fields = [field for field in product_fields if field not in PRICE_FIELDS]
    price_fields = [field for field in product_fields if field in PRICE_FIELDS]
    if card_fields:
        product.save(update_fields=tuple(card_fields))
    if price_fields:
        update_product_prices(
            actor=actor,
            product_type=product_kind,
            product_id=product.pk,
            changes={field: form.cleaned_data[field] for field in price_fields},
            record_audit=False,
        )
    changed_warehouses = []
    stock_changes = []
    for field_name in stock_fields:
        warehouse_id = int(field_name.removeprefix("stock_"))
        quantity = form.cleaned_data[field_name]
        warehouse = form.warehouses_by_id[warehouse_id]
        stock = stocks_by_warehouse.get(warehouse_id)
        old_quantity = stock.quantity if stock is not None else 0
        if stock is None:
            if quantity == 0:
                continue
            stock_model.objects.create(
                warehouse_id=warehouse_id,
                quantity=quantity,
                **{stock_product_field: product},
            )
        else:
            stock.quantity = quantity
            stock.full_clean()
            stock.save(update_fields=("quantity",))
            clear_storage_locations_if_zero(
                stock=stock,
                actor=actor,
                source=ProductChangeEvent.Source.NOMENCLATURE,
            )
        stock_changes.append(stock_change(
            warehouse=warehouse,
            old_quantity=old_quantity,
            new_quantity=quantity,
        ))
        changed_warehouses.append(str(warehouse_id))

    for field_name in storage_location_fields:
        warehouse_id = int(field_name.removeprefix("storage_location_"))
        stock = stock_model.objects.filter(
            warehouse_id=warehouse_id,
            **{f"{stock_product_field}_id": product.pk},
        ).first()
        if stock is None or stock.quantity <= 0:
            # Пустое значение уже обеспечено zero-stock cleanup и не требует повторного Save.
            continue
        update_storage_locations(
            actor=actor,
            warehouse_id=warehouse_id,
            product_type=product_kind,
            product_id=product.pk,
            raw_value=form.cleaned_data[field_name],
            source=ProductChangeEvent.Source.NOMENCLATURE,
        )

    barcode_changes = save_barcode_formset(product=product, formset=barcode_formset_instance)
    changes = changed_snapshots(product, before, product_fields) + stock_changes + barcode_changes
    try:
        record_product_changes(
            actor=actor,
            instance=product,
            changes=changes,
            source=ProductChangeEvent.Source.NOMENCLATURE,
        )
    except Exception:
        logger.exception(
            "Ошибка сохранения истории товара: user_id=%s type=%s product_id=%s",
            actor.pk,
            product_kind,
            product.pk,
        )
        raise
    if changes:
        logger.info(
            "Карточка товара изменена: user_id=%s type=%s product_id=%s fields=%s",
            actor.pk,
            product_kind,
            product.pk,
            ",".join(change["field_name"] for change in changes),
        )
    if changed_warehouses:
        logger.info(
            "Складские остатки товара скорректированы: user_id=%s type=%s product_id=%s warehouses=%s",
            actor.pk,
            product_kind,
            product.pk,
            ",".join(changed_warehouses),
        )
    return ProductUpdateResult(
        product=product, form=form, saved=True, barcode_formset=barcode_formset_instance,
    )
