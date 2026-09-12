"""Атомарное редактирование карточек номенклатуры."""
import logging
from dataclasses import dataclass

from django.db import transaction

from pricing.services import update_product_prices
from warehouse.models import CDWarehouseStock, TechWarehouseStock, Warehouse
from warehouse.storage_services import clear_storage_locations_if_zero, update_storage_locations

from .audit import changed_snapshots, field_change, product_snapshot, record_product_changes, stock_change
from .models import CD, ProductChangeEvent, Tech
from .nomenclature_forms import CDCardForm, TechCardForm, product_version
from .product_fields import CD_CARD_FIELDS, PRICE_FIELDS, TECH_CARD_FIELDS

logger = logging.getLogger("gamebat.business")


CREATE_FIELDS = {
    "cd": ("platform", "name", "description", "sku", "barcode", "cusa_ppsa_code", "comment"),
    "tech": ("brand", "product_type", "name", "description", "sku", "barcode", "comment"),
}


@dataclass
class ProductUpdateResult:
    product: object
    form: object
    saved: bool = False
    stale: bool = False


def product_configuration(product_kind):
    if product_kind == "cd":
        return CD, CDCardForm, CD_CARD_FIELDS, ("platform",), CDWarehouseStock, "cd"
    if product_kind == "tech":
        return Tech, TechCardForm, TECH_CARD_FIELDS, ("brand", "product_type"), TechWarehouseStock, "tech"
    raise ValueError("Неизвестный тип товара.")


@transaction.atomic
def create_product(*, actor, product_kind, data):
    """Атомарно создаёт номенклатурную карточку с нулевым системным состоянием и audit."""
    if product_kind not in CREATE_FIELDS:
        raise ValueError("Неизвестный тип товара.")
    model = CD if product_kind == "cd" else Tech
    product = model(**{field: data[field] for field in CREATE_FIELDS[product_kind]})
    product.full_clean()
    product.save()
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
def update_product_card(*, actor, product_kind, product_id, data):
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
    locked_stocks = list(
        stock_model.objects.select_for_update().filter(
            **{stock_product_field: product}
        ).select_related("warehouse")
    )
    stocks_by_warehouse = {stock.warehouse_id: stock for stock in locked_stocks}
    current_version = product_version(product)
    before = product_snapshot(product, audited_fields)
    form = form_class(data, instance=product, user=actor)
    if not form.is_valid():
        if form.forbidden_fields:
            logger.warning(
                "Отклонена попытка изменения защищённых полей: user_id=%s type=%s product_id=%s fields=%s",
                actor.pk,
                product_kind,
                product.pk,
                ",".join(form.forbidden_fields),
            )
        return ProductUpdateResult(product=product, form=form)
    if form.cleaned_data["version"] != current_version:
        form.add_error(
            None,
            "Карточка уже была изменена другим пользователем. Обновите страницу и повторите изменения.",
        )
        return ProductUpdateResult(product=product, form=form, stale=True)

    changed_fields = [field for field in form.changed_data if field in form.allowed_fields]
    stock_fields = [field for field in changed_fields if field.startswith("stock_")]
    storage_location_fields = [
        field for field in changed_fields if field.startswith("storage_location_")
    ]
    product_fields = [field for field in changed_fields if field in audited_fields]
    if not product_fields and not stock_fields and not storage_location_fields:
        return ProductUpdateResult(product=product, form=form)

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

    changes = changed_snapshots(product, before, product_fields) + stock_changes
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
    return ProductUpdateResult(product=product, form=form, saved=True)
