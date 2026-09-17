"""Единый регистронезависимый поиск CD и Tech для складских операций."""


def filter_products_by_text(queryset, query, *, product_kind):
    query = str(query or "").strip()
    if not query:
        return queryset
    fields = ("name", "sku", "barcode", "cusa_ppsa_code") if product_kind == "cd" else (
        "name", "sku", "barcode",
    )
    needle = query.casefold()
    numeric_id = int(query) if query.isdecimal() and len(query) <= 19 else None
    matches = []
    for values in queryset.values_list("id", *fields).iterator(chunk_size=2000):
        product_id, *text_values = values
        if product_id == numeric_id or any(needle in str(value or "").casefold() for value in text_values):
            matches.append(product_id)
    return queryset.filter(pk__in=matches)


def search_product_querysets(cd_queryset, tech_queryset, query):
    return (
        filter_products_by_text(cd_queryset.active(), query, product_kind="cd"),
        filter_products_by_text(tech_queryset.active(), query, product_kind="tech"),
    )
