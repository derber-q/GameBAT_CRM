"""Windows-исполнитель печати ярлыков. Подтверждённая печать отделена от постановки задания/готовности FBS."""
import uuid

from django.core.management.base import BaseCommand
from django.db import close_old_connections, connections, OperationalError
from sales.market_fulfillment import process_print_jobs
from integrations.worker_heartbeat import monitored_worker
from integrations.worker_runtime import AlreadyRunning, graceful_shutdown


class Command(BaseCommand):
    help = 'Печатает ярлыки на локальный принтер и завершает сборку заказов Яндекса.'

    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true')
        parser.add_argument('--worker-instance', type=uuid.UUID)

    def handle(self, *args, **options):
        context = monitored_worker(('print',), options['worker_instance'])
        try:
            with graceful_shutdown() as stop, context as heartbeat:
                while not stop.is_set():
                    close_old_connections()
                    try:
                        if heartbeat:
                            heartbeat.action = 'print'
                        process_print_jobs(stop=stop)
                        from sales.avito_shipping import process_jobs
                        process_jobs(stop=stop)
                    except OperationalError:
                        pass
                    finally:
                        if heartbeat:
                            heartbeat.action = 'idle'
                    if options['once']:
                        return
                    stop.wait(1)
        except AlreadyRunning:
            self.stdout.write('Печать уже обслуживается другим процессом.')
        finally:
            connections.close_all()
