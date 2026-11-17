"""Переход сохраняет PK/наценки и не связывает по похожему имени."""
from datetime import timedelta
from decimal import Decimal
import uuid
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from digital_sales.models import Buyer
from .api import Offer
from .models import Product, CatalogState, Integration, BuyerMarkup, SyncJob
from .services import apply_catalog, edit_product
from .v2_mapping import plan


class V2MappingTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_superuser(username='mapping-synthetic', password=None)
        self.buyer = Buyer.objects.create(name='Покупатель наценок')
        CatalogState.objects.update_or_create(pk=1, defaults={'revision': 1})
        Integration.objects.update_or_create(pk=1, defaults={'enabled': True})
        self.attrs = {'family': 'PlayStation', 'code_category': 'PlayStation', 'denomination': '250 TRY'}
        self.old = Product.objects.create(external_id='v1_code_500', source_name='250 TRY', source_type='code',
            platform='PlayStation', region='tr', currency='RUB', purchase_cost=100, markup=50,
            attributes=self.attrs, availability='yes', confirmed_at=timezone.now(), last_seen_at=timezone.now())
        self.fee = BuyerMarkup.objects.create(product=self.old, buyer=self.buyer, markup=0, edited_by=self.actor)

    def offer(self, **changes):
        data = dict(identity='pv2_new', name='250 TRY', kind='code', platform='playstation', region='turkey',
            cost=Decimal('105'), currency='RUB', available=True, attributes={**self.attrs, 'api_version': 2,
                'requirements': {'account': False}, 'fulfillment': 'automatic',
                'limits': {'min_quantity': 1, 'max_quantity': 20, 'quantity_step': 1}})
        data.update(changes)
        return Offer(**data)

    def apply(self, offers):
        job = SyncJob.objects.create(state='running', owner=uuid.uuid4(), run_after=timezone.now(),
            lease_until=timezone.now() + timedelta(minutes=2), requested_by=self.actor)
        apply_catalog(offers, job_id=job.pk, owner=job.owner)

    def test_unique_mapping_preserves_pk_and_buyer_markup(self):
        self.apply([self.offer()])
        self.old.refresh_from_db()
        self.fee.refresh_from_db()
        self.assertEqual(Product.objects.count(), 1)
        self.assertEqual(self.old.external_id, 'pv2_new')
        self.assertEqual(self.old.legacy_external_id, 'v1_code_500')
        self.assertEqual(self.old.markup, Decimal('50'))
        self.assertEqual(self.fee.product_id, self.old.pk)
        self.assertEqual(self.fee.markup, Decimal('0'))

    def test_similar_name_with_different_region_is_not_matched(self):
        matched, _, missing = plan([self.offer(region='usa')], [self.old])
        self.assertEqual(matched, {})
        self.assertIn(self.old.pk, missing)

    def test_multiple_candidates_are_blocked_without_copying_fees(self):
        self.apply([self.offer(), self.offer(identity='pv2_another')])
        self.old.refresh_from_db()
        self.assertEqual(self.old.external_id, 'v1_code_500')
        for row in Product.objects.filter(api_version=2):
            self.assertTrue(row.requires_review)
            self.assertEqual(row.mapping_issue, 'ambiguous')
            self.assertIsNone(row.markup)

    def test_unavailable_offer_preserves_last_cost_and_no_manual_api_cost_edit(self):
        self.apply([self.offer()])
        row = Product.objects.get(pk=self.old.pk)
        self.apply([self.offer(cost=None, available=False)])
        row.refresh_from_db()
        self.assertEqual(row.purchase_cost, Decimal('105'))
        self.assertEqual(row.availability, 'no')
        with self.assertRaises(ValidationError):
            edit_product(actor=self.actor, product_id=row.pk, revision=row.revision, values={'purchase_cost': '1'})
