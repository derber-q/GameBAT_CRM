"""Распознавание только процессов данного контейнера без Docker socket и реальных API."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings


class LinuxProcessesTests(SimpleTestCase):
    def test_inventory_rejects_foreign_scripts_and_reads_birth_and_instance(self):
        from .linux_processes import LinuxProcesses
        with TemporaryDirectory() as folder:
            root = Path(folder)
            for pid, argv, cwd in (
                (10, ['python', '/app/manage.py', 'run_integration_worker', '--service', 'avito',
                      '--worker-instance', 'f099f933-8f73-43f9-8aa9-a5c663f22af1'], '/app'),
                (11, ['python', '/other/manage.py', 'run_label_print_worker'], '/app'),
                (12, ['python', 'manage.py', 'run_label_print_worker'], '/app'),
                (13, ['python', 'manage.py', 'run_integration_worker'], '/other'),
                (14, ['python', '/app/manage.py', 'run_telegram_staff_bot'], '/app'),
            ):
                proc = root / str(pid)
                proc.mkdir()
                (proc/'cmdline').write_bytes(('\0'.join(argv)+'\0').encode())
                (proc/'stat').write_text(f'{pid} (python unusual name) S ' + ' '.join(['0']*18 + ['12345']))
                (proc/'cwd').write_text(cwd)
            with override_settings(BASE_DIR=Path('/app')), patch('integrations.linux_processes.os.readlink', side_effect=lambda p: Path(p).read_text()):
                rows = LinuxProcesses(proc_root=root).inventory()
            self.assertEqual([r['pid'] for r in rows], [10, 12, 14])
            self.assertEqual(rows[0]['services'], ['avito'])
            self.assertEqual(rows[0]['birth'], '12345')
            self.assertEqual(rows[1]['services'], ['print'])
            self.assertEqual(rows[2]['services'], ['telegram_staff'])

    def test_factory_preserves_windows_and_test_mode_is_denied(self):
        from .worker_processes import process_adapter, WindowsProcesses
        from .linux_processes import LinuxProcesses
        with patch('integrations.worker_processes.sys.platform', 'win32'):
            self.assertIsInstance(process_adapter(), WindowsProcesses)
        with patch('integrations.worker_processes.sys.platform', 'linux'):
            self.assertIsInstance(process_adapter(), LinuxProcesses)
        with override_settings(GAMEBAT_ENV='local_test'):
            with self.assertRaises(Exception):
                LinuxProcesses().inventory()
