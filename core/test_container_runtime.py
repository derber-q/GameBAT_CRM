"""Жизненный цикл контейнера проверяется только фиктивными процессами без БД и API."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
from unittest import skipUnless

from django.test import SimpleTestCase, TestCase
from unittest.mock import patch
from contextlib import nullcontext


class ContainerPolicyTests(TestCase):
    def test_linux_never_requires_native_windows_printing(self):
        from integrations.worker_policy import expected_services
        with patch('integrations.worker_policy.sys.platform', 'linux'), \
                patch('sales.label_printing.printer_configuration') as printer:
            self.assertEqual(expected_services()['print'], 'disabled')
        printer.assert_not_called()


class WorkerShutdownTests(SimpleTestCase):
    def test_container_entry_rejects_test_mode_before_commands(self):
        from GameBAT_CRM.container_runtime import main
        with patch.dict(os.environ, {'GAMEBAT_ENV': 'local_test'}), \
                patch('GameBAT_CRM.container_runtime.subprocess.run') as command:
            with self.assertRaises(SystemExit):
                main()
        command.assert_not_called()

    def test_signal_finishes_current_processor_and_never_starts_the_next(self):
        from django.core.management import call_command
        module = 'integrations.management.commands.run_integration_worker'
        def finish_job():
            handler = signal.getsignal(signal.SIGTERM)
            self.assertTrue(callable(handler))
            handler(signal.SIGTERM, None)
            return False
        with patch(module+'.monitored_worker', return_value=nullcontext(None)), \
                patch(module+'.process_one_job', side_effect=finish_job) as avito, \
                patch(module+'.process_one_google_sheets_job') as google, \
                patch(module+'.process_yandex_job') as yandex:
            call_command('run_integration_worker', service='all', once=True)
        avito.assert_called_once()
        google.assert_not_called()
        yandex.assert_not_called()


@skipUnless(os.name == 'posix', 'Нужны группы процессов Linux')
class ContainerRuntimeTests(SimpleTestCase):
    def test_controller_restarts_and_shutdown_drains_its_worker(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'manage.py').write_text('''import os, signal, subprocess, sys, time
from pathlib import Path
root=Path(__file__).parent
if sys.argv[1]=='run_worker_supervisor':
    path=root/'starts'
    count=int(path.read_text())+1 if path.exists() else 1
    path.write_text(str(count))
    if count==1: sys.exit(7)
    code="import signal,time; from pathlib import Path; stop=False; signal.signal(signal.SIGTERM, lambda *_: globals().__setitem__('stop',True)); Path(%r).write_text('ready'); exec('while not stop: time.sleep(.02)'); time.sleep(.3); Path(%r).write_text('done')" % (str(root/'worker-ready'),str(root/'worker-done'))
    subprocess.Popen([sys.executable,'-c',code])
while True: time.sleep(.05)
''', encoding='utf-8')
            entry = ("from pathlib import Path; from GameBAT_CRM.container_runtime import run_services; "
                     f"raise SystemExit(run_services(Path({str(root)!r}), restart_delay=.05, shutdown_timeout=3))")
            process = subprocess.Popen([sys.executable, '-c', entry], stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, text=True)
            try:
                deadline=time.monotonic()+10
                while not (root/'worker-ready').exists() and process.poll() is None and time.monotonic()<deadline:
                    time.sleep(.03)
                self.assertTrue((root/'worker-ready').exists())
                self.assertEqual((root/'starts').read_text(), '2')
                process.send_signal(signal.SIGTERM)
                stdout, stderr=process.communicate(timeout=6)
                self.assertEqual(process.returncode, 0, stdout+stderr)
                self.assertTrue((root/'worker-done').exists(), stdout+stderr)
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=6)
