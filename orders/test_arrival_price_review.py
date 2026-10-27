"""Приход рейса подтверждает цены по средней себестоимости физического склада."""
from decimal import Decimal
from django.test import TestCase
from django.urls import reverse
from django.core.exceptions import ValidationError
from .test_arrival_finalization import ArrivalFinalizationFixture
from .arrival_finalization import finalize_arrival
from supplies.models import Supply
from supplies.services import confirm_supply_price_review


class ArrivalPriceReviewTests(ArrivalFinalizationFixture, TestCase):
    def test_posting_opens_review_without_stock_or_price_changes(self):
        _,supply=self.prepare(); self.finalize();supply.refresh_from_db()
        response=self.client.post(reverse('orders:arrival_supply_post',args=[supply.pk]),
                                  {'revision_number':supply.revision_number})
        self.assertRedirects(response,reverse('supplies:price_review',args=[supply.pk]))
        supply.refresh_from_db()
        self.assertEqual(supply.status,Supply.Status.PRICE_REVIEW_REQUIRED)
        self.no_stock_change()
        page=self.client.get(response.url)
        self.assertContains(page,'Подтвердить цены и поставить на баланс')
        calculation=page.context['rows'][0]['calculation']
        self.assertEqual(calculation.old_owned_quantity,5)
        self.assertEqual(calculation.resulting_unit_cost,Decimal('1216.00'))
        self.assertContains(page,'data-cost="1216.00"')
        result=self.client.post(response.url,{'expected_revision_number':supply.revision_number,
            f'cd_{self.cd.pk}_wholesale_price':'1500',f'cd_{self.cd.pk}_avito_price':'1700'})
        self.assertRedirects(result,reverse('supplies:detail',args=[supply.pk]))
        supply.refresh_from_db();self.stock.refresh_from_db();self.cd.refresh_from_db()
        self.assertEqual(supply.status,Supply.Status.ACCEPTED)
        self.assertEqual(self.stock.quantity,7)
        self.assertEqual(self.cd.cost,Decimal('1216.00'))
        self.assertEqual(self.cd.wholesale_price,Decimal('1500'))
        self.assertEqual(self.cd.avito_price,Decimal('1700'))

    def test_joint_finalization_has_no_global_price_inputs(self):
        self.prepare()
        page=self.client.get(reverse('orders:arrival_finalization',args=[self.trip.pk]))
        self.assertNotContains(page,'data-trip-price-key')
        self.assertNotContains(page,'Будущая оптовая цена')
        with self.assertRaises(ValidationError):
            finalize_arrival(actor=self.user,arrival_id=self.arrival.pk,expected_revision=self.arrival.revision,
                raw_rows=self.inputs(),proposed_prices={('cd',self.cd.pk):{'wholesale_price':'4800'}})

    def test_unreviewed_supply_cannot_skip_confirmation(self):
        _,supply=self.prepare();self.finalize()
        with self.assertRaises(ValidationError):
            confirm_supply_price_review(actor=self.user,supply_id=supply.pk)
        self.no_stock_change()

    def test_preview_includes_independent_expenses_and_refresh_is_idempotent(self):
        from .arrival_finalization import prepare_supply_price_review
        _,supply=self.prepare();self.finalize()
        prepare_supply_price_review(actor=self.user,supply_id=supply.pk,
            independent_expenses=[{'name':'Упаковка','amount':'7'}])
        supply.refresh_from_db();revision=supply.revision_number
        page=self.client.get(reverse('supplies:price_review',args=[supply.pk]))
        self.assertEqual(page.context['rows'][0]['calculation'].resulting_unit_cost,Decimal('1217.00'))
        supply.refresh_from_db();self.assertEqual(supply.revision_number,revision)
        self.no_stock_change()

    def test_inventory_change_after_preview_does_not_silently_reprice_at_confirmation(self):
        _,supply=self.prepare();self.finalize()
        url=reverse('supplies:price_review',args=[supply.pk])
        self.client.get(url);supply.refresh_from_db()
        self.stock.quantity=3;self.stock.save(update_fields=['quantity'])
        response=self.client.post(url,{'expected_revision_number':supply.revision_number,
            f'cd_{self.cd.pk}_wholesale_price':'1500'})
        self.assertContains(response,'изменились после расчёта')
        supply.refresh_from_db();self.cd.refresh_from_db();self.stock.refresh_from_db()
        self.assertEqual(supply.status,Supply.Status.PRICE_REVIEW_REQUIRED)
        self.assertEqual(self.cd.wholesale_price,Decimal('9999'))
        self.assertEqual(self.stock.quantity,3)

    def test_changed_inventory_rejects_old_form_and_reload_recalculates_average(self):
        _,supply=self.prepare();self.finalize()
        url=reverse('supplies:price_review',args=[supply.pk])
        self.client.get(url);supply.refresh_from_db();old_revision=supply.revision_number
        self.stock.quantity=3;self.stock.save(update_fields=['quantity'])
        page=self.client.get(url);supply.refresh_from_db()
        self.assertGreater(supply.revision_number,old_revision)
        self.assertEqual(page.context['rows'][0]['calculation'].resulting_unit_cost,Decimal('1422.40'))
        response=self.client.post(url,{'expected_revision_number':old_revision,
            f'cd_{self.cd.pk}_wholesale_price':'1500'})
        self.assertContains(response,'изменён')
        supply.refresh_from_db();self.assertEqual(supply.status,Supply.Status.PRICE_REVIEW_REQUIRED)
        self.stock.refresh_from_db();self.assertEqual(self.stock.quantity,3)
