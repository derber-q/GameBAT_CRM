from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from .models import (DigitalBot, Supplier, DigitalOrder, SupplierMessage, BalanceObservation,
                     SupplierPurchase, Buyer, Notification)
from .ingestion import accept_update, expected_balance
from .test_parser import checklist
from .services import manual_sale
import uuid


class IngestionTests(TestCase):
    def test_account_creation_fee_is_not_an_extra_delivered_bundle(self):
        rows = '● Новый аккаунт · 45 руб\n● PS Deluxe · 100 руб | #7617\n● PS Ea Play · 200 руб | #7618'
        order = accept_update(self.event(checklist(rows, '345', '1000')))
        result = accept_update(self.event('✅ Ваш заказ #7617+1 готов!', reply_to_message={'message_id':1}))
        self.assertEqual(result.pk, order.pk)
        self.assertEqual(result.state, 'ready')
        self.assertTrue(result.goods_received)
        self.assertEqual(SupplierPurchase.objects.filter(order=order).count(), 1)
        self.assertEqual(result.cost, Decimal('345'))

    def test_edit_with_replaced_references_does_not_create_another_order(self):
        original = self.event(checklist())
        order = accept_update(original)
        edited = dict(original['message'],text=checklist().replace('#6099','#9999'),edit_date=int(timezone.now().timestamp())+20)
        result = accept_update({'update_id':2,'edited_message':edited})
        self.assertEqual(result.pk, order.pk)
        self.assertEqual(DigitalOrder.objects.count(),1)
        self.assertEqual(SupplierPurchase.objects.count(),1)
        self.assertTrue(result.review_reason)

    def setUp(self):
        from catalog.models import SystemProduct
        SystemProduct.objects.get_or_create(kind='DIGITAL_PRODUCT')
        self.cipher = patch('digital_sales.crypto.cipher', return_value=Fernet(Fernet.generate_key()))
        self.cipher.start()
        self.addCleanup(self.cipher.stop)
        self.bot = DigitalBot.objects.create(enabled=True)
        self.supplier = Supplier.objects.create(name='Test', chat_ids=[-123], sender_ids=[55])
        self.sequence = 0

    def event(self, text, **fields):
        self.sequence += 1
        message = {'message_id': self.sequence, 'date': int(timezone.now().timestamp()) + self.sequence,
                   'chat': {'id': -123, 'type': 'supergroup'}, 'from': {'id': 55, 'is_bot': True}, 'text': text}
        message.update(fields)
        return {'update_id': self.sequence, 'message': message}

    def test_checklist_and_ready_one_order_original_encrypted(self):
        order = accept_update(self.event(checklist()))
        self.assertEqual(order.state, 'goods')
        self.assertFalse(Notification.objects.exists())
        result = accept_update(self.event('✅ Ваш заказ #6099 готов!\npassword: SYNTHETIC_SECRET'))
        self.assertEqual(result.pk, order.pk)
        self.assertEqual(result.state, 'ready')
        self.assertNotIn('SYNTHETIC_SECRET', SupplierMessage.objects.last().encrypted_payload)
        self.assertEqual(SupplierPurchase.objects.count(), 1)
        self.assertEqual(self.supplier.balance, Decimal('12521'))
        self.assertEqual(expected_balance(self.supplier), Decimal('11677'))

    def test_status_only_edit_clears_old_warning_without_manual_review(self):
        pending = checklist().replace('Статус: ✅ Выполнено', 'Статус: ⏳ Ожидается').replace('Оплата: ✅ Получена', 'Оплата: ⏳ Ожидается')
        original = self.event(pending)
        order = accept_update(original)
        self.assertEqual(order.state, 'review')
        source = dict(original['message'], text=checklist().replace('Оплата: ✅ Получена', 'Оплата: ⏳ Ожидается'),
                      edit_date=int(timezone.now().timestamp()) + 10)
        accept_update({'update_id': 2, 'edited_message': source})
        self.sequence = 2
        order = accept_update(self.event('✅ Ваш заказ #6099 готов!'))
        self.assertEqual(order.state, 'ready')
        self.assertEqual(order.review_reason, '')
        self.assertTrue(order.checklist_received)
        self.assertEqual(SupplierPurchase.objects.filter(order=order).count(), 1)

    def test_negative_supplier_snapshot_sets_negative_opening(self):
        accept_update(self.event('Баланс: -1250,50 руб'))
        self.assertEqual(self.supplier.balance, Decimal('-1250.50'))
        observation = BalanceObservation.objects.get()
        self.assertEqual(observation.balance, Decimal('-1250.50'))
        self.assertEqual(observation.difference, Decimal('0'))

    def test_readiness_first_and_group_not_arithmetic(self):
        order = accept_update(self.event('✅ Ваш заказ #6128+2 ✅'))
        rows = '● A · 2317 руб | #6126\n● B · 418 руб | #6127\n● C · 2923 руб | #6128'
        result = accept_update(self.event(checklist(rows, '5658', '5939')))
        self.assertEqual(result.pk, order.pk)
        self.assertEqual(result.state, 'ready')
        self.assertEqual(set(result.references.values_list('number', flat=True)), {'6126', '6127', '6128'})

    def test_repeated_updates_and_messages_do_not_duplicate(self):
        event = self.event(checklist())
        accept_update(event)
        accept_update(event)
        accept_update(self.event(checklist()))
        self.assertEqual(DigitalOrder.objects.count(), 1)
        self.assertEqual(SupplierMessage.objects.count(), 1)
        self.assertEqual(BalanceObservation.objects.count(), 1)

    def test_reply_to_checklist_is_not_proof_of_readiness(self):
        order = accept_update(self.event(checklist()))
        result = accept_update(self.event('Завтра сделаем', reply_to_message={'message_id': 1}))
        self.assertEqual(result.pk, order.pk)
        self.assertEqual(result.state, 'goods')
        self.assertFalse(result.goods_received)
        self.assertFalse(Notification.objects.exists())

    def test_new_checklist_reply_to_sold_order_uses_its_own_numbers(self):
        user = get_user_model().objects.create_superuser(username='reply-sold-order')
        buyer = Buyer.objects.create(name='Synthetic buyer')
        sale = manual_sale(actor=user, supplier_id=self.supplier.pk, buyer_id=buyer.pk,
            items=[{'name': 'Previous product', 'cost': '10', 'number': '100'}],
            numbers=['100'], price='20', creation_key=uuid.uuid4())
        old = sale.digital_order
        accept_update(self.event('✅ Ваш заказ #100 готов!'))
        result = accept_update(self.event(checklist(), reply_to_message={'message_id': 1}))
        self.assertIsNotNone(result)
        self.assertNotEqual(result.pk, old.pk)
        self.assertEqual(result.cost, Decimal('844'))
        self.assertEqual(list(result.references.values_list('number', flat=True)), ['6099'])
        old.refresh_from_db()
        self.assertEqual(old.review_reason, '')
        self.assertEqual(old.cost, Decimal('10'))
        self.assertEqual(old.sale_id, sale.pk)

    def test_new_checklist_reply_does_not_reuse_an_unfinished_order(self):
        old = accept_update(self.event(checklist('● Previous · 10 руб | #100', '10')))
        result = accept_update(self.event(checklist(), reply_to_message={'message_id': 1}))
        self.assertNotEqual(result.pk, old.pk)
        self.assertEqual(result.cost, Decimal('844'))
        old.refresh_from_db()
        self.assertEqual(old.review_reason, '')
        self.assertEqual(old.cost, Decimal('10'))

    def test_readiness_and_checklist_with_unrelated_reply_fill_one_new_order(self):
        old = accept_update(self.event(checklist('● Previous · 10 руб | #100', '10')))
        order = accept_update(self.event('✅ Ваш заказ #6099 готов!', reply_to_message={'message_id': 1}))
        self.assertNotEqual(order.pk, old.pk)
        result = accept_update(self.event(checklist(), reply_to_message={'message_id': 1}))
        self.assertEqual(result.pk, order.pk)
        self.assertEqual(result.state, 'ready')
        self.assertTrue(result.checklist_received)
        self.assertTrue(result.goods_received)
        self.assertEqual(result.cost, Decimal('844'))
        self.assertEqual(SupplierPurchase.objects.get(order=result).amount, Decimal('844'))
        old.refresh_from_db()
        self.assertFalse(old.goods_received)
        self.assertEqual(old.review_reason, '')

    def test_known_number_with_reply_to_another_order_is_not_a_group_overlap(self):
        old = accept_update(self.event(checklist('● Previous · 10 руб | #100', '10')))
        order = accept_update(self.event('✅ Ваш заказ #6099 готов!'))
        result = accept_update(self.event(checklist(), reply_to_message={'message_id': 1}))
        self.assertIsNotNone(result)
        self.assertEqual(result.pk, order.pk)
        self.assertEqual(result.state, 'ready')
        self.assertEqual(result.cost, Decimal('844'))
        old.refresh_from_db()
        self.assertEqual(old.review_reason, '')

    def test_unknown_chat_sender_and_free_text_are_not_orders(self):
        for event in [self.event(checklist(), chat={'id': -999, 'type': 'supergroup'}),
                      self.event(checklist(), **{'from': {'id': 99}}), self.event('Здравствуйте, 400 рублей')]:
            accept_update(event)
        self.assertFalse(DigitalOrder.objects.exists())
        self.assertFalse(SupplierMessage.objects.exists())

    def test_mismatch_and_unknown_forward_require_review(self):
        order = accept_update(self.event(checklist(total='900')))
        self.assertEqual(order.state, 'review')
        self.assertFalse(SupplierPurchase.objects.exists())
        text = checklist().replace('#6099', '#7000')
        forwarded = accept_update(self.event(text, forward_origin={'type': 'hidden_user', 'date': int(timezone.now().timestamp())}))
        self.assertEqual(forwarded.state, 'review')

    def test_delayed_balance_does_not_reset_history_or_money(self):
        accept_update(self.event('Баланс: 12521 руб'))
        order = accept_update(self.event(checklist()))
        old = accept_update(self.event('Баланс: 999 руб', date=int((timezone.now() - timedelta(days=2)).timestamp())))
        self.assertIsNone(old)
        observation = BalanceObservation.objects.last()
        self.assertTrue(observation.uncertain)
        self.assertIsNone(observation.expected)
        self.assertEqual(self.supplier.balance, Decimal('12521'))

    def test_real_mismatch_no_guessed_cause(self):
        accept_update(self.event('Баланс: 11677 руб'))
        rows = '● A · 2317 руб | #6126\n● B · 418 руб | #6127\n● C · 2923 руб | #6128'
        accept_update(self.event(checklist(rows, '5658', '5939')))
        observation = BalanceObservation.objects.last()
        self.assertEqual(observation.expected, Decimal('6019'))
        self.assertEqual(observation.difference, Decimal('-80'))

    def test_manual_order_is_not_duplicated_or_repriced(self):
        user = get_user_model().objects.create_superuser(username='manual-test')
        buyer = Buyer.objects.create(name='Test')
        sale = manual_sale(actor=user, supplier_id=self.supplier.pk, buyer_id=buyer.pk,
                           items=[{'name': 'Synthetic Game', 'cost': '844', 'number': '6099'}],
                           numbers=['6099'], price='1000', creation_key=uuid.uuid4())
        order = accept_update(self.event(checklist()))
        self.assertEqual(order.sale_id, sale.pk)
        self.assertEqual(DigitalOrder.objects.count(), 1)
        self.assertEqual(SupplierPurchase.objects.count(), 1)
        accept_update(self.event(checklist(total='900')))
        sale.refresh_from_db()
        self.assertEqual(sale.total_amount, Decimal('1000'))

    def test_group_overlap_does_not_merge_confirmed_sale(self):
        user = get_user_model().objects.create_superuser(username='overlap')
        buyer = Buyer.objects.create(name='Test')
        manual_sale(actor=user, supplier_id=self.supplier.pk, buyer_id=buyer.pk,
                    items=[{'name': 'A', 'cost': '10'}], numbers=['100'], price='20', creation_key=uuid.uuid4())
        result = accept_update(self.event(checklist('● A · 10 руб | #100\n● B · 20 руб | #101', '30')))
        self.assertIsNone(result)
        self.assertIn('пересекается', DigitalOrder.objects.first().review_reason)
        self.assertIsNone(SupplierMessage.objects.last().order_id)

    def test_manual_without_number_can_be_linked_without_dropping_history(self):
        from .ingestion import link_orders
        user = get_user_model().objects.create_superuser(username='link-manual')
        buyer = Buyer.objects.create(name='Test')
        sale = manual_sale(actor=user, supplier_id=self.supplier.pk, buyer_id=buyer.pk,
            items=[{'name': 'Synthetic Game', 'cost': '844'}], price='1000', creation_key=uuid.uuid4())
        source = accept_update(self.event(checklist()))
        result = link_orders(actor=user, source_id=source.pk, target_id=sale.digital_order.pk,
                             revision=source.revision, reason='Сверены оригиналы')
        self.assertEqual(result.sale_id, sale.pk)
        self.assertEqual(SupplierPurchase.objects.count(), 2)
        self.assertEqual(SupplierPurchase.objects.filter(superseded_by__isnull=True).count(), 1)

    def test_manual_correction_and_review_of_unverified_forward(self):
        from .ingestion import correct_checklist
        user = get_user_model().objects.create_superuser(username='verify-forward')
        order = accept_update(self.event(checklist(), forward_origin={'type': 'hidden_user', 'date': int(timezone.now().timestamp())}))
        self.assertFalse(SupplierPurchase.objects.exists())
        corrected = correct_checklist(actor=user, order_id=order.pk, revision=order.revision,
            items=[{'name': 'Verified synthetic', 'cost': '844', 'number': '6099'}],
            reason='Проверены источник и сумма', goods_confirmed=True)
        self.assertEqual(corrected.state, 'ready')
        self.assertEqual(SupplierPurchase.objects.count(), 1)
