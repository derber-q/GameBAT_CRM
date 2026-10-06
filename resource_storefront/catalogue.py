from catalog.product_search import filter_products_by_text

from catalog.models import CD, Tech, Platform, Brand, ProductType, ProductImage
from warehouse.models import CDWarehouseStock, TechWarehouseStock

from .models import StorefrontSettings, StorefrontProduct, RetailSettings
from .filters import category_type_ids


def storefront_warehouse(mode="wholesale"):
    model = RetailSettings if mode == "retail" else StorefrontSettings
    return model.objects.select_related("warehouse").filter(pk=1).first()


def visible_product_rows(*, kind="", category="", query="", platform="", brand="", product_type="", price_min=None, price_max=None, ordering="name", ids=None, mode="wholesale"):
    config = storefront_warehouse(mode)
    price_field = "avito_price" if mode == "retail" else "wholesale_price"
    if not config or not config.warehouse_id:
        return []
    if mode == "retail":
        if config.price_source != "avito_price":
            return []
        price_field = config.price_source
    wh_id = config.warehouse_id
    result = []
    models = (("cd", CD, CDWarehouseStock, "cd"), ("tech", Tech, TechWarehouseStock, "tech"))
    if category:
        kind = "cd" if category == "cd" else "tech"
    category_ids = category_type_ids(category) if category in {"consoles", "gamepads", "accessories"} else None
    for product_kind, model, stock_model, relation in models:
        if kind and kind != product_kind:
            continue
        if (platform and product_kind != "cd") or ((brand or product_type) and product_kind != "tech"):
            continue
        stocks = stock_model.objects.filter(warehouse_id=wh_id, quantity__gt=0)
        if ids is not None:
            stocks = stocks.filter(**{f"{relation}_id__in": ids.get(product_kind, ())})
        stock = {getattr(row, f"{relation}_id"): row.quantity for row in stocks}
        qs = model.objects.active().filter(**{price_field + "__gt": 0}, pk__in=stock)
        if mode != "retail":
            qs = qs.filter(wholesale_site_enabled=True)
        if ids is not None:
            qs = qs.filter(pk__in=ids.get(product_kind, ()))
        if query:
            qs = filter_products_by_text(qs, query, product_kind=product_kind)
        if product_kind == "cd":
            qs = qs.select_related("platform", "game_series")
            if platform:
                qs = qs.filter(platform_id=platform)
        else:
            qs = qs.select_related("brand", "product_type")
            if brand:
                qs = qs.filter(brand_id=brand)
            if product_type:
                qs = qs.filter(product_type_id=product_type)
            if category_ids is not None:
                qs = qs.filter(product_type_id__in=category_ids)
        if price_min is not None and price_min != "":
            qs = qs.filter(**{price_field + "__gte": price_min})
        if price_max is not None and price_max != "":
            qs = qs.filter(**{price_field + "__lte": price_max})
        for product in qs:
            result.append({"product": product, "kind": product_kind, "available": stock[product.pk], "price": getattr(product, price_field), "mode": mode})
    reverse = ordering == "price_desc"
    if ordering in {"price", "price_desc"}:
        result.sort(key=lambda row: (row["price"], row["product"].name.casefold(), row["kind"], row["product"].pk), reverse=reverse)
    elif ordering == "newest":
        dates = {(slot.product_kind, slot.cd_id or slot.tech_id): slot.created_at.timestamp()
                 for slot in StorefrontProduct.objects.filter(placement="new")}
        result.sort(key=lambda row: (-dates.get((row["kind"], row["product"].pk), 0), row["product"].name.casefold(), row["kind"], row["product"].pk))
    else:
        result.sort(key=lambda row: (row["product"].name.casefold(), row["kind"], row["product"].pk))
    return result


def product_by_id(kind, pk, mode="wholesale"):
    rows = visible_product_rows(kind=kind, ids={kind: [pk]}, mode=mode)
    return rows[0] if rows else None


def buyer_filters(rows=None):
    rows = visible_product_rows() if rows is None else rows
    cds = [row["product"] for row in rows if row["kind"] == "cd"]
    techs = [row["product"] for row in rows if row["kind"] == "tech"]
    return {
        "platforms": Platform.objects.filter(pk__in={p.platform_id for p in cds}).order_by("name"),
        "brands": Brand.objects.filter(pk__in={p.brand_id for p in techs}).order_by("name"),
        "product_types": ProductType.objects.filter(pk__in={p.product_type_id for p in techs}).order_by("name"),
    }


def product_images(row):
    product = row["product"]
    gallery = ProductImage.objects.filter(product_kind=row["kind"], image_kind="product")
    gallery = gallery.filter(cd=product) if row["kind"] == "cd" else gallery.filter(tech=product)
    from django.urls import reverse
    namespace = "retailer" if row.get("mode") == "retail" else "resource_storefront"
    urls = []
    if product.title_image:
        urls.append(reverse(f"{namespace}:product_photo", kwargs={"kind": row["kind"], "pk": product.pk, "image_id": 0}))
    urls.extend(reverse(f"{namespace}:product_photo", kwargs={"kind": row["kind"], "pk": product.pk, "image_id": image.pk}) for image in gallery if image.image)
    return urls


def row_key(kind, product_id):
    return f"{kind}:{int(product_id)}"


def parse_cart(session, mode="wholesale"):
    cart = session.get("retailer_cart" if mode == "retail" else "resource_cart", {})
    result = {}
    if isinstance(cart, dict):
        for key, value in cart.items():
            try:
                kind, raw_id = key.split(":", 1)
                quantity = int(value)
                product_id = int(raw_id)
                if kind in {"cd", "tech"} and quantity > 0:
                    result[row_key(kind, product_id)] = quantity
            except (ValueError, TypeError):
                continue
    return result


def set_cart(session, cart, mode="wholesale"):
    session["retailer_cart" if mode == "retail" else "resource_cart"] = cart
    session.modified = True
