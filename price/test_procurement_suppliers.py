"""Закрепление выбранного поставщика, точный пересчёт и защита снимка прайса."""
import json
from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from catalog.models import CD, Platform
from catalog.supplier_exclusions import set_supplier_exclusions
from orders.services import create_customer_procurement_order
from partners.models import Supplier
from pricing.models import SupplierCDPrice

from .models import ProcurementPricePreference
from .procurement_suppliers import prepare_supplier_choices, supplier_base_price
from .services import NegativeProcurementMarkup, create_procurement_price_list, update_procurement_pricing


class ProcurementSupplierTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_superuser('supplier-choice-owner')
        self.product = CD.objects.create(name='Игра поставщиков', platform=Platform.objects.create(name='PS5'), sku='SUP-1')
        self.suppliers = {}
        for letter, price in [('A', '10'), ('F', '15'), ('M', '9')]:
            supplier = Supplier.objects.create(name=f'Закрытое название {letter}', letter=letter,
                highlight_color='#37A7BA', legal_entity='Компания', phone_1='1')
            self.suppliers[letter] = supplier
            SupplierCDPrice.objects.create(supplier=supplier, cd=self.product, price=price)
        self.price = create_procurement_price_list(actor=self.actor, exchange_rate_usdt_aed='3.67',
            exchange_rate_usdt_rub='90', delivery_general_usdt_per_kg=0, delivery_devices_usdt_per_kg=0,
            delivery_storage_usdt_per_kg=0, delivery_cd_rub=5)
        self.item = self.price.items.get()

    def rows(self, letter='F', **changes):
        return {self.item.pk: {'supplier_id': str(self.suppliers[letter].pk),
            'supplier_initial_id': str(self.item.selected_supplier_id), 'markup': '123.45', 'delivery': '5',
            'price_source': 'markup', **changes}}

    def update(self, rows=None, actor=None, **kwargs):
        return update_procurement_pricing(actor=actor or self.actor, price_list_id=self.price.pk,
            rows=rows or self.rows(), can_change_markup=True, can_change_delivery=True, **kwargs)

    def test_manual_winner_uses_snapshot_recalculates_and_reaches_order(self):
        SupplierCDPrice.objects.filter(supplier=self.suppliers['F'], cd=self.product).update(price=999)
        self.update()
        self.item.refresh_from_db()
        base = (Decimal('15') / Decimal('3.67') * 90).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
        self.assertEqual(self.item.selected_supplier, self.suppliers['F'])
        self.assertEqual(self.item.supplier_price_aed, Decimal('15'))
        self.assertEqual(self.item.base_price_rub, base)
        self.assertEqual(self.item.original_markup_rub, Decimal('123.45'))
        self.assertEqual(self.item.delivery_rub, Decimal('5'))
        self.assertEqual((self.item.prepayment_price_rub, self.item.postpayment_price_rub), (Decimal('500'), Decimal('560')))
        self.assertEqual(self.item.supplier_offers.count(), 3)
        self.assertEqual(ProcurementPricePreference.objects.get(cd=self.product).markup_rub, Decimal('123.45'))
        order = create_customer_procurement_order(actor=self.actor, price_list_id=self.price.pk,
            recipient='Покупатель', comment='', lines=[{'price_list_item_id': self.item.pk,
                'prepayment_quantity': 1, 'postpayment_quantity': 0}])
        ordered = order.items.get()
        self.assertEqual(ordered.selected_supplier_id, self.suppliers['F'].pk)
        self.assertEqual(ordered.supplier_price_aed_snapshot, Decimal('15'))
        self.assertEqual(self.product.change_events.filter(field_changes__field_name=f'procurement_supplier_{self.price.pk}').count(), 1)

    def test_http_save_and_reload_show_chosen_supplier_without_full_names(self):
        user = User.objects.create_user('supplier-choice-editor')
        user.user_permissions.add(*Permission.objects.filter(content_type__app_label='price', codename__in=(
            'view_price_page', 'view_supplier_prices', 'change_procurement_markup')))
        self.client.force_login(user)
        response = self.client.post(reverse('price:procurement_update', args=[self.price.pk]),
            {'pricing_rows': json.dumps(self.rows())})
        self.assertEqual(response.status_code, 302)
        response = self.client.get(response.url)
        self.assertContains(response, 'Цены поставщиков, AED')
        self.assertContains(response, 'Итоговая себестоимость, RUB')
        self.assertContains(response, 'data-total-cost-display title="Закупка в рублях + доставка">372.85')
        self.assertNotContains(response, 'Округление предоплаты:')
        self.assertNotContains(response, 'Округление постоплаты:')
        self.assertNotContains(response, '<th class="numeric">Курс</th>')
        self.assertNotContains(response, '<th class="numeric">AED</th>')
        for supplier in self.suppliers.values():
            self.assertNotContains(response, supplier.name)
        self.assertContains(response, f'data-supplier-id="{self.suppliers["F"].pk}" aria-current="true"')
        self.item.refresh_from_db()
        self.assertEqual(self.item.selected_supplier_id, self.suppliers['F'].pk)

    def test_supplier_permissions_cannot_be_bypassed_with_service_flags(self):
        for permission in ('view_supplier_prices', 'change_procurement_markup'):
            user = User.objects.create_user(f'supplier-choice-{permission}')
            user.user_permissions.add(Permission.objects.get(content_type__app_label='price', codename=permission))
            with self.assertRaisesMessage(ValidationError, 'нужны права'):
                self.update(actor=user)
        self.item.refresh_from_db()
        self.assertEqual(self.item.selected_supplier_id, self.suppliers['M'].pk)
        self.assertFalse(ProcurementPricePreference.objects.exists())

    def test_excluded_and_new_live_offer_are_rejected_without_partial_save(self):
        set_supplier_exclusions(product=self.product, supplier_ids=[self.suppliers['F'].pk], actor=self.actor)
        with self.assertRaisesMessage(ValidationError, 'исключён'):
            self.update()
        outsider = Supplier.objects.create(name='Новый', letter='Z', highlight_color='#37A7BA', legal_entity='Z', phone_1='1')
        SupplierCDPrice.objects.create(supplier=outsider, cd=self.product, price=1)
        rows = self.rows(supplier_id=str(outsider.pk))
        with self.assertRaisesMessage(ValidationError, 'данной версии'):
            self.update(rows)
        self.item.refresh_from_db()
        self.assertEqual(self.item.selected_supplier_id, self.suppliers['M'].pk)
        self.assertFalse(ProcurementPricePreference.objects.exists())

    def test_used_price_is_locked_on_backend_and_in_picker(self):
        create_customer_procurement_order(actor=self.actor, price_list_id=self.price.pk, recipient='Покупатель',
            comment='', lines=[{'price_list_item_id': self.item.pk, 'prepayment_quantity': 1, 'postpayment_quantity': 0}])
        with self.assertRaisesMessage(ValidationError, 'использован в заказе'):
            self.update()
        self.client.force_login(self.actor)
        response = self.client.get(reverse('price:procurement_detail', args=[self.price.pk]))
        self.assertFalse(response.context['can_change_supplier'])
        self.assertNotContains(response, '>Сохранить расчёт</button>')

    def test_negative_confirmation_rolls_back_choice_until_confirmed(self):
        rows = self.rows(markup='-1.00')
        with self.assertRaises(NegativeProcurementMarkup):
            self.update(rows)
        self.item.refresh_from_db()
        self.assertEqual(self.item.selected_supplier_id, self.suppliers['M'].pk)
        self.assertFalse(ProcurementPricePreference.objects.exists())
        self.update(rows, negative_markup_confirmed=True)
        self.item.refresh_from_db()
        self.assertEqual(self.item.selected_supplier_id, self.suppliers['F'].pk)
        self.assertEqual(self.item.original_markup_rub, Decimal('-1'))

    def test_stale_supplier_baseline_is_rejected_and_old_payload_does_not_reset_winner(self):
        stale = self.rows('A')
        self.update()
        with self.assertRaisesMessage(ValidationError, 'уже изменён'):
            self.update(stale)
        self.update({self.item.pk: {'markup': '125', 'delivery': '5'}})
        self.item.refresh_from_db()
        self.assertEqual(self.item.selected_supplier_id, self.suppliers['F'].pk)

    def test_legacy_version_does_not_invent_historical_offers(self):
        self.item.supplier_offers.all().delete()
        self.price.supplier_offers_complete = False
        self.price.save(update_fields=['supplier_offers_complete'])
        item = self.price.items.select_related('selected_supplier').get()
        prepare_supplier_choices([item], self.price)
        self.assertEqual([row['supplier'].pk for row in item.supplier_choices], [self.suppliers['M'].pk])
        with self.assertRaisesMessage(ValidationError, 'данной версии'):
            self.update()

    def test_conversion_uses_two_saved_rates_and_legacy_item_rate(self):
        amount = Decimal('9999.123456')
        expected = (amount / Decimal('3.67') * 90).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
        self.assertEqual(supplier_base_price(self.item, self.price, amount), expected)
        self.price.exchange_rate_usdt_aed = self.price.exchange_rate_usdt_rub = None
        self.assertEqual(supplier_base_price(self.item, self.price, amount),
            (amount * self.item.exchange_rate_aed_rub).quantize(Decimal('.01'), rounding=ROUND_HALF_UP))
