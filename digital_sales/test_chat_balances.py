"""Синтетические группы: отдельные сообщения баланса и идемпотентная очередь."""
import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from catalog.models import SystemProduct
from telegram_bots.client import TelegramError
from telegram_bots.models import StaffBot, StaffBotAccess
from .models import Buyer, Supplier, DigitalBot, BuyerBalanceChat, BalanceChatCommand, BalanceChatPublication
from . import services
from .chat_balances import (balance_text, enqueue_balance, ingest_chat_update, process_command,
                            publish_one, recover_publications, retry_publication, unpin_previous_balance)


class ChatBalanceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(username='chat-balances')
        self.owner = uuid.uuid4()
        self.bot = DigitalBot.objects.create(enabled=True, lease_owner=self.owner,
            lease_until=timezone.now() + timedelta(minutes=3))
        self.staff = StaffBot.objects.create(enabled=True)
        StaffBotAccess.objects.create(bot=self.staff, user=self.user, telegram_user_id=44, allowed=True)
        self.buyer = Buyer.objects.create(name='Синтетический покупатель')
        self.supplier = Supplier.objects.create(name='Синтетический поставщик')
        services.move_balance(actor=self.user, buyer_id=self.buyer.pk, kind='opening', amount='1000', reason='Тест')
        self.chat = BuyerBalanceChat.objects.create(chat_id=-100123, title='Синтетическая группа', buyer=self.buyer)
        self.client_api = Mock()
        self.sequence = 100
        def call(method, data):
            if method == 'getChatMember':
                return {'status': 'administrator', 'can_pin_messages': True, 'can_delete_messages': True}
            if method == 'sendMessage':
                self.sequence += 1
                return {'message_id': self.sequence}
            return True
        self.client_api.call.side_effect = call

    def publish(self):
        return publish_one(self.client_api, owner=self.owner, bot_id=999)

    def test_manual_balance_menu_is_inline_and_request_sends_once_without_movements(self):
        from telegram_bots.menu import main_menu, BUYER_BALANCE
        from telegram_bots.handlers import accept_update
        from .models import BalanceMovement
        keyboard=main_menu(self.user)
        self.assertIn([{'text':BUYER_BALANCE.title, 'callback_data': BUYER_BALANCE.code}],keyboard['inline_keyboard'])
        opening={'update_id':801,'message':{'message_id':10,'chat':{'id':44,'type':'private'},
            'from':{'id':44},'text':BUYER_BALANCE.title}}
        reply=accept_update(self.staff.pk,opening)
        self.assertIn('Кому отправить',reply['text'])
        button=reply['reply_markup']['inline_keyboard'][0][0]
        self.assertTrue(button['callback_data'].startswith(f'buyerbalance:send:{self.buyer.pk}:'))
        self.assertLessEqual(len(button['callback_data'].encode()), 64)
        before=list(BalanceMovement.objects.values())
        callback={'update_id':802,'callback_query':{'id':'synthetic','data':button['callback_data'],
            'from':{'id':44},'message':{'message_id':101,'chat':{'id':44,'type':'private'}}}}
        reply=accept_update(self.staff.pk,callback)
        self.assertIn('очередь',reply['text'])
        self.assertIsNone(accept_update(self.staff.pk,callback))
        callback['update_id']=803
        self.assertIn('Повторное сообщение не создано',accept_update(self.staff.pk,callback)['text'])
        self.assertEqual(BalanceChatPublication.objects.count(),1)
        self.assertEqual(before,list(BalanceMovement.objects.values()))
        self.assertTrue(self.publish())
        self.assertEqual([call.args[0] for call in self.client_api.call.call_args_list],['getChatMember','sendMessage'])
        self.assertIn('+1 000,00 ₽',self.client_api.call.call_args.args[1]['text'])

    def test_manual_balance_missing_chat_revoked_access_and_disabled_bot_do_not_queue(self):
        from telegram_bots.access import BotDenied
        from .staff_balances import request_balance, buyers_menu
        access=StaffBotAccess.objects.get(bot=self.staff,user=self.user)
        unbound=Buyer.objects.create(name='Без чата')
        self.assertTrue(any('нет чата' in button['text'] for row in buyers_menu()['reply_markup']['inline_keyboard'] for button in row))
        with self.assertRaises(BotDenied):
            request_balance(access=access,buyer_id=unbound.pk,message_id=1)
        self.bot.enabled=False;self.bot.save(update_fields=['enabled'])
        with self.assertRaises(BotDenied):
            request_balance(access=access,buyer_id=self.buyer.pk,message_id=1)
        self.bot.enabled=True;self.bot.save(update_fields=['enabled'])
        access.allowed=False;access.save(update_fields=['allowed'])
        with self.assertRaises(BotDenied):
            request_balance(access=access,buyer_id=self.buyer.pk,message_id=1)
        self.assertFalse(BalanceChatPublication.objects.exists())

    def test_manual_menu_cannot_be_reused_for_other_buyer_or_bypass_uncertain_delivery(self):
        from telegram_bots.access import BotDenied
        from .staff_balances import request_balance
        access=StaffBotAccess.objects.get(bot=self.staff,user=self.user)
        publication,created=request_balance(access=access,buyer_id=self.buyer.pk,message_id=101)
        self.assertTrue(created)
        other=Buyer.objects.create(name='Другой покупатель')
        BuyerBalanceChat.objects.create(chat_id=-100456,buyer=other)
        with self.assertRaises(BotDenied):
            request_balance(access=access,buyer_id=other.pk,message_id=101)
        publication.state='uncertain';publication.save(update_fields=['state'])
        with self.assertRaises(BotDenied):
            request_balance(access=access,buyer_id=self.buyer.pk,message_id=102)
        self.assertEqual(BalanceChatPublication.objects.count(),1)

    def test_reopened_inline_menu_has_new_delivery_key_on_the_same_message(self):
        from telegram_bots.handlers import accept_update
        from telegram_bots.menu import BUYER_BALANCE
        self.staff.cooldown_seconds = 0
        self.staff.save(update_fields=['cooldown_seconds'])

        def press(number, data):
            return accept_update(self.staff.pk, {'update_id': number, 'callback_query': {
                'id': str(number), 'from': {'id': 44}, 'data': data,
                'message': {'message_id': 101, 'chat': {'id': 44, 'type': 'private'},
                            'photo': [{'file_id': 'synthetic'}]}}})

        first = press(900, BUYER_BALANCE.code)['reply_markup']['inline_keyboard'][0][0]['callback_data']
        press(901, first)
        press(902, first)
        self.assertEqual(BalanceChatPublication.objects.count(), 1)
        second = press(903, BUYER_BALANCE.code)['reply_markup']['inline_keyboard'][0][0]['callback_data']
        self.assertNotEqual(first, second)
        press(904, second)
        self.assertEqual(BalanceChatPublication.objects.count(), 2)

    def test_exact_signed_text_and_new_message_on_every_change_without_pin_or_edit(self):
        at = timezone.now()
        self.assertRegex(balance_text(Decimal('-1250.50'), at), r'^Текущий баланс на \d{2}\.\d{2}\.\d{4} \d{2}:\d{2}: -1 250,50 ₽$')
        self.assertIn('+0,00 ₽', balance_text(Decimal(0), at))
        first = enqueue_balance(self.buyer, event='initial')
        self.assertTrue(self.publish())
        self.chat.refresh_from_db()
        self.assertIsNone(self.chat.message_id)
        first.refresh_from_db()
        self.assertEqual(first.message_id, 101)
        self.assertEqual([c.args[0] for c in self.client_api.call.call_args_list],
                         ['getChatMember', 'sendMessage'])
        self.client_api.reset_mock()
        services.move_balance(actor=self.user, buyer_id=self.buyer.pk, kind='topup', amount='250', reason='Тест')
        self.assertTrue(self.publish())
        self.chat.refresh_from_db()
        self.assertIsNone(self.chat.message_id)
        calls = self.client_api.call.call_args_list
        self.assertEqual([c.args[0] for c in calls], ['getChatMember', 'sendMessage'])
        self.assertIn('+1 250,00 ₽', calls[1].args[1]['text'])
        self.assertNotIn('message_id', calls[1].args[1])
        self.assertFalse(self.publish())

    def test_completed_sale_and_cancellation_enqueue_once_but_unpaid_sale_does_not(self):
        SystemProduct.objects.get_or_create(kind='DIGITAL_PRODUCT')
        sale = services.manual_sale(actor=self.user, supplier_id=self.supplier.pk, buyer_id=self.buyer.pk,
            items=[{'name': 'Товар', 'cost': '10'}], price='250', creation_key=uuid.uuid4())
        self.assertFalse(BalanceChatPublication.objects.exists())
        services.complete_sale(actor=self.user, sale_id=sale.pk)
        services.complete_sale(actor=self.user, sale_id=sale.pk)
        self.assertEqual(BalanceChatPublication.objects.count(), 1)
        self.assertIn('+750,00 ₽', BalanceChatPublication.objects.get().text)
        text = BalanceChatPublication.objects.get().text
        self.assertIn(sale.visible_id, text)
        self.assertIn('Товар × 1', text)
        self.assertIn('Сумма продажи: 250,00 ₽', text)
        self.assertNotIn(self.supplier.name, text)
        services.cancel_digital_sale(actor=self.user, sale_id=sale.pk, comment='Отмена')
        services.cancel_digital_sale(actor=self.user, sale_id=sale.pk, comment='Повтор')
        self.assertEqual(BalanceChatPublication.objects.count(), 2)
        self.assertIn('+1 000,00 ₽', BalanceChatPublication.objects.order_by('-pk').first().text)

    def test_balance_change_and_outbox_rollback_together(self):
        from django.db import transaction
        with self.assertRaises(RuntimeError), transaction.atomic():
            services.move_balance(actor=self.user, buyer_id=self.buyer.pk, kind='topup', amount='10', reason='Тест')
            raise RuntimeError('Откат')
        self.assertEqual(self.buyer.balance, 1000)
        self.assertFalse(BalanceChatPublication.objects.exists())

    def test_ambiguous_copy_is_not_repeated_and_known_message_can_finish(self):
        enqueue_balance(self.buyer, event='initial')
        self.publish()
        self.client_api.reset_mock()
        services.move_balance(actor=self.user, buyer_id=self.buyer.pk, kind='topup', amount='10', reason='Тест')
        original = self.client_api.call.side_effect
        def timeout(method, data):
            if method == 'sendMessage':
                raise TelegramError('timeout', uncertain=True)
            return original(method, data)
        self.client_api.call.side_effect = timeout
        self.publish()
        row = BalanceChatPublication.objects.order_by('-pk').first()
        self.assertEqual((row.state, row.stage), ('uncertain', 'create'))
        self.assertFalse(self.publish())
        retry_publication(actor=self.user, publication_id=row.pk, checked=True, message_id='102')
        self.client_api.reset_mock()
        self.publish()
        self.assertEqual([c.args[0] for c in self.client_api.call.call_args_list], ['getChatMember'])
        row.refresh_from_db()
        self.assertEqual(row.state, 'done')

    def test_restart_distinguishes_unknown_sends_and_legacy_stages(self):
        first = enqueue_balance(self.buyer, event='first')
        first.state, first.stage = 'working', 'create'
        first.save(update_fields=['state', 'stage'])
        recover_publications()
        first.refresh_from_db()
        self.assertEqual(first.state, 'uncertain')
        retry_publication(actor=self.user, publication_id=first.pk, checked=True, message_id=101)
        first.state, first.stage = 'working', 'pin'
        first.save(update_fields=['state', 'stage'])
        recover_publications()
        first.refresh_from_db()
        self.assertEqual(first.state, 'queued')

    def test_sending_does_not_require_pin_permission_or_administrator_status(self):
        self.client_api.call.side_effect = lambda method, data: (
            {'status': 'member'} if method == 'getChatMember' else {'message_id': 501})
        row = enqueue_balance(self.buyer, event='no-pin-rights')
        self.publish()
        row.refresh_from_db()
        self.assertEqual(row.state, 'done')
        self.assertEqual([c.args[0] for c in self.client_api.call.call_args_list], ['getChatMember', 'sendMessage'])

    def test_old_pin_stage_sends_once_without_touching_original_message(self):
        self.chat.message_id = 50
        self.chat.save(update_fields=['message_id'])
        row = enqueue_balance(self.buyer, event='old-pin-stage')
        row.stage, row.message_id = 'pin', 50
        row.save(update_fields=['stage', 'message_id'])
        self.publish()
        row.refresh_from_db()
        self.chat.refresh_from_db()
        self.assertEqual((row.state, row.message_id, self.chat.message_id), ('done', 101, 50))
        self.assertEqual([c.args[0] for c in self.client_api.call.call_args_list], ['getChatMember', 'sendMessage'])

    def test_transition_unpins_only_known_exact_message_without_sending(self):
        row = enqueue_balance(self.buyer, event='old-root')
        row.message_id, row.copy_message_id, row.state = 29, 29, 'done'
        row.save(update_fields=['message_id', 'copy_message_id', 'state'])
        self.chat.message_id = 29
        self.chat.save(update_fields=['message_id'])
        self.client_api.call.side_effect = lambda method, data=None: (
            {'username': self.bot.username} if method == 'getMe' else True)
        self.assertTrue(unpin_previous_balance(actor=self.user, client=self.client_api, chat_id=self.chat.pk))
        self.chat.refresh_from_db()
        self.assertIsNone(self.chat.message_id)
        self.assertEqual([c.args[0] for c in self.client_api.call.call_args_list], ['getMe', 'unpinChatMessage'])
        self.assertEqual(self.client_api.call.call_args_list[-1].args[1], {'chat_id': self.chat.pk, 'message_id': 29})

    def test_explicit_binding_requires_staff_and_group_admin_and_blocks_supplier_chat(self):
        self.chat.buyer = None
        self.chat.save(update_fields=['buyer'])
        def update(number, sender):
            return {'update_id': number, 'message': {'chat': {'id': self.chat.pk, 'title': self.chat.title,
                'type': 'supergroup'}, 'from': {'id': sender}, 'text': f'/balance_bind {self.buyer.pk}'}}
        ingest_chat_update(update(1, 555))
        process_command(self.client_api, 999)
        self.client_api.call.assert_not_called()
        self.assertFalse(BalanceChatCommand.objects.filter(update_id=1).exists())
        ingest_chat_update(update(2, 44))
        process_command(self.client_api, 999)
        self.chat.refresh_from_db()
        self.assertEqual(self.chat.buyer_id, self.buyer.pk)
        self.assertEqual(BalanceChatPublication.objects.count(), 1)
        self.supplier.chat_ids = [self.chat.pk]
        self.supplier.save(update_fields=['chat_ids'])
        ingest_chat_update(update(3, 44))
        process_command(self.client_api, 999)
        self.assertEqual(BalanceChatCommand.objects.get(update_id=3).error_category, 'supplier_chat')
