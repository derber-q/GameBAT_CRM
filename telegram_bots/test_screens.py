"""Переходы одного меню проверяются без настоящего Telegram и рабочих данных."""
import json
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, TestCase

from .client import TelegramClient, TelegramError
from .menu import WHOLESALE, DIGITAL, SUPPLIER_TEMPLATES, main_menu
from .worker import dispatch_reply


class InlineMenuTests(SimpleTestCase):
    def test_menu_removes_legacy_keyboard_and_deletes_only_its_helper(self):
        client = Mock()
        client.message.return_value = {'message_id': 77}
        markup = {'inline_keyboard': [[{'text':'Меню', 'callback_data':'menu'}]]}
        dispatch_reply(client, {'chat_id':101, 'text':'Меню', 'screen':True,
                               'remove_reply_keyboard':True, 'reply_markup':markup})
        client.message.assert_called_once_with(101, 'Открываю меню…', {'remove_keyboard':True})
        client.menu_photo.assert_called_once_with(101, 'Меню', markup)
        client.call.assert_called_once_with('deleteMessage', {'chat_id':101, 'message_id':77})

    def test_cleanup_error_does_not_send_another_menu(self):
        client = Mock()
        client.message.return_value = {'message_id':77}
        client.call.side_effect = TelegramError('network')
        dispatch_reply(client, {'chat_id':101, 'text':'Меню', 'screen':True,
                               'remove_reply_keyboard':True})
        client.menu_photo.assert_called_once()

    def test_banner_sends_inline_buttons_with_photo_in_one_request(self):
        session = Mock()
        session.post.return_value.status_code = 200
        session.post.return_value.json.return_value = {'ok': True, 'result': {'message_id': 77}}
        client = TelegramClient('synthetic-token', session)
        markup = {'inline_keyboard': [[{'text': 'Меню', 'callback_data': 'menu'}]]}
        result = client.menu_photo(101, 'ReSOURCE', markup)
        first = session.post.call_args_list[0]
        self.assertTrue(first.args[0].endswith('/sendPhoto'))
        self.assertEqual(json.loads(first.kwargs['data']['reply_markup']), markup)
        self.assertTrue(first.kwargs['files']['photo'][1].startswith(b'\x89PNG\r\n\x1a\n'))
        session.post.assert_called_once()
        self.assertEqual(result['message_id'], 77)

    def test_caption_and_keyboard_noop_are_successful_without_an_extra_message(self):
        for method in ('editMessageCaption', 'editMessageReplyMarkup'):
            session = Mock()
            session.post.return_value.status_code = 400
            session.post.return_value.json.return_value = {
                'ok': False, 'error_code': 400, 'description': 'Bad Request: message is not modified'}
            result = TelegramClient('synthetic-token', session).call(method, {'message_id': 77})
            self.assertEqual(result, {'message_id': 77})
            session.post.assert_called_once()

    def test_main_menu_uses_callbacks_and_hides_unavailable_functions(self):
        user = Mock()
        user.has_perms.side_effect = lambda permissions: permissions == WHOLESALE.permissions
        with patch('digital_prices.services.ready', return_value=False):
            menu = main_menu(user)
        self.assertNotIn('keyboard', menu)
        self.assertEqual([button['callback_data'] for row in menu['inline_keyboard']
                          for button in row], [WHOLESALE.code])

    def test_first_screen_sends_banner(self):
        client = Mock()
        markup = {'inline_keyboard': [[{'text': 'Прайс', 'callback_data': WHOLESALE.code}]]}
        dispatch_reply(client, {'chat_id': 101, 'text': 'ReSOURCE',
                               'reply_markup': markup, 'screen': True})
        client.menu_photo.assert_called_once_with(101, 'ReSOURCE', markup)
        client.message.assert_not_called()

    def test_photo_callback_edits_caption_and_buttons_in_place(self):
        client = Mock()
        markup = {'inline_keyboard': [[{'text': 'Назад', 'callback_data': 'menu'}]]}
        dispatch_reply(client, {'chat_id': 101, 'text': 'Выберите склад:',
            'reply_markup': markup, 'callback_id': 'cb', 'screen': True,
            'message_id': 42, 'message_has_photo': True})
        self.assertEqual(client.call.call_args_list[0].args,
                         ('answerCallbackQuery', {'callback_query_id': 'cb'}))
        client.call.assert_any_call('editMessageCaption', {
            'chat_id': 101, 'message_id': 42, 'caption': 'Выберите склад:', 'reply_markup': markup})
        client.message.assert_not_called()
        client.menu_photo.assert_not_called()

    def test_legacy_text_callback_edits_text_without_repeating_action(self):
        client = Mock()
        markup = {'inline_keyboard': [[{'text': 'Назад', 'callback_data': 'menu'}]]}
        dispatch_reply(client, {'chat_id': 101, 'text': 'Готово', 'reply_markup': markup,
            'screen': True, 'message_id': 42, 'message_has_photo': False})
        client.call.assert_called_once_with('editMessageText', {
            'chat_id': 101, 'message_id': 42, 'text': 'Готово', 'reply_markup': markup})
        client.message.assert_not_called()

    def test_long_card_is_not_truncated_to_photo_caption_limit(self):
        client = Mock()
        text = 'Подробная карточка\n' + 'Товар и его стоимость\n' * 80
        markup = {'inline_keyboard': [[{'text': 'Подтвердить', 'callback_data': 'dg:1:2:confirm'}]]}
        dispatch_reply(client, {'chat_id': 101, 'text': text, 'reply_markup': markup,
            'screen': True, 'message_id': 42, 'message_has_photo': True})
        client.message.assert_called_once_with(101, text, markup)
        client.call.assert_called_once_with('editMessageCaption', {
            'chat_id': 101, 'message_id': 42, 'caption': 'Подробная карточка открыта ниже.',
            'reply_markup': {'inline_keyboard': []}})

    def test_missing_screen_is_recreated_but_network_failure_is_not_retried(self):
        for category in ('message_missing', 'network'):
            with self.subTest(category=category):
                client = Mock()
                client.call.side_effect = TelegramError(category)
                reply = {'chat_id': 101, 'text': 'Меню', 'reply_markup': {'inline_keyboard': []},
                         'screen': True, 'message_id': 42, 'message_has_photo': True}
                if category == 'network':
                    with self.assertRaises(TelegramError):
                        dispatch_reply(client, reply)
                    client.menu_photo.assert_not_called()
                else:
                    dispatch_reply(client, reply)
                    client.menu_photo.assert_called_once()


class ScreenNavigationTests(TestCase):
    def setUp(self):
        from accounts.models import User
        from .models import StaffBot, StaffBotAccess
        self.user = User.objects.create_superuser('inline-menu-owner')
        self.bot = StaffBot.objects.create(enabled=True, cooldown_seconds=0)
        self.access = StaffBotAccess.objects.create(bot=self.bot, user=self.user,
            allowed=True, telegram_user_id=101)

    def press(self, number, data):
        from .handlers import accept_update
        return accept_update(self.bot.pk, {'update_id': number, 'callback_query': {
            'id': f'cb-{number}', 'from': {'id': 101}, 'data': data,
            'message': {'message_id': 42, 'chat': {'id': 101, 'type': 'private'},
                        'photo': [{'file_id': 'synthetic-logo'}]}}})

    def test_menu_and_supplier_navigation_keep_the_same_photo_message(self):
        from partners.models import Supplier
        Supplier.objects.create(name='Поставщик меню', letter='A')
        for number, data in enumerate(('menu', SUPPLIER_TEMPLATES.code, 'menu'), 1):
            reply = self.press(number, data)
            self.assertTrue(reply['screen'])
            self.assertEqual(reply['message_id'], 42)
            self.assertTrue(reply['message_has_photo'])
            if data == SUPPLIER_TEMPLATES.code:
                self.assertIn('Выберите поставщика', reply['text'])

    def test_digital_root_callback_opens_list_and_clears_only_pending_text_input(self):
        from digital_sales.models import Supplier, DigitalOrder, StaffConversation
        from django.utils import timezone
        from datetime import timedelta
        supplier = Supplier.objects.create(name='Поставщик цифрового теста')
        order = DigitalOrder.objects.create(supplier=supplier, state='ready')
        StaffConversation.objects.create(access=self.access, order=order, revision=order.revision,
            field='price', expires_at=timezone.now()+timedelta(minutes=10))
        reply = self.press(1, DIGITAL.code)
        self.assertIn('Цифровые заказы', reply['text'])
        self.assertIn(f'dg:{order.pk}:{order.revision}:open', str(reply['reply_markup']))
        self.assertIn('menu', str(reply['reply_markup']))
        self.assertFalse(StaffConversation.objects.exists())
        self.assertEqual(DigitalOrder.objects.get(pk=order.pk).state, 'ready')

    def test_revoked_access_cannot_open_an_old_button(self):
        self.access.allowed = False
        self.access.save(update_fields=['allowed'])
        reply = self.press(1, SUPPLIER_TEMPLATES.code)
        self.assertIn('Доступ закрыт', reply['text'])
        self.assertNotIn('Выберите поставщика', reply['text'])

    def test_invalid_callback_data_does_not_crash_dispatch(self):
        reply = self.press(1, ['untrusted', 'data'])
        self.assertIn('Откройте /menu', reply['text'])

