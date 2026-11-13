"""Отменённый входящий заказ не возвращается из повторных событий поставщика."""
from decimal import Decimal
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone

from .ingestion import accept_update, expected_balance
from .models import (AuditEvent, BalanceMovement, BalanceObservation, DigitalBot,
                     DigitalOrder, Supplier, SupplierMessage, SupplierPurchase)
from .services import ignore_incoming_order, confirm_order
from .telegram import card
from .test_parser import checklist


class IgnoredIncomingTests(TestCase):
    def setUp(self):
        self.enterContext(patch('digital_sales.crypto.cipher', return_value=Fernet(Fernet.generate_key())))
        self.owner = get_user_model().objects.create_superuser(username='ignore-owner')
        self.bot = DigitalBot.objects.create(enabled=True)
        self.supplier = Supplier.objects.create(name='Synthetic', chat_ids=[-123], sender_ids=[55])
        self.sequence = 0

    def event(self, text, **extra):
        self.sequence += 1
        message = {'message_id': self.sequence, 'date': int(timezone.now().timestamp()) + self.sequence,
                   'chat': {'id': -123, 'type': 'group'}, 'from': {'id': 55, 'is_bot': True}, 'text': text}
        message.update(extra)
        return {'update_id': self.sequence, 'message': message}

    def ignore(self, order):
        return ignore_incoming_order(actor=self.owner, order_id=order.pk, revision=order.revision)

    def test_ignore_preserves_purchase_and_balances_and_is_idempotent(self):
        order = accept_update(self.event(checklist()))
        before = self.supplier.balance, expected_balance(self.supplier), BalanceMovement.objects.count()
        old_revision = order.revision
        ignored = self.ignore(order)
        again = ignore_incoming_order(actor=self.owner, order_id=order.pk, revision=old_revision)
        self.assertTrue(ignored.processing_stopped)
        self.assertEqual(again.pk, ignored.pk)
        self.assertIsNotNone(ignored.ignored_at)
        self.assertEqual(ignored.ignored_by_id, self.owner.pk)
        self.assertEqual(SupplierPurchase.objects.get(order=order).amount, Decimal('844'))
        self.assertEqual(before, (self.supplier.balance, expected_balance(self.supplier), BalanceMovement.objects.count()))
        self.assertEqual(AuditEvent.objects.filter(order=order, kind='incoming_order_ignored').count(), 1)
        self.assertEqual(card(ignored)['reply_markup']['inline_keyboard'], [])

    def test_new_goods_and_edited_checklist_do_not_reopen_or_create_purchase(self):
        pending = checklist().replace('Статус: ✅ Выполнено', 'Статус: ⏳ Ожидается')
        original = self.event(pending)
        order = self.ignore(accept_update(original))
        observation_count = BalanceObservation.objects.count()
        with patch('digital_sales.notifications.enqueue_order') as notify:
            accept_update(self.event('✅ Ваш заказ #6099 готов!'))
            edited = dict(original['message'], text=checklist().replace('#6099', '#7001'), edit_date=1794100000)
            accept_update({'update_id': 3, 'edited_message': edited})
        notify.assert_not_called()
        order.refresh_from_db()
        self.assertTrue(order.processing_stopped)
        self.assertFalse(order.goods_received)
        self.assertFalse(SupplierPurchase.objects.exists())
        self.assertEqual(DigitalOrder.objects.count(), 1)
        self.assertEqual(BalanceObservation.objects.count(), observation_count)
        self.assertTrue(order.references.filter(number='7001').exists())

    def test_balance_reply_to_ignored_order_is_not_a_new_topup_notice(self):
        order = self.ignore(accept_update(self.event(checklist())))
        count = BalanceObservation.objects.count()
        with patch('digital_sales.reconciliation.enqueue_observation') as notify:
            accept_update(self.event('Баланс: 99999 руб', reply_to_message={'message_id': 1}))
        notify.assert_not_called()
        self.assertEqual(BalanceObservation.objects.count(), count)
        self.assertEqual(SupplierMessage.objects.order_by('-pk').first().order_id, order.pk)

    def test_old_confirmation_callback_cannot_create_sale(self):
        order = self.ignore(accept_update(self.event(checklist())))
        with self.assertRaises(ValidationError):
            confirm_order(actor=self.owner, order_id=order.pk, revision=order.revision)
        order.refresh_from_db()
        self.assertIsNone(order.sale_id)

    def test_permissions_are_checked_again_for_repeat(self):
        order = self.ignore(accept_update(self.event(checklist())))
        self.owner.is_active = False
        self.owner.save(update_fields=['is_active'])
        with self.assertRaises(PermissionDenied):
            self.ignore(order)

    def test_cancel_is_last_button(self):
        order = accept_update(self.event(checklist()))
        last = card(order)['reply_markup']['inline_keyboard'][-1][0]
        self.assertEqual(last['text'], 'Отменить')
        self.assertTrue(last['callback_data'].endswith(':ignore'))
