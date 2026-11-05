"""Расписание и один слот проверяются без рабочей БД/файлов и без сети."""
import datetime
import uuid
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.core.exceptions import ValidationError
from .models import BackupConfiguration, BackupJob
from .crypto import generate_keys
from .jobs import request_job, schedule


class BackupQueueTests(TestCase):
    def setUp(self):
        _, public = generate_keys(b'test-owner-passphrase')
        self.config = BackupConfiguration.objects.create(enabled=True, public_key=public.decode(), recovery_key_saved=True)

    def test_duplicate_and_concurrent_slot_return_one_job(self):
        request = uuid.uuid4()
        first = request_job(request)
        self.assertEqual(request_job(request).pk, first.pk)
        self.assertEqual(request_job(uuid.uuid4()).pk, first.pk)
        self.assertEqual(BackupJob.objects.count(), 1)

    def test_disabled_key_not_saved_and_local_test_refused(self):
        self.config.recovery_key_saved=False; self.config.save()
        with self.assertRaises(ValidationError): request_job(uuid.uuid4())
        with override_settings(GAMEBAT_ENV='local_test'), self.assertRaises(ValidationError):
            request_job(uuid.uuid4())

    def test_daily_schedule_and_actual_catchup_date(self):
        now = datetime.datetime(2026, 11, 3, 10, tzinfo=datetime.timezone.utc)
        self.config.last_schedule_day=datetime.date(2026, 11, 1); self.config.save()
        schedule(now)
        daily = BackupJob.objects.get(kind='daily')
        self.assertEqual(daily.scheduled_for, datetime.date(2026,11,3))
        self.assertEqual(BackupJob.objects.filter(state='skipped').count(), 1)
        schedule(now)
        self.assertEqual(BackupJob.objects.filter(kind='daily').count(), 1)

    def test_worker_lock_is_tied_to_database_not_archive_folder(self):
        import tempfile
        from pathlib import Path
        from .configuration import sqlite_worker_lock
        with tempfile.TemporaryDirectory() as tmp:
            first=Path(tmp)/'one.sqlite3';second=Path(tmp)/'two.sqlite3'
            first.write_bytes(b'artificial');second.write_bytes(b'artificial')
            with override_settings(CRM_BACKUP_ROOT=Path(tmp)/'cache-one'):one=sqlite_worker_lock(first)
            with override_settings(CRM_BACKUP_ROOT=Path(tmp)/'cache-two'):two=sqlite_worker_lock(first)
            self.assertEqual(one,two)
            self.assertNotEqual(one,sqlite_worker_lock(second))

    def test_full_pending_queue_records_skipped_day_without_inventing_archive(self):
        for _ in range(2):BackupJob.objects.create(request_id=uuid.uuid4(),state='ready',active_slot=None)
        today=datetime.datetime(2026,11,3,10,tzinfo=datetime.timezone.utc)
        schedule(today);schedule(today)
        self.assertEqual(BackupJob.objects.filter(state='skipped',scheduled_for=today.date()).count(),1)
        self.assertFalse(BackupJob.objects.filter(state='queued').exists())
