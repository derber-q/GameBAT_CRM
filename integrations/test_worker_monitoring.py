"""Контроль процессов проверяется без запуска API, Windows-печати и рабочих worker."""
from datetime import timedelta
from unittest.mock import patch
import uuid

from django.test import TestCase, TransactionTestCase, Client, SimpleTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from integrations.worker_models import WorkerController, WorkerService, WorkerProcess, WorkerCommand
from integrations.worker_monitoring import supervise_once, monitoring_snapshot, request_recovery


class FakeProcesses:
    def __init__(self):
        self.rows = []
        self.launches = []
        self.available = True
        self.fail = False

    def inventory(self):
        if not self.available:
            raise OSError('SECRET must never appear in status')
        return self.rows.copy()

    def launch(self, service, instance):
        self.launches.append((service, instance))
        if self.fail:
            raise OSError('SECRET launch failure')
        self.rows.append({'pid': 120 + len(self.launches), 'birth': str(instance),
                          'instance': str(instance), 'services': [service]})


class SupervisorTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.adapter = FakeProcesses()
        WorkerController.objects.create(mode='managed')
        self.policy = patch('integrations.worker_monitoring.expected_services', return_value={
            code: 'required' if code == 'avito' else 'disabled' for code in ('avito', 'yandex', 'google', 'print')})
        self.policy.start()
        self.addCleanup(self.policy.stop)

    def tick(self, seconds=0):
        supervise_once(self.adapter, now=self.now + timedelta(seconds=seconds))
        return WorkerService.objects.get(pk='avito')

    def heartbeat(self, seconds):
        code, instance = self.adapter.launches[-1]
        row = self.adapter.rows[-1]
        WorkerProcess.objects.update_or_create(instance=instance, defaults={
            'pid': row['pid'], 'birth': row['birth'], 'services': [code],
            'heartbeat_at': self.now + timedelta(seconds=seconds), 'ready': True})

    def test_launch_is_not_success_until_stable_heartbeat(self):
        service = self.tick()
        self.assertEqual(service.status, 'recovering')
        self.assertIsNone(service.last_started_at)
        self.heartbeat(10)
        self.assertEqual(self.tick(10).status, 'recovering')
        self.heartbeat(75)
        service = self.tick(75)
        self.assertEqual(service.status, 'running')
        self.assertIsNotNone(service.last_started_at)
        self.assertEqual(service.failures, 0)

    def test_three_failures_persist_and_stop_automatic_launches(self):
        self.adapter.fail = True
        for seconds in (0, 60, 120, 240, 360):
            service = self.tick(seconds)
        self.assertEqual(len(self.adapter.launches), 3)
        self.assertEqual(service.failures, 3)
        self.assertEqual(service.status, 'paused')
        self.assertNotIn('SECRET', str(monitoring_snapshot(now=self.now + timedelta(seconds=360))))

    def test_inventory_failure_never_launches_or_counts_failure(self):
        self.adapter.available = False
        service = self.tick()
        self.assertEqual(service.status, 'unknown')
        self.assertEqual(service.failures, 0)
        self.assertEqual(self.adapter.launches, [])

    def test_all_worker_without_heartbeat_is_unknown_and_never_duplicated(self):
        self.adapter.rows = [{'pid': 99, 'birth': 'legacy', 'instance': '',
                              'services': ['avito', 'google', 'yandex']}]
        self.assertEqual(self.tick().status, 'unknown')
        self.assertEqual(self.adapter.launches, [])

    def test_stale_heartbeat_of_live_process_does_not_spawn_duplicate(self):
        self.tick()
        self.heartbeat(1)
        self.assertEqual(self.tick(200).status, 'unknown')
        self.assertEqual(len(self.adapter.launches), 1)

    def test_reused_pid_does_not_accept_old_heartbeat(self):
        instance = uuid.uuid4()
        WorkerProcess.objects.create(instance=instance, pid=99, birth='old', services=['avito'],
                                     ready=True, heartbeat_at=self.now)
        self.adapter.rows = [{'pid': 99, 'birth': 'new', 'instance': str(instance), 'services': ['avito']}]
        self.assertEqual(self.tick().status, 'unknown')

    def test_manual_command_is_idempotent_and_does_not_reset_paused_on_failure(self):
        from accounts.models import User
        actor = User.objects.create_superuser('worker-admin')
        WorkerService.objects.create(code='avito', expected='required', status='paused', failures=3)
        request_id = uuid.uuid4()
        first = request_recovery(actor, ['avito'], request_id)
        second = request_recovery(actor, ['avito'], request_id)
        self.assertEqual(first, second)
        self.assertEqual(WorkerCommand.objects.count(), 1)
        self.adapter.fail = True
        self.tick()
        self.tick(90)
        self.assertEqual(len(self.adapter.launches), 1)
        self.assertEqual(WorkerService.objects.get(pk='avito').failures, 3)

    def test_site_only_does_not_start_workers(self):
        controller = WorkerController.objects.get()
        controller.mode = 'site_only'
        controller.save()
        service = self.tick()
        self.assertEqual(service.expected, 'disabled')
        self.assertEqual(self.adapter.launches, [])

    def test_crash_after_intent_waits_and_does_not_blindly_launch(self):
        service = self.tick()
        instance = service.launch_instance
        self.assertEqual(self.tick(20).launch_instance, instance)
        self.assertEqual(len(self.adapter.launches), 1)

    def test_fast_crashes_do_not_reset_failures(self):
        for start in (0, 90, 180):
            self.tick(start)
            self.heartbeat(start + 1)
            self.tick(start + 1)
            self.adapter.rows.clear()
            self.tick(start + 46)
        self.assertEqual(self.tick(300).failures, 3)
        self.assertEqual(len(self.adapter.launches), 3)

    def test_long_job_is_healthy_and_task_errors_do_not_increment_failures(self):
        from integrations.models import AvitoSyncJob
        self.tick()
        self.heartbeat(1000)
        self.tick(1000)
        self.heartbeat(1061)
        self.assertEqual(self.tick(1061).status, 'running')
        AvitoSyncJob.objects.create(dedupe_key='failed', job_type='manual', status='error',
                                   run_after=self.now, last_error='SECRET')
        self.heartbeat(1080)
        service = self.tick(1080)
        self.assertEqual(service.failures, 0)
        self.assertEqual(service.status, 'running')

    def test_manual_success_after_limit_resets_only_when_stable(self):
        from accounts.models import User
        actor = User.objects.create_superuser('manual-ok')
        WorkerService.objects.create(code='avito', failures=3, status='paused', expected='required')
        ids = request_recovery(actor, ['avito'], uuid.uuid4())
        self.tick()
        self.heartbeat(1)
        self.assertEqual(self.tick(1).failures, 3)
        self.heartbeat(62)
        self.assertEqual(self.tick(62).failures, 0)
        self.assertEqual(WorkerCommand.objects.get(pk=ids[0]).state, 'confirmed')

    def test_services_are_independent_and_all_worker_covers_three(self):
        self.policy.stop()
        with patch('integrations.worker_monitoring.expected_services', return_value=dict.fromkeys(
                ('avito', 'yandex', 'google', 'print'), 'required')):
            self.adapter.rows = [{'pid': 10, 'birth': 'legacy', 'instance': '',
                                  'services': ['avito', 'yandex', 'google']}]
            self.tick()
            self.assertEqual([code for code, _ in self.adapter.launches], ['print'])

    def test_all_four_services_recover_independently(self):
        self.policy.stop()
        with patch('integrations.worker_monitoring.expected_services', return_value=dict.fromkeys(
                ('avito', 'yandex', 'google', 'print'), 'required')):
            self.tick()
            for code, instance in self.adapter.launches:
                row = next(row for row in self.adapter.rows if row['instance'] == str(instance))
                WorkerProcess.objects.create(instance=instance, pid=row['pid'], birth=row['birth'],
                    services=[code], ready=True, heartbeat_at=self.now)
            self.tick(1)
            self.tick(62)
            self.assertEqual(WorkerService.objects.filter(status='running').count(), 4)
            self.assertEqual(len(self.adapter.launches), 4)
            self.assertFalse(monitoring_snapshot(now=self.now + timedelta(seconds=62))['alarm'])

    def test_controller_disappearance_never_preserves_old_green(self):
        controller = WorkerController.objects.get()
        controller.heartbeat_at = self.now - timedelta(seconds=120)
        controller.save()
        WorkerService.objects.create(code='avito', status='running', expected='required',
            observed_at=self.now, heartbeat_at=self.now)
        data = monitoring_snapshot(now=self.now)
        self.assertTrue(data['controller_alarm'])
        self.assertEqual(data['services'][0]['status'], 'unknown')
        self.assertTrue(data['alarm'])

    def test_disabled_services_do_not_raise_alarm_with_live_controller(self):
        controller = WorkerController.objects.get()
        controller.heartbeat_at = self.now
        controller.save()
        with patch('integrations.worker_monitoring.expected_services', return_value=dict.fromkeys(
                ('avito', 'yandex', 'google', 'print'), 'disabled')):
            self.assertFalse(monitoring_snapshot(now=self.now)['alarm'])

    def test_new_process_must_complete_its_own_stable_period(self):
        self.tick()
        self.heartbeat(1)
        self.tick(1)
        code, old_instance = self.adapter.launches[-1]
        replacement = uuid.uuid4()
        row = self.adapter.rows[-1]
        row['instance'], row['birth'] = str(replacement), 'replacement'
        WorkerProcess.objects.create(instance=replacement, pid=row['pid'], birth=row['birth'],
            services=[code], ready=True, heartbeat_at=self.now + timedelta(seconds=62))
        service = self.tick(62)
        self.assertEqual(service.status, 'recovering')
        self.assertEqual(service.stable_instance, replacement)

    def test_recheck_adopts_all_worker_appearing_immediately_before_launch(self):
        rows = [{'pid': 77, 'birth': 'late', 'instance': '', 'services': ['avito', 'yandex', 'google']}]
        with patch.object(self.adapter, 'inventory', side_effect=[[], rows]):
            self.assertEqual(self.tick().status, 'unknown')
        self.assertEqual(self.adapter.launches, [])

    def test_failed_manual_attempt_does_not_invent_three_failures(self):
        from accounts.models import User
        actor = User.objects.create_superuser('manual-first-fails')
        request_recovery(actor, ['avito'], uuid.uuid4())
        self.adapter.fail = True
        service = self.tick()
        self.assertEqual(service.failures, 1)
        self.assertTrue(service.auto_paused)
        self.tick(100)
        self.assertEqual(len(self.adapter.launches), 1)

    def test_heartbeat_arriving_during_inventory_is_not_a_failed_launch(self):
        instance = uuid.uuid4()
        self.adapter.rows = [{'pid': 99, 'birth': 'live', 'instance': str(instance), 'services': ['avito']}]
        WorkerProcess.objects.create(instance=instance, pid=99, birth='live', services=['avito'],
            ready=True, heartbeat_at=self.now + timedelta(seconds=1))
        WorkerService.objects.create(code='avito', expected='required', status='recovering',
            launch_instance=instance, launch_started_at=self.now - timedelta(seconds=75),
            stable_instance=instance, stable_since=self.now - timedelta(seconds=70))
        clock = [self.now]

        def inventory():
            clock[0] = self.now + timedelta(seconds=2)
            return self.adapter.rows

        with patch('integrations.worker_monitoring.timezone.now', side_effect=lambda: clock[0]), \
                patch.object(self.adapter, 'inventory', side_effect=inventory):
            supervise_once(self.adapter)
        service = WorkerService.objects.get(pk='avito')
        self.assertEqual(service.status, 'running')
        self.assertEqual(service.failures, 0)


class WorkerAccessTests(TestCase):
    def setUp(self):
        from accounts.models import User
        self.user = User.objects.create_user('worker-staff')
        self.admin = User.objects.create_superuser('worker-super')

    def test_login_active_user_read_only_and_keys_stay_protected(self):
        url = reverse('integrations:workers')
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Обработчики')
        self.assertContains(response, 'data-notification-sound-enable', count=1)
        self.assertContains(response, 'data-worker-alert')
        self.assertNotContains(response, 'Восстановить все')
        self.assertEqual(self.client.get(reverse('integrations:api_keys')).status_code, 403)
        self.assertEqual(self.client.get(reverse('integrations:worker_status')).status_code, 200)
        self.assertEqual(self.client.post(reverse('integrations:worker_start', args=['avito']),
                                         {'request_id': uuid.uuid4()}).status_code, 403)

    def test_post_only_superuser_csrf_and_allowlist(self):
        self.client.force_login(self.admin)
        url = reverse('integrations:worker_start', args=['avito'])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url, {'request_id': 'bad'}).status_code, 400)
        self.assertEqual(self.client.post(reverse('integrations:worker_start', args=['cmd.exe']),
                                         {'request_id': uuid.uuid4()}).status_code, 400)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.admin)
        self.assertEqual(csrf_client.post(url, {'request_id': uuid.uuid4()}).status_code, 403)
        csrf_client.get(reverse('integrations:workers'))
        response = csrf_client.post(url, {'request_id': uuid.uuid4()},
            HTTP_X_CSRFTOKEN=csrf_client.cookies['csrftoken'].value)
        self.assertEqual(response.status_code, 202)
        command = response.json()['commands'][0]
        self.assertEqual(self.client.get(reverse('integrations:worker_command', args=[command])).json()['state'], 'skipped')
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('integrations:worker_command', args=[command])).status_code, 403)

    def test_get_never_creates_runtime_or_queue_rows_and_redacts_errors(self):
        from integrations.models import AvitoSyncJob
        self.client.force_login(self.user)
        AvitoSyncJob.objects.create(dedupe_key='bad', job_type='manual', status='error',
                                   run_after=timezone.now(), last_error='SECRET token C:/private/key')
        before = list(AvitoSyncJob.objects.values())
        for name in ('workers', 'worker_status'):
            response = self.client.get(reverse('integrations:' + name))
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, 'SECRET')
            self.assertNotContains(response, 'private/key')
        self.assertEqual(list(AvitoSyncJob.objects.values()), before)
        self.assertEqual(WorkerController.objects.count(), 0)
        self.assertEqual(WorkerService.objects.count(), 0)


class WorkerScheduleTests(TestCase):
    def test_due_priority_future_time_disabled_and_running(self):
        from integrations.models import AvitoSyncJob
        from integrations.worker_schedule import queue_snapshot
        now = timezone.now()
        AvitoSyncJob.objects.create(dedupe_key='old', job_type='reconcile', run_after=now - timedelta(minutes=5))
        manual = AvitoSyncJob.objects.create(dedupe_key='manual', job_type='manual', run_after=now - timedelta(seconds=1))
        data = queue_snapshot('avito', now=now)
        self.assertEqual(data['next_action'], 'Ручная сверка')
        self.assertTrue(data['overdue'])
        manual.status = 'running'
        manual.started_at = now
        manual.save()
        self.assertEqual(queue_snapshot('avito', now=now)['current_action'], 'Ручная сверка')
        self.assertIsNone(queue_snapshot('avito', now=now, enabled=False)['next_at'])

    def test_future_manual_never_hides_earlier_future_reconcile(self):
        from integrations.models import AvitoSyncJob
        from integrations.worker_schedule import queue_snapshot
        now = timezone.now()
        AvitoSyncJob.objects.create(dedupe_key='first', job_type='reconcile', run_after=now + timedelta(minutes=1))
        AvitoSyncJob.objects.create(dedupe_key='later', job_type='manual', run_after=now + timedelta(minutes=2))
        self.assertEqual(queue_snapshot('avito', now=now)['next_action'], 'Контрольная сверка')

    def test_google_retry_and_empty_print_queue(self):
        from integrations.models import GoogleSheetsSyncJob
        from integrations.worker_schedule import queue_snapshot
        now = timezone.now()
        GoogleSheetsSyncJob.objects.create(dedupe_key='manual', attempts=1, run_after=now)
        self.assertEqual(queue_snapshot('google', now=now)['next_action'], 'Повторная попытка Google Sheets')
        data = queue_snapshot('print', now=now)
        self.assertIsNone(data['next_at'])
        self.assertEqual(data['next_action'], 'Ожидание задания на печать')


class WorkerLockTests(SimpleTestCase):
    def test_second_owner_cannot_take_lock_and_release_allows_new_owner(self):
        import tempfile
        from integrations.worker_runtime import process_lock, AlreadyRunning
        with tempfile.TemporaryDirectory() as directory, override_settings(WORKER_RUNTIME_DIR=directory):
            with process_lock('supervisor'):
                with self.assertRaises(AlreadyRunning):
                    with process_lock('supervisor'):
                        self.fail('Два владельца')
            with process_lock('supervisor'):
                pass

    def test_inventory_timeout_is_unknown_and_never_leaks_raw_exception(self):
        import subprocess
        from integrations.worker_processes import WindowsProcesses
        with patch('integrations.worker_processes.subprocess.run', side_effect=subprocess.TimeoutExpired('SECRET', 12)):
            with self.assertRaises(OSError) as result:
                WindowsProcesses().inventory()
        self.assertNotIn('SECRET', str(result.exception))

    def test_heartbeat_retries_after_database_error_and_uses_own_connection(self):
        from django.db import OperationalError
        from integrations.worker_heartbeat import Heartbeat
        beat = Heartbeat(['avito'], uuid.uuid4(), 'birth')
        with patch('integrations.worker_heartbeat.WorkerProcess.objects.update_or_create',
                   side_effect=[OperationalError('locked'), (None, False)]) as write, \
                patch('integrations.worker_heartbeat.connections.close_all') as close:
            beat.write()
            beat.write()
            self.assertEqual(write.call_count, 2)
            self.assertEqual(close.call_count, 2)


class WorkerPolicyTests(TestCase):
    def test_avito_requires_previous_confirmation_but_api_error_does_not_disable_it(self):
        from integrations.models import IntegrationCredential
        from integrations.worker_policy import expected_services
        credential = IntegrationCredential.objects.create(provider='avito', encrypted_client_id='test',
                                                           encrypted_client_secret='test')
        self.assertEqual(expected_services()['avito'], 'unconfigured')
        credential.last_success_at = timezone.now()
        credential.status = 'error'
        credential.save()
        self.assertEqual(expected_services()['avito'], 'required')

    def test_disabled_google_and_missing_credentials_are_not_incidents(self):
        from integrations.models import GoogleSheetsIntegration
        from integrations.worker_policy import expected_services
        google = GoogleSheetsIntegration.objects.create(enabled=False, spreadsheet_url='https://example.invalid', spreadsheet_id='test')
        self.assertEqual(expected_services()['google'], 'disabled')
        google.enabled = True
        google.save()
        with override_settings(GOOGLE_SERVICE_ACCOUNT_FILE=''):
            self.assertEqual(expected_services()['google'], 'unconfigured')

    def test_site_only_configuration_preserves_live_supervisor_mode(self):
        from django.core.management import call_command
        from integrations.worker_runtime import AlreadyRunning
        WorkerController.objects.create(mode='managed')
        with patch('integrations.management.commands.configure_worker_monitoring.process_lock', side_effect=AlreadyRunning):
            call_command('configure_worker_monitoring', site_only=True)
        self.assertEqual(WorkerController.objects.get().mode, 'managed')


class WorkerCommandConcurrencyTests(TransactionTestCase):
    def test_two_admin_requests_share_one_intent(self):
        from concurrent.futures import ThreadPoolExecutor
        import threading
        from django.db import connections
        from accounts.models import User
        actor = User.objects.create_superuser('concurrent-worker-admin')
        WorkerController.objects.create(mode='managed')
        barrier = threading.Barrier(2)

        def submit():
            try:
                barrier.wait(timeout=5)
                return request_recovery(actor, ['avito'], uuid.uuid4())
            finally:
                connections.close_all()

        with patch('integrations.worker_monitoring.expected_services', return_value={'avito': 'required'}), \
                ThreadPoolExecutor(max_workers=2) as pool:
            first, second = list(pool.map(lambda _: submit(), range(2)))
        self.assertEqual(first, second)
        self.assertEqual(WorkerCommand.objects.count(), 1)
