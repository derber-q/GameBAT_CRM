"""Разрешённые операции Маркета из продажи; отправку выполняет существующий worker."""
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import OperationalError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST, require_GET

from core.decorators import permission_required_any
from yandex_market.documents import request_labels
from yandex_market.models import OrderMetadata, LabelDocument
from yandex_market.orders import request_order_action
from .market_fulfillment import record_scan, request_print
from .models import MarketPrintJob


def _back(request, sale_id):
    if request.POST.get('return_to') == 'list' and request.user.has_perm('sales.view_sales'):
        return redirect('sales:incomplete')
    if request.user.has_perm('sales.view_sale_detail'):
        return redirect('sales:detail', pk=sale_id)
    return redirect('sales:incomplete')


def _confirm(request):
    if request.POST.get('confirm') != 'yes':
        raise ValidationError('Подтвердите отмену заказа в Яндекс Маркете.')


@require_POST
@permission_required_any('sales.view_sales', 'sales.view_sale_detail')
@permission_required_any('yandex_market.manage_orders')
def sale_market_action(request, pk):
    order = get_object_or_404(OrderMetadata.objects.select_related('integration', 'sale'), sale_id=pk)
    try:
        action = request.POST.get('action')
        if action not in {'refresh', 'ready', 'cancel'}:
            raise ValidationError('Выберите разрешённое действие Маркета.')
        if action == 'cancel':
            _confirm(request)
        if action == 'ready' and not MarketPrintJob.objects.filter(order=order, printed_at__isnull=False).exists():
            raise ValidationError('Сначала напечатайте стикер и дождитесь подтверждения печати Windows.')
        if order.sale.is_cancelled or order.sale.is_completed:
            raise ValidationError('Продажа уже завершена или отменена.')
        request_order_action(order_id=order.pk, actor=request.user, action=action,
            expected_status=(request.POST.get('market_status'), request.POST.get('market_substatus')))
        messages.success(request, 'Запрос отправлен в обработку. Статус изменится после подтверждения Маркета; обновите страницу.')
    except ValidationError as exc:
        messages.error(request, ' '.join(exc.messages))
    except OperationalError:
        messages.error(request, 'База занята. Обновите страницу и проверьте действие перед повторной отправкой.')
    return _back(request, pk)


@require_POST
@never_cache
@permission_required_any('sales.view_sales', 'sales.view_sale_detail')
@permission_required_any('yandex_market.print_labels')
def sale_market_label(request, pk):
    order = get_object_or_404(OrderMetadata.objects.select_related('integration'), sale_id=pk)
    try:
        if order.fake:
            raise ValidationError('Это тестовый заказ Маркета.')
        document = request_labels(integration=order.integration, orders=[order], actor=request.user,
            format_name='A9_HORIZONTALLY', reuse=True)
    except ValidationError as exc:
        return JsonResponse({'error': ' '.join(exc.messages)}, status=400)
    except OperationalError:
        return JsonResponse({'error': 'База занята. Повторите печать стикера через несколько секунд.'}, status=503)
    return _label_response(document, pk)


def _label_response(document, sale_id):
    data = {'state': document.state,
            'status_url': reverse('sales:market_label_status', args=[sale_id, document.pk])}
    if document.state == 'done' and document.file:
        data['file_url'] = reverse('yandex_market:label_file', args=[document.pk])
    elif document.state == 'error' or document.state == 'done':
        data.update(state='error', error=document.last_error or 'Не удалось получить PDF стикера. Повторите печать.')
    return JsonResponse(data)


@require_GET
@never_cache
@permission_required_any('sales.view_sales', 'sales.view_sale_detail')
@permission_required_any('yandex_market.print_labels')
def sale_market_label_status(request, pk, document_id):
    document = get_object_or_404(LabelDocument, pk=document_id, order__sale_id=pk)
    return _label_response(document, pk)


def _print_response(job):
    messages_by_state = {
        'pending': 'Подготавливаем заказ и стикер…', 'waiting_pdf': 'Яндекс готовит PDF стикера…',
        'printing': 'Передаём стикер на принтер…', 'spooled': 'Ожидаем завершения печати…',
        'printed': 'Стикер напечатан. Отправляем готовность…' if job.ready_after_print else 'Стикер напечатан.',
        'waiting_ready': 'Стикер напечатан. Яндекс подтверждает готовность…',
        'done': 'Стикер напечатан, заказ готов к отгрузке.' if job.ready_after_print else 'Стикер напечатан.',
    }
    return {'state': job.state, 'print_job_id': str(job.request_id), 'order_id': job.order.order_id,
            'sale_pk': job.order.sale_id, 'printed': bool(job.printed_at),
            'market_status': job.order.status, 'market_substatus': job.order.substatus,
            'status_url': reverse('sales:market_print_status', args=[job.request_id]),
            'message': job.last_error if job.state in {'error', 'uncertain'} else messages_by_state.get(job.state, 'Обработка…')}


@require_POST
@never_cache
@permission_required_any('sales.view_sales')
@permission_required_any('yandex_market.print_labels')
@permission_required_any('yandex_market.manage_orders')
def sale_market_scan(request):
    try:
        result = record_scan(actor=request.user, barcode=request.POST.get('barcode'), request_id=request.POST.get('request_id'))
        if result.get('print_job_id'):
            result = {**result, 'status_url': reverse('sales:market_print_status', args=[result['print_job_id']])}
        return JsonResponse(result)
    except ValidationError as exc:
        return JsonResponse({'error': ' '.join(exc.messages)}, status=400)
    except OperationalError:
        return JsonResponse({'error': 'База занята. Повторите тот же скан через несколько секунд.'}, status=503)


@require_POST
@never_cache
@permission_required_any('sales.view_sales', 'sales.view_sale_detail')
@permission_required_any('yandex_market.print_labels')
def sale_market_print(request, pk):
    order = get_object_or_404(OrderMetadata.objects.select_related('integration'), sale_id=pk)
    try:
        job = request_print(order=order, actor=request.user, request_id=request.POST.get('request_id'))
        return JsonResponse(_print_response(job))
    except ValidationError as exc:
        return JsonResponse({'error': ' '.join(exc.messages)}, status=400)
    except OperationalError:
        return JsonResponse({'error': 'База занята. Повторите запрос печати через несколько секунд.'}, status=503)


@require_GET
@never_cache
@permission_required_any('sales.view_sales', 'sales.view_sale_detail')
@permission_required_any('yandex_market.print_labels')
def sale_market_print_status(request, request_id):
    job = get_object_or_404(MarketPrintJob.objects.select_related('order'), request_id=request_id)
    return JsonResponse(_print_response(job))
