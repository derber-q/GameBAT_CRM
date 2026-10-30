"""Пустой рейс, дополнительные партии и привязка первым обычным заказом."""
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from price.models import ProcurementPriceList, ProcurementPriceListItem
from .models import SupplierOrderBatch, TripAdditionReceipt
from .services import create_customer_procurement_order
from . import test_trip_additions as addition_fixtures
from .trip_additions import FIXED_FIELDS, prepare_addition, commit_addition
from .trips import create_empty_trip, create_trip, assign_order_to_trip, add_orders_to_trip, available_trips, _assert_balances


class EmptyTripTests(TestCase):
    def setUp(self):
        addition_fixtures.TripAdditionTests.setUp(self)
        self.seed_batch = self.batch
        self.key = uuid4()
        self.batch = create_empty_trip(actor=self.user, creation_key=self.key, name='Новый рейс')

    def order(self, price=None):
        price = price or self.price
        source = price.items.first()
        return create_customer_procurement_order(actor=self.user, price_list_id=price.pk, recipient=self.partner.name,
            partner_id=self.partner.pk, comment='', lines=[{'price_list_item_id': source.pk,
                'prepayment_quantity': 1, 'postpayment_quantity': 1}])

    def other_price(self):
        fields = {field: getattr(self.price, field) for field in FIXED_FIELDS}
        fields.update(exchange_rate_usdt_rub=100, exchange_rate_aed_rub=25)
        price = ProcurementPriceList.objects.create(created_by=self.user, **fields)
        ProcurementPriceListItem.objects.create(price_list=price, product_kind='cd', cd=self.cd,
            product_name_snapshot=self.cd.name, article_snapshot=self.cd.sku, selected_supplier=self.supplier,
            supplier_price_aed=100, exchange_rate_aed_rub=25, base_price_rub=2500, delivery_rub=50,
            prepayment_price_rub=2600, postpayment_price_rub=2700)
        return price

    def additions(self, **overrides):
        _, _, _, fingerprint = prepare_addition(batch=self.batch, lines=self.lines, partner_ids=self.ids,
            allocations=self.allocations, calculation_price_list_id=self.price.pk)
        args = dict(actor=self.user, batch_id=self.batch.pk, key=uuid4(), lines=self.lines,
            partner_ids=self.ids, allocations=self.allocations, preview_fingerprint=fingerprint,
            revision=self.batch.revision, calculation_price_list_id=self.price.pk)
        args.update(overrides)
        return commit_addition(**args)

    def test_empty_creation_identity_links_and_idempotence(self):
        self.assertTrue(self.batch.is_trip)
        self.assertIsNone(self.batch.price_list_id)
        self.assertFalse(self.batch.is_completed)
        self.assertFalse(self.batch.trip_orders.exists())
        self.assertFalse(self.batch.lines.exists())
        self.assertIn('Рейс №', str(self.batch))
        self.assertEqual(create_empty_trip(actor=self.user, creation_key=self.key, name='Новый рейс').pk, self.batch.pk)
        self.assertEqual(self.batch.changes.count(), 1)
        response = self.client.get(reverse('orders:list'))
        self.assertContains(response, reverse('orders:trip_detail', args=[self.batch.pk]))
        self.assertContains(response, 'Создать пустой рейс')
        detail = self.client.get(reverse('orders:trip_detail', args=[self.batch.pk]))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, 'Добавить заказы')
        self.assertContains(detail, 'Добавить дополнительные товары')
        self.assertNotContains(detail, 'Прайс №None')
        legacy = SupplierOrderBatch.objects.create(created_by=self.user)
        self.assertFalse(legacy.is_trip)
        self.assertNotIn(legacy, SupplierOrderBatch.objects.trips())
        self.assertEqual(self.client.get(reverse('orders:trip_detail', args=[legacy.pk])).status_code, 404)
        with self.assertRaises(ValidationError):
            create_trip(actor=self.user, order_ids=[], creation_key=uuid4())

    def test_additional_goods_do_not_bind_and_first_normal_order_preserves_their_snapshots(self):
        additional = self.additions()
        self.batch.refresh_from_db()
        self.assertIsNone(self.batch.price_list_id)
        self.assertEqual(len(additional), 3)
        self.assertTrue(all(order.price_list.is_trip_addition for order in additional))
        snapshots = {order.pk: (order.price_list_id, list(order.items.values())) for order in additional}
        price = self.other_price()
        normal = self.order(price)
        batch = add_orders_to_trip(actor=self.user, batch_id=self.batch.pk, order_ids=[normal.pk], revision=self.batch.revision)
        self.assertEqual(batch.price_list_id, price.pk)
        for order in additional:
            order.refresh_from_db()
            self.assertEqual((order.price_list_id, list(order.items.values())), snapshots[order.pk])
        _assert_balances(batch)
        self.assertEqual(batch.trip_orders.count(), 4)
        self.assertEqual(create_empty_trip(actor=self.user, creation_key=self.key, name='Новый рейс').pk, batch.pk)

    def test_first_order_binds_via_existing_assignment_and_later_other_price_is_rejected(self):
        first = self.order()
        self.assertIn(self.batch, available_trips(price_list_id=self.price.pk))
        self.batch = assign_order_to_trip(actor=self.user, order_id=first.pk, target_batch_id=self.batch.pk,
            target_revision=self.batch.revision)
        self.assertEqual(self.batch.price_list_id, self.price.pk)
        second = self.order(self.other_price())
        with self.assertRaises(ValidationError):
            assign_order_to_trip(actor=self.user, order_id=second.pk, target_batch_id=self.batch.pk,
                target_revision=self.batch.revision)
        second.refresh_from_db()
        self.assertIsNone(second.trip_id)
        self.assertEqual(self.batch.changes.get(revision=0).details, {'order_ids': [], 'empty': True})
        self.assertEqual(self.batch.changes.order_by('-revision').first().details['bound_price_list_id'], self.price.pk)

    def test_mixed_price_bulk_selection_rolls_back_first_binding_and_all_orders(self):
        first, second = self.order(), self.order(self.other_price())
        with self.assertRaises(ValidationError):
            add_orders_to_trip(actor=self.user, batch_id=self.batch.pk, order_ids=[first.pk, second.pk], revision=0)
        self.batch.refresh_from_db()
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual((self.batch.price_list_id, self.batch.revision, first.trip_id, second.trip_id), (None, 0, None, None))
        self.assertFalse(self.batch.lines.exists())
        self.assertEqual(self.batch.changes.count(), 1)

    def test_multiple_orders_same_price_and_stale_revision(self):
        first, second = self.order(), self.order()
        batch = add_orders_to_trip(actor=self.user, batch_id=self.batch.pk, order_ids=[first.pk, second.pk], revision=0)
        self.assertEqual(batch.trip_orders.count(), 2)
        self.assertEqual(batch.price_list_id, self.price.pk)
        third = self.order()
        with self.assertRaises(ValidationError):
            add_orders_to_trip(actor=self.user, batch_id=batch.pk, order_ids=[third.pk], revision=0)
        third.refresh_from_db()
        self.assertIsNone(third.trip_id)

    def test_calculation_requires_explicit_price_and_does_not_bind_or_write(self):
        with self.assertRaises(ValidationError):
            prepare_addition(batch=self.batch, lines=self.lines, partner_ids=self.ids, allocations=self.allocations)
        count = ProcurementPriceList.objects.count()
        response = self.client.post(reverse('orders:trip_addition_calculation', args=[self.batch.pk]), {
            'calculation_price_list': self.price.pk, 'lines-TOTAL_FORMS': '1', 'lines-INITIAL_FORMS': '0',
            'lines-0-product': f'cd:{self.cd.pk}', 'lines-0-supplier': self.supplier.pk,
            'lines-0-aed': '110', 'lines-0-customer_price': '2500', 'lines-0-stock_qty': '1', 'lines-0-customer_qty': '0'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['rows'][0]['cost'], '2250.00')
        self.batch.refresh_from_db()
        self.assertIsNone(self.batch.price_list_id)
        self.assertFalse(self.batch.lines.exists())
        self.assertEqual(ProcurementPriceList.objects.count(), count)

    def test_changed_binding_invalidates_old_addition_preview_without_new_orders(self):
        _, _, _, fingerprint = prepare_addition(batch=self.batch, lines=self.lines, partner_ids=self.ids,
            allocations=self.allocations, calculation_price_list_id=self.price.pk)
        order = self.order(self.other_price())
        add_orders_to_trip(actor=self.user, batch_id=self.batch.pk, order_ids=[order.pk], revision=0)
        with self.assertRaises(ValidationError):
            commit_addition(actor=self.user, batch_id=self.batch.pk, key=uuid4(), lines=self.lines,
                partner_ids=self.ids, allocations=self.allocations, preview_fingerprint=fingerprint,
                revision=0, calculation_price_list_id=self.price.pk)
        self.assertFalse(TripAdditionReceipt.objects.exists())

    def test_unbound_trip_with_additions_supports_exports_and_arrival_and_then_locks(self):
        from .arrival import confirm_arrival
        self.additions()
        self.batch.refresh_from_db()
        self.assertEqual(self.client.get(reverse('orders:trip_full_export', args=[self.batch.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse('orders:trip_export', args=[self.batch.pk, self.supplier.pk])).status_code, 200)
        arrival = confirm_arrival(actor=self.user, batch_id=self.batch.pk, expected_revision=self.batch.revision,
            usdt_aed='4', usdt_rub='80', actual_delivery='300')
        self.assertTrue(arrival.arrived)
        self.assertNotIn(self.batch, available_trips(price_list_id=self.price.pk))
        first = self.order()
        self.batch.refresh_from_db()
        with self.assertRaises(ValidationError):
            add_orders_to_trip(actor=self.user, batch_id=self.batch.pk, order_ids=[first.pk], revision=self.batch.revision)
        self.batch.refresh_from_db()
        self.assertIsNone(self.batch.price_list_id)

    def test_new_pages_methods_permissions_and_creation_token(self):
        response = self.client.get(reverse('orders:trip_empty_create'))
        key = response.context['form']['creation_key'].value()
        response = self.client.post(reverse('orders:trip_empty_create'), {'creation_key': key, 'name': 'Через форму'})
        batch = SupplierOrderBatch.objects.get(creation_key=key)
        self.assertRedirects(response, reverse('orders:trip_detail', args=[batch.pk]))
        self.client.post(reverse('orders:trip_empty_create'), {'creation_key': key, 'name': 'Через форму'})
        self.assertEqual(SupplierOrderBatch.objects.filter(creation_key=key).count(), 1)
        first = self.order()
        response = self.client.post(reverse('orders:trip_add_orders', args=[batch.pk]), {'orders': [first.pk], 'revision': 0})
        self.assertRedirects(response, reverse('orders:trip_detail', args=[batch.pk]))
        user = User.objects.create_user('cannot-create-trip')
        with self.assertRaises(PermissionDenied):
            create_empty_trip(actor=user, creation_key=uuid4())
        self.client.force_login(user)
        for endpoint, args in [('orders:trip_empty_create', []), ('orders:trip_add_orders', [batch.pk]),
            ('orders:trip_addition', [self.batch.pk])]:
            self.assertEqual(self.client.get(reverse(endpoint, args=args)).status_code, 403)
