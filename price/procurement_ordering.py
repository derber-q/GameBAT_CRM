"""Порядок строк редактора как в ценообразовании, без разделения игр по сериям."""
from catalog.product_ordering import cd_order_key, tech_brand_groups


def ordered_procurement_items(items):
    items = list(items)
    brands = tech_brand_groups(
        [item for item in items if item.product_kind == 'tech'], product_of=lambda item: item.product,
    )
    tech = [item for brand in brands for _product_type, rows in brand['type_groups'] for item in rows]
    cds = sorted(
        (item for item in items if item.product_kind == 'cd'), key=lambda item: cd_order_key(item.product),
    )
    return tech + cds
