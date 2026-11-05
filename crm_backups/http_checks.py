"""Сквозной HTTP клиент → очередь → зашифрованный архив → Windows downloader
→ подтверждение → отдельное восстановление. Только временная БД/файлы/ключи.
"""
import hashlib
import os
from pathlib import Path
import tempfile
import uuid
from unittest.mock import patch
from cryptography.fernet import Fernet
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connections
from django.test import override_settings
from accounts.models import User
from .crypto import generate_keys
from .models import BackupConfiguration,BackupDevice,BackupJob
from .devices import issue_enrollment,enroll
from .jobs import claim_job,run_job
from .snapshot import restore_bundle
from local_agent.transport import BackupAPI
from local_agent.journal import BackupJournal
from local_agent.downloads import download


class BackupHTTPChecks(StaticLiveServerTestCase):
    def test_request_download_confirm_and_restore_over_real_local_http(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);media=root/'media';media.mkdir()
            (media/'artificial-document.pdf').write_bytes(b'%PDF-artificial')
            key=Fernet.generate_key().decode()
            with override_settings(MEDIA_ROOT=media,CRM_BACKUP_ROOT=root/'cache',CRM_APP_ARTIFACT_ROOT=root/'apps',
                SECRET_KEY='synthetic-http-key',INTEGRATION_ENCRYPTION_KEY=key,RESOURCE_TOKEN_ENCRYPTION_KEY=key,
                GOOGLE_SERVICE_ACCOUNT_FILE='',YANDEX_MARKET_API_KEY='',YANDEX_MARKET_KEY_FILE=root/'absent-yandex',
                TELEGRAM_STAFF_TOKEN_FILE=root/'absent-telegram',LABEL_PRINTER_CONFIG_PATH=root/'absent-printer'),\
                patch.dict(os.environ,{'GAMEBAT_TELEGRAM_STAFF_BOT_TOKEN':''}):
                actor=User.objects.create_superuser('http-backup-artificial')
                private,public=generate_keys(b'owner-http-test-password')
                BackupConfiguration.objects.create(enabled=True,public_key=public.decode(),recovery_key_saved=True)
                token='synthetic-backup-'+uuid.uuid4().hex;device_id=uuid.uuid4()
                code=issue_enrollment(actor,can_request=True)
                enroll(code,device_id,hashlib.sha256(token.encode()).hexdigest(),'Artificial HTTP device')
                api=BackupAPI({'server_url':self.live_server_url,'device_id':str(device_id),'backup_token':token},uuid.uuid4())
                self.assertTrue(api.heartbeat()['ok'])
                receipt=api.create(uuid.uuid4())
                job=claim_job();self.assertEqual(str(job.pk),receipt['id'])
                run_job(job);job.refresh_from_db();self.assertEqual(job.state,'ready',job.error)
                meta=next(row for row in api.status() if row['id']==receipt['id'])
                journal=BackupJournal(root/'local-journal.sqlite3')
                try:path=download(meta,root/'local-archives',journal,api.stream,minimum_free_bytes=0)
                finally:journal.close()
                self.assertTrue(api.confirm(meta)['ok'])
                job.refresh_from_db();self.assertEqual(job.state,'verified');self.assertIsNotNone(job.downloaded_at)
                manifest=restore_bundle(path,root/'restored',private,b'owner-http-test-password')
                self.assertEqual((root/'restored/protected_media/artificial-document.pdf').read_bytes(),b'%PDF-artificial')
                self.assertEqual(manifest['integrity_check'],'ok')
                self.assertLess(manifest['write_window_seconds'],15)
