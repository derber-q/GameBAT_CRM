"""Квитанции пополнения: подтверждение, порядок сообщений и защита от повторного зачисления."""
from decimal import Decimal
from unittest.mock import patch
from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, SimpleTestCase
from django.utils import timezone
from .parser import parse
from .ingestion import accept_update
from .models import DigitalBot, Supplier, BalanceObservation, BalanceMovement, DigitalOrder
from .reconciliation import remaining_topup, apply_topup, card, receipt_details
from .services import move_balance


def receipt(amount='244', balance='11662'):
    return (f'💳 Пополнение баланса\n\n🏪 ОПТ: Test\n🆔 ID: 379855109\n💰 Сумма: {amount} руб\n'
            f'📊 Новый баланс: {balance} руб\n🕒 13.11.2026 10:56:57')


class ReceiptParserTests(SimpleTestCase):
    def test_provider_receipt_has_separate_amount_and_new_balance(self):
        parsed = parse(receipt())
        self.assertEqual(parsed['kind'], 'balance')
        self.assertEqual(parsed['topup_amount'], '244.00')
        self.assertEqual(parsed['balance'], '11662.00')
        self.assertEqual(parsed['topup_issues'], [])

    def test_new_balance_has_priority_over_previous_balance(self):
        parsed = parse('Баланс: 100 руб\n' + receipt('244','344'))
        self.assertEqual(parsed['balance'], '344.00')

    def test_pending_negative_ambiguous_or_missing_balance_cannot_be_confirmed(self):
        for text in (receipt()+'\nСтатус: ожидается', receipt('-244'), receipt().replace('Новый баланс:', 'Остаток:'),
                     receipt()+'\nСумма: 300 руб', receipt('999999999999999999999')):
            with self.subTest(text=text):
                self.assertTrue(parse(text)['topup_issues'])

    def test_request_to_pay_and_price_publication_are_not_topup_receipts(self):
        for text in ('Пополните баланс на 244 руб', 'Как пополнить баланс? Сумма: 244 руб',
                     'Пришлите реквизиты для пополнения счета', 'Прайс: Сумма: 244 руб'):
            result = parse(text)
            self.assertFalse(result and result.get('topup_receipt'))


class ReceiptAccountingTests(TestCase):
    def test_pending_receipt_is_reminded_after_each_interaction_until_confirmation(self):
        from telegram_bots.models import StaffBot,StaffBotAccess
        from .models import Notification
        from .reconciliation import remind_pending_topups
        from .notifications import notification_allowed
        bot=StaffBot.objects.create(enabled=True)
        access=StaffBotAccess.objects.create(bot=bot,user=self.owner,allowed=True,telegram_user_id=123)
        self.ingest('Баланс: 11418 руб')
        observation=self.ingest(receipt())
        before=self.supplier.balance
        self.assertEqual(remind_pending_topups(bot_id=bot.pk,chat_id=123,update_id=100),1)
        self.assertEqual(remind_pending_topups(bot_id=bot.pk,chat_id=123,update_id=100),0)
        self.assertEqual(remind_pending_topups(bot_id=bot.pk,chat_id=123,update_id=101),1)
        notices=Notification.objects.filter(access=access,event_key__contains=':reminder:')
        self.assertEqual(notices.filter(state='queued').count(),1)
        self.assertEqual(self.supplier.balance,before)
        current=notices.get(state='queued')
        self.assertTrue(notification_allowed(current))
        apply_topup(actor=self.owner,observation_id=observation.pk,displayed_amount='244')
        self.assertFalse(notification_allowed(current))
        self.assertEqual(remind_pending_topups(bot_id=bot.pk,chat_id=123,update_id=102),0)

    def setUp(self):
        self.cipher = patch('digital_sales.crypto.cipher',return_value=Fernet(Fernet.generate_key()))
        self.cipher.start()
        self.addCleanup(self.cipher.stop)
        self.owner = get_user_model().objects.create_superuser('receipt-owner')
        self.bot = DigitalBot.objects.create(enabled=True)
        self.supplier = Supplier.objects.create(name='Test',chat_ids=[-123],sender_ids=[55])
        self.sequence = 0

    def ingest(self, text, **extra):
        self.sequence += 1
        message = {'message_id':self.sequence, 'date':int(timezone.now().timestamp())+self.sequence,
            'chat':{'id':-123,'type':'group'},'from':{'id':55,'is_bot':True},'text':text,**extra}
        accept_update({'update_id':self.sequence,'message':message})
        return BalanceObservation.objects.order_by('-pk').first()

    def test_detect_and_notify_but_credit_only_after_confirmation(self):
        self.ingest('Баланс: 11418 руб')
        with patch('digital_sales.reconciliation.enqueue_observation') as enqueue:
            observation = self.ingest(receipt())
        enqueue.assert_called_once()
        self.assertEqual(self.supplier.balance, Decimal('11418'))
        self.assertFalse(DigitalOrder.objects.exists())
        self.assertIn('Подтвердить пополнение',card(observation)['reply_markup']['inline_keyboard'][0][0]['text'])
        movement = apply_topup(actor=self.owner,observation_id=observation.pk,displayed_amount='244')
        again = apply_topup(actor=self.owner,observation_id=observation.pk,displayed_amount='244')
        self.assertEqual(movement.pk,again.pk)
        self.assertEqual(self.supplier.balance,Decimal('11662'))
        self.assertEqual(BalanceMovement.objects.filter(kind='topup').count(),1)

    def test_first_receipt_never_sets_opening_balance_or_credits_itself(self):
        observation = self.ingest(receipt('244','244'))
        self.assertFalse(BalanceMovement.objects.exists())
        apply_topup(actor=self.owner,observation_id=observation.pk,displayed_amount='244')
        self.assertEqual(self.supplier.balance,Decimal('244'))

    def test_two_receipts_can_be_confirmed_in_reverse_order(self):
        self.ingest('Баланс: 100 руб')
        first = self.ingest(receipt('200','300'))
        second = self.ingest(receipt('500','800'))
        apply_topup(actor=self.owner,observation_id=second.pk,displayed_amount='500')
        self.assertEqual(remaining_topup(first),Decimal('200'))
        apply_topup(actor=self.owner,observation_id=first.pk,displayed_amount='200')
        self.assertEqual(self.supplier.balance,Decimal('800'))

    def test_manual_credit_cannot_be_credited_again_after_a_later_receipt(self):
        self.ingest('Баланс: 100 руб')
        first = self.ingest(receipt('200','300'))
        move_balance(actor=self.owner,supplier_id=self.supplier.pk,amount='200',kind='topup',reason='Внесено вручную')
        second = self.ingest(receipt('500','800'))
        with self.assertRaises(ValidationError):
            remaining_topup(first)
        apply_topup(actor=self.owner,observation_id=second.pk,displayed_amount='500')
        self.assertEqual(self.supplier.balance,Decimal('800'))

    def test_wrong_displayed_amount_and_supplier_edits_do_not_credit(self):
        self.ingest('Баланс: 100 руб')
        observation = self.ingest(receipt('200','300'))
        with self.assertRaises(ValidationError):
            apply_topup(actor=self.owner,observation_id=observation.pk,displayed_amount='201')
        # Тот же Telegram message_id, новая версия и изменённая сумма.
        changed = self.ingest(receipt('250','350'),message_id=observation.message.message_id,
                             edit_date=int(timezone.now().timestamp())+100)
        with self.assertRaises(ValidationError):
            apply_topup(actor=self.owner,observation_id=observation.pk,displayed_amount='200')
        self.assertEqual(remaining_topup(changed),Decimal('250'))
        self.assertFalse(BalanceMovement.objects.filter(kind='topup').exists())

    def test_receipt_parsed_as_balance_before_upgrade_is_detected_without_reimport(self):
        self.ingest('Баланс: 11418 руб')
        observation = self.ingest(receipt())
        message = observation.message
        message.parsed = {'kind':'balance','balance':'11662.00','numbers':[]}
        message.save(update_fields=['parsed'])
        observation.refresh_from_db()
        self.assertEqual(receipt_details(observation)['topup_amount'],'244.00')
        self.assertEqual(remaining_topup(observation),Decimal('244'))
