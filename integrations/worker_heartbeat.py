"""Независимое подтверждение живого worker с отдельным Django-соединением."""
from contextlib import ExitStack, contextmanager
import logging
import os
import threading
import uuid

from django.db import close_old_connections, connections, OperationalError
from django.utils import timezone

from .worker_models import WorkerProcess
from .worker_processes import process_adapter
from .worker_runtime import AlreadyRunning, HEARTBEAT_SECONDS, process_lock

logger = logging.getLogger('gamebat.business')


class Heartbeat:
    def __init__(self, services, instance, birth):
        self.services, self.instance, self.birth = list(services), instance, birth
        self.action = 'idle'
        self.stop = threading.Event()
        self.main = threading.current_thread()

    def write(self):
        close_old_connections()
        try:
            WorkerProcess.objects.update_or_create(instance=self.instance, defaults={
                'pid': os.getpid(), 'birth': self.birth, 'services': self.services,
                'heartbeat_at': timezone.now(), 'ready': True, 'action': self.action})
        except OperationalError:
            # Одна блокировка не доказывает остановку; следующая запись повторится.
            logger.warning('worker_heartbeat_write_failed instance=%s', self.instance)
        finally:
            connections.close_all()

    def run(self):
        while not self.stop.wait(HEARTBEAT_SECONDS) and self.main.is_alive():
            self.write()


@contextmanager
def monitored_worker(services, instance=None, adapter=None):
    adapter = adapter or process_adapter()
    instance = uuid.UUID(str(instance)) if instance else uuid.uuid4()
    with ExitStack() as stack:
        for service in sorted(services):
            stack.enter_context(process_lock(service))
        rows = adapter.inventory()
        own = next((row for row in rows if row['pid'] == os.getpid()), None)
        # Старые процессы без блокировок также запрещают второй запуск.
        own_family = {os.getpid(), os.getppid()}
        if any(set(row['services']) & set(services) and row['pid'] not in own_family for row in rows):
            raise AlreadyRunning('Очередь уже обслуживается')
        if not own or not own['birth']:
            raise OSError('Не удалось подтвердить принадлежность процесса')
        heartbeat = Heartbeat(services, instance, own['birth'])
        # Первый heartbeat пишет отдельный поток: основное соединение не закрывается.
        thread = threading.Thread(target=lambda: (heartbeat.write(), heartbeat.run()), daemon=True,
                                  name='worker-heartbeat')
        thread.start()
        try:
            yield heartbeat
        finally:
            heartbeat.stop.set()
            thread.join(timeout=2)
