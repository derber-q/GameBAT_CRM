"""Общая выборка CD/Tech для таблицы и этапов РФ/Ростова, без N+1."""
from django.db.models import Sum, Exists, OuterRef
from catalog.models import CD, Tech
from catalog.product_search import filter_products_by_text
from integrations.avito_check import manual_search_url
from integrations.models import AvitoListingConnection, AvitoManualPrice
from price.models import ProcurementPriceList

SCOPES = tuple(AvitoManualPrice.Scope.values)
SCOPE_LABELS = dict(AvitoManualPrice.Scope.choices)
WARNING = 'Минимальная цена по России выше цены по Ростову-на-Дону. Проверьте актуальность данных.'


def found_prices(product):
    """Профиль и обе цены уже загружены listed_products одним prefetch."""
    return {price.scope: price for price in product.avito_profile.manual_prices.all()}


def listed_products(*, query='', sort='name', product_id=None, kind=None):
    result = []
    for current, model, relations in [('cd', CD, ('platform', 'game_series')), ('tech', Tech, ('brand', 'product_type'))]:
        if kind and current != kind:
            continue
        # Exists не размножает складские строки. Сам профиль ещё не означает привязку.
        products = model.objects.annotate(has_listing=Exists(AvitoListingConnection.objects.filter(
            **{'profile__' + current + '_id': OuterRef('pk')},
        ))).filter(has_listing=True).select_related(
            'avito_profile', *relations,
        ).prefetch_related('avito_profile__manual_prices').annotate(
            physical_stock=Sum('warehouse_stocks__quantity'),
        ).filter(physical_stock__gt=0)
        if product_id is not None:
            products = products.filter(pk=product_id)
        if query:
            products = filter_products_by_text(products, query, product_kind=current)
        result.extend(products)
    result.sort(key=lambda product: (product.name.casefold(), product._meta.model_name, product.pk))
    if sort in {'oldest', 'newest'}:
        # Прежняя дата теперь относится к РФ; смешивать её с датой Ростова нельзя.
        dated = [product for product in result if 'russia' in found_prices(product)]
        undated = [product for product in result if 'russia' not in found_prices(product)]
        dated.sort(key=lambda product: found_prices(product)['russia'].recorded_at, reverse=sort == 'newest')
        result = dated + undated
    return result


def import_costs():
    """Сохранённая база + доставка последней обычной версии, без отката к старой."""
    price = ProcurementPriceList.objects.filter(is_trip_addition=False).first()
    if not price:
        return None, {}
    items = price.items.only('price_list', 'product_kind', 'cd', 'tech', 'base_price_rub', 'delivery_rub')
    return price, {(item.product_kind, item.product_id): item.stock_unit_cost for item in items}


def manual_product_data(product, scope):
    kind = product._meta.model_name
    found = found_prices(product).get(scope)
    return {
        'id': product.pk, 'product_id': product.pk, 'kind': kind,
        'scope': scope, 'scope_label': SCOPE_LABELS[scope], 'name': product.name,
        'price': str(found.price) if found else '',
        'recorded_at': found.recorded_at.isoformat() if found else '',
        'search_url': manual_search_url(product, kind, scope),
    }
