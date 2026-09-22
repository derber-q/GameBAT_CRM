"""Сверка связанных активных объявлений с фактическим состоянием Avito."""

from django.utils import timezone

from .client import AvitoAPIError, AvitoClient
from .models import AvitoListingConnection, AvitoProductProfile
from .services import desired_state, global_stock, refresh_remote_listings
from .verification import fetch_remote_stocks


def _update_progress(job, **values):
    if job is None:
        return
    for name, value in values.items():
        setattr(job, name, value)
    job.save(update_fields=(*values.keys(), "updated_at"))


def _api_error(exc):
    return f"{exc} (HTTP {exc.status})" if exc.status else str(exc)


def _accepted(payload, *, field):
    if not isinstance(payload, dict):
        raise AvitoAPIError(f"Avito вернул некорректный ответ при изменении {field}.", "temporary")
    result = payload.get("result") if field == "цены" else payload.get("stocks")
    if isinstance(result, dict):
        result = result.get("stocks", [result])
    if isinstance(result, list) and result and any(
        row.get("success") is False for row in result if isinstance(row, dict)
    ):
        raise AvitoAPIError(f"Avito не принял изменение {field}.", "validation")
    if isinstance(result, dict) and result.get("success") is False:
        raise AvitoAPIError(f"Avito не принял изменение {field}.", "validation")


def reconcile_active_listings(*, job=None, client=None):
    """Сравнить, исправить только расхождения и повторно прочитать Avito.

    Неактивные/исчезнувшие объявления не меняются: их цену нельзя надёжно
    прочитать из актуального списка. Ошибка одного товара не прерывает остальные.
    """
    client = client or AvitoClient()
    _update_progress(
        job, total_count=0, checked_count=0, changed_count=0,
        stock_changed_count=0, price_changed_count=0, failed_count=0,
        skipped_count=0, details=[], current_item="",
        phase="Загрузка актуального списка Avito",
    )
    refresh_remote_listings()
    connections = list(AvitoListingConnection.objects.select_related(
        "profile__cd", "profile__tech", "remote_listing",
    ).order_by("remote_listing__avito_item_id"))
    active = [
        connection for connection in connections
        if not connection.remote_listing.missing_since
        and connection.remote_listing.status.lower() == "active"
        and not connection.profile.product.is_archived
    ]
    skipped = len(connections) - len(active)
    _update_progress(
        job, total_count=len(active), skipped_count=skipped,
        phase="Чтение остатков Avito",
    )
    item_ids = [connection.remote_listing.avito_item_id for connection in active]
    initial_read_errors = {}
    initial_stocks = fetch_remote_stocks(
        item_ids, client=client,
        tolerate_errors=True,
        on_error=lambda ids, exc: initial_read_errors.update({
            item_id: _api_error(exc) for item_id in ids
        }),
        progress=lambda count: _update_progress(
            job, current_item=f"Получено остатков: {count} из {len(active)}"
        ),
        batch_retries=2,
    )
    _update_progress(job, phase="Сверка и отправка изменений")
    states = []
    for connection in active:
        profile = connection.profile
        product = profile.product
        item_id = connection.remote_listing.avito_item_id
        expected_stock = global_stock(profile) if profile.sell_on_avito else 0
        expected_price = product.avito_price if profile.sell_on_avito else None
        remote_stock = initial_stocks.get(item_id)
        remote_price = connection.remote_listing.remote_price
        errors = []
        stock_needs_confirmation = False
        if remote_stock is None:
            errors.append("Не удалось прочитать остаток: " + initial_read_errors.get(
                item_id, "Avito не вернул объявление в ответе.")
            )
        elif remote_stock != expected_stock:
            try:
                _accepted(client.update_stock(item_id, expected_stock), field="остатка")
                stock_needs_confirmation = True
            except AvitoAPIError as exc:
                errors.append("Остаток: " + _api_error(exc))
        if profile.sell_on_avito:
            if expected_price is None or expected_price <= 0 or expected_price != expected_price.to_integral_value():
                errors.append("В CRM не указана корректная целая цена Avito.")
            elif remote_price != expected_price:
                try:
                    _accepted(client.update_price(item_id, expected_price), field="цены")
                except AvitoAPIError as exc:
                    errors.append("Цена: " + _api_error(exc))
        states.append({
            "connection": connection, "item_id": item_id,
            "expected_stock": expected_stock, "expected_price": expected_price,
            "initial_stock": remote_stock, "initial_price": remote_price,
            "stock_needs_confirmation": stock_needs_confirmation,
            "price_needs_confirmation": bool(
                profile.sell_on_avito and expected_price is not None
                and expected_price > 0 and remote_price != expected_price
            ),
            "errors": errors,
        })
        _update_progress(
            job, checked_count=len(states), current_item=product.name[:255],
        )

    stock_confirmation_ids = [
        state["item_id"] for state in states if state["stock_needs_confirmation"]
    ]
    confirmation_required = stock_confirmation_ids or any(
        state["price_needs_confirmation"] for state in states
    )
    _update_progress(
        job,
        phase=("Повторная проверка результата через Avito" if confirmation_required
               else "Фиксация результата"),
        current_item="",
    )
    final_read_errors = {}
    final_stocks = {}
    if stock_confirmation_ids:
        final_stocks = fetch_remote_stocks(
            stock_confirmation_ids, client=client,
            tolerate_errors=True,
            on_error=lambda ids, exc: final_read_errors.update({
                item_id: _api_error(exc) for item_id in ids
            }),
            progress=lambda count: _update_progress(
                job,
                current_item=(
                    f"Подтверждено изменённых остатков: {count} "
                    f"из {len(stock_confirmation_ids)}"
                ),
            ),
            batch_retries=2,
        )
    price_refresh_started = None
    price_refresh_error = None
    if any(state["price_needs_confirmation"] for state in states):
        price_refresh_started = timezone.now()
        try:
            refresh_remote_listings()
        except AvitoAPIError as exc:
            price_refresh_error = _api_error(exc)
    details = []
    changed = stock_changed = price_changed = failed = 0
    for state in states:
        connection = state["connection"]
        profile = connection.profile
        item_id = state["item_id"]
        listing = connection.remote_listing
        listing.refresh_from_db(fields=["remote_price", "last_seen_at", "missing_since", "status"])
        errors = state["errors"]
        if state["stock_needs_confirmation"]:
            actual_stock = final_stocks.get(item_id)
            if actual_stock is None:
                errors.append("Повторная проверка остатка не удалась: " + final_read_errors.get(
                    item_id, "Avito не вернул объявление в ответе.")
                )
            elif actual_stock != state["expected_stock"]:
                errors.append(
                    f"Остаток не подтверждён: CRM {state['expected_stock']}, Avito {actual_stock}."
                )
        price_required = state["expected_price"] is not None and profile.sell_on_avito
        if listing.missing_since or listing.status.lower() != "active":
            errors.append("Объявление исчезло из актуального списка Avito или перестало быть активным.")
        elif price_required:
            if state["price_needs_confirmation"] and price_refresh_error:
                errors.append("Повторная проверка цены не удалась: " + price_refresh_error)
            elif listing.remote_price != state["expected_price"] or (
                state["price_needs_confirmation"] and (
                    not listing.last_seen_at or listing.last_seen_at < price_refresh_started
                )
            ):
                errors.append(
                    f"Цена не подтверждена: CRM {state['expected_price']}, "
                    f"Avito {listing.remote_price if listing.remote_price is not None else 'не получена'}."
                )
        if errors:
            failed += 1
            message = " ".join(errors)
            AvitoProductProfile.objects.filter(pk=profile.pk).update(
                sync_status=AvitoProductProfile.SyncStatus.ERROR, last_error=message,
            )
            details.append({"avito_id": item_id, "name": profile.product.name, "error": message})
        else:
            stock_was_changed = state["initial_stock"] != state["expected_stock"]
            price_was_changed = price_required and state["initial_price"] != state["expected_price"]
            stock_changed += int(stock_was_changed)
            price_changed += int(price_was_changed)
            changed += int(stock_was_changed or price_was_changed)
            AvitoProductProfile.objects.filter(pk=profile.pk).update(
                sync_status=AvitoProductProfile.SyncStatus.OK,
                last_error="", last_successful_sync_at=timezone.now(),
                desired_state_hash=desired_state(profile)["hash"],
            )
        _update_progress(
            job, changed_count=changed, stock_changed_count=stock_changed,
            price_changed_count=price_changed, failed_count=failed, details=details,
        )
    _update_progress(
        job, phase="Завершено с ошибками" if failed else "Завершено",
        current_item="",
    )
    return {
        "total": len(active), "checked": len(states), "changed": changed,
        "stock_changed": stock_changed, "price_changed": price_changed,
        "failed": failed, "skipped": skipped, "details": details,
    }
