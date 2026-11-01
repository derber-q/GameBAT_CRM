"""Фоновый исполнитель очередей Avito/Яндекс/Sheets; даже --once может менять реальные внешние данные."""
import uuid

from django.core.management.base import BaseCommand
from django.db import close_old_connections, connections

from integrations.tasks import process_one_job
from integrations.google_tasks import process_one_google_sheets_job
from yandex_market.tasks import process_one_job as process_yandex_job
from integrations.worker_heartbeat import monitored_worker
from integrations.worker_runtime import AlreadyRunning, graceful_shutdown


class Command(BaseCommand):
    help = "Запускает DB-backed worker и планировщик интеграций."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")
        parser.add_argument("--poll", type=float, default=2.0)
        parser.add_argument("--service", choices=("all", "avito", "google", "yandex"), default="all",
                            help="Обрабатывать только выбранную интеграцию или все сервисы.")
        parser.add_argument('--worker-instance', type=uuid.UUID)

    def handle(self, *args, **options):
        processors = {"avito": process_one_job, "google": process_one_google_sheets_job, "yandex": process_yandex_job}
        services = tuple(processors) if options['service'] == 'all' else (options['service'],)
        context = monitored_worker(services, options['worker_instance'])
        try:
            with graceful_shutdown() as stop, context as heartbeat:
                while not stop.is_set():
                    close_old_connections()
                    processed = False
                    for service in services:
                        if stop.is_set():
                            break
                        if heartbeat:
                            heartbeat.action = service
                        processed = processors[service]() or processed
                    if heartbeat:
                        heartbeat.action = 'idle'
                    if options['once']:
                        break
                    if not processed:
                        stop.wait(max(0.2, options['poll']))
        except AlreadyRunning:
            self.stdout.write('Выбранная очередь уже обслуживается другим процессом.')
        finally:
            connections.close_all()
