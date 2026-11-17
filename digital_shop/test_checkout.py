"""Финансовые сценарии для отдельной тестовой БД; сеть и ключи всегда фиктивные."""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock, patch
import uuid
from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError, PermissionDenied
from django.test import TestCase
from django.utils import timezone
from digital_prices.models import Product, CatalogState, BuyerMarkup
from digital_sales.models import Buyer, Supplier, BuyerBalanceChat, DigitalBot, SupplierPurchase, DigitalOrder
from digital_sales.services import move_balance, cancel_digital_sale
from digital_sales.crypto import decrypt
from .models import ShopConfig, ShopChat, BalanceHold, PurchaseIntent, ResultDelivery
from .access import Access, member
from .catalog import products
from . import services, execution


class ShopFixture:
    def setUp(self):
        from catalog.models import SystemProduct
        SystemProduct.objects.get_or_create(kind='DIGITAL_PRODUCT')
        self.enterContext(patch('digital_sales.crypto.cipher', return_value=Fernet(Fernet.generate_key())))
        self.user = get_user_model().objects.create_superuser(username='shop-synthetic', password=None)
        self.buyer = Buyer.objects.create(name='Покупатель')
        self.supplier = Supplier.objects.create(name='Внутренний поставщик')
        self.binding = BuyerBalanceChat.objects.create(chat_id=-9001, title='Группа', buyer=self.buyer)
        ShopChat.objects.create(binding=self.binding, enabled=True)
        self.config = ShopConfig.objects.create(enabled=True, purchases_enabled=True, actor=self.user, supplier=self.supplier)
        DigitalBot.objects.update_or_create(pk=1, defaults={'enabled': True})
        CatalogState.objects.update_or_create(pk=1, defaults={'revision': 1, 'source_at': timezone.now()})
        self.product = Product.objects.create(external_id='pv2_synthetic_code', api_version=2, source_name='Тестовая игра',
            source_type='code', platform='steam', region='us', currency='RUB', purchase_cost=100, markup=20,
            availability='yes', fulfillment='automatic', requirements={'account': False},
            quantity_limits={'min_quantity': 1, 'max_quantity': 20, 'quantity_step': 1},
            confirmed_at=timezone.now(), last_seen_at=timezone.now())
        move_balance(actor=self.user, buyer_id=self.buyer.pk, amount='300', kind='opening', reason='Синтетический начальный баланс')
        move_balance(actor=self.user, supplier_id=self.supplier.pk, amount='1000', kind='opening', reason='Синтетический начальный баланс')
        self.access = Access(self.binding.pk, self.buyer.pk, 1234)

    def quote(self, cart, *, adjustment=0):
        fake = Mock()
        def response(body):
            values = [{'id': row['id'], 'price': Decimal(100) * row['qty']} for row in body['items']]
            return {'ok': True, 'quote_id': 'qv2_synthetic', 'expires_at': int((timezone.now() + timedelta(minutes=4)).timestamp()),
                'currency': 'rub', 'total': sum(v['price'] for v in values) + adjustment,
                'lines': values, 'adjustment': adjustment}
        fake.quote.side_effect = response
        cart = services.prepare_credentials(self.access_for(cart), cart.pk, cart.revision)
        return services.quote_cart(self.access_for(cart), cart.pk, cart.revision, fake)

    def access_for(self, cart):
        return Access(cart.chat_id, cart.buyer_id, cart.telegram_user_id)

    def prepared(self, user_id=1234, quantity=1):
        access = Access(self.binding.pk, self.buyer.pk, user_id)
        cart = services.open_cart(access)
        cart = services.add(access, cart.pk, cart.revision, self.product.pk)
        if quantity > 1:
            for _ in range(quantity - 1):
                cart = services.change(access, cart.pk, cart.revision, cart.lines.get().pk, delta=1)
        return self.quote(cart)

    def reserved(self, user_id=1234):
        cart = self.prepared(user_id)
        return services.confirm(self.access_for(cart), cart.pk, cart.revision)

    def response(self, intent, *, status='completed', line_status='completed', result=None):
        line = intent.lines.get()
        return {'ok': True, 'order_id': 'ov2_synthetic_' + intent.pk.hex, 'client_order_id': intent.client_order_id,
            'currency': 'rub', 'status': status, 'quoted_total': intent.cart.quoted_total, 'charged_total': Decimal('100'),
            'unconfirmed_items': [], 'items': [{'line_id': line.line_id, 'purchase_id': 90000 + line.pk,
                'status': line_status, 'paid': False, 'price': Decimal('100'), 'currency': 'rub',
                'result': {'codes': ['SYNTHETIC-CODE']} if result is None else result}]}

    def claim(self, intent):
        intent.owner, intent.lease_until = uuid.uuid4(), timezone.now() + timedelta(minutes=3)
        intent.save(update_fields=['owner', 'lease_until'])
        return intent


class CheckoutTests(ShopFixture, TestCase):
    def test_checkout_error_is_visible_even_if_callback_has_expired(self):
        from .models import ChatEvent
        from .telegram import process_one
        from digital_sales.crypto import encrypt
        from digital_prices.api import APIError
        from telegram_bots.client import TelegramError
        event = ChatEvent.objects.create(update_id=901, encrypted_payload=encrypt({
            'callback_query': {'id': 'expired', 'data': 's:cart:1:q:',
                               'message': {'chat': {'id': self.binding.pk}}}}))
        client = Mock()
        client.call.side_effect = TelegramError('expired')
        with patch('digital_shop.telegram.handle', side_effect=APIError('invalid_quote')):
            self.assertTrue(process_one(client))
        client.message.assert_called_once()
        self.assertEqual(client.message.call_args.args[0], self.binding.pk)
        self.assertIn('покупка не запускалась', client.message.call_args.args[1])
        event.refresh_from_db()
        self.assertEqual((event.state, event.encrypted_payload), ('rejected', ''))

    def test_account_mode_is_explicit_and_credentials_are_never_reused(self):
        self.product.fulfillment = 'manual'
        self.product.requirements = {'account': True, 'account_modes': ['new', 'existing'],
                                    'account_format': 'credentials'}
        self.product.save()
        cart = services.open_cart(self.access)
        with self.assertRaises(ValidationError):
            services.add(self.access, cart.pk, cart.revision, self.product.pk)
        cart = services.add(self.access, cart.pk, cart.revision, self.product.pk, mode='existing')
        first = cart.lines.get()
        cart = services.add(self.access, cart.pk, cart.revision, self.product.pk, mode='new')
        second = cart.lines.exclude(pk=first.pk).get()
        self.assertEqual((first.account_mode, second.account_mode), ('existing', 'new'))
        self.assertNotEqual(first.account_key, second.account_key)
        second.account_mode = 'unknown'
        second.save(update_fields=['account_mode'])
        with self.assertRaises(ValidationError):
            services.prepare_credentials(self.access, cart.pk, cart.revision)
        second.account_mode = 'existing'
        second.account_key = first.account_key
        second.save(update_fields=['account_mode', 'account_key'])
        with self.assertRaises(ValidationError):
            services.validate_accounts(list(cart.lines.select_related('product')))
        for options in ({'mode': 'unknown'}, {'mode': 'existing', 'account_key': first.account_key}):
            with self.subTest(options=options), self.assertRaises(ValidationError):
                services.add(self.access, cart.pk, cart.revision, self.product.pk, **options)
        self.product.requirements['account_modes'] = ['new']
        self.product.save()
        self.assertEqual([p.pk for p in products(self.buyer.pk)], [self.product.pk])

    def test_new_account_quote_uses_exact_buyer_fee_without_supplier_fee_twice(self):
        self.product.fulfillment = 'manual'
        self.product.requirements = {'account': True, 'account_modes': ['existing', 'new']}
        self.product.save()
        self.buyer.name = 'Подписки Играть'
        self.buyer.save()
        cart = services.open_cart(self.access)
        cart = services.add(self.access, cart.pk, cart.revision, self.product.pk, mode='new')
        cart = services.prepare_credentials(self.access, cart.pk, cart.revision)
        self.assertEqual(cart.credential_groups[0]['fields'], [])
        api = Mock()
        def quote(body):
            adjustment = 40 if any(a['mode'] == 'new' for a in body['accounts']) else 0
            return {'quote_id': 'qv2_synthetic', 'expires_at': int((timezone.now() + timedelta(minutes=4)).timestamp()),
                    'currency': 'rub', 'total': Decimal(100) + adjustment, 'adjustment': adjustment,
                    'lines': [{'id': body['items'][0]['id'], 'price': Decimal(100)}]}
        api.quote.side_effect = quote
        cart = services.quote_cart(self.access, cart.pk, cart.revision, api)
        self.assertEqual(cart.quoted_total, Decimal('140'))
        self.assertEqual(cart.client_total, Decimal('220'))  # 100 + 20 + согласованные 100, без повторных 40.
        self.assertEqual(api.quote.call_args.args[0]['accounts'][0]['mode'], 'new')
        self.assertFalse(PurchaseIntent.objects.exists())
        self.buyer.name = 'Подписки GNS'
        self.buyer.save()
        with self.assertRaises(ValidationError):
            services.confirm(self.access, cart.pk, cart.revision)
        cart = services.quote_cart(self.access, cart.pk, cart.revision, api)
        self.assertEqual(cart.client_total, Decimal('270'))
        intent = services.confirm(self.access, cart.pk, cart.revision)
        import json
        self.assertEqual(json.loads(decrypt(intent.encrypted_body)['wire'])['accounts'], [])
        self.assertEqual(intent.lines.get().client_price, Decimal('270'))
        self.assertEqual(intent.lines.get().cost, Decimal('140'))
        api.purchase.assert_not_called()

    def test_new_only_xbox_never_sends_unsupported_existing_mode(self):
        self.product.fulfillment = 'manual'
        self.product.requirements = {'account': True, 'account_modes': ['new']}
        self.product.save()
        cart = services.open_cart(self.access)
        cart = services.add(self.access, cart.pk, cart.revision, self.product.pk)
        self.assertEqual(cart.lines.get().account_mode, 'new')
        cart = services.prepare_credentials(self.access, cart.pk, cart.revision)
        api = Mock()
        api.quote.return_value = {'quote_id': 'qv2_synthetic',
            'expires_at': int((timezone.now() + timedelta(minutes=4)).timestamp()),
            'currency': 'rub', 'total': Decimal(140), 'adjustment': 40,
            'lines': [{'id': 'l' + str(cart.lines.get().pk), 'price': Decimal(100)}]}
        services.quote_cart(self.access, cart.pk, cart.revision, api)
        self.assertEqual(api.quote.call_count, 1)
        self.assertEqual(api.quote.call_args.args[0]['accounts'][0]['mode'], 'new')

    def test_existing_selection_immediately_requests_fresh_free_form_data(self):
        from .telegram import add_product
        self.product.fulfillment = 'manual'
        self.product.requirements = {'account': True, 'account_modes': ['existing', 'new']}
        self.product.save()
        cart = services.open_cart(self.access)
        with patch('digital_shop.telegram.show') as show:
            add_product(Mock(), self.access, cart, str(self.product.pk))
            self.assertIn('На какой аккаунт', show.call_args.args[2])
            self.assertFalse(cart.lines.exists())
        with patch('digital_shop.telegram.request_input') as prompt:
            add_product(Mock(), self.access, cart, str(self.product.pk) + '.existing')
            self.assertEqual(prompt.call_args.args[2], 'credentials')
            self.assertIn('свободной форме', prompt.call_args.args[3])
        self.assertEqual(cart.lines.get().account_mode, 'existing')
        self.assertEqual(services.groups_for(list(cart.lines.select_related('product')))[0]['fields'], ['manual_credentials'])

    def test_new_selection_calculates_without_requesting_credentials(self):
        from .telegram import add_product
        self.product.fulfillment = 'manual'
        self.product.requirements = {'account': True, 'account_modes': ['existing', 'new']}
        self.product.save()
        cart = services.open_cart(self.access)
        with patch('digital_shop.telegram.request_input') as prompt, patch('digital_shop.telegram.calculated') as calculated:
            add_product(Mock(), self.access, cart, str(self.product.pk) + '.new')
            prompt.assert_not_called()
            calculated.assert_called_once()

    def test_close_unsubmitted_cart_cannot_start_or_cancel_purchase(self):
        from .admin_services import close_unsubmitted_cart
        cart = services.open_cart(self.access)
        cart = services.add(self.access, cart.pk, cart.revision, self.product.pk)
        old_revision = cart.revision
        closed = close_unsubmitted_cart(actor=self.user, cart_id=cart.pk, reason='Уже оформлено менеджером')
        self.assertEqual(closed.state, 'closed')
        self.assertGreater(closed.revision, old_revision)
        self.assertEqual(closed.lines.count(), 1)
        self.assertFalse(PurchaseIntent.objects.filter(cart=closed).exists())
        self.assertEqual(self.buyer.balance, Decimal('300'))
        with self.assertRaises(PermissionDenied):
            services.prepare_credentials(self.access, closed.pk, closed.revision)
        intent = self.reserved(user_id=999)
        with self.assertRaises(ValidationError):
            close_unsubmitted_cart(actor=self.user, cart_id=intent.cart_id, reason='Запрещено')
        intent.refresh_from_db()
        self.assertEqual(intent.state, 'queued')
        self.assertEqual(BalanceHold.objects.get().remaining, Decimal('120'))

    def test_reserve_does_not_debit_and_repeated_confirm_is_idempotent(self):
        cart = self.prepared()
        intent = services.confirm(self.access, cart.pk, cart.revision)
        again = services.confirm(self.access, cart.pk, cart.revision)
        self.assertEqual(intent.pk, again.pk)
        self.assertEqual(PurchaseIntent.objects.count(), 1)
        self.assertEqual(BalanceHold.objects.count(), 1)
        self.assertEqual(self.buyer.balance, Decimal('300'))
        self.assertEqual(services.available_balance(self.buyer), Decimal('180'))
        self.assertEqual(self.supplier.balance, Decimal('1000'))
        self.assertEqual(decrypt(intent.encrypted_body)['wire'].count(intent.client_order_id), 1)

    def test_group_members_share_cart_and_keep_separate_confirmed_orders(self):
        first_cart = services.open_cart(self.access)
        another = Access(self.binding.pk, self.buyer.pk, 999)
        self.assertEqual(services.open_cart(another).pk, first_cart.pk)
        first_cart = services.add(another, first_cart.pk, first_cart.revision, self.product.pk)
        self.assertEqual(services.owned(self.access, first_cart.pk).lines.count(), 1)
        services.change(self.access, first_cart.pk, first_cart.revision, first_cart.lines.get().pk, remove=True)
        first, second = self.reserved(1), self.reserved(2)
        self.assertNotEqual(first.cart_id, second.cart_id)
        self.assertEqual(services.available_balance(self.buyer), Decimal('60'))
        third = self.prepared(3)
        services.confirm(self.access_for(third), third.pk, third.revision)
        self.assertEqual(BalanceHold.objects.count(), 3)
        self.assertEqual(services.available_balance(self.buyer), Decimal('-60'))
        self.assertEqual(self.buyer.balance, Decimal('300'))

    def test_negative_balances_allow_order_and_single_completion_debit(self):
        move_balance(actor=self.user, buyer_id=self.buyer.pk, amount='-400', kind='adjustment',
                     reason='Синтетический отрицательный баланс покупателя')
        move_balance(actor=self.user, supplier_id=self.supplier.pk, amount='-1100', kind='adjustment',
                     reason='Синтетический отрицательный внутренний баланс поставщика')
        intent = self.claim(self.reserved())
        self.assertEqual(self.buyer.balance, Decimal('-100'))
        self.assertEqual(services.available_balance(self.buyer), Decimal('-220'))
        response = self.response(intent)
        execution.reconcile(intent, response)
        self.assertEqual(self.buyer.balance, Decimal('-220'))
        self.assertEqual(self.supplier.balance, Decimal('-200'))
        self.assertTrue(DigitalOrder.objects.get().sale.is_completed)
        execution.reconcile(self.claim(intent), response)
        self.assertEqual(self.buyer.balance, Decimal('-220'))
        self.assertEqual(self.supplier.balance, Decimal('-200'))

    def test_zero_balance_does_not_block_confirmation(self):
        move_balance(actor=self.user, buyer_id=self.buyer.pk, amount='-300', kind='adjustment',
                     reason='Синтетический нулевой баланс')
        intent = self.reserved()
        self.assertEqual(intent.state, 'queued')
        self.assertEqual(self.buyer.balance, Decimal('0'))
        self.assertEqual(services.available_balance(self.buyer), Decimal('-120'))

    def test_old_revision_foreign_user_and_foreign_chat_are_rejected(self):
        cart = self.prepared()
        for access in (Access(cart.chat_id, 999, 99), Access(-9999, cart.buyer_id, cart.telegram_user_id)):
            with self.subTest(access=access), self.assertRaises(PermissionDenied):
                services.confirm(access, cart.pk, cart.revision)
        with self.assertRaises(ValidationError):
            services.confirm(self.access, cart.pk, cart.revision - 1)

    def test_another_group_member_can_confirm_once_and_next_cart_reuses_menu(self):
        cart = self.prepared()
        cart.menu_message_id = 701
        cart.save(update_fields=['menu_message_id'])
        another = Access(cart.chat_id, cart.buyer_id, 999)
        intent = services.confirm(another, cart.pk, cart.revision)
        self.assertEqual(services.confirm(self.access, cart.pk, cart.revision).pk, intent.pk)
        following = services.open_cart(another)
        self.assertNotEqual(following.pk, cart.pk)
        self.assertEqual(following.menu_message_id, 701)
        self.assertEqual(services.open_cart(self.access).pk, following.pk)

    def test_credentials_reply_is_shared_but_only_current_prompt_is_accepted(self):
        self.product.fulfillment = 'manual'
        self.product.requirements = {'account': True, 'account_modes': ['existing'], 'account_format': 'credentials'}
        self.product.save()
        cart = services.open_cart(self.access)
        cart = services.add(self.access, cart.pk, cart.revision, self.product.pk)
        cart = services.prepare_credentials(self.access, cart.pk, cart.revision)
        cart.prompt_message_id = 701
        cart.save(update_fields=['prompt_message_id'])
        another = Access(cart.chat_id, cart.buyer_id, 999)
        services.save_credentials(another, cart.pk, 701, '[1]\nlogin=example\npassword=fake')
        with self.assertRaises(ValidationError):
            services.save_credentials(another, cart.pk, 700, '[1]\nlogin=example\npassword=fake')

    def test_expiry_fee_change_and_catalog_revision_require_new_confirmation(self):
        cart = self.prepared()
        cart.quote_expires_at = timezone.now() - timedelta(seconds=1)
        cart.save(update_fields=['quote_expires_at'])
        with self.assertRaises(ValidationError):
            services.confirm(self.access, cart.pk, cart.revision)
        cart = self.quote(cart)
        self.product.markup = 21
        self.product.save(update_fields=['markup'])
        with self.assertRaises(ValidationError):
            services.confirm(self.access, cart.pk, cart.revision)
        self.product.markup = 20
        self.product.save(update_fields=['markup'])
        state = CatalogState.objects.get(pk=1)
        state.revision += 1
        state.save(update_fields=['revision'])
        with self.assertRaises(ValidationError):
            services.confirm(self.access, cart.pk, cart.revision)

    def test_zero_override_and_general_fallback_and_no_markup_visibility(self):
        self.assertEqual(len(products(self.buyer.pk)), 1)
        override = BuyerMarkup.objects.create(buyer=self.buyer, product=self.product, markup=0, edited_by=self.user)
        cart = self.prepared()
        self.assertEqual(cart.client_total, Decimal('100'))
        override.markup = None
        override.save()
        cart = self.quote(cart)
        self.assertEqual(cart.client_total, Decimal('120'))
        self.product.markup = None
        self.product.save(update_fields=['markup'])
        self.assertEqual(products(self.buyer.pk), [])

    def test_api_cost_unavailable_unknown_currency_or_unconfirmed_id_is_not_buyable(self):
        for fields in ({'availability': 'no'}, {'currency': 'USD'}, {'api_version': 0},
                       {'mapping_issue': 'ambiguous'}, {'requires_review': True}, {'fulfillment': ''}):
            with self.subTest(fields=fields):
                original = {key: getattr(self.product, key) for key in fields}
                for key, value in fields.items():
                    setattr(self.product, key, value)
                self.product.save(update_fields=list(fields))
                self.assertEqual(products(self.buyer.pk), [])
                for key, value in original.items():
                    setattr(self.product, key, value)
                self.product.save(update_fields=list(fields))

    def test_accepted_is_supplier_obligation_but_not_customer_payment(self):
        intent = self.claim(self.reserved())
        execution.reconcile(intent, self.response(intent, status='accepted', line_status='queued', result={}))
        self.assertEqual(self.buyer.balance, Decimal('300'))
        self.assertEqual(self.supplier.balance, Decimal('900'))
        self.assertEqual(SupplierPurchase.objects.count(), 1)
        self.assertFalse(DigitalOrder.objects.get().sale_id)
        self.assertEqual(services.available_balance(self.buyer), Decimal('180'))

    def test_completed_item_posts_once_and_does_not_double_charge_supplier(self):
        intent = self.claim(self.reserved())
        response = self.response(intent)
        execution.reconcile(intent, response)
        self.assertEqual(self.buyer.balance, Decimal('180'))
        self.assertEqual(self.supplier.balance, Decimal('900'))
        self.assertEqual(ResultDelivery.objects.count(), 1)
        order = DigitalOrder.objects.get()
        self.assertTrue(order.sale.is_completed)
        self.assertEqual(order.sale.custom_items.get().article_snapshot, '')
        self.assertEqual(BalanceHold.objects.get().remaining, 0)
        intent.refresh_from_db()
        self.assertEqual(intent.encrypted_body, '')
        execution.reconcile(self.claim(intent), response)
        self.assertEqual(self.buyer.balance, Decimal('180'))
        self.assertEqual(self.supplier.balance, Decimal('900'))
        self.assertEqual(ResultDelivery.objects.count(), 1)
        with self.assertRaises(ValidationError):
            cancel_digital_sale(actor=self.user, sale_id=order.sale_id, comment='Без подтверждения возврата')

    def test_unsafe_result_holds_customer_money_and_never_becomes_outbox(self):
        intent = self.claim(self.reserved())
        execution.reconcile(intent, self.response(intent, result={'data': 'PanYanStore закупка 100 ₽'}))
        self.assertEqual(self.supplier.balance, Decimal('900'))
        self.assertEqual(self.buyer.balance, Decimal('300'))
        self.assertEqual(ResultDelivery.objects.count(), 0)
        intent.refresh_from_db()
        self.assertEqual(intent.state, 'review')
        self.assertEqual(BalanceHold.objects.get().remaining, Decimal('120'))

    def test_cancelled_item_is_not_a_proven_refund(self):
        intent = self.claim(self.reserved())
        execution.reconcile(intent, self.response(intent, status='finished', line_status='cancelled', result={}))
        self.assertEqual(self.supplier.balance, Decimal('900'))
        self.assertEqual(BalanceHold.objects.get().remaining, Decimal('120'))
        from .admin_services import confirm_refund
        line = intent.lines.get()
        confirm_refund(actor=self.user, line_id=line.pk, reason='Возврат проверен по фактической операции')
        confirm_refund(actor=self.user, line_id=line.pk, reason='Повторное нажатие после проверки возврата')
        self.assertEqual(self.supplier.balance, Decimal('1000'))
        self.assertEqual(self.buyer.balance, Decimal('300'))
        self.assertEqual(BalanceHold.objects.get().remaining, Decimal('0'))

    def test_proven_failed_order_releases_hold(self):
        intent = self.claim(self.reserved())
        response = self.response(intent, status='failed')
        response['items'], response['charged_total'] = [], Decimal(0)
        execution.reconcile(intent, response)
        self.assertEqual(BalanceHold.objects.get().state, 'released')
        self.assertEqual(self.buyer.balance, Decimal('300'))
        self.assertEqual(self.supplier.balance, Decimal('1000'))

    def test_unknown_status_and_unconfirmed_partial_never_trigger_repurchase(self):
        intent = self.claim(self.reserved())
        response = self.response(intent, status='new_unknown')
        execution.reconcile(intent, response)
        self.assertEqual(self.buyer.balance, Decimal('300'))
        self.assertEqual(ResultDelivery.objects.count(), 0)
        intent.refresh_from_db()
        self.assertEqual(intent.state, 'review')

    def test_membership_is_verified_and_anonymous_bots_are_refused(self):
        client = Mock()
        client.call.return_value = {'status': 'member'}
        access = member(client, chat={'id': self.binding.pk, 'type': 'supergroup'}, sender={'id': 55, 'is_bot': False})
        self.assertEqual(access.buyer_id, self.buyer.pk)
        for sender, sender_chat in [({'id': 55, 'is_bot': True}, None), ({'id': 55, 'is_bot': False}, {'id': -9})]:
            with self.subTest(sender=sender), self.assertRaises(PermissionDenied):
                member(client, chat={'id': self.binding.pk, 'type': 'supergroup'}, sender=sender, sender_chat=sender_chat)
        client.call.return_value = {'status': 'left'}
        with self.assertRaises(PermissionDenied):
            member(client, chat={'id': self.binding.pk, 'type': 'supergroup'}, sender={'id': 55, 'is_bot': False})
