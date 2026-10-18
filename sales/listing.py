"""Общие выборки списков и данные интерфейса; переходы выполняет sales.services."""
from itertools import chain, islice

from django.core.paginator import Paginator
from .models import Sale
from .services import can_mark_paid, next_order_status


def sales_queryset():
    return Sale.objects.select_related(
        'warehouse', 'created_by', 'cancelled_by', 'consignment_platform',
    ).prefetch_related('cd_items', 'tech_items', 'custom_items', 'consignment_items')


def _items_preview(sale):
    if sale.sale_type == Sale.SaleType.WHOLESALE:
        return [], False
    groups = [sorted(sale._related_items(name), key=lambda item: item.pk) for name in (
        'cd_items', 'tech_items', 'custom_items', 'consignment_items',
    )]
    # У старых продаж реализации могут быть складские строки-зеркала.
    if sale.sale_type == Sale.SaleType.CONSIGNMENT and groups[-1]:
        groups = groups[-1:]
    items = list(islice(chain.from_iterable(groups), 5))
    return [{'name': item.product_name_snapshot, 'quantity': item.quantity} for item in items[:4]], len(items) > 4


def status_context(sale, user, editable=True):
    order = next_order_status(sale) if editable and (
        user.is_superuser or user.has_perm('sales.advance_order_status')) else None
    payment = editable and can_mark_paid(sale) and (
        user.is_superuser or user.has_perm('sales.mark_sale_paid'))
    items, has_more_items = _items_preview(sale)
    return {
        'sale': sale, 'version': sale.updated_at.isoformat(), 'next_order': order,
        'next_order_label': Sale.OrderStatus(order).label if order else '',
        'can_mark_paid': payment, 'items_preview': items, 'has_more_items': has_more_items,
    }


def list_groups(request, state):
    queryset = sales_queryset()
    if state == 'cancelled':
        queryset = queryset.filter(cancelled_at__isnull=False)
    else:
        queryset = queryset.filter(cancelled_at__isnull=True)
        # Дата completed_at сама по себе не определяет завершённость: нужны
        # оба состояния, а отменённые уже исключены отдельным фильтром выше.
        terminal = dict(order_status=Sale.OrderStatus.DELIVERED, payment_status=Sale.PaymentStatus.PAID)
        queryset = queryset.filter(**terminal) if state == 'completed' else queryset.exclude(**terminal)
    groups = []
    for kind, label in Sale.SaleType.choices:
        page_key = f'page_{kind}'
        page = Paginator(queryset.filter(sale_type=kind), 50).get_page(request.GET.get(page_key))
        def page_url(number):
            params = request.GET.copy()
            params[page_key] = number
            return '?' + params.urlencode()
        groups.append({
            'kind': kind, 'label': label, 'sale_types': (kind,), 'page': page,
            'column_count': (9 if kind == Sale.SaleType.WHOLESALE else 8) + {
                'completed': 1, 'cancelled': 2,
            }.get(state, 0),
            'rows': [status_context(sale, request.user, state == 'incomplete') for sale in page],
            'previous_url': page_url(page.previous_page_number()) if page.has_previous() else '',
            'next_url': page_url(page.next_page_number()) if page.has_next() else '',
        })
    return groups
