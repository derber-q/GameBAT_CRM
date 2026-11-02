"""Отдельный entry point: не совпадает с сигнатурами рабочих Windows-процессов."""
import os
import sys
from pathlib import Path


def main():
    from .environments import SECRET_VARIABLES
    # Очищается только окружение дочернего тестового процесса, не Windows/рабочего сайта.
    for key in SECRET_VARIABLES:
        os.environ.pop(key, None)
    os.environ['GAMEBAT_ENV'] = 'local_test'
    os.environ['DJANGO_SETTINGS_MODULE'] = 'GameBAT_CRM.settings'
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    sys.dont_write_bytecode = True
    if any(arg.startswith('--settings') for arg in sys.argv[1:]):
        raise SystemExit('local_test: подмена модуля настроек запрещена.')
    if len(sys.argv) > 1 and sys.argv[1] in (
        'run_integration_worker','run_label_print_worker','run_worker_supervisor','run_telegram_staff_bot'):
        raise SystemExit('local_test: реальные worker запрещены. Моделирование выполняется изолированными тестами.')
    if len(sys.argv)>1 and sys.argv[1]=='runserver':
        address=next((arg for arg in sys.argv[2:] if not arg.startswith('-')), '')
        container = os.environ.get('GAMEBAT_TEST_CONTAINER') == '1' and Path('/.dockerenv').is_file()
        allowed = address.startswith('127.0.0.1:') or (container and address.startswith('0.0.0.0:'))
        if not allowed or not address.rsplit(':',1)[1].isdigit() or address.endswith(':8000'):
            raise SystemExit('local_test: нужен отдельный loopback-порт, отличный от 8000.')
        if '--noreload' not in sys.argv:
            sys.argv.append('--noreload')
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
