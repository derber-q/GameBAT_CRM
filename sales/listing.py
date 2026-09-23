"""Общие выборки списков и данные интерфейса; переходы выполняет sales.services."""
from django.core.paginator import Paginator
from .models import Sale
from .services import can_mark_paid, next_order_status


def sales_queryset():
    return Sale.objects.select_related(
        'warehouse', 'created_by', 'cancelled_by', 'consignment_platform',
    ).prefetch_related('cd_items', 'tech_items')


def status_context(sale, user, editable=True):
    order = next_order_status(sale) if editable and (
        user.is_superuser or user.has_perm('sales.advance_order_status')) else None
    payment = editable and can_mark_paid(sale) and (
        user.is_superuser or user.has_perm('sales.mark_sale_paid'))
    return {
        'sale': sale, 'version': sale.updated_at.isoformat(), 'next_order': order,
        'next_order_label': Sale.OrderStatus(order).label if order else '',
        'can_mark_paid': payment,
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
            'kind': kind, 'label': label, 'page': page,
            'rows': [status_context(sale, request.user, state == 'incomplete') for sale in page],
            'previous_url': page_url(page.previous_page_number()) if page.has_previous() else '',
            'next_url': page_url(page.next_page_number()) if page.has_next() else '',
        })
    return groups
