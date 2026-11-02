"""Адаптер локальных процессов. Ни view, ни модель не вызывают команды ОС."""
import json
from pathlib import Path
import subprocess
import sys

from django.conf import settings

from .worker_runtime import SERVICES
from core.external_policy import require_live_operation


def process_adapter():
    if sys.platform == 'linux':
        from .linux_processes import LinuxProcesses
        return LinuxProcesses()
    return WindowsProcesses()


class WindowsProcesses:
    def inventory(self):
        require_live_operation('windows_process_inventory')
        if sys.platform != 'win32':
            raise OSError('Windows adapter unavailable')
        try:
            result = subprocess.run([
                'powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                '-File', str(settings.BASE_DIR / 'scripts/worker_processes.ps1'),
                '-ProjectDir', str(settings.BASE_DIR),
            ], capture_output=True, encoding='utf-8-sig', timeout=12, creationflags=subprocess.CREATE_NO_WINDOW)
        except (OSError, subprocess.SubprocessError):
            raise OSError('Process inventory unavailable') from None
        if result.returncode:
            raise OSError('Process inventory unavailable')
        rows = json.loads(result.stdout)
        if not isinstance(rows, list) or any(not isinstance(row, dict) or
                not isinstance(row.get('pid'), int) or not isinstance(row.get('birth'), str) or
                not isinstance(row.get('instance'), str) or not isinstance(row.get('services'), list)
                for row in rows):
            raise OSError('Invalid process inventory')
        return rows

    def launch(self, service, instance):
        require_live_operation('windows_process_launch')
        if service not in SERVICES or sys.platform != 'win32':
            raise ValueError('Unsupported worker')
        command = ['run_label_print_worker'] if service == 'print' else ['run_integration_worker', '--service', service]
        if service == 'telegram_staff':
            command = ['run_telegram_staff_bot']
        folder = Path(settings.BASE_DIR) / 'outputs/localhost'
        folder.mkdir(parents=True, exist_ok=True)
        with (folder / f'{instance}.stdout.log').open('ab') as stdout, (folder / f'{instance}.stderr.log').open('ab') as stderr:
            subprocess.Popen([sys.executable, '-u', str(settings.BASE_DIR / 'manage.py'), *command,
                              '--worker-instance', str(instance)], cwd=settings.BASE_DIR, stdin=subprocess.DEVNULL,
                             stdout=stdout, stderr=stderr, creationflags=subprocess.CREATE_NO_WINDOW, close_fds=True)
