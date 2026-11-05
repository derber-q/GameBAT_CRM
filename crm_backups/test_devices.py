"""Один получатель и независимость токена печати; архивы только в temp."""
import hashlib
import json
from pathlib import Path
import secrets
import tempfile
import uuid
from django.test import TestCase, override_settings
from django.urls import reverse
from .models import BackupDevice, BackupJob, BackupConfiguration
from .devices import issue_enrollment, enroll
from .configuration import backup_root


class BackupDeviceTests(TestCase):
    def setUp(self):
        self.client.defaults['HTTP_HOST']='localhost'
        from accounts.models import User
        self.admin = User.objects.create_superuser('backup-admin')
        self.token = secrets.token_urlsafe(48)
        self.device_id = uuid.uuid4(); self.session = uuid.uuid4()
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.enterContext(override_settings(CRM_BACKUP_ROOT=Path(self.temp.name)))

    def connect(self, *, replace=False):
        code = issue_enrollment(self.admin, replace=replace, can_request=True)
        return enroll(code, self.device_id, hashlib.sha256(self.token.encode()).hexdigest(), 'Test device')

    def post(self, name, data=None, **headers):
        return self.client.post(reverse('crm_backups:'+name), data=json.dumps(data or {}), content_type='application/json',
            HTTP_AUTHORIZATION='Bearer '+self.token, HTTP_X_BACKUP_DEVICE=str(self.device_id),
            HTTP_X_BACKUP_SESSION=str(self.session), **headers)

    def test_enrollment_one_use_and_explicit_replacement(self):
        self.connect()
        with self.assertRaises(ValueError): issue_enrollment(self.admin)
        old = self.device_id
        self.device_id = uuid.uuid4(); self.token = secrets.token_urlsafe(48)
        self.connect(replace=True)
        self.assertIsNone(BackupDevice.objects.get(pk=old).active_slot)
        self.assertEqual(BackupDevice.objects.filter(active_slot=1).count(), 1)

    def test_reuse_code_and_non_admin_denied(self):
        from accounts.models import User
        code = issue_enrollment(self.admin)
        enroll(code, self.device_id, hashlib.sha256(self.token.encode()).hexdigest(), 'device')
        with self.assertRaises(ValueError):
            enroll(code, uuid.uuid4(), 'a'*64, 'other')
        with self.assertRaises(PermissionError): issue_enrollment(User.objects.create_user('employee'))

    def test_scope_http_origin_and_revocation(self):
        self.connect()
        self.assertEqual(self.post('heartbeat').status_code, 200)
        self.assertEqual(self.post('heartbeat', HTTP_ORIGIN='https://foreign.example').status_code, 403)
        self.assertEqual(self.post('heartbeat', HTTP_HOST='192.0.2.1').status_code, 400)
        with override_settings(GAMEBAT_ENV='local_test'):
            self.assertEqual(self.post('heartbeat').status_code, 403)
        device=BackupDevice.objects.get(pk=self.device_id); device.active_slot=None; device.save()
        self.assertEqual(self.post('heartbeat').status_code, 401)

    def test_print_token_has_no_backup_access_and_reverse(self):
        from sales.models import PrintAgent
        print_token = secrets.token_urlsafe(48)
        PrintAgent.objects.create(id=self.device_id, name='printer', printer_name='Fake',
            token_hash=hashlib.sha256(print_token.encode()).hexdigest())
        self.token=print_token
        self.assertEqual(self.post('heartbeat').status_code, 401)
        self.token=secrets.token_urlsafe(48); self.connect()
        with override_settings(LABEL_PRINT_BACKEND='agent'):
            response=self.client.post('/crm/print-agent/heartbeat/',data='{}',content_type='application/json',
                HTTP_AUTHORIZATION='Bearer '+self.token, HTTP_X_PRINT_AGENT=str(self.device_id),
                HTTP_X_PRINT_SESSION=str(self.session), HTTP_X_PRINT_PROTOCOL='1')
        self.assertEqual(response.status_code,401)

    def test_range_and_confirm_after_hash_verification(self):
        self.connect(); self.post('heartbeat')
        body=b'only encrypted fixture'*100
        digest=hashlib.sha256(body).hexdigest()
        job=BackupJob.objects.create(request_id=uuid.uuid4(),state='ready',active_slot=None,
            sha256=digest,size=len(body),metadata={'environment_id':str(BackupConfiguration.objects.get(pk=1).environment_id)})
        (backup_root()/(str(job.pk)+'.backup')).write_bytes(body)
        url=reverse('crm_backups:download',args=[job.pk])
        headers={'HTTP_AUTHORIZATION':'Bearer '+self.token,'HTTP_X_BACKUP_DEVICE':str(self.device_id),
            'HTTP_X_BACKUP_SESSION':str(self.session),'HTTP_RANGE':'bytes=5-','HTTP_IF_MATCH':'"'+digest+'"'}
        response=self.client.get(url,**headers)
        self.assertEqual(response.status_code,206)
        self.assertEqual(b''.join(response.streaming_content),body[5:])
        self.assertEqual(self.client.get(url,**{**headers,'HTTP_IF_MATCH':'"wrong"'}).status_code,412)
        confirm=reverse('crm_backups:confirm',args=[job.pk])
        auth={k:v for k,v in headers.items() if k not in ('HTTP_RANGE','HTTP_IF_MATCH')}
        self.assertEqual(self.client.post(confirm,data=json.dumps({'size':1,'sha256':digest}),content_type='application/json',**auth).status_code,400)
        self.assertEqual(self.client.post(confirm,data=json.dumps({'size':len(body),'sha256':digest}),content_type='application/json',**auth).status_code,200)
        job.refresh_from_db(); self.assertEqual(job.state,'verified')

    def test_second_active_device_is_rejected_by_database(self):
        from django.db import transaction, IntegrityError
        self.connect()
        with self.assertRaises(IntegrityError), transaction.atomic():
            BackupDevice.objects.create(pk=uuid.uuid4(),name='other',token_hash='a'*64,active_slot=1)
        self.assertEqual(BackupDevice.objects.filter(active_slot=1).count(),1)

    def test_expired_enrollment_code_is_refused(self):
        from .models import BackupEnrollment
        from django.utils import timezone
        from datetime import timedelta
        code=issue_enrollment(self.admin)
        operation=BackupEnrollment.objects.get()
        operation.expires_at=timezone.now()-timedelta(seconds=1); operation.save()
        with self.assertRaises(ValueError): enroll(code,self.device_id,'a'*64,'device')
