"""Запуск на компьютере принтера. Ни одного входящего сетевого порта."""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import signal
import sys
import threading
import uuid

from .driver import WindowsDriver
from .engine import Engine
from .journal import Journal
from .transport import API, TransportError


def default_config():
    return Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.local/share')))/'ReSOURCE/PrintAgent/config.json'


@contextmanager
def exclusive(path):
    with path.open('a+b') as lock:
        if not lock.tell():
            lock.write(b'0');lock.flush()
        lock.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            raise SystemExit('Print Agent уже работает.') from None
        try:
            yield
        finally:
            lock.seek(0)
            if os.name=='nt':
                msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
            else:
                fcntl.flock(lock.fileno(),fcntl.LOCK_UN)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,default=default_config())
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    config=json.loads(args.config.read_text('utf-8-sig'))
    api=API(config,uuid.uuid4())
    driver=WindowsDriver(config['printer_name'])
    if args.check:
        print('Принтер доступен.' if driver.available() else 'Принтер недоступен.')
        return
    state=args.config.parent
    with exclusive(state/'agent.lock'):
        journal=Journal(state/'journal.sqlite3',config['agent_id'])
        engine=Engine(api,journal,driver,config['printer_name'])
        stop=threading.Event()
        for sig in (signal.SIGTERM,signal.SIGINT):
            signal.signal(sig,lambda *_:stop.set())
        stop_file=state/'stop-request'
        stop_file.unlink(missing_ok=True)
        previous=None
        try:
            while not stop.is_set() and not stop_file.exists():
                try:
                    engine.step()
                    error=None
                except TransportError as exc:
                    error=f'Связь с CRM: {exc.code}, HTTP {exc.status}.'
                except Exception as exc:
                    # Ни токен, ни тело ответа/документ не попадают в журнал.
                    error='Операция приостановлена: '+type(exc).__name__
                if error!=previous:
                    print(error or 'Агент подключён, обработка продолжается.',flush=True)
                    previous=error
                stop.wait(3)
        finally:
            journal.close()


if __name__=='__main__':
    main()
