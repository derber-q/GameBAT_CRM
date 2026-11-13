"""Транспорт/перезапуск без рабочего токена и без реальных Telegram-запросов."""
from threading import Event as Stop
from unittest.mock import MagicMock as Mock, patch
from django.test import SimpleTestCase, TransactionTestCase, override_settings
from telegram_bots.client import TelegramError
from .client import WholesaleClient
from .configuration import expected_status
from .models import BotConfig, Customer, Event, Delivery


class TransportTests(SimpleTestCase):
    def test_download_rejects_paths_and_oversized_metadata_before_http(self):
        session = Mock()
        for path, size in [('https://example.invalid/a', 1), ('../file', 1), ('/file', 1),
                           ('documents/a.xlsx', 6 * 1024 * 1024)]:
            client = WholesaleClient('synthetic-token', session=session)
            with patch.object(client, 'call', return_value={'file_path': path, 'file_size': size}),\
                    self.subTest(path=path), self.assertRaises(TelegramError):
                client.download('id')
        session.get.assert_not_called()

    def test_download_checks_actual_size_and_disallows_redirects(self):
        session = Mock()
        response = session.get.return_value.__enter__.return_value
        response.status_code = 200
        response.iter_content.return_value = [b'x' * (5 * 1024 * 1024), b'x']
        client = WholesaleClient('synthetic-token', session=session)
        with patch.object(client, 'call', return_value={'file_path': 'documents/file.xlsx', 'file_size': 1}),\
                self.assertRaises(TelegramError):
            client.download('id')
        self.assertFalse(session.get.call_args.kwargs['allow_redirects'])

    @override_settings(GAMEBAT_ENV='local_test')
    def test_test_mode_does_not_read_live_secret(self):
        with patch('wholesale_bot.configuration.token_path', side_effect=AssertionError('No live file')):
            self.assertEqual(expected_status(), 'disabled')


class WorkerFailureTests(TransactionTestCase):
    def test_download_error_is_persisted_and_customer_receives_safe_notice(self):
        from .worker import run_polling
        BotConfig.objects.create()
        customer = Customer.objects.create(telegram_id=991)
        event = Event.objects.create(update_id=1, customer=customer)
        client = Mock()
        client.call.side_effect = lambda method, *a, **k: (
            {'username': 'ReSOURCE_OPT_BOT'} if method == 'getMe' else
            {'url': ''} if method == 'getWebhookInfo' else [])
        with patch('wholesale_bot.worker.expected_status', return_value='required'),\
                patch('wholesale_bot.worker.read_token', return_value='synthetic-token'),\
                patch('wholesale_bot.worker.process_event', side_effect=TelegramError('download_network')):
            run_polling(Stop(), client_factory=lambda _: client, once=True)
        event.refresh_from_db()
        self.assertEqual(event.state, 'error')
        self.assertEqual(event.error, 'download_network')
        self.assertEqual(Delivery.objects.get().state, 'sent')
        self.assertIn('Не удалось получить файл', client.message.call_args.args[1])
