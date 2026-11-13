"""Снимок расписания и очереди: не создаёт заданий и не вызывает API."""
from django.utils import timezone
from django.db.utils import OperationalError, ProgrammingError
from .models import Integration, SyncJob


def queue_snapshot():
    data = {'next_action': 'Ожидание ручного или ежедневного обновления', 'task_error': ''}
    try:
        config = Integration.objects.filter(pk=1).first()
        if config:
            data.update(last_task_success_at=config.last_success_at, next_at=config.next_at,
                        task_error=config.error_category, overdue=bool(config.next_at and config.next_at < timezone.now()))
        job = SyncJob.objects.filter(active=True).first()
        if job:
            data.update(next_action='Получение цифрового каталога' if job.state == 'running' else 'Обновление цифрового каталога',
                        next_at=job.run_after)
            if job.state == 'running':
                data['current_action'] = 'Получение страниц API и проверка полного снимка'
    except (OperationalError, ProgrammingError):
        pass
    return data
