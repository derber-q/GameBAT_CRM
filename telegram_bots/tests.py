"""Фиктивные Telegram API и товары. Рабочие ключи, сообщения и склад не используются."""
from datetime import timedelta
from io import BytesIO, StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
import threading
import uuid
import requests
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError, PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase, SimpleTestCase, override_settings, Client
from django.urls import reverse
from django.utils import timezone
from openpyxl import load_workbook
from accounts.models import User
from catalog.models import CD, Platform
from warehouse.models import Warehouse, CDWarehouseStock
from price.excel import import_wholesale_price_to_sale, generate_wholesale_price_xlsx
from sales.models import Sale
from .access import BotDenied, issue_link, consume_link, authorize, set_employee_access, check_function_access
from .client import TelegramClient, TelegramError
from .configuration import save_token, read_token, expected_status, token_configured
from .documents import wholesale_document
from .handlers import accept_update
from .jobs import claim_job, run_job, recover_interrupted
from .menu import WHOLESALE
from .models import StaffBot, StaffBotAccess, StaffBotJob, StaffBotUpdate, StaffBotLink
from .worker import run_polling, lease

FAKE_TOKEN = '123456:' + 'x' * 35


def update(update_id, user_id=101, *, text='', data=None, chat_type='private'):
    message = {'chat': {'id': user_id, 'type': chat_type}, 'from': {'id': user_id}, 'text': text}
    if data is not None:
        return {'update_id': update_id, 'callback_query': {'id': 'callback-test', 'from': message['from'], 'message': message, 'data': data}}
    return {'update_id': update_id, 'message': message}


class FakeClient:
    def __init__(self, *_):
        self.documents, self.messages, self.calls = [], [], []
        self.error = None
        self.updates = []

    def call(self, method, data=None):
        self.calls.append((method, data))
        if self.error:
            raise self.error
        return {'getMe': {'username': 'StaffTestBot'}, 'getWebhookInfo': {'url': ''}, 'getUpdates': self.updates}.get(method, True)

    def document(self, chat_id, filename, data):
        self.documents.append((chat_id, filename, data))
        if self.error:
            raise self.error
        return {'message_id': 15}

    def message(self, *args):
        self.messages.append(args)
        if self.error:
            raise self.error

    def close(self):
        pass


@override_settings(GAMEBAT_ENV='local_live')
class StaffBotTests(TestCase):
    def setUp(self):
        folder = self.enterContext(TemporaryDirectory())
        self.enterContext(override_settings(TELEGRAM_STAFF_TOKEN_FILE=Path(folder) / 'token'))
        self.enterContext(patch.dict('os.environ', {'GAMEBAT_TELEGRAM_STAFF_BOT_TOKEN': ''}))
        self.user = User.objects.create_user('staff-bot-user')
        self.user.user_permissions.add(*Permission.objects.filter(
            codename__in=['use_staff_bot', 'generate_wholesale_price']))
        self.admin = User.objects.create_superuser('staff-bot-admin')
        self.bot = StaffBot.objects.create(username='StaffTestBot', enabled=True, cooldown_seconds=30)
        self.access = StaffBotAccess.objects.create(bot=self.bot, user=self.user, allowed=True,
            telegram_user_id=101, linked_at=timezone.now())
        self.wh = Warehouse.objects.first() or Warehouse.objects.create(name='Тестовый склад')
        self.wh.name = 'Тестовый склад'
        self.wh.save()
        for other in Warehouse.objects.exclude(pk=self.wh.pk):
            other.delete()
        self.game = CD.objects.create(name='Тестовая игра', platform=Platform.objects.create(name='TestBot'), wholesale_price=100)
        self.stock = CDWarehouseStock.objects.create(cd=self.game, warehouse=self.wh, quantity=3)

    def request(self, number=1, **kwargs):
        return accept_update(self.bot.pk, update(number, data=WHOLESALE.code, **kwargs))

    def test_single_warehouse_and_persistent_update_dedupe(self):
        self.assertIn('Формирую', self.request()['text'])
        self.assertIsNone(self.request())
        self.assertEqual(StaffBotJob.objects.count(), 1)
        self.bot.refresh_from_db()
        self.assertEqual(self.bot.next_update_id, 2)
        self.assertEqual(StaffBotUpdate.objects.count(), 1)

    def test_only_one_active_job_and_cooldown_after_completion(self):
        self.request()
        self.assertIn('уже', self.request(2)['text'])
        self.assertEqual(StaffBotJob.objects.count(), 1)
        job = claim_job(self.bot.pk)
        run_job(job, FakeClient())
        self.assertIn('частые', self.request(3)['text'])
        self.bot.cooldown_seconds = 0
        self.bot.save()
        self.request(4)
        self.assertEqual(StaffBotJob.objects.count(), 2)

    def test_unknown_users_and_non_private_chats_never_get_file(self):
        for number, args in enumerate([{'user_id': 999}, {'chat_type': 'group'}, {'chat_type': 'supergroup'}, {'chat_type': 'channel'}], 1):
            self.request(number, **args)
        self.assertEqual(StaffBotJob.objects.count(), 0)

    def test_inactive_missing_permissions_revocation_and_disallowed_access(self):
        for state in ['inactive', 'no_price', 'no_bot', 'revoked', 'not_allowed']:
            with self.subTest(state=state):
                self.user.is_active = state != 'inactive'
                self.user.save()
                self.user.user_permissions.set(Permission.objects.filter(codename__in=[
                    code for code in ['use_staff_bot', 'generate_wholesale_price']
                    if code != {'no_price': 'generate_wholesale_price', 'no_bot': 'use_staff_bot'}.get(state)]))
                self.access.allowed = state != 'not_allowed'
                self.access.revoked_at = timezone.now() if state == 'revoked' else None
                self.access.save()
                if state == 'no_price':
                    authorize(self.bot, 101)  # Общий допуск теперь не требует права отдельной функции.
                    with self.assertRaises(BotDenied):
                        check_function_access(self.access, WHOLESALE.code)
                else:
                    with self.assertRaises(BotDenied):
                        authorize(self.bot, 101)

    def test_forged_callbacks_and_missing_warehouse(self):
        for i, data in enumerate(['arbitrary_action', WHOLESALE.code + ':999999', WHOLESALE.code + ':-1', WHOLESALE.code + ':1;DROP'], 1):
            accept_update(self.bot.pk, update(i, data=data))
        self.assertEqual(StaffBotJob.objects.count(), 0)

    def test_multiple_warehouses_select_and_back(self):
        second = Warehouse.objects.create(name='Другой склад')
        result = self.request()
        self.assertIn('Выберите склад', result['text'])
        self.assertEqual(len(result['reply_markup']['inline_keyboard']), 3)
        self.assertEqual(StaffBotJob.objects.count(), 0)
        accept_update(self.bot.pk, update(2, data=f'{WHOLESALE.code}:{second.pk}'))
        self.assertEqual(StaffBotJob.objects.get().warehouse_id, second.pk)
        result = accept_update(self.bot.pk, update(3, data='menu'))
        self.assertIn(WHOLESALE.title, str(result))

    def test_menu_commands_and_no_warehouse(self):
        for i, command in enumerate(['/start', '/menu', '/help'], 1):
            self.assertIn(WHOLESALE.title, str(accept_update(self.bot.pk, update(i, text=command))))
        with patch('telegram_bots.handlers.Warehouse.objects.order_by', return_value=[]):
            self.assertIn('нет доступных', self.request(10)['text'])

    def test_menu_uses_persistent_reply_keyboard_and_button_creates_document(self):
        for i, command in enumerate(['/start', '/menu', '/help'], 1):
            with self.subTest(command=command):
                reply = accept_update(self.bot.pk, update(i, text=command))
                keyboard = reply['reply_markup']
                self.assertEqual(keyboard.get('keyboard'), [[{'text': WHOLESALE.title}]])
                self.assertTrue(keyboard.get('is_persistent'))
                self.assertTrue(keyboard.get('resize_keyboard'))
                self.assertFalse(keyboard.get('one_time_keyboard', True))
                self.assertNotIn('inline_keyboard', keyboard)
        result = accept_update(self.bot.pk, update(4, text=WHOLESALE.title))
        self.assertIn('Формирую', result['text'])
        client = FakeClient()
        run_job(claim_job(self.bot.pk), client)
        self.assertEqual(len(client.documents), 1)
        self.assertEqual(client.documents[0][0], 101)

    def test_reply_keyboard_button_selects_warehouse_and_rechecks_access(self):
        second = Warehouse.objects.create(name='Другой склад')
        result = accept_update(self.bot.pk, update(1, text=WHOLESALE.title))
        buttons = result['reply_markup']['inline_keyboard']
        self.assertIn(f'{WHOLESALE.code}:{second.pk}', str(buttons))
        self.assertEqual(StaffBotJob.objects.count(), 0)
        self.access.allowed = False
        self.access.save()
        accept_update(self.bot.pk, update(2, text=WHOLESALE.title))
        self.assertEqual(StaffBotUpdate.objects.get(update_id=2).result, 'denied')
        self.assertEqual(StaffBotJob.objects.count(), 0)

    def test_link_is_hashed_expiring_one_time_and_rejects_username_identity(self):
        self.access.telegram_user_id = None
        self.access.save()
        link = issue_link(self.user, self.bot)
        token = link.split('start=')[1]
        row = StaffBotLink.objects.get()
        self.assertNotEqual(row.token_hash, token)
        self.assertNotIn(token, str(row.__dict__))
        result = accept_update(self.bot.pk, update(1, user_id=202, text='/start ' + token))
        self.assertIn(WHOLESALE.title, str(result))
        self.assertEqual(StaffBotAccess.objects.get(pk=self.access.pk).telegram_user_id, 202)
        self.assertIn('недействительна', accept_update(self.bot.pk, update(2, user_id=303, text='/start ' + token))['text'])
        with self.assertRaises(BotDenied):
            consume_link(self.bot, 'not-a-real-code-at-all', 303)

    def test_expired_and_replaced_links_and_identity_collision(self):
        self.access.telegram_user_id = None
        self.access.save()
        first = issue_link(self.user, self.bot).split('start=')[1]
        second = issue_link(self.user, self.bot).split('start=')[1]
        with self.assertRaises(BotDenied):
            consume_link(self.bot, first, 202)
        link = StaffBotLink.objects.get(used_at__isnull=True)
        link.expires_at = timezone.now() - timedelta(seconds=1)
        link.save()
        with self.assertRaises(BotDenied):
            consume_link(self.bot, second, 202)
        third = issue_link(self.user, self.bot).split('start=')[1]
        StaffBotAccess.objects.create(bot=self.bot, user=self.admin, allowed=True, telegram_user_id=202)
        with self.assertRaises(BotDenied):
            consume_link(self.bot, third, 202)
        with transaction.atomic(), self.assertRaises(IntegrityError):
            StaffBotAccess.objects.create(bot=self.bot, user=User.objects.create_user('duplicate'), telegram_user_id=202)

    def test_revoking_and_regranting_invalidates_old_links(self):
        self.access.telegram_user_id = None
        self.access.save()
        token = issue_link(self.user, self.bot).split('start=')[1]
        set_employee_access(self.admin, self.bot, self.user, False)
        set_employee_access(self.admin, self.bot, self.user, True)
        with self.assertRaises(BotDenied):
            consume_link(self.bot, token, 202)
        with self.assertRaises(PermissionDenied):
            set_employee_access(self.user, self.bot, self.user, True)

    def test_document_is_anonymous_and_imports_with_existing_signed_metadata(self):
        filename, data = wholesale_document(self.access, self.wh.pk)
        self.assertEqual(filename, f'ReSOURCE Price List Опт {timezone.localdate():%d.%m.%Y}.xlsx')
        workbook = load_workbook(BytesIO(data))
        self.assertIn('_resource_meta', workbook.sheetnames)
        sheet = workbook[workbook.sheetnames[0]]
        row = next(row for row in sheet.iter_rows() if row[0].value == self.game.name)
        self.assertEqual(row[1].value, 100)
        self.assertEqual(row[2].value, 3)
        row[3].value = 1
        stream = BytesIO()
        workbook.save(stream)
        wh, lines, customer = import_wholesale_price_to_sale(SimpleUploadedFile(filename, stream.getvalue()), with_customer=True)
        self.assertEqual(wh.pk, self.wh.pk)
        self.assertEqual(lines[0]['product_id'], self.game.pk)
        self.assertIsNone(customer)
        self.assertEqual(Sale.objects.count(), 0)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 3)

    def test_each_document_reads_current_stock_price_and_matches_web_generator(self):
        _, first = wholesale_document(self.access, self.wh.pk)
        self.stock.quantity = 7
        self.stock.save()
        self.game.wholesale_price = 123
        self.game.save()
        _, second = wholesale_document(self.access, self.wh.pk)
        web = generate_wholesale_price_xlsx(warehouse_id=self.wh.pk, actor=self.user)
        values = lambda data: list(load_workbook(BytesIO(data)).worksheets[0].values)
        self.assertNotEqual(values(first), values(second))
        self.assertEqual(values(second), values(web))
        self.stock.quantity = 0
        self.stock.save()
        _, third = wholesale_document(self.access, self.wh.pk)
        self.assertNotIn(self.game.name, str(values(third)))

    def test_document_size_and_generation_failure(self):
        with override_settings(TELEGRAM_STAFF_MAX_DOCUMENT_BYTES=1), self.assertRaises(ValidationError):
            wholesale_document(self.access, self.wh.pk)
        self.request()
        job = claim_job(self.bot.pk)
        with patch('telegram_bots.jobs.wholesale_document', side_effect=ValueError('sensitive internal detail')):
            run_job(job, FakeClient())
        job.refresh_from_db()
        self.assertEqual(job.state, 'error')
        self.assertNotIn('sensitive', job.error_category)

    def test_revoked_after_queued_or_while_generating_never_sends(self):
        for during in [False, True]:
            self.bot.cooldown_seconds = 0
            self.bot.save()
            self.access.allowed = True
            self.access.save()
            self.request(10 + int(during))
            job, client = claim_job(self.bot.pk), FakeClient()
            def generated(*_):
                self.access.allowed = False
                self.access.save()
                return 'test.xlsx', b'fake'
            if during:
                with patch('telegram_bots.jobs.wholesale_document', side_effect=generated):
                    run_job(job, client)
            else:
                self.access.allowed = False
                self.access.save()
                run_job(job, client)
            self.assertEqual(client.documents, [])
            self.assertEqual(job.state, 'error')

    def test_uncertain_send_is_not_repeated_and_restart_keeps_unknown_result(self):
        self.request()
        job = claim_job(self.bot.pk)
        client = FakeClient()
        client.error = TelegramError('timeout', uncertain=True)
        run_job(job, client)
        self.assertEqual(job.state, 'uncertain')
        self.assertIsNone(claim_job(self.bot.pk))
        self.assertEqual(len(client.documents), 1)
        job.state = 'sending'
        job.save()
        recover_interrupted(self.bot.pk)
        job.refresh_from_db()
        self.assertEqual(job.state, 'uncertain')

    def test_lease_and_policy_do_not_change_other_workers(self):
        from integrations.worker_runtime import AlreadyRunning
        from integrations.worker_policy import expected_services
        owner = uuid.uuid4()
        lease(self.bot.pk, owner)
        with self.assertRaises(AlreadyRunning):
            lease(self.bot.pk, uuid.uuid4())
        lease(self.bot.pk, owner, release=True)
        self.assertEqual(expected_services()['telegram_staff'], 'unconfigured')
        save_token(FAKE_TOKEN)
        self.assertEqual(expected_services()['telegram_staff'], 'required')
        self.bot.enabled = False
        self.bot.save()
        self.assertEqual(expected_services()['telegram_staff'], 'disabled')

    def test_failed_database_ack_after_delivery_stays_uncertain(self):
        from .jobs import finish_job
        self.request()
        job, client = claim_job(self.bot.pk), FakeClient()
        def fail_ack(job, state, *args, **kwargs):
            if state == 'done':
                job.state = state
                raise RuntimeError('database ack unavailable')
            return finish_job(job, state, *args, **kwargs)
        with patch('telegram_bots.jobs.finish_job', side_effect=fail_ack):
            run_job(job, client)
        self.assertEqual(job.state, 'uncertain')
        run_job(job, client)
        self.assertEqual(len(client.documents), 1)

    def test_skipped_and_archived_products_and_unselected_warehouse_are_not_added(self):
        for name, price, quantity, archived in [('ZeroStock', 10, 0, False), ('NoPrice', None, 3, False), ('Archived', 20, 3, True)]:
            game = CD.objects.create(name=name, platform=self.game.platform, wholesale_price=price, is_archived=archived)
            CDWarehouseStock.objects.create(cd=game, warehouse=self.wh, quantity=quantity)
        elsewhere = Warehouse.objects.create(name='Не выбранный склад')
        game = CD.objects.create(name='OtherWarehouse', platform=self.game.platform, wholesale_price=10)
        CDWarehouseStock.objects.create(cd=game, warehouse=elsewhere, quantity=20)
        _, content = wholesale_document(self.access, self.wh.pk)
        values = str(list(load_workbook(BytesIO(content)).worksheets[0].values))
        for name in ['ZeroStock', 'NoPrice', 'Archived', 'OtherWarehouse']:
            self.assertNotIn(name, values)

    def test_admin_and_self_service_permissions_and_csrf(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('telegram_bots:dashboard')).status_code, 403)
        response = self.client.get(reverse('telegram_bots:connection'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.admin.username)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('telegram_bots:dashboard')).status_code, 200)
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.admin)
        self.assertEqual(strict.post(reverse('telegram_bots:dashboard'), {'action': 'revoke', 'user_id': self.user.pk}).status_code, 403)

    def test_saving_token_does_not_call_api_and_never_echoes_token(self):
        self.client.force_login(self.admin)
        with patch('telegram_bots.client.requests.Session.post') as request:
            response = self.client.post(reverse('telegram_bots:dashboard'), {'action': 'save', 'name': 'Staff',
                'username': 'StaffTestBot', 'enabled': '', 'cooldown_seconds': 30, 'token': FAKE_TOKEN})
            self.assertEqual(response.status_code, 302)
            request.assert_not_called()
        response = self.client.get(reverse('telegram_bots:dashboard'))
        self.assertNotContains(response, FAKE_TOKEN)
        self.assertEqual(read_token(), FAKE_TOKEN)

    @override_settings(GAMEBAT_ENV='local_test')
    def test_local_test_denies_every_external_entrypoint_and_reads_no_secret(self):
        self.client.force_login(self.admin)
        with patch('telegram_bots.configuration.Path.read_text', side_effect=AssertionError('secret read')), \
                patch('telegram_bots.client.requests.Session.post') as network, \
                patch.dict('os.environ', {'GAMEBAT_TELEGRAM_STAFF_BOT_TOKEN': FAKE_TOKEN}):
            self.assertFalse(token_configured())
            self.assertEqual(expected_status(), 'disabled')
            for action in ['save', 'check', 'allow', 'revoke']:
                response = self.client.post(reverse('telegram_bots:dashboard'), {'action': action, 'token': FAKE_TOKEN})
                self.assertContains(response, 'Тестовый режим. Взаимодействие с Telegram отключено.')
            for operation in [lambda: TelegramClient(FAKE_TOKEN), read_token,
                              lambda: save_token(FAKE_TOKEN), lambda: run_polling(self.bot.pk, uuid.uuid4(), threading.Event())]:
                with self.assertRaises(ValidationError):
                    operation()
            out = StringIO()
            call_command('run_telegram_staff_bot', once=True, stdout=out)
            self.assertIn('Тестовый режим', out.getvalue())
            network.assert_not_called()
        self.assertEqual(StaffBotJob.objects.count(), 0)


@override_settings(GAMEBAT_ENV='local_live')
class TelegramTransportTests(SimpleTestCase):
    def test_http_requests_are_fixed_origin_and_do_not_retry_uncertain_send(self):
        session = Mock()
        session.post.side_effect = requests.Timeout('secret URL must not leak')
        client = TelegramClient(FAKE_TOKEN, session)
        with self.assertRaises(TelegramError) as caught:
            client.document(101, 'test.xlsx', b'fake')
        self.assertTrue(caught.exception.uncertain)
        self.assertNotIn('secret', str(caught.exception))
        session.post.assert_called_once()
        self.assertFalse(session.post.call_args.kwargs['allow_redirects'])

    def test_api_categories_invalid_json_and_redirect_are_sanitized(self):
        for code, category in [(401, 'unauthorized'), (403, 'forbidden'), (409, 'conflict'), (429, 'rate_limited'), (500, 'refused')]:
            session = Mock()
            session.post.return_value.status_code = code
            session.post.return_value.json.return_value = {'ok': False, 'error_code': code, 'description': FAKE_TOKEN}
            with self.assertRaises(TelegramError) as caught:
                TelegramClient(FAKE_TOKEN, session).call('getMe')
            self.assertEqual(caught.exception.category, category)
            self.assertNotIn(FAKE_TOKEN, str(caught.exception))
        with self.assertRaises(ValueError):
            TelegramClient(FAKE_TOKEN).call('deleteWebhook')
