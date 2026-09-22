from dataclasses import dataclass
from decimal import Decimal
import time

from django.utils import timezone

from .client import AvitoAPIError, AvitoClient
from .models import AvitoListingConnection
from .services import global_stock, refresh_remote_listings, sync_profile


MATCH = "MATCH"
MISMATCH = "MISMATCH"
MISMATCH_FIXED = "MISMATCH_FIXED"
MISMATCH_FAILED = "MISMATCH_FAILED"
NOT_VERIFIABLE = "NOT_VERIFIABLE"


@dataclass
class AvitoVerificationRow:
    avito_id: int
    product_type: str
    product_id: int
    name: str
    expected_stock: int
    remote_stock: int | None
    stock_status: str
    expected_price: Decimal | None
    remote_price: Decimal | None
    price_status: str
    sync_action: str
    final_result: str
    initial_stock_status: str
    initial_price_status: str


def _chunks(values, size=10):
    for index in range(0, len(values), size):
        yield values[index:index + size]


def fetch_remote_stocks(
    item_ids, *, client=None, progress=None, tolerate_errors=False,
    on_error=None, batch_retries=0,
):
    client = client or AvitoClient()
    result = {}
    processed = 0
    for item_ids_chunk in _chunks(list(item_ids)):
        rows = None
        final_error = None
        for retry_number in range(batch_retries + 1):
            try:
                payload = client.get_stocks(item_ids_chunk)
                rows = payload.get("stocks") if isinstance(payload, dict) else None
                if not isinstance(rows, list):
                    raise AvitoAPIError(
                        "Avito вернул некорректный ответ об остатках.", "temporary"
                    )
                final_error = None
                break
            except AvitoAPIError as exc:
                final_error = exc
                if not exc.retryable or retry_number >= batch_retries:
                    break
                time.sleep(1.5 * (retry_number + 1))
        if final_error is not None:
            exc = final_error
            if not tolerate_errors or exc.category in {"auth", "rate_limit"}:
                raise exc
            if on_error:
                on_error(item_ids_chunk, exc)
            processed += len(item_ids_chunk)
            if progress:
                progress(processed)
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            try:
                item_id = int(row["item_id"])
                quantity = int(row["quantity"])
            except (KeyError, TypeError, ValueError):
                continue
            result[item_id] = quantity
        processed += len(item_ids_chunk)
        if progress:
            progress(processed)
    return result


def _fresh_remote_prices(connections):
    refresh_started_at = timezone.now()
    refresh_remote_listings()
    for connection in connections:
        connection.remote_listing.refresh_from_db()
    return {
        connection.remote_listing.avito_item_id: connection.remote_listing.remote_price
        for connection in connections
        if connection.remote_listing.last_seen_at
        and connection.remote_listing.last_seen_at >= refresh_started_at
    }


def _status(expected, remote):
    if expected is None or remote is None:
        return NOT_VERIFIABLE
    return MATCH if expected == remote else MISMATCH


def _final_status(initial_status, expected, remote, *, fix_requested):
    if initial_status == MATCH:
        return MATCH
    if initial_status == NOT_VERIFIABLE:
        return NOT_VERIFIABLE
    if not fix_requested:
        return MISMATCH
    if remote is None:
        return NOT_VERIFIABLE
    return MISMATCH_FIXED if expected == remote else MISMATCH_FAILED


def verify_avito_connections(*, fix=False, client=None):
    client = client or AvitoClient()
    connections = list(AvitoListingConnection.objects.select_related(
        "profile__cd", "profile__tech", "remote_listing",
    ).order_by("remote_listing__avito_item_id"))
    item_ids = [connection.remote_listing.avito_item_id for connection in connections]
    initial_stocks = fetch_remote_stocks(item_ids, client=client)
    initial_prices = _fresh_remote_prices(connections)
    state = []
    profiles_to_fix = []
    for connection in connections:
        profile = connection.profile
        product = profile.product
        item_id = connection.remote_listing.avito_item_id
        expected_stock = global_stock(profile)
        expected_price = product.avito_price
        remote_stock = initial_stocks.get(item_id)
        remote_price = initial_prices.get(item_id)
        stock_status = _status(expected_stock, remote_stock)
        price_status = _status(expected_price, remote_price)
        needs_fix = stock_status == MISMATCH or price_status == MISMATCH
        if fix and needs_fix:
            profiles_to_fix.append(profile.pk)
        state.append({
            "connection": connection,
            "expected_stock": expected_stock,
            "expected_price": expected_price,
            "initial_remote_stock": remote_stock,
            "initial_remote_price": remote_price,
            "initial_stock_status": stock_status,
            "initial_price_status": price_status,
            "needs_fix": needs_fix,
            "sync_action": "NONE",
        })
    sync_errors = {}
    for profile_id in profiles_to_fix:
        try:
            sync_profile(profile_id, force_remote_check=True)
        except AvitoAPIError as exc:
            sync_errors[profile_id] = str(exc)
    final_stocks = fetch_remote_stocks(item_ids, client=client) if profiles_to_fix else initial_stocks
    final_prices = _fresh_remote_prices(connections) if profiles_to_fix else initial_prices
    rows = []
    for item in state:
        connection = item["connection"]
        profile = connection.profile
        product = profile.product
        item_id = connection.remote_listing.avito_item_id
        fix_requested = fix and item["needs_fix"]
        remote_stock = final_stocks.get(item_id) if fix_requested else item["initial_remote_stock"]
        remote_price = final_prices.get(item_id) if fix_requested else item["initial_remote_price"]
        stock_status = _final_status(
            item["initial_stock_status"], item["expected_stock"], remote_stock,
            fix_requested=fix_requested,
        )
        price_status = _final_status(
            item["initial_price_status"], item["expected_price"], remote_price,
            fix_requested=fix_requested,
        )
        if profile.pk in sync_errors:
            action = f"SYNC_FAILED: {sync_errors[profile.pk]}"
        elif fix_requested:
            action = "SYNC_REQUESTED"
        else:
            action = "NONE"
        statuses = {stock_status, price_status}
        if MISMATCH_FAILED in statuses or MISMATCH in statuses or profile.pk in sync_errors:
            final_result = MISMATCH_FAILED
        elif NOT_VERIFIABLE in statuses:
            final_result = NOT_VERIFIABLE
        elif MISMATCH_FIXED in statuses:
            final_result = MISMATCH_FIXED
        else:
            final_result = MATCH
        rows.append(AvitoVerificationRow(
            avito_id=item_id,
            product_type=profile.product_kind,
            product_id=profile.product_id,
            name=product.name,
            expected_stock=item["expected_stock"],
            remote_stock=remote_stock,
            stock_status=stock_status,
            expected_price=item["expected_price"],
            remote_price=remote_price,
            price_status=price_status,
            sync_action=action,
            final_result=final_result,
            initial_stock_status=item["initial_stock_status"],
            initial_price_status=item["initial_price_status"],
        ))
    return rows


def verification_summary(rows):
    return {
        "total": len(rows),
        "stock_initial_match": sum(row.initial_stock_status == MATCH for row in rows),
        "stock_fixed": sum(row.stock_status == MISMATCH_FIXED for row in rows),
        "stock_failed": sum(row.stock_status in {MISMATCH, MISMATCH_FAILED} for row in rows),
        "price_initial_match": sum(row.initial_price_status == MATCH for row in rows),
        "price_fixed": sum(row.price_status == MISMATCH_FIXED for row in rows),
        "price_failed": sum(row.price_status in {MISMATCH, MISMATCH_FAILED} for row in rows),
        "not_verifiable": sum(row.final_result == NOT_VERIFIABLE for row in rows),
    }
