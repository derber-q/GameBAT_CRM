"""Транспорт и восстановление проверяются без настоящей печати и сети."""
import hashlib
from pathlib import Path
import tempfile
import unittest
import uuid
import os
from unittest.mock import patch

from .engine import Engine
from .journal import Journal
from .transport import TransportError, NoRedirect, server_origin


class FakeAPI:
    def __init__(self):
        self.data=b'%PDF-synthetic'
        self.job={'id':str(uuid.uuid4()),'claim':str(uuid.uuid4()),'sha256':hashlib.sha256(self.data).hexdigest(),'state':'agent_claimed'}
        self.results=[];self.fail_confirm=False
    def heartbeat(self,data): pass
    def claim(self): return self.job
    def document(self,job): return self.data
    def result(self,job,state,spool=None):
        self.results.append(state)
        if state=='begin':self.job['state']='agent_printing'
        if state=='confirmed':
            self.job=None
            if self.fail_confirm:
                self.fail_confirm=False
                raise TransportError('lost_reply')


class FakeDriver:
    def __init__(self):self.prints=0;self.complete=True;self.releases=0
    def available(self):return True
    def validate(self,data):pass
    def submit(self,data,title):self.prints+=1;return 77
    def completed(self,spool,title):return self.complete
    def release(self,spool,title):self.releases+=1


class AgentClientTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.journal=Journal(Path(self.temp.name)/'journal.sqlite3','test');self.addCleanup(self.journal.close)
        self.api=FakeAPI();self.driver=FakeDriver();self.engine=Engine(self.api,self.journal,self.driver,'Fake printer')

    def test_lost_confirm_reply_is_retried_without_second_print(self):
        self.api.fail_confirm=True
        with self.assertRaises(TransportError):self.engine.step()
        self.engine.step()
        self.assertEqual(self.driver.prints,1);self.assertEqual(self.driver.releases,1)

    def test_restart_after_print_marker_never_resubmits(self):
        self.journal.put(self.api.job,'printing')
        self.engine.step()
        self.assertEqual(self.driver.prints,0);self.assertIn('uncertain',self.api.results)

    def test_foreign_machine_without_journal_does_not_repeat_started_job(self):
        self.api.job['state']='agent_printing'
        self.engine.step()
        self.assertEqual(self.driver.prints,0);self.assertIn('uncertain',self.api.results)

    def test_spooled_is_not_confirmation_and_only_one_submit_occurs(self):
        self.driver.complete=False
        self.engine.step();self.engine.step()
        self.assertNotIn('confirmed',self.api.results)
        self.driver.complete=True;self.engine.step()
        self.assertEqual(self.driver.prints,1);self.assertIn('confirmed',self.api.results)

    def test_tampered_pdf_never_reaches_driver(self):
        self.api.data=b'%PDF-changed'
        self.engine.step()
        self.assertEqual(self.driver.prints,0);self.assertIn('error',self.api.results)

    def test_remote_plain_http_credentials_and_redirect_are_refused(self):
        for url in ('http://example.com','https://user:secret@example.com','https://example.com/path','https://example.com/?token=x'):
            with self.assertRaises(ValueError):server_origin(url)
        self.assertEqual(server_origin('http://127.0.0.1:8000/'),'http://127.0.0.1:8000')
        with self.assertRaises(TransportError):NoRedirect().redirect_request(None,None,None,None,None,None)

    def test_real_driver_is_forbidden_in_local_test(self):
        from .driver import WindowsDriver
        with patch.dict(os.environ,{'GAMEBAT_ENV':'local_test'}):
            with self.assertRaisesRegex(RuntimeError,'local_test'):
                WindowsDriver('Must not access printer')
