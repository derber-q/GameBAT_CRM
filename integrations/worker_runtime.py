"""Блокировки Windows/Linux и параметры локального контроля. Файлы блокировок не удаляются."""
from contextlib import contextmanager
from pathlib import Path
import os
import signal
import threading

from django.conf import settings

SERVICES = ('avito', 'yandex', 'google', 'print')
POLL_SECONDS = 15
HEARTBEAT_SECONDS = 20
STALE_SECONDS = 90
START_SECONDS = 45
STABLE_SECONDS = 60
RETRY_SECONDS = (15, 30, 60)
MAX_FAILURES = 3


class AlreadyRunning(Exception):
    pass


@contextmanager
def graceful_shutdown():
    """SIGTERM прекращает получение новых задач, но не обрывает текущий внешний вызов."""
    stop = threading.Event()
    handlers = {}
    if threading.current_thread() is threading.main_thread():
        handlers = {sig: signal.signal(sig, lambda *_: stop.set())
                    for sig in (signal.SIGTERM, signal.SIGINT)}
    try:
        yield stop
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)


@contextmanager
def process_lock(name):
    if name not in (*SERVICES, 'supervisor', 'startup'):
        raise ValueError('Неизвестная блокировка')
    folder = Path(getattr(settings, 'WORKER_RUNTIME_DIR', settings.BASE_DIR / 'outputs/localhost/workers'))
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / f'{name}.lock').open('a+b') as stream:
        stream.seek(0, os.SEEK_END)
        if not stream.tell():
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise AlreadyRunning(name) from None
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
