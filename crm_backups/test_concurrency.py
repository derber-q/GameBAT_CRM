"""Настоящие отдельные соединения: два запроса не создают два тяжёлых задания/устройства."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import threading
import uuid
from django.db import connections,close_old_connections
from django.test import TransactionTestCase
from accounts.models import User
from .crypto import generate_keys
from .devices import issue_enrollment,enroll
from .jobs import request_job
from .models import BackupConfiguration,BackupDevice,BackupJob


class BackupConcurrencyTests(TransactionTestCase):
    def setUp(self):
        _,public=generate_keys(b'artificial-owner-password')
        BackupConfiguration.objects.create(enabled=True,public_key=public.decode(),recovery_key_saved=True)
        self.actor=User.objects.create_superuser('concurrent-backup-owner')

    def concurrent(self,operation):
        barrier=threading.Barrier(2)
        def run(index):
            close_old_connections();barrier.wait(timeout=10)
            try:return operation(index)
            except ValueError:return 'refused'
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:return list(pool.map(run,range(2)))

    def test_two_enrollments_consume_code_once(self):
        code=issue_enrollment(self.actor)
        results=self.concurrent(lambda i:str(enroll(code,uuid.uuid4(),hashlib.sha256(str(i).encode()).hexdigest(),'test '+str(i)).pk))
        self.assertEqual(results.count('refused'),1)
        self.assertEqual(BackupDevice.objects.filter(active_slot=1).count(),1)

    def test_two_requests_share_the_single_active_job(self):
        results=self.concurrent(lambda i:str(request_job(uuid.uuid4()).pk))
        self.assertEqual(len(set(results)),1)
        self.assertEqual(BackupJob.objects.filter(active_slot=1).count(),1)
