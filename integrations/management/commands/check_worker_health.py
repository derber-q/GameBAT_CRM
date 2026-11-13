"""Проверка готовности контейнера по результатам рабочих циклов; без API и постановки задач."""
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from urllib.request import urlopen
from urllib.error import URLError
from django.utils import timezone
from integrations.worker_health import fresh
from integrations.worker_monitoring import monitoring_snapshot


class Command(BaseCommand):
    help = 'Возвращает ненулевой код, пока необходимые обработчики или агент печати не подтвердили работу.'

    def handle(self, *args, **options):
        if settings.GAMEBAT_ENV == 'local_test':
            raise CommandError('В тестовой среде проверка рабочего HTTP и реальных обработчиков отключена.')
        data = monitoring_snapshot(include_queues=False)
        failures = [row['code'] + ':' + row['status'] for row in data['services']
                    if row['expected'] == 'required' and row['status'] != 'running']
        if not data['controller_ok'] or data['mode'] != 'managed':
            failures.append('supervisor:unavailable')
        for agent in data.get('print_agents', []):
            if agent['enabled'] and (not agent['connected'] or not agent['printer_available']):
                failures.append('print_agent:unavailable')
        from crm_backups.models import BackupConfiguration
        backup = BackupConfiguration.objects.filter(pk=1).first()
        if backup and backup.enabled and not fresh(backup.last_worker_at, timezone.now(), 900):
            failures.append('backup_worker:unavailable')
        try:
            with urlopen('http://127.0.0.1:8000/crm/accounts/login/', timeout=3) as response:
                if response.status != 200:
                    failures.append('web:unavailable')
        except (URLError, OSError, TimeoutError):
            failures.append('web:unavailable')
        if failures:
            raise CommandError('Готовность не подтверждена: ' + ', '.join(failures))
        self.stdout.write('Обработчики подтвердили рабочие циклы; необходимые агенты печати доступны.')
