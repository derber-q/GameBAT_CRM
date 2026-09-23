"""Рекомендательные предупреждения о цене; не блокируют её сохранение."""
from catalog.product_fields import PRICE_FIELDS

MARKUP_FOR_PRICE = {
    "avito_price": "avito_markup_from_wholesale",
    "yandex_market_price": "yandex_markup_from_wholesale",
}


def price_warning(*, price, wholesale, cost, markup=None):
    reasons = []
    if price is not None:
        if markup is not None and wholesale is not None and price - wholesale < markup:
            reasons.append(f"Наценка от оптовой цены ниже установленной: {price - wholesale:.2f} ₽ < {markup:.2f} ₽")
        if cost is not None and price < cost:
            reasons.append(f"Цена ниже себестоимости: {price:.2f} ₽ < {cost:.2f} ₽")
    return "\n".join(reasons)


def product_price_warnings(product):
    return {field: price_warning(
        price=getattr(product, field), wholesale=product.wholesale_price, cost=product.cost,
        markup=getattr(product, MARKUP_FOR_PRICE[field]) if field in MARKUP_FOR_PRICE else None,
    ) for field in PRICE_FIELDS}
