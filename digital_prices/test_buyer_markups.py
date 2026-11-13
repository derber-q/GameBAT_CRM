"""Изоляция покупательских наценок, общий себес и явный выбор профиля в CRM-боте."""
from decimal import Decimal
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError, PermissionDenied
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from digital_sales.models import Buyer
from telegram_bots.handlers import accept_update
from telegram_bots.models import StaffBot, StaffBotAccess, StaffBotJob, StaffBotUpdate
from .buyer_pricing import edit_buyer_markup, profile_rows
from .models import BuyerMarkup, BuyerPriceRequest, CatalogState, ManualPriceEntry, Product
from .public import product_row, manual_row, snapshot


class BuyerMarkupTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_superuser(username='buyer-pricing-owner')
        self.buyer = Buyer.objects.create(name='Первый покупатель')
        self.other = Buyer.objects.create(name='Второй покупатель')
        CatalogState.objects.get_or_create(pk=1)
        self.product = Product.objects.create(external_id='buyer-price-test', source_name='Код Steam',
            source_type='code', currency='RUB', purchase_cost=Decimal('100'), markup=Decimal('20'),
            last_seen_at=timezone.now(), confirmed_at=timezone.now(), availability='yes')
        self.manual = ManualPriceEntry.objects.create(kind='steam_tariff', label='До 99 ₽',
            pricing_mode='percent', cost_percent=Decimal('6'), markup_percent=Decimal('1'))

    def edit(self, **kwargs):
        return edit_buyer_markup(actor=self.owner, buyer_id=self.buyer.pk,
            product_id=self.product.pk, revision=f'{self.product.revision}:0', values={'markup': '50'}, **kwargs)

    def test_individual_markup_does_not_change_other_buyer_or_global_price(self):
        self.edit()
        self.product.refresh_from_db()
        self.assertEqual(self.product.markup, Decimal('20'))
        self.assertEqual(product_row(self.product).price, '120 ₽')
        own = profile_rows([self.product], [], self.buyer)[0]
        other = profile_rows([self.product], [], self.other)[0]
        self.assertEqual(product_row(own).price, '150 ₽')
        self.assertEqual(product_row(other).price, '120 ₽')
        self.assertTrue(other.inherited_markup)
        self.assertEqual(own.purchase_cost, self.product.purchase_cost)
        self.assertEqual(snapshot(actor=self.owner, buyer=self.buyer).rows[0].price, '150 ₽')

    def test_empty_markup_inherits_general_and_stale_save_is_rejected(self):
        edit_buyer_markup(actor=self.owner, buyer_id=self.buyer.pk, product_id=self.product.pk,
            revision=f'{self.product.revision}:0', values={'markup': ''})
        own = profile_rows([self.product], [], self.buyer)[0]
        self.assertEqual(own.markup, Decimal('20'))
        self.assertIsNone(own.buyer_markup_values['markup'])
        self.assertTrue(own.inherited_markup)
        with self.assertRaises(ValidationError):
            self.edit()

    def test_manual_percent_and_coefficient_use_own_markup_and_shared_cost(self):
        row = edit_buyer_markup(actor=self.owner, buyer_id=self.buyer.pk, entry_id=self.manual.pk,
            revision=f'{self.manual.revision}:0', values={'markup_percent': '2'})
        self.assertEqual(manual_row(row).price, '+8%')
        self.manual.refresh_from_db()
        self.assertEqual(self.manual.markup_percent, Decimal('1'))
        self.assertEqual(self.manual.cost_percent, Decimal('6'))
        self.manual.pricing_mode = 'coefficient'
        self.manual.cost_coefficient = Decimal('2.960')
        self.manual.save()
        row = edit_buyer_markup(actor=self.owner, buyer_id=self.buyer.pk, entry_id=self.manual.pk,
            revision=f'{self.manual.revision}:1', values={'markup_coefficient': '0.100'})
        self.assertEqual(manual_row(row).price, '3.060')

    def test_buyer_cannot_change_shared_cost_or_mode(self):
        for values in ({'manual_cost': '1'}, {'pricing_mode': 'rub'}, {'markup': '-1'}):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                edit_buyer_markup(actor=self.owner, buyer_id=self.buyer.pk, entry_id=self.manual.pk,
                    revision=f'{self.manual.revision}:0', values=values)
        self.assertFalse(BuyerMarkup.objects.exists())

    def test_web_selection_and_ajax_keep_the_selected_buyer(self):
        self.client.force_login(self.owner)
        url = reverse('pricing:digital_prices:catalog')
        response = self.client.get(url, {'buyer': self.buyer.pk})
        self.assertContains(response, 'Чьи наценки отображаются')
        self.assertContains(response, f'name="buyer" value="{self.buyer.pk}"')
        response = self.client.post(reverse('pricing:digital_prices:markup', args=[self.product.pk]),
            {'buyer': self.buyer.pk, 'revision': f'{self.product.revision}:0', 'markup': '75'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['price'], '180 ₽')
        self.assertFalse(response.json()['inherited_markup'])
        self.assertEqual(self.client.get(url, {'buyer': 'retail'}).status_code, 400)
        self.assertEqual(self.client.get(url, {'buyer': '999999'}).status_code, 400)

    def test_unauthorized_actor_cannot_write_individual_markup(self):
        viewer = get_user_model().objects.create_user(username='buyer-pricing-viewer')
        with self.assertRaises(PermissionDenied):
            edit_buyer_markup(actor=viewer, buyer_id=self.buyer.pk, product_id=self.product.pk,
                revision=f'{self.product.revision}:0', values={'markup': '1'})

    def test_bot_asks_before_queueing_and_duplicate_update_does_not_repeat_job(self):
        bot = StaffBot.objects.create(enabled=True)
        StaffBotAccess.objects.create(bot=bot, user=self.owner, telegram_user_id=77, allowed=True)
        root = {'update_id': 900, 'message': {'chat': {'id': 77, 'type': 'private'},
            'from': {'id': 77}, 'text': 'Прайс цифровых товаров'}}
        reply = accept_update(bot.pk, root)
        self.assertIn('Для какого покупателя', reply['text'])
        self.assertFalse(StaffBotJob.objects.exists())
        choice = {'update_id': 901, 'callback_query': {'id': 'pick', 'from': {'id': 77},
            'data': f'digital_price_images:buyer:{self.buyer.pk}',
            'message': {'chat': {'id': 77, 'type': 'private'}, 'message_id': 5}}}
        accept_update(bot.pk, choice)
        accept_update(bot.pk, choice)
        self.assertEqual(StaffBotJob.objects.count(), 1)
        self.assertEqual(BuyerPriceRequest.objects.get().buyer_id, self.buyer.pk)

    def test_executor_passes_the_fixed_buyer_to_the_same_bundle_generator(self):
        from .telegram import run_job
        from telegram_bots.jobs import claim_job
        bot = StaffBot.objects.create(enabled=True)
        access = StaffBotAccess.objects.create(bot=bot, user=self.owner, telegram_user_id=77, allowed=True)
        receipt = StaffBotUpdate.objects.create(bot=bot, update_id=1000)
        job = StaffBotJob.objects.create(bot=bot, access=access, update=receipt, chat_id=77, function='digital_price_images')
        BuyerPriceRequest.objects.create(job=job, buyer=self.buyer)
        job = claim_job(bot.pk)
        with patch('digital_prices.telegram.generate_bundle', side_effect=ValidationError('stop')) as generate:
            run_job(job, Mock())
        self.assertEqual(generate.call_args.kwargs['buyer'].pk, self.buyer.pk)
