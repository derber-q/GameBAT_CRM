"""Список необходимых действий со связанными объявлениями без изменения публикаций."""
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlsplit

from django.db.models import Sum

from warehouse.models import CDWarehouseStock, TechWarehouseStock
from .models import AvitoListingConnection
from .services import global_stock


class RemotePublicationState(StrEnum):
    PUBLISHED = "published"
    ARCHIVED = "archived"
    OTHER = "other"


class RequiredAction(StrEnum):
    UNPUBLISH_MANUALLY = "unpublish"
    PUBLISH_MANUALLY = "publish"


def normalize_remote_status(status):
    # Item API /core/v1/accounts/{account_id}/items/{item_id}/.
    # Проверенные ответы аккаунта: active — опубликовано, old — снято/истекло.
    # Не смешивать удаление, блокировку, отклонение и неизвестный статус с архивом.
    return {
        "active": RemotePublicationState.PUBLISHED,
        "old": RemotePublicationState.ARCHIVED,
    }.get(str(status or "").strip().lower(), RemotePublicationState.OTHER)


def is_remote_published(status):
    return normalize_remote_status(status) == RemotePublicationState.PUBLISHED


def is_remote_archived(status):
    return normalize_remote_status(status) == RemotePublicationState.ARCHIVED


def safe_listing_url(listing):
    snapshot = listing.snapshot if isinstance(listing.snapshot, dict) else {}
    for value in (listing.url, snapshot.get("url")):
        if not isinstance(value, str) or any(ord(c) < 32 for c in value):
            continue
        try:
            parsed = urlsplit(value)
            if (parsed.scheme == "https" and parsed.hostname in {"avito.ru", "www.avito.ru"}
                    and not parsed.username and not parsed.password and parsed.port in (None, 443)
                    and parsed.path not in ("", "/")):
                return value
        except ValueError:
            continue
    return ""


@dataclass(frozen=True)
class RequiredActionRow:
    listing: object
    product: object
    product_kind: str
    global_stock: int
    remote_status: str
    action: RequiredAction
    listing_url: str

    @property
    def label(self):
        return "Снять с публикации" if self.action == RequiredAction.UNPUBLISH_MANUALLY else "Опубликуйте объявление"


def get_avito_required_actions():
    connections = list(AvitoListingConnection.objects.select_related(
        "remote_listing", "profile__cd", "profile__tech",
    ))
    totals = {}
    for kind, model in (("cd", CDWarehouseStock), ("tech", TechWarehouseStock)):
        ids = [c.profile.product_id for c in connections if c.profile.product_kind == kind]
        totals.update({(kind, row[f"{kind}_id"]): row["total"] for row in
                       model.objects.filter(**{f"{kind}_id__in": ids})
                       .values(f"{kind}_id").annotate(total=Sum("quantity"))})
    actions = []
    for connection in connections:
        profile, listing = connection.profile, connection.remote_listing
        if profile.product.is_archived or listing.missing_since:
            continue  # No reliable remote state; do not guess an action.
        stock = global_stock(profile, stock_totals=totals)
        if is_remote_published(listing.status) and (stock == 0 or not profile.sell_on_avito):
            action = RequiredAction.UNPUBLISH_MANUALLY
        elif stock > 0 and profile.sell_on_avito and is_remote_archived(listing.status):
            action = RequiredAction.PUBLISH_MANUALLY
        else:
            continue
        actions.append(RequiredActionRow(
            listing, profile.product, profile.product_kind, stock,
            listing.status, action, safe_listing_url(listing),
        ))
    return sorted(actions, key=lambda row: (
        row.action != RequiredAction.UNPUBLISH_MANUALLY,
        row.listing.title.casefold(), row.listing.avito_item_id,
    ))
