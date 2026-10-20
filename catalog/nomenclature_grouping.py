"""Иерархия страницы номенклатуры для самой страницы и закупочных документов."""
from collections import OrderedDict

from .product_ordering import cd_order_key, tech_brand_groups


def get_nomenclature_grouping(tech_items, cd_items, *, product_of=lambda item: item):
    """Сохраняет исходные строки, включая несколько распределений одного товара."""
    platforms = OrderedDict()
    for item in sorted(cd_items, key=lambda row: cd_order_key(product_of(row))):
        product = product_of(item)
        platform = product.platform
        platform_id = platform.pk if platform is not None else None
        if platform_id not in platforms:
            platforms[platform_id] = {"platform": platform, "items": []}
        platforms[platform_id]["items"].append(item)
    cd_groups = []
    for group in platforms.values():
        series_groups = OrderedDict()
        for item in group["items"]:
            series = product_of(item).game_series
            series_id = series.pk if series is not None else None
            if series_id not in series_groups:
                series_groups[series_id] = (series, [])
            series_groups[series_id][1].append(item)
        ordered_series = sorted(
            series_groups.values(),
            key=lambda pair: (pair[0] is None, pair[0].name.casefold() if pair[0] else ""),
        )
        cd_groups.append((group["platform"], {
            "count": len(group["items"]), "items": group["items"], "series_groups": ordered_series,
        }))
    return {
        "tech_brand_groups": tech_brand_groups(tech_items, product_of=product_of),
        "cd_groups": cd_groups,
    }


def nomenclature_product_groups(tech_items, cd_items, *, product_of=lambda item: item):
    """Группы закупочных Excel: Tech → бренд → тип; CD → платформа → товар."""
    grouping = get_nomenclature_grouping(tech_items, cd_items, product_of=product_of)
    groups = []
    for brand_group in grouping["tech_brand_groups"]:
        brand = brand_group["brand"]
        brand_name = brand.name if brand and brand.name else "Без бренда"
        for product_type, items in brand_group["type_groups"]:
            type_name = product_type.name if product_type and product_type.name else "Без типа"
            groups.append(("tech", f"Tech · {brand_name} · {type_name}", items))
    for platform, group in grouping["cd_groups"]:
        platform_name = platform.name if platform and platform.name else "Без платформы"
        groups.append(("cd", f"CD · Платформа: {platform_name}", group["items"]))
    return groups
