import os
from pathlib import Path
import unittest
from unittest.mock import patch

from .__main__ import load_config
from .store import UpdateError


class DeploymentPolicyTests(unittest.TestCase):
    def test_ci_uses_file_sqlite_without_spawn_clones_on_windows(self):
        from .ci_checks import main
        for platform, parallel in (('nt', '1'), ('posix', '4')):
            with self.subTest(platform=platform), \
                    patch('deployment.ci_checks.os.name', platform), \
                    patch.dict(os.environ), \
                    patch('sys.argv', ['ci_checks']), \
                    patch('deployment.ci_checks.subprocess.check_output', return_value=''), \
                    patch('deployment.ci_checks.subprocess.run'), \
                    patch('deployment.ci_checks.multiprocessing.set_start_method'), \
                    patch('django.core.management.execute_from_command_line') as execute:
                main()
                self.assertEqual(execute.call_args_list[-1].args[0],
                    ['manage.py', 'test', '--parallel', parallel, '--noinput'])

    def test_nonproduction_manager_refuses_before_reading_config_or_running_docker(self):
        with patch.dict(os.environ,{'GAMEBAT_ENV':'local_live'}), \
                patch('deployment.__main__.sys.platform','linux'), \
                patch('deployment.__main__.os.geteuid',return_value=1000,create=True):
            with self.assertRaises(UpdateError):load_config(Path('/nonexistent-config.json'))

    def test_release_workflow_has_only_manual_trigger_and_production_gate(self):
        root=Path(__file__).resolve().parent.parent
        text=(root/'.github/workflows/production-release.yml').read_text('utf-8')
        self.assertIn('on:\n  workflow_dispatch:',text)
        for trigger in ('schedule:','repository_dispatch:','push:\n','pull_request:'):
            self.assertNotIn(trigger,text)
        self.assertIn('python -m deployment.production_gate',text)
        self.assertNotIn('git pull',text)
        self.assertNotIn('ssh ',text)
