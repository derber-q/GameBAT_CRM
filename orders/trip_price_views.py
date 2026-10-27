"""Предпросмотр и подтверждённое сохранение закупочной цены выбранной строки."""
import logging

from django.core.exceptions import ValidationError
from django.db import OperationalError, transaction
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from core.decorators import permission_required_all
from .trip_prices import change_trip_price, preview_trip_price
from .trips import MANAGE_PERMISSIONS
from .trip_invoices import require_page_editable

logger = logging.getLogger('gamebat.business')


def _price_response(request, pk, line_pk, *, save):
    arguments = {'actor': request.user, 'batch_id': pk, 'line_id': line_pk,
                 'revision': request.POST.get('revision'), 'price_aed': request.POST.get('price_aed')}
    try:
        with transaction.atomic():
            require_page_editable(batch_id=pk, line_id=line_pk)
            if save:
                batch = change_trip_price(**arguments, reason=request.POST.get('reason', ''))
                return JsonResponse({'success': True, 'revision': batch.revision})
            return JsonResponse({'success': True, **preview_trip_price(**arguments)})
    except ValidationError as exc:
        return JsonResponse({'success': False, 'message': ' '.join(exc.messages)}, status=409)
    except OperationalError:
        logger.exception('Ошибка изменения закупочной цены рейса: batch_id=%s line_id=%s', pk, line_pk)
        return JsonResponse({'success': False, 'message': 'База занята. Обновите страницу и повторите.'}, status=503)


@require_POST
@never_cache
@permission_required_all(*MANAGE_PERMISSIONS)
def preview(request, pk, line_pk):
    return _price_response(request, pk, line_pk, save=False)


@require_POST
@never_cache
@permission_required_all(*MANAGE_PERMISSIONS)
def update(request, pk, line_pk):
    return _price_response(request, pk, line_pk, save=True)
