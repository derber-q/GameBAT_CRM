"""Перенос целых заказов между рейсами без изменения их цен, денег и количества."""
from decimal import Decimal
from uuid import uuid4
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from cash.models import CashTransaction
from price.models import ProcurementPriceList
from .models import CustomerProcurementOrder, OrderAdjustment, SupplierOrderBatch, SupplierTripAllocation
from . import test_trips as trip_fixtures
from .trips import (assign_order_to_trip, available_trips, create_trip, delete_empty_trip,
                    change_trip_line, return_line_to_m, _assert_balances)


class TripAssignmentTests(TestCase):
    order = classmethod(trip_fixtures.TripTests.order.__func__)

    @classmethod
    def setUpTestData(cls):
        trip_fixtures.TripTests.setUpTestData.__func__(cls)

    def setUp(self):
        self.client.force_login(self.user)

    def trip(self, *orders):
        return create_trip(actor=self.user, order_ids=[order.pk for order in orders], creation_key=uuid4())

    def assign(self, order, target, source=None, **overrides):
        target.refresh_from_db()
        if source:
            source.refresh_from_db()
        values = {"actor": self.user, "order_id": order.pk, "target_batch_id": target.pk,
                  "target_revision": target.revision, "source_batch_id": source.pk if source else None,
                  "source_revision": source.revision if source else None}
        values.update(overrides)
        return assign_order_to_trip(**values)

    def order_snapshot(self, order):
        order.refresh_from_db()
        return (order.purpose, order.status, order.recipient, order.comment, order.price_list_id,
                order.prepayment_total, order.postpayment_total, order.grand_total,
                list(order.items.order_by("pk").values()))

    def test_free_order_joins_existing_trip_and_repeat_does_not_duplicate_it(self):
        target = self.trip(self.first)
        before = self.order_snapshot(self.second)
        self.assign(self.second, target)
        self.second.refresh_from_db()
        self.assertEqual(self.second.trip_id, target.pk)
        self.assertEqual(target.lines.get(cd=self.cd).quantity, 10)
        self.assertEqual(target.lines.get(tech=self.tech).quantity, 3)
        self.assertEqual(set(target.source_orders.values_list("pk", flat=True)), {self.first.pk, self.second.pk})
        self.assertEqual(before, self.order_snapshot(self.second))
        with self.assertRaises(ValidationError):
            self.assign(self.second, target)
        self.assertEqual(target.lines.get(cd=self.cd).quantity, 10)
        self.assertEqual(CashTransaction.objects.count(), 0)
        self.assertEqual(OrderAdjustment.objects.count(), 0)
        _assert_balances(target)

    def test_move_preserves_supplier_splits_prices_caps_and_other_orders(self):
        source = self.trip(self.first, self.second)
        line = source.lines.get(cd=self.cd)
        change_trip_line(actor=self.user, batch_id=source.pk, line_id=line.pk, revision=source.revision,
                         quantity=7, action="transfer", target_supplier_id=self.c.pk, price_supplier_id=self.b.pk)
        third = self.order("Третий", 0, 3)
        target = self.trip(third)
        snapshots = [self.order_snapshot(order) for order in (self.first, self.second, third)]
        allocations = list(SupplierTripAllocation.objects.filter(order_item__order=self.second).order_by("pk").values_list(
            "pk", "prepayment_quantity", "postpayment_quantity", "prepayment_cap",
            "line__supplier_id", "line__price_supplier_id", "line__supplier_price_aed_snapshot"))
        self.assign(self.second, target, source)
        self.assertEqual(allocations, list(SupplierTripAllocation.objects.filter(order_item__order=self.second).order_by("pk").values_list(
            "pk", "prepayment_quantity", "postpayment_quantity", "prepayment_cap",
            "line__supplier_id", "line__price_supplier_id", "line__supplier_price_aed_snapshot")))
        self.assertEqual(snapshots, [self.order_snapshot(order) for order in (self.first, self.second, third)])
        self.assertEqual(sum(source.lines.values_list("quantity", flat=True)), 6)
        self.assertEqual(sum(target.lines.values_list("quantity", flat=True)), 10)
        self.assertFalse(SupplierTripAllocation.objects.filter(line__batch=source, order_item__order=self.second).exists())
        self.assertFalse(source.source_orders.filter(pk=self.second.pk).exists())
        self.assertTrue(target.source_orders.filter(pk=self.second.pk).exists())
        self.assertEqual(target.lines.get(supplier=self.c).supplier_price_aed_snapshot, Decimal("110"))
        _assert_balances(source)
        _assert_balances(target)

    def test_empty_trip_deletion_archives_history_without_deleting_orders(self):
        source, target = self.trip(self.first), self.trip(self.second)
        original_history = list(source.changes.values_list("description", flat=True))
        self.assign(self.first, target, source)
        self.assertFalse(source.lines.exists())
        source.refresh_from_db()
        delete_empty_trip(actor=self.user, batch_id=source.pk, revision=source.revision, archive_batch_id=target.pk)
        self.assertFalse(SupplierOrderBatch.objects.filter(pk=source.pk).exists())
        self.assertEqual(CustomerProcurementOrder.objects.count(), 2)
        archived = target.changes.get(details__action="delete_empty_trip")
        self.assertEqual(archived.details["deleted_batch_id"], source.pk)
        self.assertEqual([row["description"] for row in archived.details["history"]][-1:], original_history)
        self.assertEqual(sum(target.lines.values_list("quantity", flat=True)), 13)

    def test_nonempty_trip_deletion_is_rejected(self):
        source, target = self.trip(self.first), self.trip(self.second)
        with self.assertRaisesMessage(ValidationError, "пустой рейс"):
            delete_empty_trip(actor=self.user, batch_id=source.pk, revision=source.revision, archive_batch_id=target.pk)
        self.assertTrue(SupplierOrderBatch.objects.filter(pk=source.pk).exists())

    def test_versions_and_membership_protect_both_trips(self):
        source, target = self.trip(self.first), self.trip(self.second)
        for overrides in ({"target_revision": 99}, {"source_revision": 99},
                          {"source_batch_id": None}, {"target_batch_id": source.pk}):
            with self.subTest(overrides=overrides), self.assertRaises(ValidationError):
                self.assign(self.first, target, source, **overrides)
        self.first.refresh_from_db()
        self.assertEqual(self.first.trip_id, source.pk)
        self.assertEqual(source.lines.get(cd=self.cd).quantity, 5)
        self.assertEqual(target.lines.get(cd=self.cd).quantity, 5)

    def test_other_price_legacy_batch_and_missing_trip_are_rejected(self):
        other_price = ProcurementPriceList.objects.create(exchange_rate_aed_rub=20, created_by=self.user)
        other = SupplierOrderBatch.objects.create(price_list=other_price, created_by=self.user)
        legacy = SupplierOrderBatch.objects.create(created_by=self.user)
        for target in (other, legacy):
            with self.subTest(target=target.pk), self.assertRaises(ValidationError):
                self.assign(self.first, target)
        with self.assertRaises(ValidationError):
            assign_order_to_trip(actor=self.user, order_id=self.first.pk, target_batch_id=999, target_revision=0)
        self.first.refresh_from_db()
        self.assertIsNone(self.first.trip_id)

    def test_available_trips_exclude_other_price_current_and_frozen(self):
        current, frozen = self.trip(self.first), self.trip(self.second)
        self.second.status = self.second.Status.CONFIRMED
        self.second.save(update_fields=("status",))
        available = SupplierOrderBatch.objects.create(price_list=self.price, created_by=self.user)
        other_price = ProcurementPriceList.objects.create(exchange_rate_aed_rub=20, created_by=self.user)
        SupplierOrderBatch.objects.create(price_list=other_price, created_by=self.user)
        self.assertEqual(list(available_trips(price_list_id=self.price.pk, exclude_id=current.pk)), [available])

    def test_confirmed_order_or_either_frozen_trip_cannot_move(self):
        source, target = self.trip(self.first), self.trip(self.second)
        for order in (self.first, self.second):
            order.status = order.Status.CONFIRMED
            order.save(update_fields=("status",))
            with self.assertRaises(ValidationError):
                self.assign(self.first, target, source)
            order.status = order.Status.CREATED
            order.save(update_fields=("status",))
        self.assertEqual(source.lines.get(cd=self.cd).quantity, 5)
        self.assertEqual(target.lines.get(cd=self.cd).quantity, 5)

    def test_failure_rolls_back_membership_lines_and_audit(self):
        source, target = self.trip(self.first), self.trip(self.second)
        before = list(SupplierTripAllocation.objects.order_by("pk").values())
        with patch("orders.trips._record_trip_change", side_effect=ValidationError("Сбой журнала")):
            with self.assertRaises(ValidationError):
                self.assign(self.first, target, source)
        self.assertEqual(list(SupplierTripAllocation.objects.order_by("pk").values()), before)
        self.first.refresh_from_db()
        self.assertEqual(self.first.trip_id, source.pk)
        self.assertEqual(source.changes.count(), 1)
        self.assertEqual(target.changes.count(), 1)
        _assert_balances(source)
        _assert_balances(target)

    def test_zero_allocation_keeps_original_prepayment_cap_after_move(self):
        source, target = self.trip(self.first), self.trip(self.second)
        line = source.lines.get(cd=self.cd)
        allocation = line.allocations.get()
        change_trip_line(actor=self.user, batch_id=source.pk, line_id=line.pk, revision=source.revision,
                         quantity=0, action="adjust", distribution=[{"allocation_id": allocation.pk, "final_quantity": 0}])
        self.assign(self.first, target, source)
        allocation.refresh_from_db()
        self.assertEqual(allocation.prepayment_cap, 2)
        self.assertEqual(allocation.quantity, 0)
        self.assertEqual(allocation.line.batch_id, target.pk)
        self.assertFalse(source.lines.exists())

    def test_permissions_apply_to_service_page_and_post(self):
        target = self.trip(self.first)
        employee = User.objects.create_user("no-trip-rights")
        self.client.force_login(employee)
        url = reverse("orders:assign_trip", args=(self.second.pk,))
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url, {"target_trip": f"{target.pk}:0"}).status_code, 403)
        with self.assertRaises(PermissionDenied):
            self.assign(self.second, target, actor=employee)
        with self.assertRaises(PermissionDenied):
            delete_empty_trip(actor=employee, batch_id=target.pk, revision=0, archive_batch_id=target.pk)

    def test_assignment_page_links_post_and_old_form_are_safe(self):
        target = self.trip(self.first)
        url = reverse("orders:assign_trip", args=(self.second.pk,))
        self.assertContains(self.client.get(reverse("orders:list")), url)
        self.assertContains(self.client.get(reverse("orders:detail", args=(self.second.pk,))), "Добавить в рейс")
        self.assertContains(self.client.get(url), f'value="{target.pk}:{target.revision}"')
        response = self.client.post(url, {"target_trip": f"{target.pk}:{target.revision}"})
        self.assertRedirects(response, reverse("orders:trip_detail", args=(target.pk,)))
        self.assertContains(self.client.get(reverse("orders:trip_detail", args=(target.pk,))), "Перенести в другой рейс")
        old_revision = target.revision
        response = self.client.post(url, {"target_trip": f"{target.pk}:{old_revision}"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(target.lines.get(cd=self.cd).quantity, 10)


class MToFTripAssignmentTests(TestCase):
    order = TripAssignmentTests.__dict__["order"]
    trip = TripAssignmentTests.trip
    assign = TripAssignmentTests.assign
    setUp = TripAssignmentTests.setUp

    @classmethod
    def setUpTestData(cls):
        trip_fixtures.TripTests.setUpTestData.__func__(cls)
        cls.a.letter, cls.b.letter = "M", "F"
        cls.a.save(update_fields=("letter",))
        cls.b.save(update_fields=("letter",))

    def test_add_applies_m_to_f_only_to_new_order_and_keeps_existing_return(self):
        target = self.trip(self.first)
        line = target.lines.get(cd=self.cd, supplier=self.b)
        return_line_to_m(actor=self.user, batch_id=target.pk, line_id=line.pk, revision=target.revision)
        self.assign(self.second, target)
        self.assertEqual(target.lines.get(cd=self.cd, supplier=self.a).quantity, 5)
        self.assertEqual(target.lines.get(cd=self.cd, supplier=self.b).quantity, 5)
        self.assertEqual(target.lines.get(cd=self.cd, supplier=self.b).supplier_price_aed_snapshot, 100)
        _assert_balances(target)

    def test_move_keeps_manual_return_to_m_and_does_not_reapply_default(self):
        source, target = self.trip(self.first), self.trip(self.second)
        source.refresh_from_db()
        line = source.lines.get(cd=self.cd, supplier=self.b)
        return_line_to_m(actor=self.user, batch_id=source.pk, line_id=line.pk, revision=source.revision)
        self.assign(self.first, target, source)
        self.assertEqual(target.lines.get(cd=self.cd, supplier=self.a).quantity, 5)
        self.assertEqual(target.lines.get(cd=self.cd, supplier=self.b).quantity, 5)
        self.assertFalse(source.lines.exists())
        _assert_balances(target)
