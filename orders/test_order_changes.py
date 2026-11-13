"""Регрессии редактирования, дополнения и удаления импортных заказов."""
from decimal import Decimal

from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from catalog.models import CD
from .arrival import unconfirm_arrival
from .arrival_models import TripArrival
from .models import CustomerProcurementOrder, SupplierTripInvoice
from .services import add_catalog_items_to_order, add_items_to_order, delete_unassigned_order, edit_created_order
from .test_arrival import ArrivalFixture
from .trips import _assert_balances


class OrderChangesTests(ArrivalFixture, TestCase):
    def edit(self, order, quantity):
        self.trip.refresh_from_db()
        return edit_created_order(actor=self.user, order_id=order.pk, revision=self.trip.revision,
            recipient=order.recipient, comment=order.comment, lines=[{
                'price_list_item_id':self.source.pk,
                'prepayment_quantity':quantity if order.is_stock_order else 0,
                'postpayment_quantity':0 if order.is_stock_order else quantity}])

    def test_customer_and_stock_quantities_follow_assigned_supplier(self):
        for order, quantity in ((self.order, 13), (self.stock_order, 5)):
            with self.subTest(purpose=order.purpose):
                self.edit(order, quantity)
                item = order.items.get()
                self.assertEqual(item.quantity, quantity)
                self.assertEqual(item.trip_allocations.get().quantity, quantity)
                self.assertEqual(item.trip_allocations.get().line.supplier_id, self.supplier.pk)
                _assert_balances(self.trip)
        self.edit(self.order, 6)
        _assert_balances(self.trip)
        self.assertEqual(self.trip.lines.get().quantity, 11)

    def test_stale_revision_and_accepted_invoice_preserve_composition(self):
        revision = self.trip.revision
        self.edit(self.order, 11)
        with self.assertRaises(ValidationError):
            add_items_to_order(actor=self.user, order_id=self.order.pk, revision=revision,
                lines=[{'price_list_item_id':self.source.pk, 'quantity':2}])
        SupplierTripInvoice.objects.create(batch=self.trip, supplier=self.supplier, accepted=True)
        with self.assertRaises(ValidationError):
            self.edit(self.order, 12)
        self.assertEqual(self.order.items.get().quantity, 11)
        _assert_balances(self.trip)

    def test_increase_stays_with_supplier_after_transfer(self):
        from partners.models import Supplier
        from price.models import ProcurementSupplierOffer
        from .trips import change_trip_line
        destination = Supplier.objects.create(name='M', letter='M', legal_entity='M', phone_1='2')
        ProcurementSupplierOffer.objects.create(price_list_item=self.source,
            supplier=self.supplier, price_aed=self.source.supplier_price_aed)
        line = self.trip.lines.get()
        change_trip_line(actor=self.user, batch_id=self.trip.pk, line_id=line.pk,
            revision=self.trip.revision, quantity=0, action='transfer',
            target_supplier_id=destination.pk, price_supplier_id=self.supplier.pk)
        self.edit(self.order, 12)
        item = self.order.items.get()
        active = item.trip_allocations.get(postpayment_quantity__gt=0)
        self.assertEqual(active.quantity, 12)
        self.assertEqual(active.line.supplier_id, destination.pk)
        line.refresh_from_db()
        self.assertEqual(line.quantity, 0)
        _assert_balances(self.trip)

    def test_cancelled_arrival_allows_editing_and_new_arrival(self):
        arrival = self.arrive()
        unconfirm_arrival(actor=self.user, arrival_id=arrival.pk, expected_revision=arrival.revision)
        self.edit(self.order, 11)
        self.trip.refresh_from_db()
        replacement = self.arrive()
        self.assertNotEqual(arrival.pk, replacement.pk)
        self.assertEqual(TripArrival.current.filter(trip=self.trip).count(), 1)
        self.assertEqual(arrival.rows.get(order=self.order).original_quantity, 10)
        self.assertEqual(replacement.rows.get(order=self.order).original_quantity, 11)

    def test_catalog_form_ignores_empty_extra_row(self):
        product = CD.objects.create(name='Дополнительная игра', sku='ORDER-EXTRA',
            platform=self.cd.platform, weight_grams=100)
        self.trip.refresh_from_db()
        response = self.client.post(reverse('orders:add_catalog_items', args=[self.order.pk]), {
            'revision':self.trip.revision, 'lines-TOTAL_FORMS':2, 'lines-INITIAL_FORMS':0,
            'lines-MIN_NUM_FORMS':1, 'lines-MAX_NUM_FORMS':100,
            'lines-0-product':f'cd:{product.pk}', 'lines-0-label':product.name,
            'lines-0-supplier':self.supplier.pk, 'lines-0-supplier_price_aed':'70.25',
            'lines-0-customer_price':'2500', 'lines-0-quantity':3,
        })
        self.assertRedirects(response, reverse('orders:trip_detail', args=[self.trip.pk]), fetch_redirect_response=False)
        item = self.order.items.get(cd=product)
        self.assertEqual(item.quantity, 3)
        self.assertEqual(item.postpayment_unit_price, Decimal('2500'))
        self.assertEqual(item.trip_allocations.get().line.supplier_id, self.supplier.pk)
        self.edit(self.order, 10)
        self.assertEqual(self.order.items.get(cd=product).quantity, 0)
        _assert_balances(self.trip)

    def test_clean_unassigned_order_deletes_only_its_items(self):
        order = self.make_order('customer', 3)
        product_id = self.cd.pk
        delete_unassigned_order(actor=self.user, order_id=order.pk)
        self.assertFalse(CustomerProcurementOrder.objects.filter(pk=order.pk).exists())
        self.assertTrue(CD.objects.filter(pk=product_id).exists())
        self.assertEqual(self.order.items.get().quantity, 10)

    def test_delete_protects_trip_and_history(self):
        with self.assertRaises(ValidationError):
            delete_unassigned_order(actor=self.user, order_id=self.order.pk)
        from .models import CustomerOrderStatusEvent
        order = self.make_order('customer', 2)
        CustomerOrderStatusEvent.objects.create(order=order, actor=self.user,
            old_status='created', new_status='created')
        with self.assertRaises(ValidationError):
            delete_unassigned_order(actor=self.user, order_id=order.pk)
        self.assertEqual(order.items.get().quantity, 2)

    def test_delete_form_works_without_trip_management_permissions(self):
        employee = User.objects.create_user('order-editor', password='test')
        employee.user_permissions.add(*Permission.objects.filter(
            content_type__app_label='orders', codename__in=['view_orders', 'edit_created_order']))
        order = self.make_order('customer', 2)
        self.client.force_login(employee)
        response = self.client.get(reverse('orders:list'))
        self.assertContains(response, f'form="delete-unassigned-order-{order.pk}"')
        self.assertContains(response, f'id="delete-unassigned-order-{order.pk}"')
        url = reverse('orders:delete_unassigned', args=[order.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertRedirects(self.client.post(url), reverse('orders:list'), fetch_redirect_response=False)
        self.assertFalse(CustomerProcurementOrder.objects.filter(pk=order.pk).exists())
        with self.assertRaises(PermissionDenied):
            delete_unassigned_order(actor=employee, order_id=self.make_order('stock', 1).pk)

    def test_delete_without_permission_is_rejected(self):
        employee = User.objects.create_user('order-reader', password='test')
        order = self.make_order('customer', 2)
        self.client.force_login(employee)
        self.assertEqual(self.client.post(reverse('orders:delete_unassigned', args=[order.pk])).status_code, 403)
        self.assertTrue(CustomerProcurementOrder.objects.filter(pk=order.pk).exists())

    def test_catalog_addition_requires_supplier_price_permissions(self):
        employee = User.objects.create_user('quantity-only-editor', password='test')
        employee.user_permissions.add(Permission.objects.get(content_type__app_label='orders',
            codename='edit_created_order'))
        order = self.make_order('customer', 2)
        self.client.force_login(employee)
        for route in ('orders:add_catalog_items', 'orders:order_addition_search'):
            self.assertEqual(self.client.get(reverse(route, args=[order.pk])).status_code, 403)
