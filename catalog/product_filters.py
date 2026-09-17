"""Общие GET-фильтры товарных списков склада, номенклатуры и цен."""

from dataclasses import dataclass
from urllib.parse import urlencode

from .models import Brand, GameSeries, Platform, ProductType
from .product_search import search_product_querysets


FILTER_KEYS = ("search", "platform", "game_series", "brand", "product_type")


@dataclass(frozen=True)
class ProductFilterState:
    search: str = ""
    platform_id: int | None = None
    game_series_id: int | None = None
    without_series: bool = False
    brand_id: int | None = None
    product_type_id: int | None = None

    @property
    def is_active(self):
        return bool(
            self.search or self.platform_id or self.game_series_id or self.without_series
            or self.brand_id or self.product_type_id
        )

    @property
    def tech_filters_active(self):
        return bool(self.brand_id or self.product_type_id)


def _integer(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def product_filter_context(params, *, include_game_series=False):
    """Возвращает нормализованное состояние и динамические варианты фильтров."""
    platforms = list(Platform.objects.order_by("name", "id"))
    brands = list(Brand.objects.order_by("name", "id"))
    product_types = list(ProductType.objects.order_by("name", "id"))
    game_series = list(GameSeries.objects.order_by("name", "id")) if include_game_series else []

    platform_id = _integer(params.get("platform"))
    brand_id = _integer(params.get("brand"))
    product_type_id = _integer(params.get("product_type"))
    series_value = str(params.get("game_series") or "") if include_game_series else ""
    without_series = series_value == "none"
    game_series_id = _integer(series_value)
    platform_ids = {item.pk for item in platforms}
    brand_ids = {item.pk for item in brands}
    product_type_ids = {item.pk for item in product_types}
    platform_id = platform_id if platform_id in platform_ids else None
    brand_id = brand_id if brand_id in brand_ids else None
    product_type_id = product_type_id if product_type_id in product_type_ids else None
    game_series_id = game_series_id if game_series_id in {item.pk for item in game_series} else None

    # Platform относится только к CD. В конфликтном вручную собранном URL она
    # имеет приоритет, а фильтры техники безопасно игнорируются.
    if platform_id or game_series_id or without_series:
        brand_id = None
        product_type_id = None

    state = ProductFilterState(
        search=(params.get("search") or params.get("q") or "").strip(),
        platform_id=platform_id,
        game_series_id=game_series_id,
        without_series=without_series,
        brand_id=brand_id,
        product_type_id=product_type_id,
    )
    return state, {
        "filter_state": state,
        "platform_options": platforms,
        "game_series_options": game_series,
        "brand_options": brands,
        "product_type_options": product_types,
    }


def filter_product_querysets(cd_queryset, tech_queryset, state):
    """Применяет одинаковые правила к уже разрешённым view queryset-ам."""
    if state.platform_id or state.game_series_id or state.without_series:
        if state.platform_id:
            cd_queryset = cd_queryset.filter(platform_id=state.platform_id)
        if state.game_series_id:
            cd_queryset = cd_queryset.filter(game_series_id=state.game_series_id)
        elif state.without_series:
            cd_queryset = cd_queryset.filter(game_series__isnull=True)
        tech_queryset = tech_queryset.none()
    elif state.tech_filters_active:
        cd_queryset = cd_queryset.none()
        if state.brand_id:
            tech_queryset = tech_queryset.filter(brand_id=state.brand_id)
        if state.product_type_id:
            tech_queryset = tech_queryset.filter(product_type_id=state.product_type_id)

    return search_product_querysets(cd_queryset, tech_queryset, state.search)


def product_filter_query_string(params):
    """Сохраняет только разрешённые параметры после inline POST на Pricing."""
    values = {key: params.get(key) for key in FILTER_KEYS if params.get(key)}
    return urlencode(values)
