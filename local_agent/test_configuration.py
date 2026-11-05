import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from .configuration import initial,save,load,profile_folder,private_folder


@unittest.skipUnless(os.name=='nt','DPAPI проверяется на настоящей Windows')
class WindowsProfileTests(unittest.TestCase):
    def test_separate_profiles_dpapi_and_process_locks(self):
        from print_agent.__main__ import exclusive
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'LOCALAPPDATA':tmp}):
            one=private_folder(profile_folder('one'));two=private_folder(profile_folder('two'))
            a=initial();b=initial();a['print_token']='first-artificial-token';b['print_token']='second-artificial-token'
            a['backup_token']='independent-backup-token'
            save(one,a);save(two,b)
            self.assertEqual(load(one),a);self.assertEqual(load(two),b)
            self.assertNotEqual(a['agent_id'],b['agent_id'])
            self.assertNotIn(a['print_token'],(one/'settings.json').read_text('utf-8'))
            from .configuration import private_file
            import win32security
            key=one/'owner.recovery.pem';key.write_bytes(b'fake encrypted private key');private_file(key)
            dacl=win32security.GetFileSecurity(str(key),win32security.DACL_SECURITY_INFORMATION).GetSecurityDescriptorDacl()
            self.assertEqual(dacl.GetAceCount(),2)
            with exclusive(one/'application.lock'):
                with self.assertRaises(SystemExit),exclusive(one/'application.lock'):pass
                with exclusive(two/'application.lock'):pass

    def test_same_printer_blocked_across_profiles_but_another_printer_allowed(self):
        from print_agent.profiles import printer_lock
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'LOCALAPPDATA':tmp}):
            one=private_folder(profile_folder('one'));two=private_folder(profile_folder('two'))
            with printer_lock('Fake printer',one):
                with self.assertRaises(SystemExit),printer_lock('Fake printer',two):pass
                with printer_lock('Another printer',two):pass
