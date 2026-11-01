"""Сайт и контроллер в одном контейнере; worker остаются под существующим мониторингом."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time


def run_services(root, *, restart_delay=3, shutdown_timeout=240):
    stop = threading.Event()
    previous = {sig: signal.signal(sig, lambda *_: stop.set())
                for sig in (signal.SIGTERM, signal.SIGINT)}
    web = controller = None
    group = None
    result = 0
    try:
        # Отдельная группа принадлежит этой установке; перезапущенный контроллер
        # присоединяется к ней, поэтому его прежние worker также корректно завершаются.
        web = subprocess.Popen([sys.executable, '-u', str(root/'manage.py'), 'runserver',
                                '0.0.0.0:8000', '--noreload'], cwd=root, process_group=0)
        group = web.pid
        while not stop.is_set():
            if web.poll() is not None:
                print('container_web_exited: перезапуск контейнера необходим.', flush=True)
                result = 1
                break
            if controller is None or controller.poll() is not None:
                if controller is not None:
                    print(f'container_controller_exited code={controller.returncode}: повторный запуск.', flush=True)
                    if stop.wait(restart_delay):
                        break
                controller = subprocess.Popen([sys.executable, '-u', str(root/'manage.py'),
                    'run_worker_supervisor'], cwd=root, process_group=group)
                print(f'container_controller_started pid={controller.pid}', flush=True)
            stop.wait(.2)
    finally:
        if group is not None:
            try:
                os.killpg(group, signal.SIGTERM)
            except ProcessLookupError:
                pass
            deadline = time.monotonic()+shutdown_timeout
            while True:
                for child in (web, controller):
                    if child is not None:
                        child.poll()
                try:
                    os.killpg(group, 0)
                except ProcessLookupError:
                    break
                if time.monotonic() >= deadline:
                    print('container_shutdown_timeout: проверьте незавершённые задания интеграций.', flush=True)
                    os.killpg(group, signal.SIGKILL)
                    result = 1
                    break
                time.sleep(.1)
            for child in (web, controller):
                if child is not None:
                    child.wait()
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    return result


def main():
    if sys.platform != 'linux' or not Path('/.dockerenv').is_file() or os.environ.get('GAMEBAT_ENV') != 'local_live':
        raise SystemExit('Этот запуск разрешён только в Linux-контейнере local_live.')
    root = Path(__file__).resolve().parent.parent
    for command in (['migrate', '--check'], ['configure_worker_monitoring']):
        subprocess.run([sys.executable, str(root/'manage.py'), *command], cwd=root, check=True)
    return run_services(root)


if __name__ == '__main__':
    raise SystemExit(main())
