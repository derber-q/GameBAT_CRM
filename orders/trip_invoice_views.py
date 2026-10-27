"""Сохранение отметки поставщика без изменения статусов заказов и ревизии рейса."""
from django.core.exceptions import ValidationError
from django.db import OperationalError
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from core.decorators import permission_required_all
from .trip_invoices import set_invoice_accepted
from .trips import MANAGE_PERMISSIONS


@require_POST
@never_cache
@permission_required_all(*MANAGE_PERMISSIONS)
def invoice_update(request, pk, supplier_pk):
    value = request.POST.get('accepted')
    if value not in ('0', '1'):
        return JsonResponse({'success': False, 'message': 'Укажите состояние флага инвойса.'}, status=400)
    try:
        flag = set_invoice_accepted(actor=request.user, batch_id=pk, supplier_id=supplier_pk, accepted=value == '1')
    except ValidationError as exc:
        return JsonResponse({'success': False, 'message': ' '.join(exc.messages)}, status=409)
    except OperationalError:
        return JsonResponse({'success': False, 'message': 'База занята. Повторите сохранение отметки.'}, status=503)
    return JsonResponse({'success': True, 'accepted': flag.accepted})
