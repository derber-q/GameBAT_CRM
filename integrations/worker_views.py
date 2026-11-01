"""Чтение состояния для сотрудников, очередь команд только для superuser."""
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import OperationalError, ProgrammingError
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.cache import never_cache

from .worker_models import WorkerCommand
from .worker_monitoring import monitoring_snapshot, request_recovery, RESULT_LABELS, ERROR_LABELS, history_snapshot
from .worker_runtime import SERVICES


def _active(request):
    if not request.user.is_active:
        raise PermissionDenied


@login_required
@never_cache
@require_GET
def workers(request):
    _active(request)
    try:
        data = monitoring_snapshot(with_history=True)
    except (OperationalError, ProgrammingError):
        data = None
    from sales.models import MarketPrintJob
    can_review=request.user.has_perm('yandex_market.print_labels') and (request.user.has_perm('sales.view_sales') or request.user.has_perm('sales.view_sale_detail'))
    uncertain=MarketPrintJob.objects.filter(state='uncertain').select_related('order')[:20] if can_review else []
    return render(request, 'integrations/workers.html', {'monitoring': data,'uncertain_print_jobs':uncertain})


@login_required
@never_cache
@require_GET
def worker_status(request):
    _active(request)
    try:
        data = monitoring_snapshot()
        data['history'] = history_snapshot()
        if request.user.is_superuser:
            data['commands'] = [{'service': command.service, 'label': RESULT_LABELS.get(command.state, ''),
                'state': command.state, 'result': ERROR_LABELS.get(command.result, '')}
                for command in WorkerCommand.objects.order_by('-created_at')[:12]]
        return JsonResponse(data)
    except (OperationalError, ProgrammingError):
        return JsonResponse({'error': 'Состояние обработчиков недоступно. Проверьте БД и миграции.'}, status=503)


@login_required
@require_POST
def worker_start(request, service=None):
    _active(request)
    if not request.user.is_superuser:
        raise PermissionDenied
    try:
        commands = request_recovery(request.user, [service] if service else SERVICES, request.POST.get('request_id'))
    except (ValueError, TypeError, ValidationError):
        return JsonResponse({'error': 'Укажите допустимый обработчик и UUID запроса.'}, status=400)
    except (OperationalError, ProgrammingError):
        return JsonResponse({'error': 'База недоступна; повторите тот же запрос позже.'}, status=503)
    rows = list(WorkerCommand.objects.filter(pk__in=commands))
    message = ('Все необходимые обработчики уже работают' if rows and any(row.result == 'already_running' for row in rows)
               and all(row.result in ('already_running', 'disabled') for row in rows)
               else 'Команда принята; отключённые и не настроенные обработчики не запускаются')
    return JsonResponse({'message': message, 'commands': commands}, status=202)


@login_required
@never_cache
@require_GET
def worker_command(request, pk):
    _active(request)
    if not request.user.is_superuser:
        raise PermissionDenied
    command = get_object_or_404(WorkerCommand, pk=pk)
    return JsonResponse({'id': str(command.pk), 'service': command.service, 'state': command.state,
        'label': RESULT_LABELS.get(command.state, 'Нет данных'),
        'result': ERROR_LABELS.get(command.result, RESULT_LABELS.get(command.result, 'Запуск не требуется'))})
