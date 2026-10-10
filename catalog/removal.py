"""Единое безопасное удаление карточек CD и Tech.

Новые связи с товаром по умолчанию считаются историей: только перечисленные
технические связи разрешено удалять вместе с никогда не использованной карточкой.
"""

import re
from dataclasses import dataclass

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from integrations.models import AvitoListingConnection, AvitoProductProfile
from warehouse.models import Warehouse, WarehouseTransfer

from .models import BarcodeRegistry, CD, ProductRemovalEvent, Tech


HAS_BARCODE = "HAS_BARCODE"
HAS_AVITO_CONNECTION = "HAS_AVITO_CONNECTION"
HAS_YANDEX_CONNECTION = "HAS_YANDEX_CONNECTION"
HAS_STOCK = "HAS_STOCK"
ALREADY_ARCHIVED = "ALREADY_ARCHIVED"
HAS_DEPENDENCIES = "HAS_DEPENDENCIES"

BLOCK_MESSAGES = {
    HAS_YANDEX_CONNECTION: "Нельзя удалить товар с активной связью Яндекс Маркета. Сначала отключите связь в интеграции.",
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
    "warehouse_stocks", "consignment_stocks", "supplier_prices", "change_events", "avito_profile", "barcodes",
    "catalog_images",
})


@dataclass(frozen=True)
class RemovalAssessment:
    action: str
    reasons: tuple[str, ...] = ()
    history_relations: tuple[str, ...] = ()


@dataclass(frozen=True)
class BulkRemovalItem:
    product_kind: str
    product_id: int
    product_name: str
    action: str
    messages: tuple[str, ...] = ()


def normalize_removal_selection(selection):
    """Проверяет весь список до начала удаления и убирает повторные ID."""
    if not isinstance(selection, (list, tuple)) or not selection:
        raise ValidationError("Выберите хотя бы один товар.")
    if len(selection) > 10000:
        raise ValidationError("За один раз можно выбрать не более 10 000 товаров.")
    tokens = []
    seen = set()
    for token in selection:
        if not isinstance(token, str) or not re.fullmatch(r"(?:cd|tech):[1-9][0-9]{0,18}", token):
            raise ValidationError("Некорректный список выбранных товаров. Обновите страницу и повторите выбор.")
        kind, value = token.split(":")
        product_id = int(value)
        if product_id > 9223372036854775807:
            raise ValidationError("Некорректный ID товара.")
        key = (kind, product_id)
        if key not in seen:
            seen.add(key)
            tokens.append(token)
    return tuple(tokens)


@transaction.atomic
def remove_products(*, selection, actor):
    """Удаляет группу штатным сервисом; защищённые карточки остаются с пояснением."""
    tokens = normalize_removal_selection(selection)
    kinds = {token.split(":", 1)[0] for token in tokens}
    if not actor.is_authenticated or any(
        not (actor.is_superuser or actor.has_perm(f"catalog.delete_{kind}"))
        for kind in kinds
    ):
        # Проверяем всю группу заранее: недостаток прав не должен дать частичное удаление.
        raise PermissionDenied("Нет права удаления выбранного типа товаров.")
    list(Warehouse.objects.select_for_update().order_by("pk"))
    results = []
    product_keys = [(kind, int(value)) for kind, value in (token.split(":") for token in tokens)]
    for kind, product_id in sorted(product_keys):
        model = CD if kind == "cd" else Tech
        product = model.objects.select_for_update().filter(pk=product_id).only("name").first()
        if product is None:
            results.append(BulkRemovalItem(kind, product_id, "Товар не найден", "BLOCKED", (
                "Карточка уже удалена или больше не существует.",
            )))
            continue
        try:
            # Отдельный savepoint откатывает очистку технических связей при отказе FK.
            assessment = remove_product(product_kind=kind, product_id=product_id, actor=actor)
        except ValidationError as exc:
            results.append(BulkRemovalItem(kind, product_id, product.name, "BLOCKED", tuple(exc.messages)))
        else:
            results.append(BulkRemovalItem(
                kind, product_id, product.name, assessment.action,
                tuple(BLOCK_MESSAGES[reason] for reason in assessment.reasons),
            ))
    return tuple(results)


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
        if relation.related_model.objects.filter(**{relation.field.name: product}).exists():
            found.append(accessor)
    return tuple(found)


def evaluate_product_removal(product):
    kind = _product_kind(product)
    reasons = []
    if product.is_archived:
        reasons.append(ALREADY_ARCHIVED)
    if BarcodeRegistry.objects.filter(**{kind: product}).exists():
        reasons.append(HAS_BARCODE)
    if AvitoListingConnection.objects.filter(**{f"profile__{kind}_id": product.pk}).exists():
        reasons.append(HAS_AVITO_CONNECTION)
    if product.yandex_connections.filter(active=True).exists():
        reasons.append(HAS_YANDEX_CONNECTION)
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
        media_files = []
        if product.title_image.name:
            media_files.append((product.title_image.storage, product.title_image.name))
        media_files.extend(
            (image.image.storage, image.image.name)
            for image in product.catalog_images.all()
            if image.image.name
        )
        product.change_events.all().delete()
        product.supplier_prices.all().delete()
        product.warehouse_stocks.all().delete()
        product.consignment_stocks.all().delete()
        AvitoProductProfile.objects.filter(**{product_kind: product}).delete()
        try:
            product.delete()
        except ProtectedError:
            raise ValidationError(BLOCK_MESSAGES[HAS_DEPENDENCIES])
        for storage, name in media_files:
            transaction.on_commit(lambda storage=storage, name=name: storage.delete(name))
    ProductRemovalEvent.objects.create(**snapshot)
    return assessment
