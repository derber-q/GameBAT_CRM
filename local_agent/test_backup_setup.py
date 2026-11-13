"""Понятные причины отказа и защита пароля; без сети и рабочей БД."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from local_agent.transport import error_message
from print_agent.transport import TransportError


class BackupSetupTests(unittest.TestCase):
    def test_expected_denials_explain_next_step_without_raw_exception(self):
        for code in ('manual_request_forbidden','backup_disabled','recovery_not_configured','unauthorized','session_conflict'):
            text=error_message(TransportError(code,403))
            self.assertNotIn('TransportError',text)
            self.assertNotIn('HTTP 403',text)
            self.assertGreater(len(text),30)

    @unittest.skipUnless(os.name=='nt','Windows DPAPI')
    def test_remembered_recovery_password_is_not_plaintext(self):
        from local_agent.configuration import initial,save,load,private_folder
        with tempfile.TemporaryDirectory() as directory:
            folder=private_folder(Path(directory)/'profile')
            config=initial();config['recovery_password']='artificial-recovery-password'
            save(folder,config)
            self.assertNotIn(config['recovery_password'],(folder/'settings.json').read_text('utf-8'))
            self.assertEqual(load(folder)['recovery_password'],config['recovery_password'])
