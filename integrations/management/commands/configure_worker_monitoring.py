"""Явная политика штатного запуска, не изменяющая настройки бизнес-интеграций."""
from django.core.management.base import BaseCommand, CommandError
from django.db import OperationalError, ProgrammingError
from django.utils import timezone

from integrations.worker_models import WorkerController
from integrations.worker_runtime import process_lock, AlreadyRunning


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--site-only', action='store_true')

    def handle(self, *args, **options):
        try:
            if options['site_only']:
                # SiteOnly не останавливает прежний supervisor и не меняет его политику.
                try:
                    with process_lock('supervisor'):
                        WorkerController.objects.update_or_create(pk=1, defaults={'mode': 'site_only'})
                except AlreadyRunning:
                    pass
            else:
                controller, _ = WorkerController.objects.get_or_create(pk=1)
                controller.mode = 'managed'
                controller.incident_started_at = controller.incident_started_at or timezone.now()
                controller.save()
        except (OperationalError, ProgrammingError):
            raise CommandError('Не удалось настроить мониторинг. Проверьте доступность БД и применение миграций.') from None
