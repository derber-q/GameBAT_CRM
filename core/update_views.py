"""Страница создаёт только ограниченную заявку; Git/Docker в HTTP не вызываются."""
from datetime import datetime, timezone
from pathlib import Path
import json
import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from deployment import SOURCE
from deployment.store import UpdateError
from deployment.gateway import submit
from deployment.version import current_version

LOCAL_MESSAGE = 'Обновления доступны только для production-версии.'
ACTION_LABELS = {'check':'Проверка обновлений','install':'Установка','rollback':'Откат кода'}
STAGE_LABELS = {'queued':'Ожидает','checking':'Проверка запроса','preparing':'Подготовка версии',
    'validating':'Проверка кандидата','stopping':'Остановка процессов','backup':'Резервное копирование',
    'switching':'Установка','health':'Проверка работоспособности','done':'Завершено','error':'Ошибка',
    'restoring':'Восстановление','interrupted':'Прервано'}


def update_state():
    raw = getattr(settings, 'UPDATE_STATUS_FILE', '')
    if not raw:
        raise UpdateError('Менеджер обновлений не настроен: требуется подключение на хостинге.')
    path = Path(raw)
    if not path.is_absolute() or path.resolve()!=path or path.stat().st_size>1024*1024:
        raise UpdateError('Недопустимый файл состояния менеджера.')
    return json.loads(path.read_text('utf-8'))


def manager_ready(heartbeat):
    try:
        age = (datetime.now(timezone.utc)-datetime.fromisoformat(heartbeat['at'])).total_seconds()
        return heartbeat['protocol'] == 1 and -10 <= age <= 30
    except (KeyError, TypeError, ValueError):
        return False


@require_http_methods(['GET', 'POST'])
@never_cache
@login_required
def updates(request):
    if not request.user.is_active or not request.user.is_superuser:
        raise PermissionDenied('Обновления доступны только суперпользователю.')
    production = settings.GAMEBAT_ENV == 'production'
    context = {'mode': settings.GAMEBAT_ENV, 'production': production, 'source': SOURCE,
               'version': current_version(settings.BASE_DIR), 'history': [], 'latest': {},
               'current': {}, 'manager_available': False, 'busy': False, 'reason': '',
               'request_check': uuid.uuid4(), 'request_install': uuid.uuid4(), 'request_rollback': uuid.uuid4()}
    # Режим выбирает сервер. GET/POST локальной и тестовой CRM не открывают журнал.
    if not production:
        if request.method == 'POST':
            messages.info(request, LOCAL_MESSAGE)
            return redirect('integrations:updates')
        return render(request, 'core/updates.html', context)
    try:
        state = update_state()
        context.update(latest=state.get('latest', {}), current=state.get('current', {}),
                       history=state.get('history', []), manager_available=manager_ready(state.get('heartbeat', {})),
                       rollback=state.get('rollback', {}))
        context['history'] = [{**operation, 'action_label':ACTION_LABELS.get(operation['action'],'Операция'),
            'state_label':STAGE_LABELS.get(operation['state'],'Неизвестное состояние'),
            'journal':[{**row,'stage_label':STAGE_LABELS.get(row['stage'],'Неизвестный этап')} for row in operation['journal']]}
            for operation in context['history']]
        context['busy'] = any(operation.get('finished_at') is None for operation in context['history'])
        if state.get('recovery_required'):
            context['manager_available'] = False
            raise UpdateError('Требуется проверка прерванной установки администратором сервера.')
        if request.method == 'POST':
            if not context['manager_available']:
                raise UpdateError('Менеджер обновлений недоступен. Установка не запущена.')
            action = request.POST.get('action')
            target = ''
            if action in ('install', 'rollback'):
                if request.POST.get('confirm') != 'yes':
                    raise UpdateError('Подтвердите установку показанной версии.')
                candidate = context['latest'] if action == 'install' else context['rollback']
                if not candidate.get('approved') or candidate.get('sha') != request.POST.get('target'):
                    raise UpdateError('Версия не проверена или изменилась. Сначала проверьте обновления.')
                target = candidate['sha']
            operation = submit(getattr(settings,'UPDATE_SOCKET',''),{'action':action,'actor':request.user.pk,
                'request_id':request.POST.get('request_id'),'target':target})
            messages.success(request, f'Операция {operation} принята менеджером. Обновляйте страницу для просмотра хода.')
            return redirect('integrations:updates')
        if not context['manager_available']:
            context['reason'] = 'Менеджер обновлений недоступен. Установка заблокирована.'
    except (UpdateError, OSError, ValueError, TypeError) as error:
        message = str(error) if isinstance(error, UpdateError) else 'Журнал обновлений недоступен. Установка заблокирована.'
        if request.method == 'POST':
            messages.error(request, message)
            return redirect('integrations:updates')
        context['reason'] = message
    return render(request, 'core/updates.html', context)
