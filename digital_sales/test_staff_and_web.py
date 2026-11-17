import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock, patch
from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import connections
from django.test import TestCase, TransactionTestCase, Client
from django.urls import reverse
from django.utils import timezone
from catalog.models import SystemProduct
from sales.models import Sale
from telegram_bots.models import StaffBot, StaffBotAccess
from telegram_bots.handlers import accept_update as staff_update
from telegram_bots.client import TelegramError
from .delivery import deliver_one
from .models import (Buyer, Supplier, DigitalOrder, SupplierMessage, AuditEvent, Notification)
from .notifications import enqueue_order
from .services import manual_sale, move_balance, confirm_order, complete_sale


class StaffAndWebTests(TestCase):
    def test_supplier_balance_button_uses_reconciliation_without_changing_money(self):
        from telegram_bots.menu import SUPPLIER_BALANCE, main_menu
        from .models import SupplierPurchase, BalanceMovement
        move_balance(actor=self.user,supplier_id=self.supplier.pk,amount='100',kind='opening',reason='Тест')
        SupplierPurchase.objects.create(order=self.order,amount='10',occurred_at=timezone.now())
        before=BalanceMovement.objects.count()
        self.assertIn(SUPPLIER_BALANCE.code,str(main_menu(self.user)))
        result=staff_update(self.bot.pk,self.update(800,data=SUPPLIER_BALANCE.code))
        self.assertIn('+90,00',result['text'])
        self.assertIn(self.supplier.name,result['text'])
        self.assertEqual(BalanceMovement.objects.count(),before)
        plain=get_user_model().objects.create_user('no-supplier-reconciliation')
        self.assertNotIn(SUPPLIER_BALANCE.code,str(main_menu(plain)))

    def test_web_can_confirm_fulfillment_without_supplier_message_or_new_sale(self):
        from .models import SupplierPurchase, BalanceMovement
        self.order.goods_received=False
        self.order.state='goods'
        self.order.save(update_fields=['goods_received','state'])
        SupplierPurchase.objects.create(order=self.order,amount='10',occurred_at=timezone.now())
        before=BalanceMovement.objects.count()
        response=self.client.post(reverse('digital_sales:action',args=[self.order.pk]),{
            'action':'confirm_goods','revision':self.order.revision})
        self.assertEqual(response.status_code,302)
        self.order.refresh_from_db()
        self.assertTrue(self.order.goods_received)
        self.assertEqual(self.order.state,'ready')
        self.assertIsNone(self.order.sale_id)
        self.assertEqual(BalanceMovement.objects.count(),before)
        self.assertEqual(SupplierPurchase.objects.filter(order=self.order).count(),1)

    def test_web_can_cancel_incoming_duplicate_before_sale_creation(self):
        response=self.client.post(reverse('digital_sales:action',args=[self.order.pk]),{
            'action':'cancel','revision':self.order.revision})
        self.assertEqual(response.status_code,302)
        self.order.refresh_from_db()
        self.assertTrue(self.order.processing_stopped)
        self.assertEqual(self.order.state,'cancelled')
        self.assertIsNone(self.order.sale_id)

    def setUp(self):
        SystemProduct.objects.get_or_create(kind='DIGITAL_PRODUCT')
        self.enterContext(patch('digital_sales.crypto.cipher', return_value=Fernet(Fernet.generate_key())))
        self.user = get_user_model().objects.create_superuser(username='digital-web')
        self.other = get_user_model().objects.create_superuser(username='digital-other')
        self.buyer = Buyer.objects.create(name='Buyer')
        self.supplier = Supplier.objects.create(name='Supplier')
        self.owner = uuid.uuid4()
        self.bot = StaffBot.objects.create(enabled=True, username='SyntheticStaffBot', lease_owner=self.owner,
                                           lease_until=timezone.now() + timedelta(minutes=3))
        self.access = StaffBotAccess.objects.create(bot=self.bot, user=self.user, allowed=True, telegram_user_id=123)
        self.other_access = StaffBotAccess.objects.create(bot=self.bot, user=self.other, allowed=True, telegram_user_id=124)
        self.order = DigitalOrder.objects.create(supplier=self.supplier, checklist_received=True, goods_received=True,
            state='ready', items=[{'name': 'Synthetic', 'cost': '10'}], cost='10')
        self.client.force_login(self.user)

    def update(self, number, data='', text='', identity=123):
        message = {'message_id': number, 'chat': {'id': identity, 'type': 'private'},
                   'from': {'id': identity}, 'text': text}
        return {'update_id': number, **({'callback_query': {'id': str(number), 'data': data,
            'from': {'id': identity}, 'message': message}} if data else {'message': message})}

    def test_existing_sale_requires_explicit_confirmation_before_cancellation(self):
        sale = manual_sale(actor=self.user, supplier_id=self.supplier.pk, buyer_id=self.buyer.pk,
            items=[{'name': 'Synthetic cancellation', 'cost': '10'}], price='20', creation_key=uuid.uuid4())
        order = sale.digital_order
        reply = staff_update(self.bot.pk, self.update(501, f'dg:{order.pk}:{order.revision}:ignore'))
        sale.refresh_from_db()
        self.assertFalse(sale.is_cancelled)
        self.assertIn('Подтвердить отмену продажи', str(reply['reply_markup']))
        reply = staff_update(self.bot.pk, self.update(502, f'dg:{order.pk}:{order.revision}:cancel_sale'))
        sale.refresh_from_db()
        self.assertTrue(sale.is_cancelled)
        self.assertEqual({button['callback_data'] for row in reply['reply_markup']['inline_keyboard']
                          for button in row}, {'digital_sales', 'menu'})

    def test_explicit_balance_resend_sends_new_message_instead_of_edit(self):
        from .crypto import encrypt
        from .models import BalanceObservation
        source = SupplierMessage.objects.create(supplier=self.supplier, chat_id=-99, message_id=500,
            occurred_at=timezone.now(), kind='balance', fingerprint='synthetic-resend',
            encrypted_payload=encrypt({'text':'Баланс: 100 руб.'}), parsed={})
        observation = BalanceObservation.objects.create(supplier=self.supplier, message=source,
            balance='100', expected='0', difference='100', credits_snapshot='0', purchases_snapshot='0')
        Notification.objects.create(access=self.access, observation=observation,
            event_key=f'balance:{observation.pk}:received', text='', state='done', telegram_message_id=700)
        row = Notification.objects.create(access=self.access, observation=observation,
            event_key=f'balance:{observation.pk}:resend:synthetic', text='')
        client = Mock()
        client.message.return_value = {'message_id': 701}
        deliver_one(client, bot_id=self.bot.pk, owner=self.owner)
        client.message.assert_called_once()
        client.call.assert_not_called()
        row.refresh_from_db()
        self.assertEqual(row.telegram_message_id, 701)

    def test_shared_buyer_and_price_and_confirmation_from_two_staff(self):
        row = self.order
        staff_update(self.bot.pk, self.update(1, f'dg:{row.pk}:1:buyer:{self.buyer.pk}'))
        reply = staff_update(self.bot.pk, self.update(2, f'dg:{row.pk}:1:open', identity=124))
        self.assertIn('Buyer', reply['text'])
        staff_update(self.bot.pk, self.update(3, f'dg:{row.pk}:2:price'))
        staff_update(self.bot.pk, self.update(4, text='25.50'))
        row.refresh_from_db()
        self.assertEqual(str(row.price), '25.50')
        response = staff_update(self.bot.pk, self.update(5, f'dg:{row.pk}:{row.revision}:confirm', identity=124))
        self.assertIn('SALE-', response['text'])
        staff_update(self.bot.pk, self.update(6, f'dg:{row.pk}:{row.revision}:confirm'))
        self.assertEqual(Sale.objects.count(), 1)

    def test_telegram_confirmation_completes_partner_sale_and_debits_balance_once(self):
        row = self.order
        staff_update(self.bot.pk, self.update(1, f'dg:{row.pk}:1:price'))
        reply = staff_update(self.bot.pk, self.update(2, text='25.50'))
        row.refresh_from_db()
        self.assertEqual(row.price, Decimal('25.50'))
        self.assertIsNone(row.buyer_id)
        self.assertFalse(Sale.objects.exists())
        staff_update(self.bot.pk, self.update(3, f'dg:{row.pk}:{row.revision}:buyer:{self.buyer.pk}'))
        row.refresh_from_db()
        reply = staff_update(self.bot.pk, self.update(4, f'dg:{row.pk}:{row.revision}:confirm'))
        row.refresh_from_db()
        self.assertIn('SALE-', reply['text'])
        self.assertTrue(row.sale.is_completed)
        self.assertEqual(row.sale.payment_status, Sale.PaymentStatus.PAID)
        self.assertEqual(row.sale.order_status, Sale.OrderStatus.DELIVERED)
        self.assertEqual(row.sale.digital_movements.count(),2)
        self.assertEqual(self.buyer.balance,Decimal('-25.50'))
        self.assertEqual(self.supplier.balance,Decimal('-10'))
        self.assertIsNone(row.sale.cash_received_amount)
        staff_update(self.bot.pk,self.update(5,f'dg:{row.pk}:{row.revision}:confirm'))
        self.assertEqual(Sale.objects.count(),1)
        self.assertEqual(row.sale.digital_movements.count(),2)

    def test_immediate_completion_requires_payment_permissions_before_creating_sale(self):
        from django.core.exceptions import PermissionDenied
        employee=get_user_model().objects.create_user(username='digital-create-without-payment')
        employee.user_permissions.add(*Permission.objects.filter(
            content_type__app_label__in=['digital_sales','sales'],codename__in=['create_digital_sales','create_sale']))
        self.order.buyer=self.buyer;self.order.price=Decimal('25.50')
        self.order.save(update_fields=['buyer','price'])
        with self.assertRaises(PermissionDenied):
            confirm_order(actor=employee,order_id=self.order.pk,revision=self.order.revision,complete_immediately=True)
        self.assertFalse(Sale.objects.exists())
        self.assertEqual(self.buyer.balance,Decimal('0'))

    def test_web_confirmation_keeps_unpaid_partner_sale(self):
        self.order.buyer=self.buyer;self.order.price=Decimal('25.50')
        self.order.save(update_fields=['buyer','price'])
        sale=confirm_order(actor=self.user,order_id=self.order.pk,revision=self.order.revision)
        self.assertFalse(sale.is_completed)
        self.assertEqual(sale.payment_status,Sale.PaymentStatus.UNPAID)
        self.assertFalse(sale.digital_movements.exists())

    def test_incomplete_order_shows_creation_button_but_service_rejects_creation(self):
        from .telegram import card
        self.order.state, self.order.goods_received = 'goods', False
        buttons = card(self.order)['reply_markup']['inline_keyboard']
        actions = [button['callback_data'].split(':')[3] for line in buttons for button in line if 'callback_data' in button]
        self.assertIn('price', actions)
        self.assertIn('buyers', actions)
        self.assertIn('confirm', actions)
        self.order.save(update_fields=['state', 'goods_received'])
        reply = staff_update(self.bot.pk, self.update(1, f'dg:{self.order.pk}:1:confirm'))
        self.assertIn('Сначала проверьте', reply['text'])
        self.assertFalse(Sale.objects.exists())

    def test_retail_selection_price_and_confirmation_complete_sale_without_wallet(self):
        reply = staff_update(self.bot.pk, self.update(1, f'dg:{self.order.pk}:1:buyers:0'))
        buttons = reply['reply_markup']['inline_keyboard']
        self.assertEqual(buttons[0][0]['text'], 'Розничный покупатель')
        self.assertNotIn('newbuyer', str(buttons))
        staff_update(self.bot.pk, self.update(2, f'dg:{self.order.pk}:1:retail'))
        self.order.refresh_from_db()
        staff_update(self.bot.pk, self.update(3, f'dg:{self.order.pk}:{self.order.revision}:price'))
        reply = staff_update(self.bot.pk, self.update(4, text='25.50'))
        self.order.refresh_from_db()
        self.assertTrue(self.order.is_retail)
        self.assertIsNone(self.order.buyer_id)
        self.assertFalse(Sale.objects.exists())
        self.assertNotIn('http', reply['text'])
        self.assertFalse(any('url' in button for line in reply['reply_markup']['inline_keyboard'] for button in line))
        staff_update(self.bot.pk, self.update(5, f'dg:{self.order.pk}:{self.order.revision}:confirm'))
        self.order.refresh_from_db()
        self.assertTrue(self.order.sale.is_completed)
        self.assertEqual(self.order.sale.cash_received_amount, Decimal('25.50'))
        self.assertFalse(self.order.sale.digital_movements.filter(buyer__isnull=False).exists())

    def test_obsolete_buyer_creation_callback_and_pending_input_create_nothing(self):
        from .models import StaffConversation
        count = Buyer.objects.count()
        reply = staff_update(self.bot.pk, self.update(1, f'dg:{self.order.pk}:1:newbuyer'))
        self.assertIn('отключено', reply['text'])
        StaffConversation.objects.create(access=self.access, order=self.order, revision=1,
            field='new_buyer', expires_at=timezone.now() + timedelta(minutes=5))
        reply = staff_update(self.bot.pk, self.update(2, text='Не создавать'))
        self.assertIn('отключено', reply['text'])
        self.assertEqual(Buyer.objects.count(), count)
        self.assertFalse(StaffConversation.objects.exists())

    def test_web_manual_retail_is_completed_and_draft_keeps_retail_choice(self):
        response = self.client.post(reverse('digital_sales:order', args=[self.order.pk]),
            {'revision': 1, 'buyer': 'retail', 'price': '25.50'})
        self.assertEqual(response.status_code, 302)
        self.order.refresh_from_db()
        self.assertTrue(self.order.is_retail)
        self.assertFalse(Sale.objects.exists())
        response = self.client.get(reverse('digital_sales:order', args=[self.order.pk]))
        self.assertContains(response, 'Розничный покупатель')
        self.assertContains(response, 'Не используется')
        response = self.client.post(reverse('digital_sales:manual'), {'supplier': self.supplier.pk,
            'buyer': 'retail', 'items': 'Synthetic | 10', 'price': '25.50', 'creation_key': uuid.uuid4()})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Sale.objects.get().is_completed)

    def test_order_shows_future_negative_balance_without_blocking_completion(self):
        sale = manual_sale(actor=self.user, supplier_id=self.supplier.pk, buyer_id=self.buyer.pk,
            items=[{'name': 'Synthetic', 'cost': '10'}], price='25', creation_key=uuid.uuid4())
        order = sale.digital_order
        response = self.client.get(reverse('digital_sales:order', args=[order.pk]))
        self.assertEqual(response.context['balance_after_completion'], Decimal('-25'))
        self.assertContains(response, 'Баланс после завершения')
        self.assertNotContains(response, 'Не хватает')
        complete_sale(actor=self.user, sale_id=sale.pk)
        response = self.client.get(reverse('digital_sales:order', args=[order.pk]))
        self.assertIsNone(response.context['balance_after_completion'])
        self.assertEqual(self.buyer.balance, -25)

    def test_notification_targets_and_secrets_not_exposed(self):
        self.other.is_active = False
        self.other.save(update_fields=['is_active'])
        enqueue_order(self.order)
        self.assertEqual(Notification.objects.count(), 1)
        client = Mock()
        client.message.return_value = {'message_id': 100}
        self.assertTrue(deliver_one(client, bot_id=self.bot.pk, owner=self.owner))
        self.assertEqual(Notification.objects.get().state, 'done')
        self.assertEqual(client.message.call_args.args[0], 123)
        self.assertFalse(deliver_one(client, bot_id=self.bot.pk, owner=self.owner))

    def test_delivery_error_preserves_order_and_unknown_result_is_not_retried(self):
        enqueue_order(self.order)
        client = Mock()
        client.message.side_effect = TelegramError('timeout')
        deliver_one(client, bot_id=self.bot.pk, owner=self.owner)
        notification = Notification.objects.order_by('pk').first()
        self.assertEqual(notification.state, 'uncertain')
        self.assertTrue(DigitalOrder.objects.filter(pk=self.order.pk).exists())
        count = client.message.call_count
        self.other_access.allowed = False
        self.other_access.save(update_fields=['allowed'])
        deliver_one(client, bot_id=self.bot.pk, owner=self.owner)
        self.assertEqual(client.message.call_count, count)

    def test_revoked_permissions_deny_old_callback(self):
        self.user.is_superuser = False
        self.user.save(update_fields=['is_superuser'])
        self.user.user_permissions.add(Permission.objects.get(content_type__app_label='telegram_bots', codename='use_staff_bot'))
        reply = staff_update(self.bot.pk, self.update(1, f'dg:{self.order.pk}:1:buyer:{self.buyer.pk}'))
        self.assertIn('Доступ закрыт', reply['text'])
        self.order.refresh_from_db()
        self.assertIsNone(self.order.buyer_id)

    def test_sources_reveal_only_by_post_and_permission_with_audit(self):
        from .ingestion import store_manual_goods
        store_manual_goods(self.order, 'SYNTHETIC-SECRET-0001', self.user)
        source = SupplierMessage.objects.get(order=self.order)
        for name, args in [('digital_sales:dashboard', []), ('digital_sales:order', [self.order.pk])]:
            response = self.client.get(reverse(name, args=args))
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, 'SYNTHETIC-SECRET-0001')
        url = reverse('digital_sales:reveal', args=[source.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        response = self.client.post(url)
        self.assertContains(response, 'SYNTHETIC-SECRET-0001')
        self.assertIn('no-store', response['Cache-Control'])
        self.assertTrue(AuditEvent.objects.filter(kind='secret_viewed', actor=self.user).exists())
        user = get_user_model().objects.create_user(username='reader')
        user.user_permissions.add(Permission.objects.get(content_type__app_label='digital_sales', codename='view_digital_sales'))
        self.client.force_login(user)
        self.assertEqual(self.client.post(url).status_code, 403)

    def test_manual_form_creates_unfinished_sale_and_csrf_is_enforced(self):
        response = self.client.post(reverse('digital_sales:manual'), {
            'supplier': self.supplier.pk, 'buyer': self.buyer.pk, 'items': 'Synthetic A | 10\nSynthetic B | 20',
            'price': '45', 'numbers': '999', 'creation_key': uuid.uuid4(), 'secret': 'SYNTHETIC-BUNDLE'})
        self.assertEqual(response.status_code, 302)
        sale = Sale.objects.get()
        self.assertFalse(sale.is_completed)
        self.assertEqual(sale.custom_items.count(), 2)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.user)
        self.assertEqual(csrf.post(reverse('digital_sales:action', args=[self.order.pk]), {'action': 'confirm'}).status_code, 403)

    def test_invalid_form_does_not_echo_multiline_secret(self):
        secret = 'SYNTHETIC-MULTILINE-SECRET\n00042'
        response = self.client.post(reverse('digital_sales:manual'), {'secret': secret})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'SYNTHETIC-MULTILINE-SECRET')

    def test_bad_link_id_is_validation_error_not_server_failure(self):
        response = self.client.post(reverse('digital_sales:action', args=[self.order.pk]),
            {'action': 'link', 'target': 'not-an-id', 'revision': self.order.revision, 'reason': 'Test'})
        self.assertEqual(response.status_code, 302)

    def test_changed_source_blocks_completion_until_explicit_review(self):
        from .ingestion import _issue, resolve_order
        from .services import save_draft
        from django.core.exceptions import ValidationError
        save_draft(actor=self.user, order_id=self.order.pk, revision=self.order.revision, buyer_id=self.buyer.pk, price=25)
        self.order.refresh_from_db()
        sale = confirm_order(actor=self.user, order_id=self.order.pk, revision=self.order.revision)
        self.order.refresh_from_db()
        _issue(self.order, 'Изменённый источник')
        with self.assertRaises(ValidationError):
            complete_sale(actor=self.user, sale_id=sale.pk)
        resolve_order(actor=self.user, order_id=self.order.pk, revision=self.order.revision, reason='Проверено без замены снимка')
        self.order.refresh_from_db()
        self.assertEqual(self.order.review_reason, '')

    def test_balance_form_and_configuration_render_and_no_network_get(self):
        for name in ['digital_sales:balance', 'digital_sales:configuration', 'digital_sales:buyer_create']:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)
        response = self.client.post(reverse('digital_sales:balance'), {'buyer': self.buyer.pk, 'kind': 'topup',
            'amount': '100', 'reason': 'Уже внесено', 'operation_key': uuid.uuid4()})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.buyer.balance, 100)


class DigitalConcurrencyTests(TransactionTestCase):
    def setUp(self):
        SystemProduct.objects.get_or_create(kind='DIGITAL_PRODUCT')
        self.user = get_user_model().objects.create_superuser(username='parallel-digital')
        self.buyer = Buyer.objects.create(name='Parallel Buyer')
        self.supplier = Supplier.objects.create(name='Parallel Supplier')
        move_balance(actor=self.user, buyer_id=self.buyer.pk, amount='100', kind='opening', reason='Test')

    def race(self, action):
        barrier = threading.Barrier(2)
        def run(index):
            try:
                barrier.wait(timeout=10)
                return action(index)
            except Exception as exc:
                return type(exc).__name__
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(run, [0, 1]))

    def test_parallel_confirm_creates_one_sale(self):
        order = DigitalOrder.objects.create(supplier=self.supplier, buyer=self.buyer, price='70', cost='10',
            items=[{'name': 'Test', 'cost': '10'}], checklist_received=True, goods_received=True, state='ready')
        result = self.race(lambda _: confirm_order(actor=self.user, order_id=order.pk, revision=1).pk)
        self.assertEqual(len(set(result)), 1, result)
        self.assertEqual(Sale.objects.count(), 1)

    def test_parallel_sales_each_debit_once_and_allow_debt(self):
        sales = [manual_sale(actor=self.user, supplier_id=self.supplier.pk, buyer_id=self.buyer.pk,
            items=[{'name': 'Test', 'cost': '10'}], price='70', creation_key=uuid.uuid4()) for _ in range(2)]
        result = self.race(lambda index: complete_sale(actor=self.user, sale_id=sales[index].pk).pk)
        self.assertEqual(sum(isinstance(value, int) for value in result), 2, result)
        self.assertEqual(self.buyer.balance, -40)
        self.assertEqual(self.supplier.balance, -20)
