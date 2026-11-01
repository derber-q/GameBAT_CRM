"""Контроллер и читаемое представление: запуск только через фиксированный OS-адаптер."""
from datetime import timedelta
import logging
import uuid

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from core.db_retry import retry_database_lock

from .worker_models import WorkerController, WorkerService, WorkerProcess, WorkerCommand, WorkerEvent, SERVICE_CHOICES
from .worker_policy import expected_services
from .worker_runtime import SERVICES, STALE_SECONDS, START_SECONDS, STABLE_SECONDS, RETRY_SECONDS, MAX_FAILURES

logger = logging.getLogger('gamebat.business')
STATUS_LABELS = {'running': 'Работает', 'recovering': 'Восстанавливается', 'stopped': 'Остановлен',
                 'paused': 'Автовосстановление приостановлено', 'disabled': 'Отключён',
                 'unconfigured': 'Не настроен', 'unknown': 'Статус неизвестен'}
EXPECTED_LABELS = {'required': 'Должен работать', 'disabled': 'Отключён', 'unconfigured': 'Не настроен'}
ERROR_LABELS = {'inventory': 'Сведения о процессах недоступны. Повторный запуск заблокирован.',
                'unconfirmed': 'Процесс обнаружен, но его активность не подтверждена. Повторный запуск заблокирован.',
                'launch_failed': 'Не удалось запустить обработчик. Проверьте локальный журнал запуска.',
                'exited': 'Обработчик завершился до подтверждения стабильной работы.',
                'timeout': 'Запуск не подтверждён в отведённое время.',
                'controller': 'Контроллер недоступен. Повторно запустите штатный ярлык CRM.'}
RESULT_LABELS = {'queued': 'Команда принята', 'running': 'Запуск выполняется',
                 'confirmed': 'Работа подтверждена', 'error': 'Ошибка', 'skipped': 'Запуск не требуется'}


def event(service, kind, result='', command=None):
    WorkerEvent.objects.create(service=service.code, kind=kind, result=result,
        incident=service.incident, command=command, actor_id=command.actor_id if command else None)
    logger.info('worker_event service=%s kind=%s incident=%s command=%s result=%s',
                service.code, kind, service.incident, command.pk if command else '', result)


def _finish(command, state, result, now):
    if command:
        command.state, command.result, command.finished_at = state, result, now
        command.save(update_fields=['state', 'result', 'finished_at'])


@retry_database_lock
def request_recovery(actor, services, request_id):
    if not actor.is_active or not actor.is_superuser:
        raise PermissionDenied
    if not services or any(code not in SERVICES for code in services):
        raise ValidationError('Неизвестный обработчик.')
    request_id = uuid.UUID(str(request_id))
    command_ids = []
    policy = expected_services()
    controller = WorkerController.objects.filter(pk=1).first()
    if not controller or controller.mode != 'managed':
        policy = dict.fromkeys(SERVICES, 'disabled')
    # IMMEDIATE на SQLite и уникальные ограничения защищают одновременные POST.
    with transaction.atomic():
        for code in services:
            command = WorkerCommand.objects.filter(request_id=request_id, service=code).first()
            if command is None:
                command = WorkerCommand.objects.filter(service=code, state__in=['queued', 'running']).first()
            if command is None:
                service, _ = WorkerService.objects.get_or_create(code=code)
                running = service.status == 'running' and _fresh(service.observed_at, timezone.now()) and _fresh(service.heartbeat_at, timezone.now())
                skip = policy[code] != 'required' or running
                command = WorkerCommand.objects.create(request_id=request_id, service=code, actor=actor,
                    state='skipped' if skip else 'queued', result='already_running' if running else
                    'disabled' if skip else '', finished_at=timezone.now() if skip else None)
                event(service, 'command_requested', command=command)
            command_ids.append(str(command.pk))
    return command_ids


def _failed(service, command, reason, now):
    manual = command is not None
    service.failures = min(MAX_FAILURES, service.failures + 1)
    service.auto_paused = manual or service.failures >= MAX_FAILURES
    service.error = reason
    service.launch_instance = service.launch_started_at = service.stable_since = None
    service.next_attempt_at = now + timedelta(seconds=RETRY_SECONDS[min(service.failures - 1, 2)])
    service.status = 'paused' if service.auto_paused else 'stopped'
    _finish(command, 'error', reason, now)
    event(service, 'launch_failed', reason, command)


def _fresh(at, now):
    return at is not None and timedelta(seconds=0) <= now - at <= timedelta(seconds=STALE_SECONDS)


def supervise_once(adapter, *, now=None, instance=None):
    """Один цикл. Вызывающий держит межпроцессную блокировку supervisor весь срок жизни."""
    supplied_now = now is not None
    now = now or timezone.now()
    controller, _ = WorkerController.objects.get_or_create(pk=1)
    if instance and controller.instance != instance:
        WorkerEvent.objects.create(service='supervisor', kind='controller_started', result='confirmed')
    controller.heartbeat_at = now
    if instance:
        controller.instance = instance
    try:
        rows = adapter.inventory()
    except (OSError, ValueError):
        rows = None
    controller.error = 'inventory' if rows is None else ''
    if controller.error and controller.incident_started_at is None:
        controller.incident, controller.incident_started_at = uuid.uuid4(), now
    elif not controller.error:
        controller.incident_started_at = None
    controller.save()
    policy = expected_services() if controller.mode == 'managed' else dict.fromkeys(SERVICES, 'disabled')
    processes = list(WorkerProcess.objects.filter(heartbeat_at__gte=now - timedelta(seconds=STALE_SECONDS)))
    if not supplied_now:
        # Heartbeat мог обновиться во время CIM/SQL. Сравниваем уже прочитанные
        # подтверждения со временем окончания чтения, а не с началом цикла.
        now = timezone.now()
    for code in SERVICES:
        service, _ = WorkerService.objects.get_or_create(code=code)
        before = (service.expected, service.status, service.error)
        service.expected, service.observed_at = policy[code], now
        command = WorkerCommand.objects.filter(service=code, state__in=['queued', 'running']).first()
        matches = [row for row in rows or [] if code in row['services']]
        active = next((process for process in processes if process.ready and code in process.services
            and _fresh(process.heartbeat_at, now) and any(
                process.pid == row['pid'] and process.birth == row['birth'] and bool(row['birth'])
                and (not row['instance'] or str(process.instance) == row['instance']) for row in matches)), None)
        service.heartbeat_at = active.heartbeat_at if active else service.heartbeat_at
        if service.expected != 'required':
            service.status, service.error = service.expected, ''
            service.incident = service.incident_started_at = None
            _finish(command, 'skipped', 'disabled', now)
        elif rows is None:
            service.status, service.error = 'unknown', 'inventory'
            service.stable_since = None
        elif active:
            service.error = ''
            changed_instance = service.stable_instance != active.instance
            if changed_instance:
                service.stable_since, service.stable_instance = now, active.instance
            if service.launch_instance or service.incident or service.status != 'running' or changed_instance:
                service.stable_since = service.stable_since or now
                if now - service.stable_since >= timedelta(seconds=STABLE_SECONDS):
                    service.status, service.failures, service.last_started_at = 'running', 0, now
                    service.auto_paused = False
                    event(service, 'recovered', 'confirmed', command)
                    service.incident = service.incident_started_at = None
                    service.launch_instance = service.launch_started_at = service.next_attempt_at = None
                    _finish(command, 'confirmed', 'confirmed', now)
                else:
                    service.status = 'recovering'
            else:
                service.status = 'running'
                _finish(command, 'confirmed', 'confirmed', now)
        elif matches:
            service.stable_since = None
            if service.launch_started_at and now - service.launch_started_at < timedelta(seconds=START_SECONDS):
                service.status = 'recovering'
            else:
                if service.launch_instance:
                    _failed(service, command, 'timeout', now)
                service.status, service.error = 'unknown', 'unconfirmed'
                _finish(command, 'error', 'unconfirmed', now)
        else:
            service.stable_since = None
            if not service.incident:
                service.incident, service.incident_started_at = uuid.uuid4(), now
                event(service, 'incident_opened', 'stopped')
            if service.launch_instance:
                # После аварии контроллера намерение уже записано: ждём окно запуска,
                # затем повторяем инвентаризацию в новом цикле перед следующим запуском.
                if now - service.launch_started_at < timedelta(seconds=START_SECONDS):
                    service.status = 'recovering'
                    service.save()
                    continue
                _failed(service, command, 'exited', now)
                command = None
            service.status = 'paused' if service.auto_paused or service.failures >= MAX_FAILURES else 'stopped'
            if command or (not service.auto_paused and service.failures < MAX_FAILURES and
                           (not service.next_attempt_at or now >= service.next_attempt_at)):
                # Между общим снимком и запуском мог появиться общий/старый worker.
                try:
                    latest_rows = adapter.inventory()
                except (OSError, ValueError):
                    service.status, service.error = 'unknown', 'inventory'
                    service.save()
                    continue
                if any(code in row['services'] for row in latest_rows):
                    service.status, service.error = 'unknown', 'unconfirmed'
                    service.save()
                    continue
                launch_instance = uuid.uuid4()
                service.launch_instance, service.launch_started_at = launch_instance, now
                service.status, service.error = 'recovering', ''
                # Сохранить намерение ДО внешнего эффекта; рестарт не запускает наугад.
                with transaction.atomic():
                    service.save()
                    if command:
                        command.state = 'running'
                        command.save(update_fields=['state'])
                    event(service, 'launch_requested', 'running', command)
                try:
                    adapter.launch(code, launch_instance)
                except (OSError, ValueError):
                    _failed(service, command, 'launch_failed', now)
        if service.expected == 'required' and service.status != 'running' and not service.incident:
            service.incident, service.incident_started_at = uuid.uuid4(), now
            event(service, 'incident_opened', service.status)
        if before != (service.expected, service.status, service.error):
            event(service, 'state_changed', service.status)
        service.save()


def monitoring_snapshot(*, now=None, with_history=False):
    """GET только читает локальные таблицы; не планирует работу и не проверяет API."""
    from .worker_schedule import queue_snapshot
    now = now or timezone.now()
    controller = WorkerController.objects.filter(pk=1).first()
    managed = bool(controller and controller.mode == 'managed')
    controller_ok = bool(controller and _fresh(controller.heartbeat_at, now) and not controller.error)
    policy = expected_services() if managed else dict.fromkeys(SERVICES, 'disabled')
    known = {row.code: row for row in WorkerService.objects.all()}
    services, incidents = [], []
    for code, name in SERVICE_CHOICES:
        row = known.get(code)
        expected = policy[code]
        status = expected if expected != 'required' else (
            row.status if row and controller_ok and _fresh(row.observed_at, now) else 'unknown')
        if status == 'running' and not _fresh(row.heartbeat_at, now):
            status = 'unknown'
        alarm = expected == 'required' and status != 'running'
        if alarm and row and row.incident:
            incidents.append({'id': str(row.incident), 'started_at': row.incident_started_at})
        queue = queue_snapshot(code, now=now, enabled=expected == 'required')
        services.append({'code': code, 'name': name, 'expected': expected,
            'expected_label': EXPECTED_LABELS[expected], 'status': status, 'status_label': STATUS_LABELS[status],
            'alarm': alarm, 'incident': str(row.incident) if row and row.incident else None,
            'heartbeat_at': row.heartbeat_at if row else None, 'last_started_at': row.last_started_at if row else None,
            'failures': row.failures if row else 0, 'paused': bool(row and (row.auto_paused or row.failures >= MAX_FAILURES)),
            'error': ERROR_LABELS.get(row.error, '') if row else '',
            'can_start': expected == 'required' and status in ('stopped', 'paused'), **queue})
    controller_alarm = managed and not controller_ok
    if controller_alarm:
        incidents.append({'id': f'controller:{controller.incident}:{controller.heartbeat_at}',
                          'started_at': controller.incident_started_at or controller.heartbeat_at})
    data = {'services': services, 'observed_at': controller.heartbeat_at if controller else None,
            'server_time': now, 'mode': 'managed' if managed else 'site_only',
            'controller_ok': controller_ok, 'controller_alarm': controller_alarm,
            'controller_label': 'Контроллер недоступен' if controller_alarm else
                'Контроль включён' if managed else 'Только сайт: автоматический запуск отключён',
            'alarm': controller_alarm or any(row['alarm'] for row in services), 'incidents': incidents,
            'running_count': sum(row['status'] == 'running' for row in services),
            'stopped_count': sum(row['alarm'] for row in services),
            'disabled_count': sum(row['expected'] != 'required' for row in services)}
    if with_history:
        data['history'] = history_snapshot()
    from django.conf import settings
    if getattr(settings,'LABEL_PRINT_BACKEND','native')=='agent':
        from sales.print_agents import snapshot as agent_snapshot
        data['print_agents']=agent_snapshot()
        problems=[a for a in data['print_agents'] if a['enabled'] and (not a['connected'] or not a['printer_available'])]
        for agent in problems:
            data['incidents'].append({'id':'print-agent:'+agent['problem_id'],
                                     'started_at':agent['problem_started_at']})
        data['alarm']=data['alarm'] or bool(problems)
        data['stopped_count']+=len(problems)
    return data


def history_snapshot():
    kinds = {'command_requested': 'Ручная команда', 'incident_opened': 'Обнаружена проблема',
             'launch_requested': 'Запрошен запуск', 'launch_failed': 'Запуск не подтверждён',
             'state_changed': 'Изменение состояния', 'recovered': 'Работа восстановлена',
             'controller_started': 'Запущен контроллер'}
    names = {**dict(SERVICE_CHOICES), 'supervisor': 'Контроллер'}
    return [{'created_at': item.created_at, 'service': names.get(item.service, item.service),
             'kind': kinds.get(item.kind, 'Событие контроля'),
             'result': ERROR_LABELS.get(item.result, STATUS_LABELS.get(item.result, RESULT_LABELS.get(item.result, ''))),
             'actor': item.actor.username if item.actor_id else 'Автоматически'}
            for item in WorkerEvent.objects.select_related('actor').all()[:40]]
