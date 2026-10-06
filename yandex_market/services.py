import hashlib
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from catalog.models import CD, Tech
from warehouse.inventory import global_stock
from .client import MarketError, YandexMarketClient, json_bytes
from .content import build_content
from .models import AuditEvent, CategorySchema, Integration, OfferConnection, RemoteOffer, ReturnMetadata, SyncJob
from .queue import enqueue, product_after_commit


def audit(integration, actor, action, entity_id, **details):
    AuditEvent.objects.create(integration=integration, actor=actor, action=action, entity_id=str(entity_id), details=details)


def connections_with_stock(queryset):
    return queryset.annotate(physical_stock=Coalesce(Sum("cd__warehouse_stocks__quantity"), Sum("tech__warehouse_stocks__quantity"), Value(0)))


def refresh_trade_snapshots(integration, *, client, offer_ids=None):
    """Только чтение цены и доступного остатка; значения CRM не изменяются."""
    body = {"offerIds": offer_ids} if offer_ids else {}
    operation = "getDefaultPrices" if integration.price_scope == "business" else "getPricesByOfferIds"
    prices = client.call(operation, body=body).get("result", {}).get("offers", []) if offer_ids else client.pages(operation, body=body, key="offers", limit=100)
    for row in prices:
        value = row.get("price", {}).get("value")
        if value is not None:
            RemoteOffer.objects.filter(integration=integration, offer_id=row["offerId"]).update(remote_price=Decimal(str(value)), price_checked_at=timezone.now())
    if integration.stock_api == "partner":
        body["partnerWarehouseId"] = integration.partner_warehouse_id
        rows = client.call("getStocksOnPartnerWarehouses", body=body).get("result", {}).get("offers", []) if offer_ids else client.pages("getStocksOnPartnerWarehouses", body=body, key="offers", limit=100)
    else:
        body["stocksWarehouseId"] = integration.partner_warehouse_id
        warehouses = client.call("getStocks", body=body).get("result", {}).get("warehouses", []) if offer_ids else client.pages("getStocks", body=body, key="warehouses", limit=100)
        rows = (row for warehouse in warehouses if warehouse["warehouseId"] == integration.partner_warehouse_id for row in warehouse["offers"])
    for row in rows:
        stocks = {s["type"]: s["count"] for s in row.get("stocks", [])}
        available = stocks.get("AVAILABLE")
        if available is None and "FIT" in stocks:
            available = max(0, stocks["FIT"] - stocks.get("FREEZE", 0))
        if available is not None:
            RemoteOffer.objects.filter(integration=integration, offer_id=row["offerId"]).update(remote_stock=available, stock_checked_at=timezone.now())


def check_connection(integration, *, client=None):
    client = client or YandexMarketClient(integration)
    campaigns = client.pages("getCampaigns", key="campaigns", limit=100)
    campaign = next((c for c in campaigns if c.get("id") == integration.campaign_id), None)
    if not campaign or campaign.get("business", {}).get("id") != integration.business_id or campaign.get("placementType") != "FBS":
        raise ValidationError("Ключ, кабинет и FBS-магазин не соответствуют настройкам подключения.")
    if campaign.get("apiAvailability") != "AVAILABLE":
        raise ValidationError("API выбранного FBS-магазина недоступен.")
    configuration = client.call("getBusinessSettings", body={}).get("result", {}).get("settings", {})
    if configuration.get("currency") != "RUR":
        raise ValidationError("Для интеграции требуется кабинет с валютой RUR.")
    if configuration.get("onlyDefaultPrice") and integration.price_scope != "business":
        raise ValidationError("Кабинет разрешает только общую цену бизнеса. Измените область цены.")
    if integration.stock_api == "partner":
        warehouses = list(client.pages("getPartnerWarehouses", body={}, key="warehouses", limit=30))
        target = next((w for w in warehouses if w.get("id") == integration.partner_warehouse_id), None)
        if not target or not any(m.get("placementType") == "FBS" and m.get("apiAvailability") == "AVAILABLE" for m in target.get("models", [])):
            raise ValidationError("Выберите доступный FBS-склад Маркета.")
    else:
        warehouses = list(client.pages("getPagedWarehouses", body={"campaignIds": [integration.campaign_id]}, key="warehouses", limit=30))
        if not any(w.get("id") == integration.partner_warehouse_id and w.get("campaignId") == integration.campaign_id for w in warehouses):
            raise ValidationError("Целевой склад не принадлежит выбранному FBS-магазину.")
    integration.configuration = {**integration.configuration, **configuration}
    integration.checked_at = timezone.now()
    integration.last_error = ""
    integration.save(update_fields=["configuration", "checked_at", "last_error"])
    return integration


def store_api_key(value):
    """Файл содержит только шифротекст; смена ключа требует повторной проверки кабинетов."""
    import os
    import tempfile
    from pathlib import Path
    from django.conf import settings
    from integrations.crypto import encrypt_secret
    value = str(value).strip()
    if not value or any(char.isspace() for char in value):
        raise ValidationError("Введите только API-Key, без пробелов и пояснений.")
    if settings.YANDEX_MARKET_API_KEY:
        raise ValidationError("Ключ задан переменной окружения сервера. Измените её в конфигурации запуска.")
    target = Path(settings.YANDEX_MARKET_KEY_FILE)
    descriptor, temporary = tempfile.mkstemp(dir=target.parent, prefix=".ym-key-")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(encrypt_secret(value))
        os.chmod(temporary, 0o600)
        os.replace(temporary, target)
    finally:
        if Path(temporary).exists():
            Path(temporary).unlink()
    Integration.objects.all().update(enabled=False, checked_at=None)


@transaction.atomic
def store_offer(integration, row, card=None):
    Integration.objects.filter(pk=integration.pk).update(last_sync_at=F("last_sync_at"))
    offer = row["offer"]
    mapping = row.get("mapping", {})
    values = {
        "name": offer.get("name", ""), "snapshot": row,
        "market_sku": mapping.get("marketSku"), "category_id": offer.get("marketCategoryId") or mapping.get("marketCategoryId"),
        "category_name": mapping.get("marketCategoryName", ""), "card_status": offer.get("cardStatus", ""),
        "archived": bool(offer.get("archived", False)), "fetched_at": timezone.now(), "last_error": "",
    }
    if card is not None:
        values.update(card=card, card_status=card.get("cardStatus", values["card_status"]), content_rating=card.get("contentRating"))
    result, _ = RemoteOffer.objects.update_or_create(integration=integration, offer_id=offer["offerId"], defaults=values)
    return result


def refresh_catalog(integration, *, client=None):
    client = client or YandexMarketClient(integration)
    count = 0
    for row in client.pages("getOfferMappings", body={}, key="offerMappings", limit=100):
        store_offer(integration, row)
        count += 1
    for card in client.pages("getOfferCardsContentStatus", body={"withRecommendations": True}, key="offerCards", limit=100):
        RemoteOffer.objects.filter(integration=integration, offer_id=card["offerId"]).update(
            card=card, card_status=card.get("cardStatus", ""), content_rating=card.get("contentRating"),
        )
    refresh_trade_snapshots(integration, client=client)
    return count


def refresh_offer(remote, *, client=None):
    client = client or YandexMarketClient(remote.integration)
    data = client.call("getOfferMappings", body={"offerIds": [remote.offer_id]})
    rows = data.get("result", {}).get("offerMappings", [])
    row = next((r for r in rows if r.get("offer", {}).get("offerId") == remote.offer_id), None)
    if row is None:
        raise ValidationError("Товар больше не найден в каталоге Маркета.")
    cards = client.call("getOfferCardsContentStatus", body={"offerIds": [remote.offer_id], "withRecommendations": True}).get("result", {}).get("offerCards", [])
    card = next((c for c in cards if c.get("offerId") == remote.offer_id), {})
    result = store_offer(remote.integration, row, card)
    refresh_trade_snapshots(remote.integration, client=client, offer_ids=[remote.offer_id])
    result.refresh_from_db()
    return result


def refresh_category(category_id, *, client):
    data = client.call("getCategoryContentParameters", params={"categoryId": category_id}, body={})
    result = data.get("result", {})
    if result.get("categoryId") != int(category_id):
        raise ValidationError("API вернул характеристики другой категории.")
    with transaction.atomic():
        CategorySchema.objects.filter(category_id=category_id).update(fetched_at=F("fetched_at"))
        schema, _ = CategorySchema.objects.update_or_create(category_id=category_id, defaults={"schema": result, "fetched_at": timezone.now()})
    return schema


@transaction.atomic
def bind_offer(*, remote_id, product_kind, product_id, actor):
    # Снимок должен быть предварительно получен через API вне транзакции.
    RemoteOffer.objects.filter(pk=remote_id).update(fetched_at=F("fetched_at"))
    remote = RemoteOffer.objects.select_for_update().select_related("integration").get(pk=remote_id)
    if remote.archived:
        raise ValidationError("Архивный товар нельзя привязать для управления.")
    if remote.card_status in {"NO_CARD_ERRORS", "HAS_CARD_CAN_UPDATE_ERRORS"}:
        raise ValidationError("Сначала устраните ошибки карточки Маркета.")
    model = {"cd": CD, "tech": Tech}.get(product_kind)
    if model is None:
        raise ValidationError("Выберите CD или Tech.")
    product = model.objects.active().get(pk=product_id)
    if OfferConnection.objects.filter(remote_offer=remote, active=True).exists():
        raise ValidationError("Товар Маркета уже связан. Используйте перепривязку.")
    if OfferConnection.objects.filter(integration=remote.integration, active=True, **{product_kind: product}).exists():
        raise ValidationError("Товар CRM уже имеет активную связь с Маркетом.")
    connection = OfferConnection.objects.create(integration=remote.integration, remote_offer=remote,
        category_id=remote.category_id, **{product_kind: product})
    audit(remote.integration, actor, "bind", connection.pk, product_kind=product_kind, product_id=product_id, offer_id=remote.offer_id)
    return connection


def ensure_unlink_allowed(connection):
    for job in SyncJob.objects.filter(integration=connection.integration, kind="products", state__in=["pending", "running"]):
        if connection.pk in job.payload.get("connection_ids", []):
            raise ValidationError("Дождитесь завершения пакетной синхронизации товара.")
    if SyncJob.objects.filter(integration=connection.integration, kind="reconcile", state="running").exists():
        raise ValidationError("Дождитесь завершения сверки магазина.")
    if connection.order_lines.filter(order__sale__cancelled_at__isnull=True).exclude(order__status__in=["CANCELLED", "DELIVERED"]).exists():
        raise ValidationError("Есть незавершённые заказы Маркета.")
    if ReturnMetadata.objects.filter(order__lines__connection=connection, accepted_at__isnull=True).exclude(status="CANCELLED").exists():
        raise ValidationError("Есть непринятые возвраты.")
    if SyncJob.objects.filter(integration=connection.integration, kind="product", payload__connection_id=connection.pk, state__in=["pending", "running"]).exists():
        raise ValidationError("Дождитесь завершения синхронизации товара.")


@transaction.atomic
def unlink_offer(connection_id, actor, *, replacement=None):
    OfferConnection.objects.filter(pk=connection_id).update(revision=F("revision") + 1)
    connection = OfferConnection.objects.select_for_update().select_related("integration", "remote_offer").get(pk=connection_id, active=True)
    ensure_unlink_allowed(connection)
    connection.active = False
    connection.managed = False
    connection.save(update_fields=["active", "managed"])
    audit(connection.integration, actor, "rebind" if replacement else "unlink", connection.pk)
    if replacement:
        return bind_offer(remote_id=connection.remote_offer_id, actor=actor, **replacement)
    return connection


@transaction.atomic
def create_offer(*, integration, product_kind, product_id, actor):
    Integration.objects.filter(pk=integration.pk).update(last_sync_at=F("last_sync_at"))
    model = {"cd": CD, "tech": Tech}.get(product_kind)
    if model is None:
        raise ValidationError("Выберите CD или Tech.")
    product = model.objects.active().get(pk=product_id)
    offer_id = f"GB-{product_kind.upper()}-{product.pk}"
    if RemoteOffer.objects.filter(integration=integration, offer_id=offer_id).exists():
        raise ValidationError("Такой offerId уже использован. Найдите существующую карточку.")
    remote = RemoteOffer.objects.create(integration=integration, offer_id=offer_id, name=product.name)
    connection = bind_offer(remote_id=remote.pk, product_kind=product_kind, product_id=product_id, actor=actor)
    from .content import valid_gtin
    content = {"name": product.name, "description": product.description, "vendorCode": product.sku}
    if product_kind == "tech":
        content["vendor"] = product.brand.name
    codes = [code for code in product.barcodes.values_list("value", flat=True) if valid_gtin(code)]
    if codes:
        content["barcodes"] = codes
    connection.content = {key: value for key, value in content.items() if value}
    connection.is_new = True
    connection.save(update_fields=["content", "is_new"])
    return connection


@transaction.atomic
def activate(connection_id, actor, *, sell):
    OfferConnection.objects.filter(pk=connection_id).update(revision=F("revision"))
    connection = OfferConnection.objects.select_related("remote_offer", "cd", "tech", "integration").get(pk=connection_id, active=True)
    if not connection.integration.checked_at:
        raise ValidationError("Сначала проверьте подключение магазина.")
    if sell and (connection.product.yandex_market_price is None or connection.product.yandex_market_price <= 0):
        raise ValidationError("Укажите положительную цену Яндекс Маркет в CRM.")
    if connection.is_new and sell:
        build_content(connection)
    connection.managed = True
    connection.sell_on_yandex = sell
    connection.revision += 1
    connection.save(update_fields=["managed", "sell_on_yandex", "revision"])
    audit(connection.integration, actor, "activate", connection.pk, sell=sell)
    product_after_commit(connection.pk)
    return connection


def sync_product(connection_id, *, client=None, force=False):
    connection = OfferConnection.objects.select_related("integration", "remote_offer", "cd", "tech").prefetch_related("media").get(pk=connection_id)
    if not connection.active or not connection.managed or not connection.integration.enabled:
        return
    client = client or YandexMarketClient(connection.integration)
    revision = connection.revision
    OfferConnection.objects.filter(pk=connection.pk).update(state="syncing", last_sync_at=timezone.now())
    quantity = global_stock(connection.product) if connection.sell_on_yandex and not connection.product.is_archived else 0
    price = connection.product.yandex_market_price
    content_error = None
    try:
        content = build_content(connection) if connection.sell_on_yandex else {"offerId": connection.remote_offer.offer_id}
    except ValidationError as exc:
        if connection.is_new:
            raise
        content, content_error = {"offerId": connection.remote_offer.offer_id}, exc
    desired_hash = hashlib.sha256(json_bytes({"content": content, "price": price, "quantity": quantity})).hexdigest()
    remote = connection.remote_offer
    sent = dict(connection.last_sent_state)
    if connection.sell_on_yandex and connection.is_new:
        client.call("updateOfferMappings", body={"offerMappings": [{"offer": content}]}, entity_id=remote.offer_id)
    if connection.sell_on_yandex:
        if price is None or price <= 0:
            raise ValidationError("Укажите положительную цену Яндекс Маркет в CRM.")
        price_known = Decimal(str(sent["price"])) if "price" in sent and not force else remote.remote_price
        if price_known != price or (force and not remote.price_checked_at):
            operation = "updateBusinessPrices" if connection.integration.price_scope == "business" else "updatePrices"
            client.call(operation, body={"offers": [{"offerId": remote.offer_id, "price": {"value": price, "currencyId": "RUR"}}]}, entity_id=remote.offer_id)
            sent["price"] = str(price)
    stock_known = sent.get("quantity", remote.remote_stock) if not force else remote.remote_stock
    if stock_known != quantity or (force and not remote.stock_checked_at):
        if connection.integration.stock_api == "partner":
            body = {"skuItems": [{"sku": remote.offer_id, "partnerWarehouseId": connection.integration.partner_warehouse_id, "count": quantity, "updatedAt": timezone.now().isoformat()}]}
            operation = "updateStocksOnPartnerWarehouses"
        else:
            body = {"skus": [{"sku": remote.offer_id, "items": [{"count": quantity, "updatedAt": timezone.now().isoformat()}]}]}
            operation = "updateStocks"
        client.call(operation, body=body, entity_id=remote.offer_id)
        sent["quantity"] = quantity
    OfferConnection.objects.filter(pk=connection.pk, revision=revision).update(last_sent_state=sent)
    # Ошибка необязательного контента не задерживает актуализацию складского остатка.
    if content_error:
        raise content_error
    if connection.sell_on_yandex and not connection.is_new and len(content) > 1:
        client.call("updateOfferMappings", body={"offerMappings": [{"offer": content}]}, entity_id=remote.offer_id)
    # HTTP-успех означает принятие запроса. Снимки цены/остатка обновляет чтение API.
    OfferConnection.objects.filter(pk=connection.pk, revision=revision).update(
        state="synced", last_success_at=timezone.now(), last_error="", last_sent_hash=desired_hash,
        last_sent_state=sent,
        **({"is_new": False, "dirty_fields": [], "delete_fields": []} if connection.sell_on_yandex else {}),
    )


def sync_price_stock_batch(integration, connection_ids, *, client):
    """Сверка отправляет пачки до 100 товаров; перед отправкой заново читает CRM."""
    from django.db.models import Sum, Value
    from django.db.models.functions import Coalesce
    for offset in range(0, len(connection_ids), 100):
        rows = list(OfferConnection.objects.filter(pk__in=connection_ids[offset:offset + 100], integration=integration,
            active=True, managed=True).select_related("remote_offer", "cd", "tech").annotate(
                physical_stock=Coalesce(Sum("cd__warehouse_stocks__quantity"), Sum("tech__warehouse_stocks__quantity"), Value(0))))
        prices, stocks, processed = [], [], []
        for row in rows:
            if row.is_new or row.dirty_fields or row.delete_fields:
                enqueue(integration, "product", row.pk, {"connection_id": row.pk, "force": True}, delay=3)
                continue
            price = row.product.yandex_market_price
            if row.sell_on_yandex and (price is None or price <= 0):
                OfferConnection.objects.filter(pk=row.pk).update(state="error", last_error="Укажите положительную цену Яндекс Маркет в CRM.")
                continue
            quantity = row.physical_stock if row.sell_on_yandex and not row.product.is_archived else 0
            if row.sell_on_yandex and row.remote_offer.remote_price != price:
                prices.append({"offerId": row.remote_offer.offer_id, "price": {"value": price, "currencyId": "RUR"}})
            if row.remote_offer.remote_stock != quantity:
                stocks.append((row.remote_offer.offer_id, quantity))
            processed.append((row, price, quantity))
        if prices:
            client.call("updateBusinessPrices" if integration.price_scope == "business" else "updatePrices", body={"offers": prices})
        if stocks:
            now = timezone.now().isoformat()
            if integration.stock_api == "partner":
                client.call("updateStocksOnPartnerWarehouses", body={"skuItems": [{"sku": sku, "partnerWarehouseId": integration.partner_warehouse_id, "count": count, "updatedAt": now} for sku, count in stocks]})
            else:
                client.call("updateStocks", body={"skus": [{"sku": sku, "items": [{"count": count, "updatedAt": now}]} for sku, count in stocks]})
        for row, price, quantity in processed:
            sent = {**row.last_sent_state, "quantity": quantity}
            if row.sell_on_yandex:
                sent["price"] = str(price)
            OfferConnection.objects.filter(pk=row.pk, revision=row.revision).update(
                state="synced", last_error="", last_sent_state=sent, last_sync_at=timezone.now(), last_success_at=timezone.now())
