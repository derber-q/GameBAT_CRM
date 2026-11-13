"""Явная политика штатного запуска, не изменяющая настройки бизнес-интеграций."""
from django.core.management.base import BaseCommand, CommandError
from django.db import OperationalError, ProgrammingError
from django.utils import timezone
from django.db import transaction

from integrations.worker_models import WorkerController, WorkerService, WorkerEvent, WorkerCommand
from integrations.worker_policy import expected_services
from integrations.worker_runtime import process_lock, AlreadyRunning


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--site-only', action='store_true')
        parser.add_argument('--new-boot', action='store_true', help='Новая загрузка контейнера: повторить технический запуск необходимых сервисов.')

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
                if options['new_boot']:
                    try:
                        with process_lock('supervisor'), transaction.atomic():
                            for code, expected in expected_services().items():
                                if expected != 'required':
                                    continue
                                service, _ = WorkerService.objects.get_or_create(code=code)
                                service.failures, service.auto_paused = 0, False
                                service.status, service.error = 'stopped', ''
                                service.launch_instance = service.launch_started_at = service.next_attempt_at = None
                                service.stable_instance = service.stable_since = None
                                service.save()
                                for command in WorkerCommand.objects.filter(service=code, state__in=['queued', 'running']):
                                    command.state, command.result, command.finished_at = 'error', 'restart', timezone.now()
                                    command.save(update_fields=['state', 'result', 'finished_at'])
                                WorkerEvent.objects.create(service=code, kind='boot_check', result='queued')
                    except AlreadyRunning:
                        raise CommandError('Контроллер уже работает; сброс запуска разрешён только до его старта.') from None
                controller, _ = WorkerController.objects.get_or_create(pk=1)
                controller.mode = 'managed'
                controller.incident_started_at = controller.incident_started_at or timezone.now()
                controller.save()
        except (OperationalError, ProgrammingError):
            raise CommandError('Не удалось настроить мониторинг. Проверьте доступность БД и применение миграций.') from None
