"""Стикер продажи: печать по POST, состояние без повторной постановки, переход по скану."""
from django.core.exceptions import ValidationError
from django.db import OperationalError
from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST
from core.decorators import permission_required_any
from .models import Sale, SaleLabelPrintJob
from . import sale_labels


def job_status(job):
    messages = {'agent_waiting': 'Стикер передан обработчику печати…', 'pending': 'Стикер ожидает печати…',
        'done': 'Стикер напечатан.', 'uncertain': 'Результат печати не подтверждён. Проверьте принтер и стикер.'}
    return {'state': job.state, 'message': job.last_error or messages.get(job.state, 'Печатаем стикер…'),
        'status_url': reverse('sales:label_print_status', args=[job.sale_id, job.request_id])}


@never_cache
@permission_required_any('sales.view_sale_detail')
@require_POST
def print_label(request, pk):
    sale = get_object_or_404(Sale, pk=pk)
    try:
        job = sale_labels.request_label(actor=request.user, sale_id=sale.pk,
            request_id=request.POST.get('request_id'),
            sale_url=request.build_absolute_uri(reverse('sales:detail', args=[sale.pk])))
        return JsonResponse(job_status(job))
    except ValidationError as error:
        return JsonResponse({'message': ' '.join(error.messages)}, status=400)
    except OperationalError:
        return JsonResponse({'message': 'База занята. Повторите нажатие чуть позже.'}, status=503)


@never_cache
@permission_required_any('sales.view_sale_detail')
@require_GET
def print_status(request, pk, request_id):
    job = get_object_or_404(SaleLabelPrintJob, sale_id=pk, request_id=request_id)
    return JsonResponse(job_status(job))


@permission_required_any('sales.view_sale_detail')
@require_GET
def scan(request):
    code = request.GET.get('code', '')
    sale_id = request.GET.get('sale_id', '')
    if code and not sale_id and sale_labels.SALE_CODE.fullmatch(code):
        sale = get_object_or_404(Sale, visible_id=code)
    elif sale_id and not code and sale_id.isascii() and sale_id.isdecimal() and 0 < len(sale_id) <= 19 and int(sale_id) > 0:
        sale = get_object_or_404(Sale, pk=int(sale_id))
    else:
        raise Http404('Некорректный номер продажи.')
    return redirect('sales:detail', pk=sale.pk)
