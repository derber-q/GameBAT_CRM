"""Общий порядок прайса и таблиц CRM без изменения состава выборок."""
from collections import OrderedDict

from price.sony_gamepad_sorting import is_sony_gamepad, normalize_product_name, sony_gamepad_sort_key


def normalized_order_name(value):
    return " ".join(str(value or "").casefold().replace("ё", "е").split())


PORTABLE_BRANDS = {"anbernic", "ayaneo", "steam deck", "gpd", "retroid", "powkiddy", "odin"}
SONY_TYPE_ORDER = (
    ("зарядная станция для геймпад", 4),
    ("игровая консоль", 0), ("внешний привод", 1), ("зарядная станция", 2),
    ("геймпад", 3), ("запасная часть", 5), ("запчаст", 5),
    ("игровая гарнитура", 6), ("vr-шлем", 7), ("vr шлем", 7),
    ("vr-аксессуар", 8), ("vr аксессуар", 8), ("стриминговая приставка", 9),
    ("консол", 0),
)
NINTENDO_TYPE_ORDER = (
    ("портатив", 0), ("handheld", 0), ("portable", 0), ("карманн", 0),
    ("чехол", 1), ("геймпад", 2), ("игровая гарнитура", 3),
)


def is_portable(product_type_name, brand_name=""):
    value = normalized_order_name(product_type_name)
    return any(token in value for token in ("портатив", "handheld", "portable", "карманн")) or normalized_order_name(brand_name) in PORTABLE_BRANDS


def type_rank(value, rules, default=999):
    value = normalized_order_name(value)
    return next((rank for token, rank in rules if token in value), default)


def tech_section(product):
    brand = normalized_order_name(product.brand.name if product.brand_id else "")
    product_type = product.product_type.name if product.product_type_id else ""
    if brand == "sony":
        return 0, "Sony"
    if brand == "nintendo":
        return 1, "Nintendo"
    if is_portable(product_type, brand):
        return 2, "Портативные консоли"
    return 3, "Прочие товары"


def tech_price_order(product, *, for_excel=False):
    """Общий порядок CRM; отдельные правила Edge и VR применяются только к XLSX."""
    section_rank, section = tech_section(product)
    product_type = product.product_type.name if product.product_type_id else "Без типа"
    normalized_type = normalized_order_name(product_type)
    brand = product.brand.name if product.brand_id else "Без бренда"
    if for_excel and normalized_order_name(brand) != "sony" and normalize_product_name(product_type).startswith(
        ("vr шлем", "vr headset", "шлем виртуальной реальности"),
    ):
        return (
            (3, normalized_order_name(brand), normalized_type, normalized_order_name(product.name), product.pk),
            f"Tech · VR-шлемы · {brand}",
        )
    rules = SONY_TYPE_ORDER if section_rank == 0 else NINTENDO_TYPE_ORDER if section_rank == 1 else ()
    rank = type_rank(normalized_type, rules)
    if section_rank in (0, 1):
        title = f"Tech · {section} · {product_type}"
        product_key = sony_gamepad_sort_key(product) if is_sony_gamepad(product) else (0, normalized_order_name(product.name), product.pk)
        if for_excel:
            name = normalize_product_name(product.name)
            edge_first = is_sony_gamepad(product) and any(token in name for token in ("dualsense edge", "dual sense edge"))
            product_key = (0 if edge_first else 1, *product_key)
        key = (section_rank, rank, normalized_type, *product_key)
    elif section_rank == 2:
        title = f"Tech · {section} · {brand}"
        key = (section_rank, normalized_order_name(brand), normalized_type, normalized_order_name(product.name), product.pk)
    else:
        title = f"Tech · {section}"
        key = (4 if for_excel else section_rank, normalized_type, normalized_order_name(product.name), product.pk)
    return key, title


def cd_order_key(product):
    return normalized_order_name(product.platform.name), normalized_order_name(product.name), product.pk


def tech_brand_groups(items, *, product_of=lambda item: item):
    """Группирует уже разрешённые строки по бренду и типу, сохраняя поля строк."""
    brands = OrderedDict()
    # Минимальный ранг бренда позволяет объединить его портативные и обычные
    # товары в одну группу, не потеряв и не продублировав ни одну позицию.
    ordered = sorted(items, key=lambda item: tech_price_order(product_of(item))[0])
    for item in ordered:
        product = product_of(item)
        if product.brand_id not in brands:
            brands[product.brand_id] = {"brand": product.brand, "count": 0, "types": OrderedDict()}
        brand = brands[product.brand_id]
        brand["count"] += 1
        type_id = product.product_type_id
        if type_id not in brand["types"]:
            brand["types"][type_id] = (product.product_type, [])
        brand["types"][type_id][1].append(item)
    result = []
    for grouping in brands.values():
        result.append({"brand": grouping["brand"], "count": grouping["count"], "type_groups": list(grouping["types"].values())})
    return result
