import hashlib
import json
from decimal import Decimal
from decimal import InvalidOperation

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from .client import AvitoAPIError, AvitoClient
from .crypto import encrypt_secret
from .models import (
    AvitoListingConnection,
    AvitoProductProfile,
    AvitoRemoteListing,
    AvitoSyncLog,
    IntegrationAuditEvent,
    IntegrationCredential,
)
from .queue import enqueue_profile_sync_after_commit
from .schema import schema_fields


AUTOLOAD_UNAVAILABLE = (
    "Для аккаунта Avito недоступен Autoload API. Создание, управление публикацией, "
    "контентом и фотографиями невозможно до подключения доступа Avito Autoload."
)


def _remote_listing_is_active(status):
    return str(status or "").strip().lower() == "active"


def _remote_price(value):
    if value in (None, ""):
        return None
    try:
        price = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return price if price >= 0 else None


def _import_remote_price_if_empty(product, remote_price):
    if product.avito_price is not None or remote_price is None:
        return False
    product.avito_price = remote_price
    product.save(update_fields=("avito_price",))
    return True


def _delete_profile_photos(profile):
    files = [(photo.image.storage, photo.image.name) for photo in profile.photos.all() if photo.image.name]
    profile.photos.all().delete()
    for storage, name in files:
        transaction.on_commit(lambda storage=storage, name=name: storage.delete(name))


def _audit(action, *, actor=None, profile=None, details=None):
    IntegrationAuditEvent.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        product_kind=profile.product_kind if profile else "",
        product_id=profile.product_id if profile else None,
        details=details or {},
    )


def get_avito_credential():
    return IntegrationCredential.objects.filter(provider=IntegrationCredential.Provider.AVITO).first()


def save_avito_credentials(*, client_id, client_secret, actor=None):
    credential, _ = IntegrationCredential.objects.get_or_create(
        provider=IntegrationCredential.Provider.AVITO
    )
    if client_id:
        credential.encrypted_client_id = encrypt_secret(client_id.strip())
    if client_secret:
        credential.encrypted_client_secret = encrypt_secret(client_secret.strip())
    if not credential.is_configured:
        raise ValidationError("Нужно указать client_id и client_secret.")
    credential.status = IntegrationCredential.Status.NOT_CONFIGURED
    credential.last_error = ""
    credential.save()
    _audit("credentials_changed", actor=actor, details={"provider": "avito"})
    return check_avito_connection(credential=credential, actor=actor)


def check_avito_connection(*, credential=None, actor=None):
    credential = credential or get_avito_credential()
    if not credential or not credential.is_configured:
        raise ValidationError("Параметры Avito ещё не сохранены.")
    now = timezone.now()
    try:
        account = AvitoClient(credential).get_self()
    except AvitoAPIError as exc:
        credential.status = IntegrationCredential.Status.ERROR
        credential.last_error = str(exc)
        credential.last_checked_at = now
        credential.save(update_fields=("status", "last_error", "last_checked_at", "updated_at"))
        _audit("connection_error", actor=actor, details={"provider": "avito", "category": exc.category})
        raise
    credential.status = IntegrationCredential.Status.CONNECTED
    credential.account_id = str(account.get("id") or "")
    credential.account_name = str(account.get("name") or "")[:255]
    credential.last_error = ""
    credential.last_checked_at = now
    credential.last_success_at = now
    credential.save(update_fields=(
        "status", "account_id", "account_name", "last_error", "last_checked_at",
        "last_success_at", "updated_at",
    ))
    _audit("connection_checked", actor=actor, details={"provider": "avito", "success": True})
    return credential


def get_or_create_profile(product, product_kind):
    if product.is_archived:
        raise ValidationError("Удалённый товар нельзя использовать в интеграции Avito.")
    lookup = {product_kind: product}
    profile, _ = AvitoProductProfile.objects.get_or_create(**lookup)
    return profile


def global_stock(profile):
    return int(profile.product.warehouse_stocks.aggregate(total=Sum("quantity"))["total"] or 0)


def validate_profile(profile):
    errors = []
    if profile.sell_on_avito and (profile.product.avito_price is None or profile.product.avito_price <= 0):
        errors.append("Не заполнена корректная «Цена Avito».")
    elif profile.sell_on_avito and profile.product.avito_price != profile.product.avito_price.to_integral_value():
        errors.append("Цена Avito должна быть указана в целых рублях.")
    schema = profile.schema_snapshot or {}
    fields = schema_fields(schema)
    for field in fields if isinstance(fields, list) else []:
        if not isinstance(field, dict):
            continue
        key = field.get("name") or field.get("slug") or field.get("id")
        if field.get("required") and key and profile.attributes.get(str(key)) in (None, "", []):
            errors.append(f"Не заполнено обязательное поле Avito: {field.get('label') or key}.")
    return errors


def refresh_category_schema(profile):
    if not profile.category_slug:
        profile.schema_snapshot = {}
        return profile
    schema = AvitoClient().get_category_fields(profile.category_slug)
    profile.schema_snapshot = schema if isinstance(schema, dict) else {}
    return profile


def update_profile(*, profile, data, actor=None, refresh_schema=False):
    old_sell = profile.sell_on_avito
    old_values = {
        "listing_title": profile.listing_title,
        "listing_description": profile.listing_description,
        "category_slug": profile.category_slug,
        "attributes": profile.attributes,
    }
    profile.sell_on_avito = bool(data.get("sell_on_avito"))
    profile.listing_title = str(data.get("listing_title") or "").strip()
    profile.listing_description = str(data.get("listing_description") or "").strip()
    profile.category_slug = str(data.get("category_slug") or "").strip()
    profile.attributes = data.get("attributes") or {}
    if refresh_schema and profile.category_slug:
        refresh_category_schema(profile)
    profile.full_clean()
    profile.save()
    changed = old_values != {
        "listing_title": profile.listing_title,
        "listing_description": profile.listing_description,
        "category_slug": profile.category_slug,
        "attributes": profile.attributes,
    }
    _audit(
        "avito_profile_changed" if changed else "sell_on_avito_changed",
        actor=actor,
        profile=profile,
        details={"sell_on_avito": profile.sell_on_avito, "sell_changed": old_sell != profile.sell_on_avito},
    )
    enqueue_profile_sync_after_commit(profile.pk)
    return profile


def refresh_remote_listings():
    client = AvitoClient()
    # Список Avito иногда возвращает неполную пагинацию. Два независимых
    # прохода и объединение ID не позволят одному короткому ответу скрыть товар.
    found = {}
    for _ in range(2):
        for page in range(1, 101):
            data = client.list_items(page=page, per_page=100)
            resources = data.get("resources") if isinstance(data, dict) else None
            if not isinstance(resources, list):
                raise AvitoAPIError("Avito вернул некорректный список объявлений.", "temporary")
            for item in resources:
                try:
                    found[int(item["id"])] = item
                except (KeyError, TypeError, ValueError):
                    continue
            if len(resources) < 100:
                break
    if not found and AvitoListingConnection.objects.exists():
        raise AvitoAPIError("Avito вернул пустой список при наличии связанных объявлений.", "temporary")
    now = timezone.now()
    for item_id, item in found.items():
        safe_snapshot = {
            key: item.get(key) for key in ("id", "title", "category", "status", "url", "address", "price")
            if item.get(key) is not None
        }
        AvitoRemoteListing.objects.update_or_create(
            avito_item_id=item_id,
            defaults={
                "title": str(item.get("title") or "")[:500],
                "category_name": str(item.get("category") or "")[:255],
                "status": str(item.get("status") or "")[:64],
                "remote_price": _remote_price(item.get("price")),
                "url": str(item.get("url") or "")[:1000],
                "snapshot": safe_snapshot,
                "last_seen_at": now,
                "missing_since": None,
            },
        )
    missing = AvitoRemoteListing.objects.exclude(avito_item_id__in=found)
    missing.filter(missing_since__isnull=True).update(missing_since=now)
    credential = get_avito_credential()
    if credential and credential.account_id:
        # Absence from the paginated list is not proof of deletion: archived
        # listings must remain visible. Ask the item endpoint for its status.
        for listing in missing.filter(connection__isnull=True).exclude(status__iexact="removed"):
            try:
                details = client.get_item_details(credential.account_id, listing.avito_item_id)
            except AvitoAPIError as exc:
                if exc.status == 404:
                    continue  # Unknown/inaccessible is not a confirmed deletion.
                raise
            status = str(details.get("status") or "").strip().lower()
            if status:
                listing.status = status
                if status != "removed":
                    listing.missing_since = None
                listing.save(update_fields=("status", "missing_since"))
    return len(found)


def _remote_snapshot(listing):
    credential = get_avito_credential()
    if not credential or not credential.account_id:
        credential = check_avito_connection(credential=credential)
    client = AvitoClient(credential)
    if listing.missing_since:
        # Avito исключает объявления old из общего списка. Не пролистываем
        # заведомо бесполезные страницы и не расходуем лимит запросов.
        item = None
    else:
        try:
            item = client.find_item(listing.avito_item_id)
        except AvitoAPIError as exc:
            if exc.status != 404 or exc.category != "validation":
                raise
            item = None
    if item is None:
        # Сохранённые поля могут быть старыми; ниже точный ID обязательно
        # проверяется через API этого аккаунта, статус берётся из ответа API.
        if not listing.last_seen_at:
            raise AvitoAPIError(
                "Объявление не было получено из списка Avito. Обновите список объявлений и повторите привязку.",
                "validation", 404,
            )
        item = {
            "title": listing.title,
            "category": listing.category_name,
            "status": listing.status,
            "price": listing.remote_price,
        }
    details = client.get_item_details(credential.account_id, listing.avito_item_id)
    return {
        "title": str(item.get("title") or listing.title),
        "category_name": str(item.get("category") or listing.category_name),
        "status": details.get("status") or item.get("status") or listing.status,
        "remote_price": _remote_price(item.get("price")),
        "details": {key: details.get(key) for key in ("status", "start_time", "finish_time") if key in details},
    }


def bind_listing(*, listing, product, product_kind, actor=None):
    snapshot = _remote_snapshot(listing)  # HTTP до открытия DB transaction.
    try:
        with transaction.atomic():
            listing = AvitoRemoteListing.objects.select_for_update().get(pk=listing.pk)
            if AvitoListingConnection.objects.filter(remote_listing=listing).exists():
                raise ValidationError("Это объявление уже связано с товаром.")
            profile = get_or_create_profile(product, product_kind)
            profile = AvitoProductProfile.objects.select_for_update().get(pk=profile.pk)
            if AvitoListingConnection.objects.filter(profile=profile).exists():
                raise ValidationError("Выбранный товар уже связан с другим объявлением.")
            listing.status = snapshot["status"]
            listing.save(update_fields=("status",))
            profile.listing_title = snapshot["title"]
            profile.category_name = snapshot["category_name"]
            profile.attributes = snapshot["details"]
            profile.sell_on_avito = _remote_listing_is_active(snapshot["status"])
            profile.sync_status = AvitoProductProfile.SyncStatus.IDLE
            profile.last_error = (
                "Avito Item API не предоставляет контент и фотографии объявления для импорта; "
                "доступные поля сохранены."
            )
            profile.full_clean()
            profile.save()
            price_imported = _import_remote_price_if_empty(product, snapshot.get("remote_price"))
            _delete_profile_photos(profile)
            connection = AvitoListingConnection.objects.create(profile=profile, remote_listing=listing)
            _audit(
                "listing_bound", actor=actor, profile=profile,
                details={"avito_item_id": listing.avito_item_id, "remote_price_imported": price_imported},
            )
            enqueue_profile_sync_after_commit(profile.pk)
            return connection
    except IntegrityError as exc:
        raise ValidationError("Объявление или товар уже были связаны другим пользователем.") from exc


def import_connection_price_if_empty(*, connection, actor=None):
    """Подтягивает цену для ранее созданной связи, не перезаписывая цену CRM."""
    snapshot = _remote_snapshot(connection.remote_listing)
    with transaction.atomic():
        connection = AvitoListingConnection.objects.select_for_update().select_related(
            "profile__cd", "profile__tech", "remote_listing"
        ).get(pk=connection.pk)
        product = connection.profile.product.__class__.objects.select_for_update().get(
            pk=connection.profile.product_id
        )
        imported = _import_remote_price_if_empty(product, snapshot.get("remote_price"))
        connection.remote_listing.remote_price = snapshot.get("remote_price")
        connection.remote_listing.save(update_fields=("remote_price",))
        if imported:
            _audit(
                "remote_price_imported", actor=actor, profile=connection.profile,
                details={"avito_item_id": connection.remote_listing.avito_item_id},
            )
            enqueue_profile_sync_after_commit(connection.profile_id)
        return imported, product.avito_price


def rebind_listing(*, connection, product, product_kind, actor=None):
    snapshot = _remote_snapshot(connection.remote_listing)  # HTTP до lock/transaction.
    try:
        with transaction.atomic():
            connection = AvitoListingConnection.objects.select_for_update().select_related(
                "profile", "remote_listing"
            ).get(pk=connection.pk)
            old_profile = AvitoProductProfile.objects.select_for_update().get(pk=connection.profile_id)
            target = get_or_create_profile(product, product_kind)
            target = AvitoProductProfile.objects.select_for_update().get(pk=target.pk)
            if target.pk == old_profile.pk:
                raise ValidationError("Объявление уже связано с этим товаром.")
            if AvitoListingConnection.objects.filter(profile=target).exists():
                raise ValidationError("Выбранный товар уже связан с другим объявлением.")
            connection.remote_listing.status = snapshot["status"]
            connection.remote_listing.save(update_fields=("status",))
            old_profile.sell_on_avito = False
            old_profile.listing_title = ""
            old_profile.listing_description = ""
            old_profile.category_slug = ""
            old_profile.category_name = ""
            old_profile.attributes = {}
            old_profile.schema_snapshot = {}
            old_profile.sync_status = AvitoProductProfile.SyncStatus.IDLE
            old_profile.last_error = ""
            old_profile.desired_state_hash = ""
            old_profile.save()
            _delete_profile_photos(old_profile)
            target.listing_title = snapshot["title"]
            target.category_name = snapshot["category_name"]
            target.attributes = snapshot["details"]
            target.sell_on_avito = _remote_listing_is_active(snapshot["status"])
            target.sync_status = AvitoProductProfile.SyncStatus.IDLE
            target.last_error = "Avito Item API предоставил только доступные метаданные объявления."
            target.full_clean()
            target.save()
            price_imported = _import_remote_price_if_empty(product, snapshot.get("remote_price"))
            _delete_profile_photos(target)
            connection.profile = target
            connection.save(update_fields=("profile", "updated_at"))
            _audit(
                "listing_rebound", actor=actor, profile=target,
                details={
                    "avito_item_id": connection.remote_listing.avito_item_id,
                    "old_product_id": old_profile.product_id,
                    "remote_price_imported": price_imported,
                },
            )
            enqueue_profile_sync_after_commit(target.pk)
            return connection
    except IntegrityError as exc:
        raise ValidationError("Перепривязка конфликтует с существующей связью.") from exc


@transaction.atomic
def unbind_listing(*, connection, actor=None):
    connection = AvitoListingConnection.objects.select_for_update().select_related(
        "remote_listing"
    ).get(pk=connection.pk)
    profile = AvitoProductProfile.objects.select_for_update().get(pk=connection.profile_id)
    listing_id = connection.remote_listing.avito_item_id
    connection.delete()
    profile.sell_on_avito = False
    profile.sync_status = AvitoProductProfile.SyncStatus.IDLE
    profile.last_error = ""
    profile.desired_state_hash = ""
    profile.save(update_fields=("sell_on_avito", "sync_status", "last_error", "desired_state_hash"))
    _audit("listing_unbound", actor=actor, profile=profile, details={"avito_item_id": listing_id})


def desired_state(profile):
    product = profile.product
    state = {
        "sell": profile.sell_on_avito,
        "stock": global_stock(profile),
        "price": str(product.avito_price) if product.avito_price is not None else None,
        "title": profile.listing_title,
        "description": profile.listing_description,
        "category": profile.category_slug,
        "attributes": profile.attributes,
        "photos": list(profile.photos.order_by("sort_order", "id").values_list("image", flat=True)),
    }
    encoded = json.dumps(state, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    state["hash"] = hashlib.sha256(encoded).hexdigest()
    return state


def sync_profile(profile_id, *, retry_number=0, force_remote_check=False):
    profile = AvitoProductProfile.objects.select_related("cd", "tech").get(pk=profile_id)
    if profile.product.is_archived:
        return None
    started = timezone.now()
    AvitoProductProfile.objects.filter(pk=profile.pk).update(sync_status=AvitoProductProfile.SyncStatus.SYNCING)
    errors = validate_profile(profile)
    connection = AvitoListingConnection.objects.select_related("remote_listing").filter(profile=profile).first()
    if not connection:
        if profile.sell_on_avito:
            errors.append(AUTOLOAD_UNAVAILABLE)
        if errors:
            message = " ".join(errors)
            AvitoProductProfile.objects.filter(pk=profile.pk).update(
                sync_status=AvitoProductProfile.SyncStatus.ERROR, last_error=message
            )
            AvitoSyncLog.objects.create(
                profile=profile, operation="ensure_listing", result=AvitoSyncLog.Result.ERROR,
                error_category="validation", message=message, retry_number=retry_number, started_at=started,
            )
        else:
            AvitoProductProfile.objects.filter(pk=profile.pk).update(
                sync_status=AvitoProductProfile.SyncStatus.OK, last_error="", last_successful_sync_at=timezone.now()
            )
        return
    if connection.remote_listing.missing_since or connection.remote_listing.status.lower() != "active":
        message = "Объявление отсутствует в актуальном активном списке Avito; цена и остаток не отправлены."
        AvitoProductProfile.objects.filter(pk=profile.pk).update(
            sync_status=AvitoProductProfile.SyncStatus.ERROR, last_error=message,
        )
        AvitoSyncLog.objects.create(
            profile=profile, remote_listing=connection.remote_listing,
            operation="outbound_sync", result=AvitoSyncLog.Result.ERROR,
            error_category="remote_state", message=message,
            retry_number=retry_number, started_at=started,
        )
        return
    if errors:
        message = " ".join(errors)
        # Цена и контент валидируются отдельно от количества: для уже связанного
        # объявления корректный CRM-остаток можно и нужно отправить даже тогда,
        # когда цена ещё не заполнена.
        try:
            AvitoClient().update_stock(
                connection.remote_listing.avito_item_id,
                global_stock(profile) if profile.sell_on_avito else 0,
            )
        except AvitoAPIError as exc:
            message = f"{message} Остаток не синхронизирован: {exc}"
        AvitoProductProfile.objects.filter(pk=profile.pk).update(
            sync_status=AvitoProductProfile.SyncStatus.ERROR, last_error=message
        )
        AvitoSyncLog.objects.create(
            profile=profile, remote_listing=connection.remote_listing, operation="validate",
            result=AvitoSyncLog.Result.ERROR, error_category="validation", message=message,
            retry_number=retry_number, started_at=started,
        )
        return
    state = desired_state(profile)
    if not force_remote_check and profile.desired_state_hash == state["hash"]:
        now = timezone.now()
        AvitoProductProfile.objects.filter(pk=profile.pk).update(
            sync_status=AvitoProductProfile.SyncStatus.OK, last_error="", last_successful_sync_at=now
        )
        AvitoSyncLog.objects.create(
            profile=profile, remote_listing=connection.remote_listing, operation="outbound_sync",
            result=AvitoSyncLog.Result.SKIPPED, message="Состояние CRM не изменилось.",
            retry_number=retry_number, started_at=started,
        )
        return
    if connection.remote_listing.status.lower() in {"blocked", "rejected", "banned"}:
        message = f"Avito не разрешает синхронизацию объявления со статусом «{connection.remote_listing.status}»."
        AvitoProductProfile.objects.filter(pk=profile.pk).update(
            sync_status=AvitoProductProfile.SyncStatus.ERROR, last_error=message
        )
        AvitoSyncLog.objects.create(
            profile=profile, remote_listing=connection.remote_listing, operation="outbound_sync",
            result=AvitoSyncLog.Result.ERROR, error_category="remote_state", message=message,
            retry_number=retry_number, started_at=started,
        )
        return
    client = AvitoClient()
    listing_id = connection.remote_listing.avito_item_id
    try:
        desired_quantity = state["stock"] if state["sell"] else 0
        stock_result = client.update_stock(listing_id, desired_quantity)
        stock_rows = stock_result.get("stocks") or stock_result.get("result") or []
        if isinstance(stock_rows, dict):
            stock_rows = stock_rows.get("stocks") or [stock_rows]
        if stock_rows and any(row.get("success") is False for row in stock_rows if isinstance(row, dict)):
            raise AvitoAPIError("Avito не принял новый остаток объявления.", "validation")
        if state["sell"] and Decimal(state["price"]) > 0:
            price_result = client.update_price(listing_id, Decimal(state["price"]))
            result_payload = price_result.get("result") if isinstance(price_result, dict) else None
            if isinstance(result_payload, dict) and result_payload.get("success") is False:
                raise AvitoAPIError("Avito не принял новую цену объявления.", "validation")
    except AvitoAPIError as exc:
        AvitoProductProfile.objects.filter(pk=profile.pk).update(
            sync_status=AvitoProductProfile.SyncStatus.ERROR, last_error=str(exc)
        )
        AvitoSyncLog.objects.create(
            profile=profile, remote_listing=connection.remote_listing, operation="outbound_sync",
            result=AvitoSyncLog.Result.ERROR, http_status=exc.status, error_category=exc.category,
            message=str(exc), retry_number=retry_number, started_at=started,
        )
        raise
    now = timezone.now()
    AvitoProductProfile.objects.filter(pk=profile.pk).update(
        sync_status=AvitoProductProfile.SyncStatus.OK,
        last_error="",
        last_successful_sync_at=now,
        desired_state_hash=state["hash"],
    )
    AvitoSyncLog.objects.create(
        profile=profile, remote_listing=connection.remote_listing, operation="outbound_sync",
        result=AvitoSyncLog.Result.SUCCESS,
        message="", retry_number=retry_number, started_at=started,
    )


def reconcile_all(*, job=None):
    # Читаем фактические данные пакетами и исправляем только расхождения.
    # Ошибка одного объявления не должна останавливать весь проход.
    from .manual_sync import reconcile_active_listings

    return reconcile_active_listings(job=job)
