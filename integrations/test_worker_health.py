"""Регрессии ложного зелёного статуса; внешние API и рабочие процессы подменяются."""
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch
import threading
import uuid

from django.test import SimpleTestCase
from django.utils import timezone

from integrations.worker_health import process_health
from integrations.worker_heartbeat import Heartbeat
from telegram_bots.client import TelegramError
from telegram_bots.connection import initialize_connection


class WorkerFunctionalHealthTests(SimpleTestCase):
    def process(self, **kwargs):
        now = timezone.now()
        data = dict(heartbeat_at=now, started_at=now - timedelta(seconds=20),
                    progress_at=None, verified_at=None, executor_at=None, health_error='', ready=True)
        data.update(kwargs)
        return SimpleNamespace(**data)

    def test_fresh_heartbeat_without_work_never_means_running(self):
        process = self.process()
        self.assertEqual(process_health(process, 'telegram_staff', timezone.now()), ('recovering', 'checking'))

    def test_actual_poll_and_executor_confirm_staff_bot(self):
        now = timezone.now()
        process = self.process(progress_at=now, verified_at=now, executor_at=now)
        self.assertEqual(process_health(process, 'telegram_staff', timezone.now()), ('running', ''))

    def test_network_error_is_visible_even_with_recent_success(self):
        now = timezone.now()
        process = self.process(progress_at=now, verified_at=now, health_error='network')
        self.assertEqual(process_health(process, 'telegram_digital', timezone.now()), ('degraded', 'network'))

    def test_wrong_token_is_blocked_instead_of_green(self):
        process = self.process(health_error='wrong_bot')
        self.assertEqual(process_health(process, 'telegram_opt', timezone.now()), ('blocked', 'wrong_bot'))

    def test_poll_stall_and_document_executor_stall_are_separate(self):
        old = timezone.now() - timedelta(seconds=1200)
        process = self.process(progress_at=old, verified_at=old, executor_at=old)
        self.assertEqual(process_health(process, 'telegram_staff', timezone.now()), ('degraded', 'stalled'))
        process.progress_at = process.verified_at = timezone.now()
        self.assertEqual(process_health(process, 'telegram_staff', timezone.now()), ('degraded', 'executor_stalled'))

    def test_heartbeat_thread_does_not_confirm_main_loop(self):
        beat = Heartbeat(['avito'], uuid.uuid4(), 'birth')
        self.assertIsNone(beat.verified_at)
        beat.progress(verified=False, error='network')
        self.assertIsNone(beat.verified_at)
        beat.progress()
        self.assertIsNotNone(beat.verified_at)
        self.assertEqual(beat.health_error, '')

    def test_connection_retries_reads_without_sending_or_faking_poll_success(self):
        client, health, stop = Mock(), Mock(), Mock()
        stop.is_set.return_value = False
        client.call.side_effect = [TelegramError('network'), {'username':'TestBot'}, {'url':''}]
        self.assertEqual(initialize_connection(client, 'TestBot', stop, health=health), {'username':'TestBot'})
        self.assertEqual([call.args[0] for call in client.call.call_args_list], ['getMe','getMe','getWebhookInfo'])
        health.progress.assert_called_once_with(verified=False, error='network')
        stop.wait.assert_called_once()

    def test_fatal_configuration_is_not_retried(self):
        client, stop = Mock(), threading.Event()
        client.call.return_value = {'username':'AnotherBot'}
        with self.assertRaises(TelegramError):
            initialize_connection(client, 'ExpectedBot', stop)
        client.call.assert_called_once_with('getMe')
