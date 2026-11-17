"""Регрессии остановки polling: фиктивные API, без сети, потоков и рабочей БД."""
from types import SimpleNamespace
from unittest.mock import Mock, patch
from django.test import SimpleTestCase, override_settings
from .client import TelegramError
from .worker import run_polling


@override_settings(GAMEBAT_ENV='local_live')
class PollingRecoveryTests(SimpleTestCase):
    def run_worker(self, client, stop, *, reply=None):
        bot = SimpleNamespace(username='SyntheticBot', next_update_id=1)
        health = Mock()
        with patch('telegram_bots.worker.require_live_operation'), \
                patch('telegram_bots.worker.expected_status', return_value='required'), \
                patch('telegram_bots.worker.lease'), patch('telegram_bots.worker.read_token', return_value='synthetic'), \
                patch('telegram_bots.worker.recover_interrupted', return_value=[]), \
                patch('telegram_bots.worker.notify_recovered_jobs'), \
                patch('telegram_bots.worker._initialize_connection', return_value=True), \
                patch('telegram_bots.worker.StaffBot.objects.get', return_value=bot), \
                patch('digital_sales.models.Notification.objects.filter', return_value=[]), \
                patch('telegram_bots.worker.threading.Thread') as thread, \
                patch('telegram_bots.worker.connection_state'), \
                patch('telegram_bots.worker.accept_update', return_value=reply), \
                patch('digital_sales.reconciliation.remind_pending_topups', return_value=0), \
                patch('telegram_bots.worker.StaffBotUpdate.objects.filter') as receipts:
            thread.return_value.is_alive.return_value = True
            run_polling(1, 'synthetic-owner', stop, client_factory=lambda _: client, health=health)
        return health, receipts

    def test_three_server_refusals_do_not_permanently_disable_polling(self):
        stop = Mock()
        stopped, calls = False, 0
        stop.is_set.side_effect = lambda: stopped
        def polling(*args, **kwargs):
            nonlocal stopped, calls
            calls += 1
            if calls <= 3:
                raise TelegramError('refused', method='getUpdates', status_code=502)
            stopped = True
            return []
        client = Mock()
        client.call.side_effect = polling
        health, _ = self.run_worker(client, stop)
        self.assertEqual(calls, 4)
        self.assertEqual([c.args[0] for c in stop.wait.call_args_list], [10, 20, 40])
        self.assertEqual(health.progress.call_args.kwargs, {})

    def test_refused_reply_to_one_employee_does_not_stop_receiving_updates(self):
        stop = Mock()
        stopped, polls = False, 0
        stop.is_set.side_effect = lambda: stopped
        def api(method, data):
            nonlocal stopped, polls
            self.assertEqual(method, 'getUpdates')
            polls += 1
            if polls == 1:
                return [{'update_id': 17}]
            stopped = True
            return []
        client = Mock()
        client.call.side_effect = api
        client.message.side_effect = TelegramError('forbidden', method='sendMessage', status_code=403)
        health, receipts = self.run_worker(client, stop, reply={'chat_id': 101, 'text': 'Synthetic reply'})
        self.assertEqual(polls, 2)
        self.assertEqual(receipts.return_value.first.return_value.result, 'reply_failed')
        self.assertEqual(health.progress.call_args.kwargs, {})

    def test_initial_safe_probe_retries_server_refusals(self):
        from .connection import initialize_connection
        client, stop = Mock(), Mock()
        stop.is_set.return_value = False
        client.call.side_effect = [TelegramError('refused', method='getMe', status_code=503),
                                  {'username': 'SyntheticBot'}, {'url': ''}]
        self.assertEqual(initialize_connection(client, 'SyntheticBot', stop), {'username': 'SyntheticBot'})
        stop.wait.assert_called_once_with(10)

    def test_probe_reports_conflict_without_bypassing_identity_checks(self):
        from .connection import initialize_connection
        client, stop = Mock(), Mock()
        stop.is_set.return_value = False
        client.call.side_effect = TelegramError('conflict', method='getMe', status_code=409)
        with self.assertRaises(TelegramError):
            initialize_connection(client, 'SyntheticBot', stop)
        stop.wait.assert_not_called()


class AutonomousCycleTests(SimpleTestCase):
    def test_configuration_errors_keep_retrying_and_can_recover_without_manual_start(self):
        from .recovery import run_autonomous
        stopped, attempts = False, 0
        stop, health = Mock(), SimpleNamespace(health_error='', progress=Mock())
        stop.is_set.side_effect = lambda: stopped
        stop.wait.return_value = False
        def run():
            nonlocal attempts, stopped
            attempts += 1
            if attempts < 8:
                raise TelegramError('unauthorized')
            stopped = True
        run_autonomous(run, service='telegram_staff', stop=stop, expected=lambda: 'required', health=health)
        self.assertEqual(attempts, 8)
        self.assertEqual(sum(c.args[0] for c in stop.wait.call_args_list), 30 + 60 + 120 + 240 + 300 * 3)
        self.assertTrue(all(c.kwargs['verified'] is False for c in health.progress.call_args_list))
        self.assertTrue(all(c.kwargs['error'] == 'unauthorized' for c in health.progress.call_args_list))

    def test_explicit_disable_during_wait_prevents_next_connection(self):
        from .recovery import run_autonomous
        enabled = True
        stop, run = Mock(), Mock(side_effect=TelegramError('webhook'))
        stop.is_set.return_value = False
        def wait(seconds):
            nonlocal enabled
            enabled = False
            return False
        stop.wait.side_effect = wait
        run_autonomous(run, service='telegram_opt', stop=stop, expected=lambda: 'required' if enabled else 'disabled')
        run.assert_called_once()

    def test_once_does_not_create_a_background_retry_loop(self):
        from .recovery import run_autonomous
        stop, run = Mock(), Mock()
        stop.is_set.return_value = False
        run_autonomous(run, service='telegram_digital', stop=stop, expected=lambda: 'required', once=True)
        run.assert_called_once()
        stop.wait.assert_not_called()

    def test_other_process_lease_is_never_bypassed(self):
        from .recovery import run_autonomous
        from integrations.worker_runtime import AlreadyRunning
        stop, run = Mock(), Mock(side_effect=AlreadyRunning('synthetic lease'))
        stop.is_set.return_value = False
        with self.assertRaises(AlreadyRunning):
            run_autonomous(run, service='telegram_staff', stop=stop, expected=lambda: 'required')
        run.assert_called_once()
        stop.wait.assert_not_called()
