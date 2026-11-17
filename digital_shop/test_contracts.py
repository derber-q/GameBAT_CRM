"""Контракты для будущего запуска. Все секреты синтетические, транспорт подменён."""
from decimal import Decimal
from datetime import datetime, timedelta, timezone
import uuid
from types import SimpleNamespace
from unittest.mock import Mock, patch
import json
import requests
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from digital_prices.api import APIError
from digital_prices.provider import ProviderClient, wire, slot, block
from digital_prices.models import ProviderGate
from .public import checked, title, result_dto
from .services import parse_credentials, allocated, quote_expiration


class PublicBoundaryTests(SimpleTestCase):
    def test_manual_data_is_one_message_and_keeps_original_for_executor(self):
        groups = [{'id': 'aFresh', 'fields': ['manual_credentials']}]
        text = 'Логин: synthetic@example.invalid\nПароль: fake-password\nДополнительно: резервные коды позже'
        result = parse_credentials(text, groups)['aFresh']
        self.assertEqual(result['login'], 'synthetic@example.invalid')
        self.assertEqual(result['password'], 'fake-password')
        self.assertEqual(result['additional_data'], text)
        self.assertEqual(parse_credentials('synthetic@example.invalid fake-password', groups)['aFresh']['password'], 'fake-password')
        self.assertEqual(parse_credentials('login=example\npassword=  keep spaces  ', groups)['aFresh']['password'], '  keep spaces  ')
        with self.assertRaises(ValidationError):
            parse_credentials('Только произвольное примечание без реквизитов', groups)

    def test_manual_messages_never_mix_two_service_accounts(self):
        groups = [{'id': 'aFresh', 'fields': ['manual_credentials']}, {'id': 'aOther', 'fields': ['manual_credentials']}]
        data = parse_credentials('[1]\nЛогин: one\nПароль: first\n[2]\nЛогин: two\nПароль: second', groups)
        self.assertEqual(data['aFresh']['login'], 'one')
        self.assertEqual(data['aOther']['password'], 'second')
        with self.assertRaises(ValidationError):
            parse_credentials('one\nfirst', groups)

    def test_cart_has_only_per_position_removal_without_quantity_controls(self):
        from .telegram import cart_view
        line = SimpleNamespace(pk=17, quantity=1, parameters={}, product=SimpleNamespace())
        cart = SimpleNamespace(pk=uuid.uuid4(), revision=2, buyer_id=1, lines=Mock())
        cart.lines.select_related.return_value.order_by.return_value = [line]
        with patch('digital_shop.telegram.caption', return_value='Example 120 RUB'), patch('digital_shop.telegram.show') as show:
            cart_view(Mock(), cart)
        keys = [b for row in show.call_args.args[3] for b in row]
        self.assertIn('Удалить позицию 1', [key['text'] for key in keys])
        actions = [key['callback_data'].split(':')[3] for key in keys]
        self.assertEqual(actions, ['x', 'q', 'h'])

    def test_quote_expiration_accepts_fractional_json_seconds_without_float(self):
        now = datetime(2026, 11, 14, 10, tzinfo=timezone.utc)
        seconds = int(now.timestamp()) + 240
        self.assertEqual(quote_expiration(Decimal(seconds) + Decimal('.123456'), now=now),
            now + timedelta(seconds=240, microseconds=123456))
        self.assertEqual(quote_expiration(seconds, now=now), now + timedelta(seconds=240))
        for value in (True, float(seconds), str(seconds), Decimal('NaN'), Decimal('Infinity'),
                      -1, 0, seconds - 240, seconds + 121, 253402300799):
            with self.subTest(value=value), self.assertRaises(APIError):
                quote_expiration(value, now=now)

    def test_numbered_credentials_keep_separate_service_values(self):
        groups = [{'id': 'aFirst', 'fields': ['login', 'password']},
                  {'id': 'aSecond', 'fields': ['login', 'password']}]
        values = parse_credentials('[1] Услуга 1\nlogin=first\npassword= one \n'
                                   '[2] Услуга 2\nlogin=second\npassword= two ', groups)
        self.assertEqual(values, {'aFirst': {'login': 'first', 'password': ' one '},
                                 'aSecond': {'login': 'second', 'password': ' two '}})

    def test_shop_command_sends_menu_below_and_retires_old_keyboard(self):
        from .telegram import show
        cart = SimpleNamespace(chat_id=-100, buyer_id=1, telegram_user_id=2, menu_message_id=10, save=Mock())
        client = Mock()
        client.call.side_effect = [{'message_id': 20}, True]
        with patch('digital_shop.telegram.binding'):
            show(client, cart, 'Магазин GameBAT', [], new_message=True)
        self.assertEqual(client.call.call_args_list[0].args[0], 'sendMessage')
        self.assertEqual(client.call.call_args_list[1].args, ('editMessageReplyMarkup',
            {'chat_id': -100, 'message_id': 10, 'reply_markup': {'inline_keyboard': []}}))
        self.assertEqual(cart.menu_message_id, 20)

    def test_menu_navigation_edits_the_current_message(self):
        from .telegram import show
        cart = SimpleNamespace(chat_id=-100, buyer_id=1, telegram_user_id=2, menu_message_id=20, save=Mock())
        client = Mock()
        client.call.return_value = {'message_id': 20}
        with patch('digital_shop.telegram.binding'):
            show(client, cart, 'Корзина', [])
        self.assertEqual(client.call.call_count, 1)
        self.assertEqual(client.call.call_args.args[0], 'editMessageText')
        self.assertEqual(client.call.call_args.args[1]['message_id'], 20)

    def test_compact_callback_fits_account_selection(self):
        from .telegram import button
        cart = SimpleNamespace(pk=uuid.uuid4(), revision=123)
        value = button(cart, 'На тот же аккаунт', 'a', '12345.existing.a1234567890')['callback_data']
        self.assertLessEqual(len(value.encode()), 64)

    def test_private_titles_are_replaced_whole(self):
        for value in ('PanYanStore 991.23', 'PAN-YAN-STORE 991.23', 'Пан Ян 991.23',
                      'Закупка 991.23', 'Себестоимость 991.23', 'наценка 991.23',
                      'https://private.invalid/991.23', 'pv2_99123', 'ov2_99123', 'qv2_99123'):
            with self.subTest(value=value):
                self.assertEqual(title(value), 'Цифровой товар')
                self.assertNotIn('991', title(value))
                with self.assertRaises(ValidationError):
                    checked(value)

    def test_codes_are_not_modified_or_replaced(self):
        result = result_dto({'codes': ['A0-B2-C3', '0000-ZYX']}, name='Игра', quantity=2, completed=True).text()
        self.assertIn('A0-B2-C3', result)
        self.assertIn('0000-ZYX', result)
        for codes in ([], ['ONE'], ['ONE', 'TWO', 'THREE'], ['ONE', 'https://private.invalid'], ['ONE', 'Cost: 5']):
            with self.subTest(codes=codes), self.assertRaises(ValidationError):
                result_dto({'codes': codes}, name='Игра', quantity=2, completed=True)

    def test_arbitrary_result_text_is_never_forwarded(self):
        for value in ('PanYanStore: цена 900', 'Поставщик 900', 'Цена: 900',
                      'Готово https://private.invalid', 'Добро пожаловать, менеджер @supplier',
                      'login: a\npassword: b\nСебестоимость: 100'):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                result_dto({'data': value}, name='Игра', quantity=1, completed=True)
        text = result_dto({'data': 'login: a@example.invalid\npassword:  keep spaces '}, name='Игра', quantity=1, completed=True).text()
        self.assertIn('  keep spaces ', text)
        self.assertIn('a@example.invalid', text)

    def test_completion_is_a_typed_confirmation_not_free_text(self):
        self.assertIn('выполнен', result_dto({'completed': True}, name='Steam', quantity=1, completed=True).text())
        for value in ({'completed': False}, {'completed': True, 'cost': 5}, {}, {'data': {'password': 'x'}}):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                result_dto(value, name='Steam', quantity=1, completed=True)

    def test_decimal_wire_and_cent_distribution(self):
        self.assertEqual(wire({'amount': Decimal('123.45')}), '{"amount":123.45}')
        self.assertEqual(json.loads(wire({'amount': Decimal('123.45')}), parse_float=Decimal)['amount'], Decimal('123.45'))
        for total, weights in [('1.01', ['1', '1', '1']), ('0', ['0', '0']), ('0.01', ['0', '0']), ('100000.01', ['1000', '500'])]:
            with self.subTest(total=total):
                values = allocated(Decimal(total), [Decimal(w) for w in weights])
                self.assertEqual(sum(values), Decimal(total))
                self.assertTrue(all(v >= 0 and v == v.quantize(Decimal('.01')) for v in values))
        with self.assertRaises(APIError):
            wire({'price': 0.1})

    def test_aggregate_credentials_preserve_password_and_separate_accounts(self):
        groups = [{'id': 'a1', 'fields': ['login', 'password']}, {'id': 'a2', 'fields': ['login', 'password']},
                  {'id': 'a3', 'fields': []}]
        values = parse_credentials('[a1]\nlogin=x\npassword=  p  \n[a2]\nlogin=y\npassword=q', groups)
        self.assertEqual(values['a1']['password'], '  p  ')
        self.assertNotEqual(values['a1'], values['a2'])
        for value in ('[a1]\nlogin=x\npassword=p', '[a1]\nlogin=x\npassword=  \n[a2]\nlogin=y\npassword=q',
                      '[a1]\nlogin=x\npassword=p\nOTP=3', '[unknown]\nlogin=x', '[a1]\nlogin=x\nlogin=y'):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                parse_credentials(value, groups)

    def test_text_account_and_delivery_are_not_credentials(self):
        groups = [{'id': 'a1', 'fields': ['data']}, {'id': 'd1', 'fields': ['friend_link']}]
        values = parse_credentials('[a1]\ndata=Сведения для оформления\n[d1]\nfriend_link=https://s.team/p/abc-def/Abc123', groups)
        self.assertEqual(set(values['a1']), {'data'})
        self.assertEqual(set(values['d1']), {'friend_link'})
        with self.assertRaises(ValidationError):
            parse_credentials('[a1]\ndata=x\n[d1]\nfriend_link=https://other.invalid', groups)


class AdapterTests(SimpleTestCase):
    def setUp(self):
        self.enterContext(patch('digital_prices.provider.require_live_operation'))
        self.enterContext(patch('digital_prices.provider.slot', return_value=0))
        self.gate = self.enterContext(patch('digital_prices.provider.block'))
        self.session = Mock()
        self.response = Mock(status_code=200, content=b'{}', headers={})
        self.response.json.return_value = {'ok': True}
        self.session.request.return_value = self.response
        self.client = ProviderClient('synthetic-key', session=self.session)

    def test_exact_documented_v2_endpoints(self):
        calls = [(lambda: self.client.balance(), 'GET', 'balance'),
                 (lambda: self.client.products(2), 'GET', 'products'),
                 (lambda: self.client.search('Game'), 'GET', 'products/search'),
                 (lambda: self.client.product('pv2_fake'), 'GET', 'products/pv2_fake'),
                 (lambda: self.client.steam_check('fake_login'), 'GET', 'steam-check'),
                 (lambda: self.client.quote({'accounts': [], 'items': []}), 'POST', 'quotes'),
                 (lambda: self.client.orders(client_order_id='gb-fake'), 'GET', 'orders'),
                 (lambda: self.client.order('ov2_fake'), 'GET', 'orders/ov2_fake'),
                 (lambda: self.client.replace_account('ov2_fake', 'account1', {'login': 'x', 'password': ' p '}), 'PUT', 'orders/ov2_fake/accounts/account1')]
        for call, method, suffix in calls:
            with self.subTest(suffix=suffix):
                call()
                args = self.session.request.call_args.args
                self.assertEqual(args, (method, 'https://yanstore.ru/api/external/v2/' + suffix))
                self.assertFalse(self.session.request.call_args.kwargs['allow_redirects'])
                self.assertNotIn('password', str(self.session.request.call_args.kwargs.get('params')))

    def test_business_and_http_errors_are_sanitized_and_429_is_shared(self):
        for status, payload, category in [(200, {'ok': False, 'error': 'price_changed'}, 'price_changed'),
                (200, {'ok': False, 'error': 'raw-secret'}, 'request_rejected'),
                (401, {}, 'authentication'), (403, {}, 'authentication'), (404, {}, 'not_found'),
                (422, {'detail': 'private'}, 'request_rejected'), (503, {}, 'upstream'), (429, {}, 'rate_limited')]:
            with self.subTest(status=status, category=category):
                self.response.status_code, self.response.json.return_value = status, payload
                with self.assertRaises(APIError) as caught:
                    self.client.balance()
                self.assertEqual(caught.exception.category, category)
                self.assertNotIn('secret', str(caught.exception))
        self.gate.assert_called()

    def test_no_hidden_retry_after_timeout(self):
        self.session.request.side_effect = requests.Timeout('not-public')
        with self.assertRaises(APIError) as caught:
            self.client.balance()
        self.assertEqual(caught.exception.category, 'network_timeout')
        self.assertEqual(self.session.request.call_count, 1)

    def test_arbitrary_urls_are_refused(self):
        for path in ('https://other.invalid', '../orders', 'products/../../balance', 'v1/codes-catalog'):
            with self.subTest(path=path), self.assertRaises(APIError):
                self.client.request('GET', path)
        self.session.request.assert_not_called()


class SharedQuotaTests(TestCase):
    def test_twenty_slots_are_shared_between_clients_and_process_claims(self):
        for _ in range(20):
            self.assertEqual(slot('urgent'), 0)
        self.assertGreater(slot('urgent'), 0)
        self.assertEqual(len(ProviderGate.objects.get(pk=1).requests_at), 20)

    def test_429_blocks_both_priorities(self):
        block(75)
        self.assertGreater(slot('urgent'), 60)
        self.assertGreater(slot('background'), 60)

    def test_urgent_work_temporarily_yields_catalog(self):
        self.assertEqual(slot('urgent'), 0)
        self.assertGreater(slot('background'), 0)
