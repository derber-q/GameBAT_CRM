"""Восстановление после неопределённого POST и выдачи. Реальные API не используются."""
from unittest.mock import Mock, patch
from django.utils import timezone
from decimal import Decimal
from digital_prices.api import APIError
from digital_prices.models import Integration
from telegram_bots.client import TelegramError
from django.test import TestCase
from .test_checkout import ShopFixture
from .models import BalanceHold, PurchaseIntent, ResultDelivery
from . import execution


class RecoveryTests(ShopFixture, TestCase):
    def test_timeout_reuses_exact_body_and_client_id_after_lookup(self):
        intent = self.reserved()
        Integration.objects.update_or_create(pk=1, defaults={'enabled': True, 'encrypted_key': 'synthetic'})
        client = Mock()
        client.purchase.side_effect = [APIError('network_timeout', 15),
            self.response(intent, status='accepted', line_status='queued', result={})]
        client.orders.return_value = {'orders': [], 'page': 1, 'has_more': False}
        factory = Mock(return_value=client)
        with patch('integrations.crypto.decrypt_secret', return_value='synthetic-key'):
            execution.process_one(client_factory=factory)
            intent.refresh_from_db()
            self.assertEqual(intent.state, 'uncertain')
            first = client.purchase.call_args.args[0]
            intent.next_at = timezone.now()
            intent.save(update_fields=['next_at'])
            execution.process_one(client_factory=factory)
        self.assertEqual(client.purchase.call_count, 2)
        self.assertEqual(first, client.purchase.call_args.args[0])
        client.orders.assert_called_once_with(client_order_id=intent.client_order_id)
        self.assertEqual(PurchaseIntent.objects.count(), 1)
        self.assertEqual(BalanceHold.objects.count(), 1)
        self.assertEqual(self.supplier.balance, Decimal('900'))

    def test_existing_order_is_read_without_second_post(self):
        intent = self.reserved()
        intent.state = 'uncertain'
        intent.save(update_fields=['state'])
        Integration.objects.update_or_create(pk=1, defaults={'enabled': True, 'encrypted_key': 'synthetic'})
        client = Mock()
        response = self.response(intent, status='accepted', line_status='queued', result={})
        client.orders.return_value = {'orders': [{'order_id': response['order_id']}], 'page': 1, 'has_more': False}
        client.order.return_value = response
        with patch('integrations.crypto.decrypt_secret', return_value='synthetic-key'):
            execution.process_one(client_factory=Mock(return_value=client))
        client.purchase.assert_not_called()
        self.assertEqual(self.supplier.balance, Decimal('900'))

    def test_idempotency_conflict_does_not_release_hold_or_create_new_id(self):
        intent = self.reserved()
        Integration.objects.update_or_create(pk=1, defaults={'enabled': True, 'encrypted_key': 'synthetic'})
        client = Mock()
        client.purchase.side_effect = APIError('idempotency_conflict')
        with patch('integrations.crypto.decrypt_secret', return_value='synthetic-key'):
            execution.process_one(client_factory=Mock(return_value=client))
        intent.refresh_from_db()
        self.assertEqual(intent.state, 'review')
        self.assertEqual(BalanceHold.objects.get().remaining, Decimal('120'))
        self.assertEqual(PurchaseIntent.objects.count(), 1)

    def test_lost_send_does_not_repeat_codes(self):
        intent = self.claim(self.reserved())
        execution.reconcile(intent, self.response(intent))
        client = Mock()
        client.message.side_effect = TelegramError('network', uncertain=True)
        execution.publish_result(client)
        self.assertEqual(ResultDelivery.objects.get().state, 'uncertain')
        execution.recover_results()
        execution.publish_result(client)
        self.assertEqual(client.message.call_count, 1)

    def test_successful_send_remembers_message_id_and_clears_outbox_secret(self):
        intent = self.claim(self.reserved())
        execution.reconcile(intent, self.response(intent))
        client = Mock()
        client.message.return_value = {'message_id': 777}
        execution.publish_result(client)
        row = ResultDelivery.objects.get()
        self.assertEqual(row.message_id, 777)
        self.assertEqual(row.state, 'sent')
        self.assertEqual(row.encrypted_text, '')
        execution.publish_result(client)
        self.assertEqual(client.message.call_count, 1)

    def test_changed_binding_blocks_result_delivery(self):
        intent = self.claim(self.reserved())
        execution.reconcile(intent, self.response(intent))
        self.binding.buyer = None
        self.binding.save(update_fields=['buyer'])
        client = Mock()
        execution.publish_result(client)
        client.message.assert_not_called()
        self.assertEqual(ResultDelivery.objects.get().state, 'review')

    def test_changed_price_requires_a_new_confirmation_and_preserves_composition(self):
        intent = self.reserved()
        Integration.objects.update_or_create(pk=1, defaults={'enabled': True, 'encrypted_key': 'synthetic'})
        client = Mock()
        client.purchase.side_effect = APIError('price_changed')
        with patch('integrations.crypto.decrypt_secret', return_value='synthetic-key'):
            execution.process_one(client_factory=Mock(return_value=client))
        intent.refresh_from_db()
        self.assertEqual(intent.state, 'failed')
        self.assertEqual(BalanceHold.objects.get().state, 'released')
        from .models import Cart
        restored = Cart.objects.exclude(state='closed').get()
        self.assertEqual(restored.lines.count(), 1)
        self.assertEqual(restored.state, 'open')
        self.assertFalse(restored.quote_id)
        self.assertEqual(PurchaseIntent.objects.count(), 1)
