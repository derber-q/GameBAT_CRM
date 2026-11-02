"""Polling и конкуренция на отдельной тестовой БД, без настоящего Telegram."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch, Mock
import threading
import uuid
from django.contrib.auth.models import Permission
from django.db import close_old_connections, connections
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from accounts.models import User
from warehouse.models import Warehouse
from integrations.worker_runtime import AlreadyRunning, process_lock
from integrations.worker_models import WorkerController, WorkerService, WorkerProcess
from integrations.worker_monitoring import supervise_once, request_recovery
from integrations.test_worker_monitoring import FakeProcesses
from .tests import FAKE_TOKEN, FakeClient, update
from .configuration import save_token
from .handlers import accept_update
from .models import StaffBot, StaffBotAccess, StaffBotJob
from .worker import run_polling


@override_settings(GAMEBAT_ENV='local_live')
class StaffWorkerTests(TransactionTestCase):
    def setUp(self):
        folder = self.enterContext(TemporaryDirectory())
        self.enterContext(override_settings(TELEGRAM_STAFF_TOKEN_FILE=Path(folder)/'token', WORKER_RUNTIME_DIR=Path(folder)/'locks'))
        self.enterContext(patch.dict('os.environ', {'GAMEBAT_TELEGRAM_STAFF_BOT_TOKEN': ''}))
        save_token(FAKE_TOKEN)
        self.bot = StaffBot.objects.create(username='StaffTestBot', enabled=True, cooldown_seconds=0)
        self.user = User.objects.create_user('threaded-bot')
        self.user.user_permissions.add(*Permission.objects.filter(codename__in=['use_staff_bot', 'generate_wholesale_price']))
        self.access = StaffBotAccess.objects.create(bot=self.bot, user=self.user, allowed=True, telegram_user_id=101)
        self.wh = Warehouse.objects.create(name='Склад тестового бота')

    def test_concurrent_updates_enqueue_only_one_job(self):
        bot_id, wh_id = self.bot.pk, self.wh.pk
        def receive(number):
            close_old_connections()
            try:
                return accept_update(bot_id, update(number, data=f'wholesale_stock_price:{wh_id}'))
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(receive, [1, 2]))
        self.assertEqual(StaffBotJob.objects.count(), 1)
        self.assertTrue(any('уже' in result['text'] for result in results))

    def test_polling_continues_while_document_is_generated(self):
        started, release, stop = threading.Event(), threading.Event(), threading.Event()
        bot_id, wh_id = self.bot.pk, self.wh.pk
        client = FakeClient()
        calls = []
        original_call = client.call
        def call(method, data=None):
            if method == 'getUpdates':
                calls.append(data)
                if len(calls) == 1:
                    return [update(1, data=f'wholesale_stock_price:{wh_id}')]
                try:
                    self.assertTrue(started.wait(5))
                finally:
                    stop.set()
                    release.set()
                return []
            return original_call(method, data)
        client.call = call
        def generate(*_):
            started.set()
            if not release.wait(10):
                raise AssertionError('Polling заблокирован генерацией')
            return 'synthetic.xlsx', b'fake-xlsx'
        with patch('telegram_bots.jobs.wholesale_document', side_effect=generate):
            run_polling(bot_id, uuid.uuid4(), stop, client_factory=lambda _: client)
        self.assertEqual(len(calls), 2)
        self.assertEqual(StaffBotJob.objects.get().state, 'done')
        self.assertEqual(len(client.documents), 1)
        self.bot.refresh_from_db()
        self.assertIsNone(self.bot.lease_owner)

    def test_webhook_and_conflict_never_delete_webhook_or_automatically_retry(self):
        for error in ['webhook', 'conflict']:
            client, stop = FakeClient(), threading.Event()
            original_call = client.call
            def call(method, data=None):
                if method == 'getWebhookInfo' and error == 'webhook':
                    return {'url': 'https://example.invalid/existing-handler'}
                if method == 'getUpdates':
                    from .client import TelegramError
                    raise TelegramError('conflict')
                return original_call(method, data)
            client.call = call
            with patch('telegram_bots.worker.job_loop', lambda *args: args[1].wait(2)):
                run_polling(self.bot.pk, uuid.uuid4(), stop, client_factory=lambda _: client, once=True)
            self.bot.refresh_from_db()
            self.assertEqual(self.bot.error_category, error)
            self.assertFalse(any(name == 'deleteWebhook' for name, _ in client.calls))
            self.assertEqual(client.documents, [])

    def test_double_process_lock_is_rejected(self):
        with process_lock('telegram_staff'):
            with self.assertRaises(AlreadyRunning):
                with process_lock('telegram_staff'):
                    pass

    def test_supervisor_retries_three_times_and_manual_recovery_is_independent(self):
        adapter = FakeProcesses()
        adapter.fail = True
        WorkerController.objects.create(mode='managed')
        now = timezone.now()
        from datetime import timedelta
        policy = dict.fromkeys(['avito', 'yandex', 'google', 'print'], 'disabled')
        policy['telegram_staff'] = 'required'
        with patch('integrations.worker_monitoring.expected_services', return_value=policy):
            for seconds in [0, 60, 120, 240]:
                supervise_once(adapter, now=now + timedelta(seconds=seconds))
            service = WorkerService.objects.get(code='telegram_staff')
            self.assertEqual(service.failures, 3)
            self.assertTrue(service.auto_paused)
            self.assertEqual(len(adapter.launches), 3)
            admin = User.objects.create_superuser('telegram-recovery')
            request_recovery(admin, ['telegram_staff'], uuid.uuid4())
            adapter.fail = False
            supervise_once(adapter, now=now + timedelta(seconds=300))
            code, instance = adapter.launches[-1]
            row = adapter.rows[-1]
            for seconds in [301, 370]:
                WorkerProcess.objects.update_or_create(instance=instance, defaults={
                    'pid': row['pid'], 'birth': row['birth'], 'services': [code], 'ready': True,
                    'heartbeat_at': now + timedelta(seconds=seconds)})
                supervise_once(adapter, now=now + timedelta(seconds=seconds))
            service.refresh_from_db()
            self.assertEqual(service.status, 'running')
            self.assertEqual(service.failures, 0)
        self.assertTrue(all(code == 'telegram_staff' for code, _ in adapter.launches))
