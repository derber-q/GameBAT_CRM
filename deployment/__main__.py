"""Отдельный менеджер хостинга. Нативный запуск локальной CRM его не использует."""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import signal
import stat
import sys
import threading
from urllib.parse import urlsplit

from .docker_backend import DockerBackend
from .github import GitHub
from .gateway import Gateway, grant, publish
from .manager import Manager
from .store import Store, UpdateError, now


def load_config(path):
    if sys.platform!='linux' or os.geteuid()==0 or os.environ.get('GAMEBAT_ENV')!='production':
        raise UpdateError('Менеджер запускается только отдельным непривилегированным пользователем Linux production.')
    path = path.absolute()
    if path.resolve()!=path or not path.is_file() or path.stat().st_mode & 0o022:
        raise UpdateError('Конфигурация должна быть обычным файлом без групповой/общей записи.')
    config = json.loads(path.read_text('utf-8'))
    if config.get('production_verified') is not True:
        raise UpdateError('Сначала требуется подтверждённый этап B и испытание конфигурации на VPS.')
    paths = []
    for key in ('root','shared_dir','compose_file'):
        value = Path(config[key])
        if not value.is_absolute() or value.resolve()!=value or value.is_symlink():
            raise UpdateError('Пути конфигурации должны быть абсолютными, без ссылок.')
        paths.append(value)
    root, shared, compose = paths
    code = Path(__file__).resolve().parent.parent
    if root==shared or root in shared.parents or shared in root.parents or root.is_relative_to(code) or shared.is_relative_to(code):
        raise UpdateError('Код, shared-данные и каталог менеджера должны храниться раздельно.')
    if not shared.is_dir() or not compose.is_file() or compose.stat().st_mode & 0o022:
        raise UpdateError('Shared и защищённый Compose-файл должны быть подготовлены администратором.')
    for key in ('project','database_user','database_name'):
        if not re.fullmatch('[a-z][a-z0-9_-]{0,62}', config[key]):
            raise UpdateError('Некорректный идентификатор конфигурации.')
    if type(config.get('web_uid')) is not int or not 0<config['web_uid']<2**32:
        raise UpdateError('Нужен host UID web-контейнера для Unix socket и ACL.')
    origin = urlsplit(config['health_origin'])
    if origin.scheme!='https' or not origin.hostname or origin.username or origin.password or origin.path or origin.query or origin.fragment:
        raise UpdateError('Health origin должен быть HTTPS-адресом CRM без пути и учётных данных.')
    root.mkdir(parents=True,exist_ok=True,mode=0o700)
    return config


@contextmanager
def exclusive(path):
    import fcntl
    with path.open('a+b') as stream:
        try:
            fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            raise UpdateError('Другой экземпляр менеджера уже работает.') from None
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(),fcntl.LOCK_UN)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--init',action='store_true')
    group.add_argument('--reconcile',action='store_true')
    args = parser.parse_args()
    os.umask(0o077)
    try:
        config = load_config(args.config)
        root = Path(config['root'])
        with exclusive(root/'manager.lock'):
            backend = DockerBackend(config)
            backend.verify_runtime()
            store = Store(root/'state/updates.sqlite3')
            if args.init or args.reconcile:
                current = backend.running()
                backend.health(current)
                backend.release_files(current)
                if args.init:
                    store.initialize()
                previous=store.get('current',{})
                current.update(installed_at=previous.get('installed_at','') if previous.get('sha')==current['sha'] else '',
                               verified_at=now(),approved=True)
                store.set('current',current)
                if args.reconcile:
                    store.interrupt_started()
                    store.delete('recovery_required')
                    store.set('reconciliation',{'at':now(),'current':current['sha'],'actor':'server-cli'})
                print('Рабочая версия проверена и записана. Обновление не выполнялось.')
                return
            store.interrupt_started()
            socket_path = root/'gateway.sock'
            if socket_path.exists():
                if not stat.S_ISSOCK(socket_path.stat().st_mode) or socket_path.stat().st_uid!=os.geteuid():
                    raise UpdateError('Вместо канала менеджера обнаружен посторонний файл.')
                socket_path.unlink()
            gateway = Gateway(socket_path,store,config['web_uid'])
            grant(socket_path,config['web_uid'],'rw')
            server_thread = threading.Thread(target=gateway.serve_forever,daemon=True)
            server_thread.start()
            stop = threading.Event()
            for sig in (signal.SIGTERM,signal.SIGINT):
                signal.signal(sig,lambda *_:stop.set())
            def heartbeat():
                while not stop.is_set():
                    try:
                        store.set('heartbeat',{'at':now(),'protocol':1})
                        publish(root,store,config['web_uid'])
                    except Exception:
                        # Нет скрытого продолжения установки при недоступном журнале.
                        stop.set()
                    stop.wait(3)
            thread = threading.Thread(target=heartbeat,daemon=True)
            thread.start()
            manager = Manager(store,GitHub(config.get('github_token_file')),backend)
            try:
                while not stop.is_set():
                    manager.tick()
                    stop.wait(2)
            finally:
                stop.set()
                thread.join(timeout=10)
                store.set('heartbeat',{})
                publish(root,store,config['web_uid'])
                gateway.shutdown()
                gateway.server_close()
                server_thread.join(timeout=5)
                socket_path.unlink(missing_ok=True)
    except UpdateError as error:
        raise SystemExit(str(error)) from None
    except Exception:
        raise SystemExit('Менеджер остановлен. Проверьте конфигурацию и журнал операций; автоматического повтора нет.') from None


if __name__=='__main__':
    main()
