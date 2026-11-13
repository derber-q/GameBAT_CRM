"""Пустое поле наследует общую наценку; незаполненные блоки не входят в клиентский комплект."""
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal
from unittest.mock import patch
from django.test import TestCase, SimpleTestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from digital_sales.models import Buyer
from .models import Product, ManualPriceEntry, BuyerMarkup, CatalogState
from .buyer_pricing import profile_rows, edit_buyer_markup
from .public import PublicRow, PublicCatalog, populated_blocks, serialize, product_row
from .catalog import product_data


class PriceInheritanceTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_superuser('inheritance-owner')
        self.buyer = Buyer.objects.create(name='Наследование')
        CatalogState.objects.get_or_create(pk=1)
        self.product = Product.objects.create(external_id='inheritance-test',source_name='Игра',source_type='code',
            purchase_cost=Decimal('100'),markup=Decimal('50'),currency='RUB',
            last_seen_at=timezone.now(),confirmed_at=timezone.now())

    def test_null_override_uses_general_and_raw_input_stays_empty(self):
        BuyerMarkup.objects.create(buyer=self.buyer,product=self.product,markup=None,edited_by=self.actor)
        own = profile_rows([self.product],[],self.buyer)[0]
        self.assertEqual(own.markup,Decimal('50'))
        self.assertTrue(own.inherited_markup)
        data = product_data(own,self.actor)
        self.assertEqual(data['price'],'150 ₽')
        self.assertIsNone(data['markup_input'])
        self.assertEqual(data['general_markup'],Decimal('50'))

    def test_explicit_zero_has_priority_and_clearing_restores_inheritance(self):
        own = edit_buyer_markup(actor=self.actor,buyer_id=self.buyer.pk,product_id=self.product.pk,
            revision=f'{self.product.revision}:0',values={'markup':'0'})
        self.assertEqual(product_row(own).price,'100 ₽')
        self.assertFalse(own.inherited_markup)
        own = edit_buyer_markup(actor=self.actor,buyer_id=self.buyer.pk,product_id=self.product.pk,
            revision=own.profile_revision,values={'markup':''})
        self.assertEqual(product_row(own).price,'150 ₽')
        self.assertTrue(own.inherited_markup)
        self.assertIsNone(BuyerMarkup.objects.get(buyer=self.buyer,product=self.product).markup)

    def test_manual_modes_inherit_independently_without_freezing_other_fields(self):
        entry = ManualPriceEntry.objects.create(kind='steam_tariff',label='До 99 ₽',pricing_mode='percent',
            cost_percent=Decimal('6'),markup_percent=Decimal('1'),markup=Decimal('50'),
            cost_coefficient=Decimal('2.960'),markup_coefficient=Decimal('0.1'))
        own = edit_buyer_markup(actor=self.actor,buyer_id=self.buyer.pk,entry_id=entry.pk,
            revision=f'{entry.revision}:0',values={'markup':'0'})
        self.assertEqual(own.markup_percent,Decimal('1'))
        self.assertTrue(own.inherited_markup)
        stored = BuyerMarkup.objects.get(manual_entry=entry,buyer=self.buyer)
        self.assertIsNone(stored.markup_percent)
        self.assertIsNone(stored.markup_coefficient)
        entry.markup_percent = Decimal('3')
        own = profile_rows([],[entry],self.buyer)[0]
        self.assertEqual(own.markup_percent,Decimal('3'))
        self.assertEqual(own.markup,Decimal('0'))


class PopulatedBlockTests(SimpleTestCase):
    def catalog(self, *rows):
        return PublicCatalog(1,datetime.now(dt_timezone.utc).isoformat(),None,False,rows)

    def row(self, name, family, section='codes', region='us', has_markup=False):
        return PublicRow(name,family,section,region,'Цена уточняется','no',family,has_markup=has_markup)

    def test_empty_blocks_and_entire_family_pages_are_removed_but_filled_blocks_are_complete(self):
        catalog = self.catalog(self.row('PS 5','PlayStation',has_markup=True),self.row('PS 10','PlayStation'),
            self.row('PS TR','PlayStation',region='tr'),self.row('Steam','Steam'),
            self.row('EA','PlayStation','services','tr'),self.row('Игры','Игры','services','sng',True))
        selected = populated_blocks(catalog)
        self.assertEqual([row.name for row in selected.rows],['PS 5','PS 10','Игры'])
        self.assertEqual(len(catalog.rows),6)
        public = str(serialize(selected))
        self.assertNotIn('has_markup',public)
        self.assertNotIn('purchase_cost',public)

    def test_empty_bundle_has_clear_validation_and_does_not_invoke_renderer(self):
        from .bundles import generate_bundle
        catalog = self.catalog(self.row('Steam','Steam'))
        with patch('digital_prices.bundles.require',return_value=None), \
             patch('digital_prices.bundles.snapshot',return_value=catalog), \
             patch('digital_prices.bundles.render') as render:
            with self.assertRaises(ValidationError) as error:
                generate_bundle(actor=None)
        self.assertEqual(error.exception.code,'no_priced_blocks')
        render.assert_not_called()
