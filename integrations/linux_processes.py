"""Локальные процессы одного Linux PID namespace; доступ к Docker socket не нужен."""
import os
from pathlib import Path
import subprocess
import sys
import uuid

from django.conf import settings
from core.external_policy import require_live_operation
from .worker_runtime import SERVICES


class LinuxProcesses:
    def __init__(self, proc_root=Path('/proc')):
        self.proc_root = Path(proc_root)

    def inventory(self):
        require_live_operation('linux_process_inventory')
        project = Path(settings.BASE_DIR).resolve()
        rows = []
        for proc in sorted(self.proc_root.iterdir(), key=lambda p: int(p.name) if p.name.isdigit() else -1):
            if not proc.name.isdigit():
                continue
            try:
                argv = (proc/'cmdline').read_bytes().decode().rstrip('\0').split('\0')
                # Учитываются только штатные manage.py из этой установки.
                script_index = next(i for i, arg in enumerate(argv) if Path(arg).name == 'manage.py')
                script = Path(argv[script_index])
                if not script.is_absolute():
                    script = Path(os.readlink(proc/'cwd')) / script
                if script.resolve() != project/'manage.py':
                    continue
                command, *args = argv[script_index+1:]
                if command == 'run_integration_worker':
                    service = self._option(args, '--service') or 'all'
                    services = ['avito', 'yandex', 'google'] if service == 'all' else [service]
                    if any(s not in SERVICES[:3] for s in services):
                        continue
                elif command in ('run_label_print_worker', 'run_worker_supervisor'):
                    services = ['print' if command == 'run_label_print_worker' else 'supervisor']
                else:
                    continue
                instance = self._option(args, '--worker-instance')
                if instance:
                    instance = str(uuid.UUID(instance))
                # starttime не меняется при повторном использовании PID. comm может содержать пробелы.
                birth = (proc/'stat').read_text().rsplit(')', 1)[1].split()[19]
                rows.append(dict(pid=int(proc.name), birth=birth, instance=instance, services=services))
            except (OSError, UnicodeError, ValueError, IndexError, StopIteration):
                # Процесс мог завершиться между чтением каталога и cmdline/stat.
                continue
        return rows

    @staticmethod
    def _option(args, name):
        for i, arg in enumerate(args):
            if arg.startswith(name+'='):
                return arg.split('=', 1)[1]
            if arg == name:
                return args[i+1]
        return ''

    def launch(self, service, instance):
        require_live_operation('linux_process_launch')
        if service not in SERVICES or sys.platform != 'linux':
            raise ValueError('Unsupported worker')
        instance = str(uuid.UUID(str(instance)))
        command = ['run_label_print_worker'] if service == 'print' else ['run_integration_worker', '--service', service]
        folder = Path(settings.WORKER_RUNTIME_DIR).parent
        folder.mkdir(parents=True, exist_ok=True)
        with (folder/f'{instance}.stdout.log').open('ab') as stdout, (folder/f'{instance}.stderr.log').open('ab') as stderr:
            subprocess.Popen([sys.executable, '-u', str(settings.BASE_DIR/'manage.py'), *command,
                              '--worker-instance', instance], cwd=settings.BASE_DIR, stdin=subprocess.DEVNULL,
                             stdout=stdout, stderr=stderr, close_fds=True)
