"""Периодическая проверка не меняет публикации и не обходит очередь повторов."""
from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase
from django.utils import timezone
from .models import IntegrationCredential, AvitoSyncJob
from .queue import ensure_required_actions_refresh


class ActionScheduleTests(TestCase):
    def test_no_credentials_no_task(self):
        self.assertIsNone(ensure_required_actions_refresh())

    def test_single_task_rearms_after_fifteen_minutes_and_preserves_retry(self):
        IntegrationCredential.objects.create(provider='avito', encrypted_client_id='test', encrypted_client_secret='test')
        now = timezone.now()
        with patch('integrations.queue.timezone.now', return_value=now):
            job = ensure_required_actions_refresh()
            self.assertEqual(job.job_type, 'status_refresh')
            self.assertEqual(ensure_required_actions_refresh().pk, job.pk)
            job.status, job.finished_at = 'done', now
            job.save()
        with patch('integrations.queue.timezone.now', return_value=now + timedelta(minutes=14, seconds=59)):
            self.assertEqual(ensure_required_actions_refresh().status, 'done')
        with patch('integrations.queue.timezone.now', return_value=now + timedelta(minutes=15)):
            self.assertEqual(ensure_required_actions_refresh().status, 'pending')
        job.refresh_from_db()
        job.run_after = now + timedelta(hours=1)
        job.attempts = 2
        job.save()
        ensure_required_actions_refresh()
        job.refresh_from_db()
        self.assertEqual(job.attempts, 2)
        self.assertEqual(job.run_after, now + timedelta(hours=1))
        self.assertEqual(AvitoSyncJob.objects.filter(job_type='status_refresh').count(), 1)
