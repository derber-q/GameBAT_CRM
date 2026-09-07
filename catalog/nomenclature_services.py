"""Атомарное редактирование карточек номенклатуры."""
import logging
from dataclasses import dataclass

from django.db import transaction

from pricing.services import update_product_prices
from warehouse.models import CDWarehouseStock, TechWarehouseStock

from .audit import changed_snapshots, product_snapshot, record_product_changes, stock_change
from .models import CD, ProductChangeEvent, Tech
from .nomenclature_forms import CDCardForm, TechCardForm, product_version
from .product_fields import CD_CARD_FIELDS, PRICE_FIELDS, TECH_CARD_FIELDS

logger = logging.getLogger("gamebat.business")


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
def update_product_card(*, actor, product_kind, product_id, data):
    model, form_class, audited_fields, related_fields, stock_model, stock_product_field = product_configuration(
        product_kind
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
    product_fields = [field for field in changed_fields if field in audited_fields]
    if not product_fields and not stock_fields:
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
        stock_changes.append(stock_change(
            warehouse=warehouse,
            old_quantity=old_quantity,
            new_quantity=quantity,
        ))
        changed_warehouses.append(str(warehouse_id))

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
