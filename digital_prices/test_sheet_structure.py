"""Смена диапазонов сохраняет строки, наценки, ссылки покупателей и защищает старые вкладки."""
from decimal import Decimal
from unittest.mock import Mock, patch
import requests

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.test import TestCase, SimpleTestCase
from digital_sales.models import Buyer
from .api import CatalogClient, APIError, PRODUCT_TIMEOUT
from .models import ManualPriceEntry, BuyerMarkup, CatalogState
from .sheet_source import SheetCost
from .sheet_structure import reconcile_sng, SNG_CURRENT
from .manual import edit_amounts
from .public import snapshot


class SheetStructureTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_superuser('sheet-structure-admin')
        self.buyer = Buyer.objects.create(name='Покупатель сетки')
        CatalogState.objects.get_or_create(pk=1)
        ManualPriceEntry.objects.all().delete()
        labels = ('1–99', '100–349', '350–999', '1000–1999', '2000–2999', '3000–3999', '4000+')
        self.rows = [ManualPriceEntry.objects.create(kind='game_tariff', region='sng', label=label,
            pricing_mode='coefficient', position=index, cost_coefficient=Decimal('2.1'),
            markup_coefficient=Decimal('0.2')) for index, label in enumerate(labels)]
        self.own = BuyerMarkup.objects.create(buyer=self.buyer, manual_entry=self.rows[4],
            markup_coefficient=Decimal('0.3'), edited_by=self.actor)
        self.source = {('game_tariff', 'sng', label): SheetCost('game_tariff','sng',label,
            'coefficient', Decimal('2.14'), 'Прайс!E29') for label in SNG_CURRENT}

    def reconcile(self, **kwargs):
        with transaction.atomic():
            return reconcile_sng(list(ManualPriceEntry.objects.select_for_update()),
                kwargs.get('costs', self.source), kwargs.get('revisions', {row.pk: row.revision for row in self.rows}))

    def test_new_five_range_layout_keeps_prices_and_overrides_on_same_ids(self):
        active, error = self.reconcile()
        self.assertEqual(error, '')
        self.assertEqual(len(active), 5)
        self.assertEqual(ManualPriceEntry.objects.count(), 7)
        self.assertEqual(ManualPriceEntry.objects.filter(source_archived=True).count(), 2)
        expanded = ManualPriceEntry.objects.get(pk=self.rows[4].pk)
        self.assertEqual(expanded.label, '2000+')
        self.assertEqual(expanded.markup_coefficient, Decimal('0.2'))
        self.own.refresh_from_db()
        self.assertEqual(self.own.manual_entry_id, expanded.pk)
        self.assertEqual(self.own.markup_coefficient, Decimal('0.3'))
        self.assertEqual(len(snapshot(actor=self.actor).rows), 5)
        repeated, error = self.reconcile()
        self.assertEqual(len(repeated), 5)
        self.assertEqual(error, '')

    def test_missing_unrelated_row_does_not_half_apply_structure(self):
        ManualPriceEntry.objects.create(kind='game_tariff', region='india', label='1000')
        _, error = self.reconcile()
        self.assertEqual(error, 'sheet_mapping')
        self.assertFalse(ManualPriceEntry.objects.filter(source_archived=True).exists())
        self.rows[4].refresh_from_db()
        self.assertEqual(self.rows[4].label, '2000–2999')

    def test_concurrent_change_does_not_rename_or_archive_anything(self):
        _, error = self.reconcile(revisions={row.pk: 0 for row in self.rows})
        self.assertEqual(error, 'sheet_local_changes')
        self.assertFalse(ManualPriceEntry.objects.filter(source_archived=True).exists())

    def test_old_open_form_cannot_edit_archived_range(self):
        self.reconcile()
        row = ManualPriceEntry.objects.get(pk=self.rows[-1].pk)
        with self.assertRaises(ValidationError):
            edit_amounts(actor=self.actor, entry_id=row.pk, revision=row.revision, values={'markup_coefficient': '9'})


class ProductTimeoutTests(SimpleTestCase):
    def test_product_request_has_bounded_longer_timeout_and_no_implicit_retry(self):
        session = Mock()
        session.get.side_effect = requests.ReadTimeout('synthetic')
        with patch('digital_prices.api.require_live_operation'):
            client = CatalogClient('synthetic-secret', session=session)
            with self.assertRaises(APIError) as caught:
                client.fetch()
        self.assertEqual(caught.exception.category, 'network_timeout')
        self.assertEqual(session.get.call_count, 1)
        self.assertEqual(session.get.call_args.kwargs['timeout'], PRODUCT_TIMEOUT)
        self.assertLess(sum(PRODUCT_TIMEOUT), 120)
