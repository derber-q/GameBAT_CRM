"""Общие GET-фильтры товарных списков склада, номенклатуры и цен."""

from dataclasses import dataclass
from urllib.parse import urlencode

from .models import Brand, Platform, ProductType


FILTER_KEYS = ("search", "platform", "brand", "product_type")


@dataclass(frozen=True)
class ProductFilterState:
    search: str = ""
    platform_id: int | None = None
    brand_id: int | None = None
    product_type_id: int | None = None

    @property
    def is_active(self):
        return bool(self.search or self.platform_id or self.brand_id or self.product_type_id)

    @property
    def tech_filters_active(self):
        return bool(self.brand_id or self.product_type_id)


def _integer(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def product_filter_context(params):
    """Возвращает нормализованное состояние и динамические варианты фильтров."""
    platforms = list(Platform.objects.order_by("name", "id"))
    brands = list(Brand.objects.order_by("name", "id"))
    product_types = list(ProductType.objects.order_by("name", "id"))

    platform_id = _integer(params.get("platform"))
    brand_id = _integer(params.get("brand"))
    product_type_id = _integer(params.get("product_type"))
    platform_ids = {item.pk for item in platforms}
    brand_ids = {item.pk for item in brands}
    product_type_ids = {item.pk for item in product_types}
    platform_id = platform_id if platform_id in platform_ids else None
    brand_id = brand_id if brand_id in brand_ids else None
    product_type_id = product_type_id if product_type_id in product_type_ids else None

    # Platform относится только к CD. В конфликтном вручную собранном URL она
    # имеет приоритет, а фильтры техники безопасно игнорируются.
    if platform_id:
        brand_id = None
        product_type_id = None

    state = ProductFilterState(
        search=(params.get("search") or params.get("q") or "").strip(),
        platform_id=platform_id,
        brand_id=brand_id,
        product_type_id=product_type_id,
    )
    return state, {
        "filter_state": state,
        "platform_options": platforms,
        "brand_options": brands,
        "product_type_options": product_types,
    }


def _search_queryset(queryset, search, *, include_cusa=False):
    if not search:
        return queryset

    numeric_id = int(search) if search.isdecimal() and len(search) <= 19 else None
    if numeric_id is not None and queryset.filter(pk=numeric_id).exists():
        return queryset.filter(pk=numeric_id)

    fields = ["id", "name", "sku", "barcode"]
    if include_cusa:
        fields.append("cusa_ppsa_code")
    needle = search.casefold()
    matches = []
    for values in queryset.values_list(*fields).iterator(chunk_size=2000):
        product_id, *text_values = values
        if any(needle in (value or "").casefold() for value in text_values):
            matches.append(product_id)
    return queryset.filter(pk__in=matches)


def filter_product_querysets(cd_queryset, tech_queryset, state):
    """Применяет одинаковые правила к уже разрешённым view queryset-ам."""
    if state.platform_id:
        cd_queryset = cd_queryset.filter(platform_id=state.platform_id)
        tech_queryset = tech_queryset.none()
    elif state.tech_filters_active:
        cd_queryset = cd_queryset.none()
        if state.brand_id:
            tech_queryset = tech_queryset.filter(brand_id=state.brand_id)
        if state.product_type_id:
            tech_queryset = tech_queryset.filter(product_type_id=state.product_type_id)

    cd_queryset = _search_queryset(cd_queryset, state.search, include_cusa=True)
    tech_queryset = _search_queryset(tech_queryset, state.search)
    return cd_queryset, tech_queryset


def product_filter_query_string(params):
    """Сохраняет только разрешённые параметры после inline POST на Pricing."""
    values = {key: params.get(key) for key in FILTER_KEYS if params.get(key)}
    return urlencode(values)
