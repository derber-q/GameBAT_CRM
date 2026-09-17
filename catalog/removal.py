"""Единое безопасное удаление карточек CD и Tech.

Новые связи с товаром по умолчанию считаются историей: только перечисленные
технические связи разрешено удалять вместе с никогда не использованной карточкой.
"""

from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from integrations.models import AvitoListingConnection, AvitoProductProfile
from warehouse.models import Warehouse, WarehouseTransfer

from .models import BarcodeRegistry, CD, ProductRemovalEvent, Tech


HAS_BARCODE = "HAS_BARCODE"
HAS_AVITO_CONNECTION = "HAS_AVITO_CONNECTION"
HAS_STOCK = "HAS_STOCK"
ALREADY_ARCHIVED = "ALREADY_ARCHIVED"
HAS_DEPENDENCIES = "HAS_DEPENDENCIES"

BLOCK_MESSAGES = {
    HAS_BARCODE: "Нельзя удалить товар, которому присвоен штрихкод.",
    HAS_AVITO_CONNECTION: (
        "Нельзя удалить товар, пока он связан с объявлением Avito. "
        "Сначала удалите или перепривяжите связь в разделе Интеграции → Avito."
    ),
    HAS_STOCK: "Нельзя удалить товар с ненулевым остатком на складе, реализации или в перемещении.",
    ALREADY_ARCHIVED: "Товар уже удалён из активной номенклатуры.",
    HAS_DEPENDENCIES: "Удаление заблокировано связанными данными товара.",
}

TECHNICAL_RELATIONS = frozenset({
    "warehouse_stocks", "consignment_stocks", "supplier_prices", "change_events", "avito_profile",
})


@dataclass(frozen=True)
class RemovalAssessment:
    action: str
    reasons: tuple[str, ...] = ()
    history_relations: tuple[str, ...] = ()


def _product_kind(product):
    if isinstance(product, CD):
        return "cd"
    if isinstance(product, Tech):
        return "tech"
    raise TypeError("Удаление поддерживается только для CD и Tech.")


def has_product_history(product):
    """Возвращает реальные бизнес-связи; неизвестная новая связь безопасно считается историей."""
    _product_kind(product)
    found = []
    if product.change_events.exclude(action_kind="").exists():
        found.append("change_events:operation")
    if product.change_events.filter(field_changes__field_name__startswith="warehouse_stock_").exists():
        found.append("change_events:stock_adjustment")
    avito_profile = AvitoProductProfile.objects.filter(**{_product_kind(product): product}).first()
    if avito_profile and (
        avito_profile.photos.exists() or avito_profile.sync_jobs.exists()
        or avito_profile.sync_logs.exists() or avito_profile.sell_on_avito
        or avito_profile.listing_title or avito_profile.listing_description
        or avito_profile.category_slug or avito_profile.category_name
        or avito_profile.attributes or avito_profile.schema_snapshot
        or avito_profile.sync_status != AvitoProductProfile.SyncStatus.IDLE
        or avito_profile.last_error or avito_profile.last_successful_sync_at
        or avito_profile.desired_state_hash
    ):
        found.append("avito_profile:history")
    for relation in product._meta.related_objects:
        accessor = relation.get_accessor_name()
        if accessor in TECHNICAL_RELATIONS:
            continue
        if accessor == "barcode_registration":
            # Сам реестр проверяется как blocker, а не как бизнес-история.
            continue
        if relation.related_model.objects.filter(**{relation.field.name: product}).exists():
            found.append(accessor)
    return tuple(found)


def evaluate_product_removal(product):
    kind = _product_kind(product)
    reasons = []
    if product.is_archived:
        reasons.append(ALREADY_ARCHIVED)
    if str(product.barcode or "").strip() or BarcodeRegistry.objects.filter(**{kind: product}).exists():
        reasons.append(HAS_BARCODE)
    if AvitoListingConnection.objects.filter(**{f"profile__{kind}_id": product.pk}).exists():
        reasons.append(HAS_AVITO_CONNECTION)
    if (
        product.quantity_on_consignment > 0
        or product.warehouse_stocks.filter(quantity__gt=0).exists()
        or product.consignment_stocks.filter(quantity__gt=0).exists()
        or product.warehouse_transfer_items.filter(
            transfer__status__in=(
                WarehouseTransfer.Status.CREATED,
                WarehouseTransfer.Status.ASSEMBLED,
                WarehouseTransfer.Status.SHIPPED,
            )
        ).exists()
    ):
        reasons.append(HAS_STOCK)
    if reasons:
        return RemovalAssessment("BLOCKED", tuple(reasons))
    history = has_product_history(product)
    return RemovalAssessment("ARCHIVED" if history else "HARD_DELETED", history_relations=history)


@transaction.atomic
def remove_product(*, product_kind, product_id, actor):
    if product_kind not in {"cd", "tech"}:
        raise ValidationError("Неизвестный тип товара.")
    # Операции прихода/продажи сначала блокируют Warehouse, затем Product.
    list(Warehouse.objects.select_for_update().order_by("pk"))
    model = CD if product_kind == "cd" else Tech
    product = model.objects.select_for_update().get(pk=product_id)
    list(product.warehouse_stocks.select_for_update())
    list(product.consignment_stocks.select_for_update())
    assessment = evaluate_product_removal(product)
    if assessment.action == "BLOCKED":
        return assessment

    snapshot = dict(
        action=ProductRemovalEvent.Action.ARCHIVE if assessment.action == "ARCHIVED"
        else ProductRemovalEvent.Action.HARD_DELETE,
        product_kind=product_kind, product_id=product.pk,
        product_sku=product.sku, product_name=product.name,
        reason=", ".join(assessment.history_relations) if assessment.history_relations else "Нет бизнес-истории",
        actor=actor,
    )
    if assessment.action == "ARCHIVED":
        product.is_archived = True
        product.archived_at = timezone.now()
        product.archived_by = actor
        product.save(update_fields=("is_archived", "archived_at", "archived_by"))
    else:
        # Только технические нулевые данные; все бизнес-FK остаются PROTECT.
        product.change_events.all().delete()
        product.supplier_prices.all().delete()
        product.warehouse_stocks.all().delete()
        product.consignment_stocks.all().delete()
        AvitoProductProfile.objects.filter(**{product_kind: product}).delete()
        try:
            product.delete()
        except ProtectedError:
            raise ValidationError(BLOCK_MESSAGES[HAS_DEPENDENCIES])
    ProductRemovalEvent.objects.create(**snapshot)
    return assessment
