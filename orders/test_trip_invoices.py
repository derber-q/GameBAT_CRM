"""Отметка инвойса блокирует только редактирование с HTTP-страницы рейса."""
from uuid import uuid4

from django.contrib.auth.models import Permission
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import User
from . import test_trips as fixtures
from .models import CustomerProcurementOrderItem, SupplierTripInvoice
from .services import advance_order_status
from .trip_prices import change_trip_price
from .trips import create_trip


class TripInvoiceTests(TestCase):
    order = classmethod(fixtures.TripTests.order.__func__)
    change = fixtures.TripTests.change

    @classmethod
    def setUpTestData(cls):
        fixtures.TripTests.setUpTestData.__func__(cls)
        cls.b.letter, cls.c.letter = 'F', 'M'
        cls.b.save(update_fields=('letter',))
        cls.c.save(update_fields=('letter',))

    def setUp(self):
        self.client.force_login(self.user)
        self.trip = create_trip(actor=self.user, order_ids=[self.first.pk, self.second.pk], creation_key=uuid4())
        self.line = self.trip.lines.get(cd=self.cd, supplier=self.a)

    def flag_url(self, supplier=None, trip=None):
        return reverse('orders:trip_invoice_update', args=[(trip or self.trip).pk, (supplier or self.a).pk])

    def toggle(self, accepted, supplier=None):
        response = self.client.post(self.flag_url(supplier), {'accepted': '1' if accepted else '0'})
        self.assertEqual(response.status_code, 200, response.content)
        return response

    def snapshot(self):
        self.trip.refresh_from_db()
        return (self.trip.revision, list(self.trip.lines.order_by('pk').values()),
            list(CustomerProcurementOrderItem.objects.order_by('pk').values()), self.trip.changes.count())

    def test_default_false_is_read_only_and_toggle_persists_without_business_changes(self):
        before = self.snapshot()
        response = self.client.get(reverse('orders:trip_detail', args=[self.trip.pk]))
        self.assertFalse(SupplierTripInvoice.objects.exists())
        self.assertTrue(response.context['editor'][str(self.line.pk)])
        self.toggle(True)
        flag = SupplierTripInvoice.objects.get()
        self.assertEqual((flag.batch_id, flag.supplier_id, flag.accepted, flag.updated_by_id),
            (self.trip.pk, self.a.pk, True, self.user.pk))
        timestamp = flag.updated_at
        self.toggle(True)
        flag.refresh_from_db()
        self.assertEqual(flag.updated_at, timestamp)
        self.assertEqual(self.snapshot(), before)
        response = self.client.get(reverse('orders:trip_detail', args=[self.trip.pk]))
        self.assertNotIn(str(self.line.pk), response.context['editor'])
        self.assertNotIn(str(self.line.pk), response.context['price_editor'])
        self.assertContains(response, 'trip-invoice-accepted')
        self.toggle(False)
        response = self.client.get(reverse('orders:trip_detail', args=[self.trip.pk]))
        self.assertIn(str(self.line.pk), response.context['editor'])
        self.assertIn(str(self.line.pk), response.context['price_editor'])
        self.assertEqual(self.snapshot(), before)

    def test_stale_quantity_price_and_preview_posts_cannot_change_accepted_supplier(self):
        self.toggle(True)
        before = self.snapshot()
        for route, payload in (
            ('orders:trip_line_update', {'action': 'adjust', 'quantity': 0}),
            ('orders:trip_price_preview', {'price_aed': '101'}),
            ('orders:trip_price_update', {'price_aed': '101'}),
        ):
            with self.subTest(route=route):
                response = self.client.post(reverse(route, args=[self.trip.pk, self.line.pk]),
                    {**payload, 'revision': self.trip.revision})
                self.assertEqual(response.status_code, 409)
                self.assertIn('Инвойс поставщика принят', response.json()['message'])
                self.assertEqual(self.snapshot(), before)

    def test_transfer_and_return_cannot_change_accepted_target(self):
        self.change(self.trip, self.line, 9, target_supplier_id=self.c.pk, price_supplier_id=self.a.pk)
        self.toggle(True, self.c)
        before = self.snapshot()
        url = reverse('orders:trip_line_update', args=[self.trip.pk, self.line.pk])
        response = self.client.post(url, {'action': 'transfer', 'quantity': 8, 'revision': self.trip.revision,
            'target_supplier': self.c.pk, 'price_supplier': self.a.pk})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.snapshot(), before)
        self.change(self.trip, self.line, 8, target_supplier_id=self.b.pk, price_supplier_id=self.c.pk)
        source = self.trip.lines.get(cd=self.cd, supplier=self.b)
        self.trip.refresh_from_db()
        response = self.client.post(reverse('orders:trip_line_update', args=[self.trip.pk, source.pk]),
            {'action': 'return_to_m', 'revision': self.trip.revision})
        self.assertEqual(response.status_code, 409)
        config = self.client.get(reverse('orders:trip_detail', args=[self.trip.pk])).context['editor'][str(self.line.pk)]
        self.assertTrue(next(target for target in config['targets'] if target['id'] == self.c.pk)['disabled'])

    def test_other_suppliers_other_trips_and_global_services_keep_their_behavior(self):
        self.toggle(True)
        # Сервис вне обработчиков страницы не использует отметку инвойса.
        self.change(self.trip, self.line, 9, target_supplier_id=self.b.pk, price_supplier_id=self.a.pk)
        self.trip.refresh_from_db()
        change_trip_price(actor=self.user, batch_id=self.trip.pk, line_id=self.line.pk,
            revision=self.trip.revision, price_aed='101', reason='Внешний сценарий')
        self.trip.refresh_from_db()
        other_line = self.trip.lines.get(cd=self.cd, supplier=self.b)
        response = self.client.post(reverse('orders:trip_line_update', args=[self.trip.pk, other_line.pk]),
            {'action': 'adjust', 'quantity': 0, 'revision': self.trip.revision})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(reverse('orders:trip_export', args=[self.trip.pk, self.a.pk])).status_code, 200)
        another_order = self.order('Новый рейс', 0, 1)
        another_trip = create_trip(actor=self.user, order_ids=[another_order.pk], creation_key=uuid4())
        response = self.client.get(reverse('orders:trip_detail', args=[another_trip.pk]))
        self.assertFalse(any(supplier.invoice_accepted for supplier, _lines in response.context['supplier_groups']))

    def test_flag_can_be_removed_after_order_confirmation(self):
        from warehouse.models import Warehouse
        warehouse = Warehouse.objects.create(name='Касса проверки отметки')
        self.toggle(True)
        for status in ('confirmed', 'receiving'):
            advance_order_status(actor=self.user, order_id=self.first.pk, next_status=status, warehouse_id=warehouse.pk)
        for supplier_id in self.trip.lines.values_list('supplier_id', flat=True).distinct():
            self.client.post(reverse('orders:trip_invoice_update', args=[self.trip.pk, supplier_id]), {'accepted': '1'})
        response = self.client.get(reverse('orders:trip_detail', args=[self.trip.pk]))
        self.assertFalse(response.context['can_edit'])
        self.assertTrue(response.context['can_manage_invoices'])
        self.assertNotContains(response, 'checked disabled')
        self.toggle(False)
        self.assertFalse(SupplierTripInvoice.objects.get(supplier=self.a).accepted)

    def test_permissions_csrf_method_and_invalid_supplier(self):
        self.assertEqual(self.client.get(self.flag_url()).status_code, 405)
        self.assertEqual(self.client.post(self.flag_url(), {'accepted': 'garbage'}).status_code, 400)
        self.assertEqual(self.client.post(reverse('orders:trip_invoice_update', args=[self.trip.pk, 999999]),
            {'accepted': '1'}).status_code, 409)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        self.assertEqual(csrf_client.post(self.flag_url(), {'accepted': '1'}).status_code, 403)
        viewer = User.objects.create_user('invoice-viewer')
        viewer.user_permissions.set(Permission.objects.filter(codename__in=('generate_supplier_orders', 'view_supplier_details')))
        self.client.force_login(viewer)
        response = self.client.get(reverse('orders:trip_detail', args=[self.trip.pk]))
        self.assertContains(response, 'name="accepted" disabled')
        self.assertEqual(self.client.post(self.flag_url(), {'accepted': '1'}).status_code, 403)
        self.assertFalse(SupplierTripInvoice.objects.exists())
