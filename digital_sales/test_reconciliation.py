"""Сценарии пополнения из Telegram; сеть и рабочие ключи не используются."""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone

from .ingestion import accept_update
from .models import (BalanceMovement, BalanceObservation, DigitalBot,
                     Supplier, SupplierPurchase)
from .reconciliation import apply_topup, card, remaining_topup, standalone
from .services import move_balance
from .test_parser import checklist


class ReconciliationTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_superuser(username='reconciliation-owner')
        self.supplier = Supplier.objects.create(name='Test', chat_ids=[-123], sender_ids=[55])
        DigitalBot.objects.create(enabled=True)
        self.crypto = patch('digital_sales.crypto.cipher', return_value=Fernet(Fernet.generate_key()))
        self.crypto.start()
        self.addCleanup(self.crypto.stop)
        self.sequence = 0

    def event(self, text, **extra):
        self.sequence += 1
        message = {'message_id': self.sequence, 'date': int(timezone.now().timestamp()) + self.sequence,
                   'chat': {'id': -123, 'type': 'group'}, 'from': {'id': 55, 'is_bot': True}, 'text': text}
        message.update(extra)
        return {'update_id': self.sequence, 'message': message}

    def topup_snapshot(self):
        accept_update(self.event('Баланс: -100 руб'))
        accept_update(self.event('Баланс: 900 руб'))
        return BalanceObservation.objects.order_by('-pk').first()

    def test_order_balance_is_retained_without_financial_alert(self):
        accept_update(self.event('Баланс: 0 руб'))
        with patch('digital_sales.reconciliation.enqueue_observation') as enqueue:
            accept_update(self.event(checklist()))
        enqueue.assert_not_called()
        observation = BalanceObservation.objects.order_by('-pk').first()
        self.assertFalse(standalone(observation))
        with self.assertRaises(ValidationError):
            apply_topup(actor=self.owner, observation_id=observation.pk, displayed_amount='100')

    def test_standalone_is_not_credited_until_click_and_repeat_is_idempotent(self):
        observation = self.topup_snapshot()
        self.assertEqual(self.supplier.balance, Decimal('-100'))
        self.assertIn('Выполнить поступление', card(observation)['reply_markup']['inline_keyboard'][0][0]['text'])
        movement = apply_topup(actor=self.owner, observation_id=observation.pk, displayed_amount='1000')
        repeated = apply_topup(actor=self.owner, observation_id=observation.pk, displayed_amount='1000')
        self.assertEqual(movement.pk, repeated.pk)
        self.assertEqual(self.supplier.balance, Decimal('900'))
        self.assertEqual(BalanceMovement.objects.filter(kind='topup').count(), 1)
        self.assertFalse(BalanceMovement.objects.filter(buyer__isnull=False).exists())

    def test_manual_credit_reduces_remainder_and_stale_amount_is_rejected(self):
        observation = self.topup_snapshot()
        move_balance(actor=self.owner, supplier_id=self.supplier.pk, amount='300', kind='topup', reason='Внесено вручную')
        with self.assertRaises(ValidationError):
            apply_topup(actor=self.owner, observation_id=observation.pk, displayed_amount='1000')
        self.assertEqual(remaining_topup(observation), Decimal('700'))
        apply_topup(actor=self.owner, observation_id=observation.pk, displayed_amount='700')
        self.assertEqual(self.supplier.balance, Decimal('900'))

    def test_later_order_does_not_shrink_historical_topup(self):
        observation = self.topup_snapshot()
        accept_update(self.event(checklist(balance='56')))
        self.assertEqual(remaining_topup(observation), Decimal('1000'))

    def test_newer_standalone_prevents_double_credit_from_older_card(self):
        old = self.topup_snapshot()
        accept_update(self.event('Баланс: 1100 руб'))
        new = BalanceObservation.objects.order_by('-pk').first()
        with self.assertRaises(ValidationError):
            apply_topup(actor=self.owner, observation_id=old.pk, displayed_amount='1000')
        apply_topup(actor=self.owner, observation_id=new.pk, displayed_amount='1200')
        self.assertEqual(self.supplier.balance, Decimal('1100'))

    def test_reply_balance_and_late_or_negative_snapshot_cannot_credit(self):
        accept_update(self.event(checklist()))
        accept_update(self.event('Баланс: 50000 руб', reply_to_message={'message_id': 1}))
        reply = BalanceObservation.objects.order_by('-pk').first()
        self.assertFalse(standalone(reply))
        accept_update(self.event('Баланс: 20 руб', date=int((timezone.now() - timedelta(days=1)).timestamp())))
        with self.assertRaises(ValidationError):
            remaining_topup(BalanceObservation.objects.order_by('-pk').first())
        accept_update(self.event('Баланс: -50000 руб'))
        with self.assertRaises(ValidationError):
            remaining_topup(BalanceObservation.objects.order_by('-pk').first())

    def test_unaccounted_prior_order_requires_review(self):
        accept_update(self.event('Баланс: 0 руб'))
        pending = checklist().replace('Статус: ✅ Выполнено', 'Статус: ⏳ Ожидается')
        accept_update(self.event(pending))
        accept_update(self.event('Баланс: 1000 руб'))
        with self.assertRaises(ValidationError):
            remaining_topup(BalanceObservation.objects.order_by('-pk').first())

    def test_legacy_snapshot_uses_immutable_credit_history(self):
        observation = self.topup_snapshot()
        observation.credits_snapshot = observation.purchases_snapshot = None
        observation.save(update_fields=['credits_snapshot', 'purchases_snapshot'])
        self.assertEqual(remaining_topup(observation), Decimal('1000'))

    def test_changed_prior_purchase_requires_manual_reconciliation(self):
        accept_update(self.event('Баланс: 0 руб'))
        accept_update(self.event(checklist(balance='-844')))
        accept_update(self.event('Баланс: 156 руб'))
        observation = BalanceObservation.objects.order_by('-pk').first()
        purchase = SupplierPurchase.objects.get()
        purchase.amount = Decimal('900')
        purchase.save(update_fields=['amount'])
        with self.assertRaises(ValidationError):
            apply_topup(actor=self.owner, observation_id=observation.pk, displayed_amount='1000')
        self.assertFalse(BalanceMovement.objects.filter(kind='topup').exists())

    def test_permission_is_rechecked_before_repeat(self):
        observation = self.topup_snapshot()
        apply_topup(actor=self.owner, observation_id=observation.pk, displayed_amount='1000')
        self.owner.is_active = False
        self.owner.save(update_fields=['is_active'])
        with self.assertRaises(PermissionDenied):
            apply_topup(actor=self.owner, observation_id=observation.pk, displayed_amount='1000')

    def test_decreasing_manual_adjustment_cannot_be_undone_by_old_snapshot(self):
        observation = self.topup_snapshot()
        move_balance(actor=self.owner, supplier_id=self.supplier.pk, amount='-300',
                     kind='adjustment', reason='Ручная корректировка')
        with self.assertRaises(ValidationError):
            apply_topup(actor=self.owner, observation_id=observation.pk, displayed_amount='1300')
        self.assertFalse(BalanceMovement.objects.filter(kind='topup').exists())
