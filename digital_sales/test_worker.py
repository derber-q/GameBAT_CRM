import threading
import uuid
from unittest.mock import patch
from cryptography.fernet import Fernet
from django.test import TestCase, override_settings
from .models import DigitalBot, Supplier, DigitalOrder, SupplierMessage
from .worker import run_polling
from .crypto import decrypt
from .test_parser import checklist


class FakeClient:
    def __init__(self, updates, *, username='ReSOURSE_digital_goods_BOT', webhook=''):
        self.updates, self.username, self.webhook = updates, username, webhook
        self.calls = []

    def call(self, method, data=None):
        self.calls.append((method, data))
        if method == 'getMe':
            return {'username': self.username}
        if method == 'getWebhookInfo':
            return {'url': self.webhook}
        if method == 'getUpdates':
            return self.updates
        raise AssertionError('Непредусмотренный внешний метод: ' + method)

    def download(self, file_id):
        return b'SYNTHETIC-FILE-CONTENT'

    def close(self):
        pass


@override_settings(GAMEBAT_ENV='local_live')
class WorkerTests(TestCase):
    def setUp(self):
        self.enterContext(patch('digital_sales.crypto.cipher', return_value=Fernet(Fernet.generate_key())))
        self.enterContext(patch('digital_sales.worker.read_token', return_value='synthetic-not-a-token'))
        self.enterContext(patch('digital_sales.worker.expected_status', return_value='required'))
        self.enterContext(patch('digital_sales.worker.close_old_connections'))
        self.enterContext(patch('digital_sales.worker.connections.close_all'))
        self.bot = DigitalBot.objects.create(enabled=True)
        self.supplier = Supplier.objects.create(name='Fake', chat_ids=[-123], sender_ids=[55])

    def event(self, text, number=1, **fields):
        from django.utils import timezone
        message = {'message_id': number, 'date': int(timezone.now().timestamp()),
                   'chat': {'id': -123, 'type': 'supergroup'}, 'from': {'id': 55}, 'text': text}
        message.update(fields)
        return {'update_id': number, 'message': message}

    def run_once(self, client):
        run_polling(uuid.uuid4(), threading.Event(), client_factory=lambda token: client, once=True)

    def test_restart_uses_saved_offset_without_duplicate_or_supplier_reply(self):
        event = self.event(checklist())
        first = FakeClient([event])
        self.run_once(first)
        second = FakeClient([event])
        self.run_once(second)
        self.assertEqual(DigitalOrder.objects.count(), 1)
        self.assertEqual(next(data for method, data in second.calls if method == 'getUpdates')['offset'], 2)
        self.assertTrue(all(method in ('getMe', 'getWebhookInfo', 'getUpdates') for method, _ in first.calls + second.calls))

    def test_webhook_and_wrong_bot_are_blocked_without_deletion(self):
        for client in [FakeClient([], webhook='https://example.invalid/webhook'), FakeClient([], username='WrongBot')]:
            self.run_once(client)
            self.assertFalse(any(method == 'getUpdates' for method, _ in client.calls))
            self.bot.refresh_from_db()
            self.assertIn(self.bot.error_category, ['webhook', 'wrong_bot'])

    def test_three_timeouts_resume_with_saved_offset(self):
        from telegram_bots.client import TelegramError
        client, stop, polls = FakeClient([]), threading.Event(), []
        original_call = client.call
        def call(method, data=None):
            if method == 'getUpdates':
                polls.append(data)
                if len(polls) <= 3:
                    raise TelegramError('timeout')
                stop.set()
                return []
            return original_call(method, data)
        client.call = call
        with patch.object(stop, 'wait', return_value=False), patch('digital_sales.worker.expected_status',
                side_effect=['required'] * 7 + ['disabled']):
            run_polling(uuid.uuid4(), stop, client_factory=lambda _: client)
        self.assertEqual(len(polls), 4)
        self.assertTrue(all(data['offset'] == self.bot.next_update_id for data in polls))
        self.bot.refresh_from_db()
        self.assertEqual(self.bot.error_category, '')

    def test_file_reply_is_stored_encrypted(self):
        self.run_once(FakeClient([self.event(checklist())]))
        file = {'file_id': 'synthetic-id', 'file_size': 22, 'file_name': 'test.txt'}
        self.run_once(FakeClient([self.event('', number=2, reply_to_message={'message_id': 1}, document=file)]))
        source = SupplierMessage.objects.get(message_id=2)
        self.assertEqual(source.attachment_state, 'done')
        self.assertNotIn('SYNTHETIC-FILE-CONTENT', source.encrypted_payload)
        self.assertEqual(len(decrypt(source.encrypted_payload)['attachments']), 1)

    def test_bad_structure_is_ignored_without_crashing(self):
        from .ingestion import accept_update
        for index, message in enumerate([{'chat': []}, {'chat': {'id': -123}, 'from': []}], start=1):
            accept_update({'update_id': index, 'message': message})
        self.assertFalse(SupplierMessage.objects.exists())
