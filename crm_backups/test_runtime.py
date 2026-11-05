"""Имитируются Popen/сигналы. Настоящие рабочие процессы не запускаются и не останавливаются."""
from pathlib import Path
import unittest
from unittest.mock import patch
from GameBAT_CRM import container_runtime


class ContainerBackupProcessTests(unittest.TestCase):
    def test_one_existing_supervisor_and_independent_backup_executor(self):
        commands=[]
        class Stop:
            stopped=False
            def is_set(self):return self.stopped
            def set(self):self.stopped=True
            def wait(self,seconds):self.stopped=True;return True
        class Process:
            def __init__(self,command,**options):
                commands.append((command,options));self.pid=100+len(commands)
            def poll(self):return None
            def wait(self):return 0
        with patch.object(container_runtime.threading,'Event',return_value=Stop()),\
             patch.object(container_runtime.subprocess,'Popen',side_effect=Process),\
             patch.object(container_runtime.signal,'signal'),\
             patch.object(container_runtime.os,'killpg',side_effect=ProcessLookupError,create=True):
            self.assertEqual(container_runtime.run_services(Path('/artificial/app')),0)
        self.assertEqual(len(commands),3)
        self.assertIn('runserver',commands[0][0])
        self.assertIn('run_worker_supervisor',commands[1][0])
        self.assertIn('run_backup_worker',commands[2][0])
        self.assertEqual(commands[1][1]['process_group'],commands[2][1]['process_group'])
