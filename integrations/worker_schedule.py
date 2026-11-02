"""Безопасные сведения о фактически назначенных заданиях; никаких ensure/enqueue."""
from django.db.models import Case, When, Value, IntegerField, Max

from .models import AvitoSyncJob, GoogleSheetsSyncJob, GoogleSheetsIntegration

YANDEX_NAMES = {'event': 'Обработка уведомления', 'order': 'Обновление заказа',
                'order_action': 'Действие по заказу', 'reconcile': 'Контрольная сверка',
                'product': 'Синхронизация товара', 'catalog': 'Обновление каталога',
                'label': 'Получение этикетки', 'boxes': 'Подготовка грузовых мест'}
AVITO_PHASES = frozenset(['Загрузка актуального списка Avito', 'Чтение остатков Avito',
    'Сверка и отправка изменений', 'Повторная проверка результата через Avito',
    'Обновление статусов Avito…'])


def _nearest(query, state, now):
    pending = query.filter(**{state: 'pending'})
    due = pending.filter(run_after__lte=now).order_by('priority', 'run_after', 'pk').first()
    return due or pending.order_by('run_after', 'priority', 'pk').first()


def queue_snapshot(code, *, now, enabled=True):
    data = {'current_action': 'Нет данных', 'current_started_at': None, 'next_action': 'Не запланировано',
            'next_at': None, 'overdue': False, 'last_task_success_at': None, 'task_error': ''}
    if code == 'telegram_staff':
        from telegram_bots.monitoring import queue_snapshot as telegram_snapshot
        data.update(telegram_snapshot())
    elif code == 'print':
        from sales.models import MarketPrintJob
        jobs = MarketPrintJob.objects.all()
        job = jobs.exclude(state__in=['done', 'error', 'uncertain']).order_by('pk').first()
        data['last_task_success_at'] = jobs.aggregate(at=Max('printed_at'))['at']
        data['next_action'] = 'Ожидание задания на печать'
        if job:
            names = {'pending': 'Подготовка ярлыка', 'printing': 'Печать', 'spooled': 'Проверка результата печати',
                     'agent_waiting':'Ожидание магазинного агента', 'agent_claimed':'Агент получает PDF',
                     'agent_printing':'Передача агентом на принтер', 'agent_spooled':'Агент проверяет результат печати',
                     'waiting_pdf': 'Ожидание PDF', 'printed': 'Подтверждённая печать',
                     'waiting_ready': 'Ожидание подтверждения готовности'}
            data['next_action'] = names.get(job.state, 'Обработка задания печати')
            if job.lease or job.state in ('printing','spooled','agent_printing','agent_spooled'):
                data['current_action'] = data['next_action']
                data['current_started_at'] = job.leased_at or job.spooled_at
        if jobs.filter(state__in=['error', 'uncertain']).exists():
            data['task_error'] = 'Есть ошибка печати или неизвестный результат. Проверьте ярлык и задание; автоматического повтора нет.'
    else:
        if code == 'avito':
            jobs, state = AvitoSyncJob.objects.all(), 'status'
            priority = Case(When(job_type__in=['manual', 'status_refresh'], then=Value(0)), default=Value(1), output_field=IntegerField())
            title = lambda job: job.get_job_type_display()
            data['last_task_success_at'] = AvitoSyncJob.objects.filter(status='done').aggregate(at=Max('finished_at'))['at']
        elif code == 'google':
            jobs, state = GoogleSheetsSyncJob.objects.all(), 'status'
            priority = Value(0, output_field=IntegerField())
            title = lambda job: ('Повторная попытка Google Sheets' if job.attempts else
                'Ручное обновление Google Sheets' if job.dedupe_key == 'manual' else 'Периодическая синхронизация Google Sheets')
            data['last_task_success_at'] = GoogleSheetsIntegration.objects.aggregate(at=Max('last_success_at'))['at']
        else:
            from yandex_market.models import SyncJob
            jobs, state = SyncJob.objects.all(), 'state'
            priority = Case(When(kind__in=['event', 'order', 'order_action'], then=Value(0)),
                When(kind='reconcile', then=Value(2)), default=Value(1), output_field=IntegerField())
            title = lambda job: YANDEX_NAMES.get(job.kind, 'Задание Яндекс Маркета')
            data['last_task_success_at'] = jobs.filter(state='done').aggregate(at=Max('updated_at'))['at']
        jobs = jobs.annotate(priority=priority)
        running = jobs.filter(**{state: 'running'}).order_by('updated_at', 'pk').first()
        if running:
            data['current_action'] = (running.phase if code == 'avito' and running.phase in AVITO_PHASES else title(running))
            data['current_started_at'] = getattr(running, 'started_at', None) or running.updated_at
        pending = _nearest(jobs, state, now)
        if pending:
            data['next_action'], data['next_at'] = title(pending), pending.run_after
            data['overdue'] = pending.run_after < now
        if jobs.filter(**{state: 'error'}).exists() or jobs.filter(**{state: 'pending'}).exclude(last_error='').exists():
            data['task_error'] = 'В очереди есть ошибка задания. Подробности доступны в соответствующей интеграции.'
    if not enabled:
        data['next_action'], data['next_at'], data['overdue'] = 'Автоматическая обработка отключена', None, False
    return data
