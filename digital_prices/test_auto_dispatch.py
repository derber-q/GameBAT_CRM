"""Авторассылка: персональные группы, полнота обновления и защита от дублей.

Внешний Telegram и генерация картинок подменены; рабочие ключи не используются.
"""
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch
import uuid
from itertools import count

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from telegram_bots.client import TelegramError
from telegram_bots.models import StaffBot, StaffBotAccess
from digital_sales.models import Buyer, BuyerBalanceChat, DigitalBot, Notification, Supplier
from .dispatch import enqueue_after_sync, publish_one, recover_dispatches, sync_failed, queue_current_pins, _public_only
from .models import BuyerPriceDispatch, CatalogState, Integration, PriceBundle, PricePage, SyncJob


class AutoDispatchTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(username='auto-prices-owner')
        self.staff = StaffBot.objects.create(enabled=True)
        self.access = StaffBotAccess.objects.create(bot=self.staff, user=self.user, telegram_user_id=77, allowed=True)
        self.owner = uuid.uuid4()
        self.bot, _ = DigitalBot.objects.get_or_create(pk=1)
        self.bot.enabled, self.bot.lease_owner = True, self.owner
        self.bot.lease_until = timezone.now() + timedelta(minutes=3)
        self.bot.save()
        self.config, _ = Integration.objects.get_or_create(pk=1)
        self.config.enabled, self.config.error_category, self.config.manual_sheet_error_category = True, '', ''
        self.config.save()
        self.at = timezone.now()
        state, _ = CatalogState.objects.get_or_create(pk=1)
        state.source_at = self.at
        state.save()
        self.job = SyncJob.objects.create(state='done', active=False, run_after=self.at, finished_at=self.at)
        self.buyer = Buyer.objects.create(name='Подписки GNS')
        self.chat = BuyerBalanceChat.objects.create(chat_id=-100123, title='Покупатель GNS', buyer=self.buyer)
        self.client = Mock()
        self.message_ids = count(101)
        self.client.call.side_effect = self.fake_call

    def fake_call(self, method, *args, **kwargs):
        if method == 'getChatMember':
            return {'status': 'administrator', 'can_pin_messages': True}
        if method in ('pinChatMessage', 'unpinChatMessage'):
            return True
        return {'message_id': next(self.message_ids)}

    def bundle(self, **kwargs):
        buyer = kwargs.get('buyer', self.buyer)
        bundle = PriceBundle.objects.create(actor=self.user, buyer=buyer, buyer_name_snapshot=buyer.name,
            source_at=self.at, revision=1, public_snapshot={'page_titles': ['Главная', 'Steam — Коды пополнения'],
                'rows': [{'family': 'PlayStation', 'section': 'services', 'price': '150 ₽'}]})
        for index in (1, 2):
            PricePage.objects.create(bundle=bundle, index=index, filename=f'price_{index}.png',
                png=b'\x89PNG\r\n\x1a\n', row_count=1, width=800, height=900)
        return bundle

    def publish(self):
        with patch('digital_prices.bundles.generate_bundle', side_effect=self.bundle):
            return publish_one(self.client, owner=self.owner, bot_id=123)

    def sent(self):
        return [call for call in self.client.call.call_args_list if call.args[0] in ('sendPhoto', 'sendDocument')]

    def complete(self):
        for _ in range(20):
            if not self.publish():
                return
        self.fail('Комплект не завершился')

    def test_successful_update_enqueues_once_for_each_bound_buyer(self):
        other = Buyer.objects.create(name='Подписки Играть')
        BuyerBalanceChat.objects.create(chat_id=-100124, title='Играть', buyer=other)
        enqueue_after_sync(self.job)
        enqueue_after_sync(self.job)
        self.assertEqual(BuyerPriceDispatch.objects.count(), 2)
        self.assertEqual(set(BuyerPriceDispatch.objects.values_list('buyer_id', flat=True)), {self.buyer.pk, other.pk})

    def test_failed_or_partial_update_never_enqueues_and_notifies_staff(self):
        self.job.summary = {'manual_sheet': {'error': 'sheet_network'}}
        enqueue_after_sync(self.job)
        self.assertFalse(BuyerPriceDispatch.objects.exists())
        self.assertEqual(Notification.objects.count(), 1)
        self.assertIn('не отправлены', Notification.objects.get().text)
        self.job.state = 'error'
        enqueue_after_sync(self.job)
        sync_failed(self.job)
        self.assertEqual(Notification.objects.count(), 1)

    def test_every_page_has_own_caption_and_current_buyer(self):
        enqueue_after_sync(self.job)
        self.complete()
        row = BuyerPriceDispatch.objects.get()
        self.assertEqual(row.state, 'done')
        self.assertEqual(len(self.sent()), 2)
        captions = [call.args[1]['caption'] for call in self.sent()]
        self.assertIn('Главная', captions[0])
        self.assertIn('Steam', captions[1])
        for call in self.sent():
            self.assertEqual(call.args[1]['chat_id'], self.chat.pk)
            self.assertIn('Для: Подписки GNS', call.args[1]['caption'])
            self.assertIn('новый аккаунт: +150 ₽', call.args[1]['caption'])
            self.assertIn('@GameBAT_Store', call.args[1]['caption'])
        self.publish()
        self.assertEqual(len(self.sent()), 2)

    def new_update(self):
        self.at += timedelta(seconds=1)
        state = CatalogState.objects.get(pk=1)
        state.source_at = self.at
        state.save()
        self.job = SyncJob.objects.create(state='done', active=False, run_after=self.at, finished_at=self.at)
        enqueue_after_sync(self.job)

    def test_new_complete_bundle_is_pinned_before_old_is_unpinned(self):
        enqueue_after_sync(self.job)
        self.complete()
        old = BuyerPriceDispatch.objects.get()
        old_ids = set(old.deliveries.values_list('message_id', flat=True))
        self.assertEqual(set(old.deliveries.values_list('state', flat=True)), {'pinned'})
        self.client.call.reset_mock()
        self.new_update()
        self.complete()
        methods = [call.args[0] for call in self.client.call.call_args_list]
        self.assertLess(max(i for i, method in enumerate(methods) if method == 'sendPhoto'), methods.index('pinChatMessage'))
        self.assertLess(max(i for i, method in enumerate(methods) if method == 'pinChatMessage'), methods.index('unpinChatMessage'))
        self.assertEqual({call.args[1]['message_id'] for call in self.client.call.call_args_list
                          if call.args[0] == 'unpinChatMessage'}, old_ids)
        self.assertEqual(set(old.deliveries.values_list('state', flat=True)), {'unpinned'})
        self.assertNotIn('unpinAllChatMessages', methods)

    def test_existing_current_price_can_be_pinned_without_resending(self):
        enqueue_after_sync(self.job)
        self.publish()
        self.publish()
        row = BuyerPriceDispatch.objects.get()
        row.state = 'done'  # Комплект, отправленный прежней версией без закрепов.
        row.save()
        self.assertEqual(queue_current_pins(actor=self.user), [row.pk])
        self.complete()
        self.assertEqual(len(self.sent()), 2)
        self.assertEqual(queue_current_pins(actor=self.user), [])

    def test_failed_new_delivery_preserves_previous_pins(self):
        enqueue_after_sync(self.job)
        self.complete()
        old = BuyerPriceDispatch.objects.get()
        self.new_update()
        self.client.call.reset_mock()
        self.client.call.side_effect = lambda method, *args, **kwargs: self._timeout() if method == 'sendPhoto' else self.fake_call(method, *args, **kwargs)
        self.publish()
        self.assertEqual(set(old.deliveries.values_list('state', flat=True)), {'pinned'})
        self.assertFalse(any(call.args[0] == 'unpinChatMessage' for call in self.client.call.call_args_list))

    def test_pin_permission_failure_does_not_resend_photos(self):
        enqueue_after_sync(self.job)
        self.publish()
        self.publish()
        self.client.call.side_effect = lambda method, *args, **kwargs: ({'status': 'member'}
            if method == 'getChatMember' else self.fake_call(method, *args, **kwargs))
        self.publish()
        self.assertEqual(BuyerPriceDispatch.objects.get().state, 'error')
        self.assertIn('закреп', Notification.objects.get().text)
        self.publish()
        self.assertEqual(len(self.sent()), 2)

    def test_pin_timeout_retries_same_message_without_resending_image(self):
        enqueue_after_sync(self.job)
        self.publish()
        self.publish()
        def timeout_pin(method, *args, **kwargs):
            if method == 'pinChatMessage':
                return self._timeout()
            return self.fake_call(method, *args, **kwargs)
        self.client.call.side_effect = timeout_pin
        self.publish()
        row = BuyerPriceDispatch.objects.get()
        self.assertEqual(row.state, 'queued')
        row.next_attempt_at = timezone.now() - timedelta(seconds=1)
        row.save()
        self.client.call.side_effect = self.fake_call
        self.publish()
        pins = [call.args[1]['message_id'] for call in self.client.call.call_args_list if call.args[0] == 'pinChatMessage']
        self.assertEqual(pins, [101, 101])
        self.assertEqual(len(self.sent()), 2)

    def test_unknown_delivery_is_not_repeated(self):
        enqueue_after_sync(self.job)
        self.client.call.side_effect = lambda method, *args, **kwargs: ({'status': 'administrator'}
            if method == 'getChatMember' else self._timeout())
        self.publish()
        self.assertEqual(BuyerPriceDispatch.objects.get().state, 'uncertain')
        self.publish()
        self.assertEqual(len(self.sent()), 1)
        self.assertEqual(Notification.objects.count(), 1)

    def _timeout(self):
        raise TelegramError('timeout', uncertain=True)

    def test_recovery_preserves_known_pages_and_blocks_unknown(self):
        enqueue_after_sync(self.job)
        self.publish()
        row = BuyerPriceDispatch.objects.get()
        page = row.deliveries.get(state='pending')
        page.state = 'sending'
        page.save()
        row.state = 'working'
        row.save()
        recover_dispatches()
        row.refresh_from_db()
        self.assertEqual(row.state, 'uncertain')
        self.assertEqual(row.deliveries.filter(state='done').count(), 1)
        self.publish()
        self.assertEqual(len(self.sent()), 1)

    def test_changed_binding_or_supplier_group_is_never_sent(self):
        for reason in ('binding', 'supplier'):
            with self.subTest(reason=reason):
                enqueue_after_sync(self.job)
                if reason == 'binding':
                    self.chat.buyer = None
                    self.chat.save()
                else:
                    self.chat.buyer = self.buyer
                    self.chat.save()
                    Supplier.objects.create(name='Protected source', chat_ids=[self.chat.pk])
                self.publish()
                self.assertFalse(self.sent())
                row = BuyerPriceDispatch.objects.get()
                self.assertEqual(row.state, 'skipped')
                row.state = 'queued'
                row.save()

    def test_new_update_blocks_old_pages(self):
        enqueue_after_sync(self.job)
        self.publish()
        SyncJob.objects.create(state='pending', active=True, run_after=timezone.now())
        self.publish()
        self.assertEqual(BuyerPriceDispatch.objects.get().state, 'skipped')
        self.assertEqual(len(self.sent()), 1)

    def test_public_snapshot_cannot_contain_internal_fields_or_names(self):
        for key in ('purchase_cost', 'markup', 'name'):
            with self.assertRaises(TelegramError):
                _public_only(SimpleNamespace(public_snapshot={'rows': [{key: 'PanYanStore'}]}))

    def test_revoked_staff_authorization_stops_delivery(self):
        enqueue_after_sync(self.job)
        self.access.allowed = False
        self.access.save()
        self.publish()
        self.assertFalse(self.sent())
        self.assertEqual(BuyerPriceDispatch.objects.get().state, 'error')
