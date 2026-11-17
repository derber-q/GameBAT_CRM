from decimal import Decimal
from django.core.exceptions import ValidationError, ImproperlyConfigured
from django.test import SimpleTestCase
from cryptography.fernet import Fernet
from unittest.mock import patch
from .parser import parse, money
from .crypto import encrypt, decrypt


def checklist(rows=None, total='844', balance='11677'):
    rows = rows or '● Synthetic Game · 844 руб | #6099'
    return f'✅🧾 Чек-лист заказа 🇷🇺 | 05.11\n{rows}\n📊 Статус: ✅ Выполнено\n💳 Оплата: ✅ Получена\n💵 Итого: {total} руб | 💰Баланс: {balance} руб'


class ParserTests(SimpleTestCase):
    def test_completed_goods_can_be_purchased_on_credit(self):
        result = parse(checklist(balance='-100').replace('Оплата: ✅ Получена', 'Оплата: ⏳ Ожидается'))
        self.assertEqual(result['issues'], [])
        self.assertFalse(result['payment_received'])
        self.assertEqual(result['balance'], '-100.00')

    def test_signed_supplier_balance_in_snapshot_and_checklist(self):
        for balance, expected in [('-1 250,50', '-1250.50'), ('− 20', '-20.00'), ('+15', '15.00')]:
            with self.subTest(balance=balance):
                self.assertEqual(parse('Баланс: ' + balance + ' руб')['balance'], expected)
                result = parse(checklist(balance=balance))
                self.assertEqual(result['balance'], expected)
                self.assertEqual(result['issues'], [])

    def test_single_and_multiple_and_missing_individual_number(self):
        one = parse(checklist())
        self.assertEqual(one['numbers'], ['6099'])
        self.assertEqual(one['issues'], [])
        rows = '● Test A · 2317 руб | #6126\n● Test B · 418 руб | #6127\n● Test C · 2923 руб | #6128'
        three = parse(checklist(rows, '5658', '5939'))
        self.assertEqual(len(three['items']), 3)
        self.assertEqual(three['issues'], [])
        no_number = parse(checklist('● Account · 45 руб\n● Subscription · 4617 руб | #6139', '4662'))
        self.assertEqual(len(no_number['items']), 2)
        self.assertEqual(no_number['numbers'], ['6139'])

    def test_matching_totals_and_completed_status_are_required(self):
        for text in [checklist(total='845'), checklist().replace('Выполнено', 'Создано'),
                     'Чек-лист заказа']:
            self.assertTrue(parse(text)['issues'])

    def test_ready_group_and_free_chat(self):
        self.assertEqual(parse('✅ Ваш заказ #6128+2 ✅\nДанные ниже')['group_count'], 3)
        self.assertEqual(parse('Ваш заказ #6099 готов!')['numbers'], ['6099'])
        self.assertEqual(parse('💰 Баланс: 12 521 руб')['balance'], '12521.00')
        for value in ['Добрый вечер', 'Можно купить за 500 руб?', 'Попробуем возврат', 'x' * 40000]:
            self.assertIsNone(parse(value))

    def test_quoted_checklist_does_not_shadow_actual_ready_message(self):
        value = '> ✅🧾 Чек-лист заказа · старое сообщение #6099\n✅ Ваш заказ #6099 готов! ✅'
        self.assertEqual(parse(value)['kind'], 'goods')

    def test_money_no_float_rounding_or_nonfinite(self):
        self.assertEqual(money('1 001,20'), Decimal('1001.20'))
        for value in ['NaN', 'Infinity', '0.001', '1e19']:
            with self.assertRaises(ValidationError):
                money(value)

    def test_encryption_fails_closed_and_preserves_original(self):
        with patch('digital_sales.crypto.cipher', return_value=Fernet(Fernet.generate_key())):
            value = {'text': 'synthetic-password\nzero: 00042'}
            encrypted = encrypt(value)
            self.assertNotIn('synthetic-password', encrypted)
            self.assertEqual(decrypt(encrypted), value)
        with patch('digital_sales.crypto.cipher', return_value=Fernet(Fernet.generate_key())):
            with self.assertRaises(ImproperlyConfigured):
                decrypt(encrypted)
