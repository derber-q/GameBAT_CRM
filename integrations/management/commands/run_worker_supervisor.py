"""Единственный локальный владелец восстановления; может возобновлять реальные очереди."""
import time
import uuid

from django.core.management.base import BaseCommand
from django.db import close_old_connections, connections, OperationalError

from integrations.worker_monitoring import supervise_once
from integrations.worker_processes import process_adapter
from integrations.worker_runtime import process_lock, AlreadyRunning, POLL_SECONDS


class Command(BaseCommand):
    help = 'Наблюдает и безопасно восстанавливает необходимые локальные обработчики.'

    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true')
        parser.add_argument('--worker-instance', type=uuid.UUID)

    def handle(self, *args, **options):
        instance = options['worker_instance'] or uuid.uuid4()
        try:
            with process_lock('supervisor'):
                adapter = process_adapter()
                while True:
                    close_old_connections()
                    try:
                        supervise_once(adapter, instance=instance)
                    except OperationalError:
                        self.stderr.write('База временно недоступна; цикл контроля будет повторён.')
                    finally:
                        connections.close_all()
                    if options['once']:
                        return
                    time.sleep(POLL_SECONDS)
        except AlreadyRunning:
            self.stdout.write('Контроллер уже запущен.')
