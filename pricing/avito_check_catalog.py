"""Единая выборка таблицы и ручной очереди Avito Check."""
from django.db.models import Sum

from catalog.models import CD
from catalog.product_search import filter_products_by_text
from integrations.avito_check import manual_search_url


def listed_products(*, query='', sort='name', product_id=None):
    products = CD.objects.filter(avito_profile__connection__isnull=False).select_related(
        'avito_profile__manual_price', 'platform', 'game_series',
    ).annotate(physical_stock=Sum('warehouse_stocks__quantity')).filter(physical_stock__gt=0)
    if product_id is not None:
        products = products.filter(pk=product_id)
    if query:
        products = filter_products_by_text(products, query, product_kind='cd')
    products = sorted(products, key=lambda p: (p.name.casefold(), p.pk))
    if sort in {'oldest', 'newest'}:
        dated = [p for p in products if getattr(p.avito_profile, 'manual_price', None) is not None]
        undated = [p for p in products if getattr(p.avito_profile, 'manual_price', None) is None]
        dated.sort(key=lambda p: p.avito_profile.manual_price.recorded_at, reverse=sort == 'newest')
        products = dated + undated
    return products


def manual_product_data(product):
    found = getattr(product.avito_profile, 'manual_price', None)
    return {'id': product.pk, 'name': product.name, 'price': str(found.price) if found else '',
        'recorded_at': found.recorded_at.isoformat() if found else '',
        'search_url': manual_search_url(product, 'cd')}
