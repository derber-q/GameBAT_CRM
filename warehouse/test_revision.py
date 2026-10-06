from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.test import Client, TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from catalog.models import CD, Tech, Platform, Brand, ProductType
from .models import Warehouse, CDWarehouseStock, TechWarehouseStock, WarehouseRevision, WarehouseRevisionItem
from .revision_services import start_revision, set_checked, revision_rows, grouped_rows, RevisionConflict
from .storage_services import update_storage_locations


class RevisionFixture:
    def seed(self):
        self.user = get_user_model().objects.create_superuser(username="revision-admin", password="test")
        self.a = Warehouse.objects.create(name="Склад A")
        self.b = Warehouse.objects.create(name="Склад B")
        self.platform = Platform.objects.create(name="PS5")
        self.cd = CD.objects.create(name="Astro Bot", platform=self.platform, cost=100)
        self.cd2 = CD.objects.create(name="Alan Wake 2", platform=self.platform)
        self.zero = CD.objects.create(name="Zero game", platform=self.platform)
        self.tech = Tech.objects.create(name="Геймпад", brand=Brand.objects.create(name="Sony"), product_type=ProductType.objects.create(name="Геймпады"))
        self.stock = CDWarehouseStock.objects.create(warehouse=self.a, cd=self.cd, quantity=5)
        CDWarehouseStock.objects.create(warehouse=self.a, cd=self.cd2, quantity=1)
        CDWarehouseStock.objects.create(warehouse=self.a, cd=self.zero, quantity=0)
        CDWarehouseStock.objects.create(warehouse=self.b, cd=self.zero, quantity=12)
        TechWarehouseStock.objects.create(warehouse=self.a, tech=self.tech, quantity=2)

    def start(self, warehouse=None, previous=None):
        return start_revision(warehouse_id=(warehouse or self.a).pk, actor=self.user, expected_revision_id=previous.pk if previous else None)

    def mark(self, revision, *, kind="cd", product=None, checked=True, warehouse=None):
        return set_checked(warehouse_id=(warehouse or self.a).pk, revision_id=revision.pk, kind=kind,
                           product_id=(product or self.cd).pk, checked=checked, actor=self.user)

    def rows(self, revision, warehouse=None):
        return revision_rows(warehouse=warehouse or self.a, revision=revision, kinds=("cd", "tech"))


class WarehouseRevisionTests(RevisionFixture, TestCase):
    def setUp(self):
        self.seed()
        self.client.force_login(self.user)

    def test_entry_and_initial_get_do_not_create_cycle(self):
        self.assertContains(self.client.get(reverse("warehouse:detail", args=[self.a.pk])), "Ревизия")
        url = reverse("warehouse:revision", args=[self.a.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["progress"]["total"], 3)
        self.assertContains(response, "Astro Bot")
        self.assertNotContains(response, "Zero game")
        self.client.get(url)
        self.assertFalse(WarehouseRevision.objects.exists())

    def test_marks_persist_across_reload_session_and_modes(self):
        revision = self.start()
        item = self.mark(revision)
        self.assertEqual(item.checked_by, self.user)
        self.assertIsNotNone(item.checked_at)
        second = Client()
        second.force_login(self.user)
        for mode in ("products", "locations"):
            response = second.get(reverse("warehouse:revision", args=[self.a.pk]), {"mode": mode})
            self.assertEqual(response.context["revision"].pk, revision.pk)
            self.assertEqual(response.context["progress"]["checked"], 1)
            self.assertContains(response, "is-checked")
        self.assertEqual(WarehouseRevision.objects.count(), 1)
        self.mark(revision, checked=False)
        self.assertFalse(any(row["checked"] for row in self.rows(revision)))

    def test_first_checkbox_starts_cycle_and_saves_atomically(self):
        url = reverse("warehouse:revision_check", args=[self.a.pk])
        data = {"revision_id": "", "kind": "cd", "product_id": self.cd.pk, "checked": "true"}
        self.assertEqual(self.client.post(url, {**data, "product_id": self.zero.pk}).status_code, 409)
        self.assertFalse(WarehouseRevision.objects.exists())
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        revision = WarehouseRevision.objects.get(warehouse=self.a, is_active=True)
        self.assertEqual(response.json()["revision_id"], revision.pk)
        self.assertTrue(revision.items.get(cd=self.cd).checked)
        self.assertEqual(self.client.post(url, data).status_code, 409)
        self.assertEqual(WarehouseRevision.objects.count(), 1)
        response = self.client.post(url, {**data, "revision_id": revision.pk, "checked": "false"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(revision.items.get(cd=self.cd).checked)

    def test_new_cycle_keeps_history_and_other_warehouse(self):
        old = self.start()
        other = self.start(self.b)
        self.mark(old)
        self.mark(other, warehouse=self.b, product=self.zero)
        new = self.start(previous=old)
        old.refresh_from_db()
        self.assertFalse(old.is_active)
        self.assertIsNotNone(old.closed_at)
        self.assertTrue(old.items.get(cd=self.cd).checked)
        self.assertFalse(any(row["checked"] for row in self.rows(new)))
        self.assertTrue(self.rows(other, self.b)[0]["checked"])
        with self.assertRaises(RevisionConflict):
            self.mark(old)
        with self.assertRaises(RevisionConflict):
            self.start(previous=old)

    def test_current_local_stock_zero_return_and_new_products(self):
        revision = self.start()
        self.mark(revision)
        self.stock.quantity = 0
        self.stock.save(update_fields=["quantity"])
        self.assertNotIn(self.cd.pk, [row["product"].pk for row in self.rows(revision) if row["kind"] == "cd"])
        self.stock.quantity = 8
        self.stock.save(update_fields=["quantity"])
        row = next(row for row in self.rows(revision) if row["kind"] == "cd" and row["product"].pk == self.cd.pk)
        self.assertEqual(row["quantity"], 8)
        self.assertFalse(row["checked"])
        zero = CDWarehouseStock.objects.get(warehouse=self.a, cd=self.zero)
        zero.quantity = 4
        zero.save(update_fields=["quantity"])
        row = next(row for row in self.rows(revision) if row["kind"] == "cd" and row["product"].pk == self.zero.pk)
        self.assertEqual(row["quantity"], 4)
        self.assertFalse(row["checked"])
        self.mark(revision)
        self.assertTrue(WarehouseRevisionItem.objects.get(revision=revision, cd=self.cd).checked)
        self.assertIsNone(WarehouseRevisionItem.objects.get(revision=revision, cd=self.cd).invalidated_at)

    def test_deleted_stock_returns_unchecked(self):
        revision = self.start()
        self.mark(revision)
        self.stock.delete()
        CDWarehouseStock.objects.create(warehouse=self.a, cd=self.cd, quantity=3)
        self.assertFalse(next(row["checked"] for row in self.rows(revision) if row["kind"] == "cd" and row["product"].pk == self.cd.pk))

    def test_mark_does_not_change_stock_cost_or_enqueue_sync(self):
        revision = self.start()
        before = list(CDWarehouseStock.objects.values_list("pk", "quantity"))
        with patch("integrations.signals.enqueue_profile_sync_after_commit") as sync:
            self.mark(revision)
            self.mark(revision, checked=False)
        sync.assert_not_called()
        self.assertEqual(list(CDWarehouseStock.objects.values_list("pk", "quantity")), before)
        self.cd.refresh_from_db()
        self.assertEqual(self.cd.cost, 100)

    def test_grouping_cd_platform_tech_type_and_alphabet(self):
        other_platform = Platform.objects.create(name="PS4")
        game = CD.objects.create(name="Z game", platform=other_platform)
        CDWarehouseStock.objects.create(warehouse=self.a, cd=game, quantity=1)
        device = Tech.objects.create(name="Аксессуар", brand=self.tech.brand, product_type=self.tech.product_type)
        TechWarehouseStock.objects.create(warehouse=self.a, tech=device, quantity=1)
        groups = grouped_rows(self.rows(None), "products")
        self.assertEqual([group["title"] for group in groups], ["CD · PS4", "CD · PS5", "TECH · Геймпады"])
        self.assertEqual([row["product"].name for row in groups[1]["rows"]], ["Alan Wake 2", "Astro Bot"])
        self.assertEqual([row["product"].name for row in groups[2]["rows"]], ["Аксессуар", "Геймпад"])

    def test_first_location_natural_order_full_display_no_duplicates(self):
        locations = (("cd", self.cd, r"A2-1-1\2, A1-1, B12-6-1"), ("cd", self.cd2, "A10-1"), ("tech", self.tech, "A1-2"))
        for kind, product, raw in locations:
            update_storage_locations(actor=self.user, warehouse_id=self.a.pk, product_type=kind, product_id=product.pk, raw_value=raw)
        stock = CDWarehouseStock.objects.get(warehouse=self.a, cd=self.zero)
        stock.quantity = 1
        stock.save(update_fields=["quantity"])
        groups = grouped_rows(self.rows(None), "locations")
        self.assertEqual([group["title"] for group in groups], ["A1-2", r"A2-1-1\2", "A10-1", "Без места хранения"])
        self.assertEqual(groups[1]["rows"][0]["locations"], locations[0][2])
        self.assertEqual(sum(len(group["rows"]) for group in groups), 4)

    def test_cd_tech_identity_and_constraints(self):
        revision = self.start()
        self.mark(revision)
        self.mark(revision, kind="tech", product=self.tech)
        self.assertEqual(revision.items.count(), 2)
        for values in ({"cd": self.cd}, {"cd": self.cd, "tech": self.tech}, {}):
            with self.assertRaises(IntegrityError), transaction.atomic():
                WarehouseRevisionItem.objects.create(revision=revision, **values)
        with self.assertRaises(IntegrityError), transaction.atomic():
            WarehouseRevision.objects.create(warehouse=self.a, started_by=self.user)

    def test_permissions_types_csrf_and_foreign_revision(self):
        revision = self.start()
        other = self.start(self.b)
        url = reverse("warehouse:revision_check", args=[self.a.pk])
        data = {"revision_id": revision.pk, "kind": "cd", "product_id": self.cd.pk, "checked": "true", "quantity": 999}
        self.assertEqual(self.client.post(url, data).status_code, 200)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 5)
        self.assertEqual(self.client.post(url, {**data, "revision_id": other.pk}).status_code, 409)
        self.assertEqual(self.client.post(url, {**data, "product_id": self.zero.pk}).status_code, 409)
        self.assertEqual(self.client.post(url, {**data, "checked": "anything"}).status_code, 400)
        self.assertEqual(self.client.get(url).status_code, 405)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.user)
        self.assertEqual(csrf.post(url, data).status_code, 403)
        user = get_user_model().objects.create_user(username="cd-only", password="test")
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("warehouse:revision", args=[self.a.pk])).status_code, 403)
        self.assertEqual(self.client.post(url, data).status_code, 403)
        user.user_permissions.add(Permission.objects.get(content_type__app_label="catalog", codename="view_cd"))
        response = self.client.get(reverse("warehouse:revision", args=[self.a.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["progress"]["total"], 2)
        self.assertNotContains(response, self.tech.name)
        self.assertEqual(self.client.post(url, data).status_code, 200)
        self.assertEqual(self.client.post(url, {**data, "kind": "tech", "product_id": self.tech.pk}).status_code, 403)
        self.assertEqual(self.client.post(reverse("warehouse:revision_start", args=[self.a.pk]), {"confirm": "yes"}).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("warehouse:revision", args=[self.a.pk])).status_code, 302)

    def test_start_confirmation_and_stale_submission(self):
        url = reverse("warehouse:revision_start", args=[self.a.pk])
        self.client.post(url, {})
        self.assertFalse(WarehouseRevision.objects.exists())
        self.client.post(url, {"confirm": "yes"})
        self.assertEqual(WarehouseRevision.objects.count(), 1)
        self.client.post(url, {"confirm": "yes"})
        self.assertEqual(WarehouseRevision.objects.count(), 1)

    def test_query_count_does_not_grow_with_items(self):
        revision = self.start()
        with CaptureQueriesContext(connection) as first:
            self.rows(revision)
        for i in range(12):
            game = CD.objects.create(name=f"Game {i}", platform=self.platform)
            CDWarehouseStock.objects.create(warehouse=self.a, cd=game, quantity=1)
        with CaptureQueriesContext(connection) as second:
            self.rows(revision)
        self.assertEqual(len(first), len(second))
        self.assertLessEqual(len(second), 5)


class WarehouseRevisionConcurrencyTests(RevisionFixture, TransactionTestCase):
    def setUp(self):
        self.seed()

    def test_concurrent_marks_have_one_item(self):
        revision = self.start()
        barrier = Barrier(2)
        def mark():
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=self.user.pk)
                barrier.wait(timeout=10)
                return set_checked(warehouse_id=self.a.pk, revision_id=revision.pk, kind="cd", product_id=self.cd.pk, checked=True, actor=actor).pk
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(mark) for _ in range(2)]
            results = [future.result(timeout=40) for future in futures]
        self.assertEqual(results[0], results[1])
        self.assertEqual(revision.items.count(), 1)

    def test_concurrent_initial_start_creates_one_active_cycle(self):
        barrier = Barrier(2)
        def start():
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=self.user.pk)
                barrier.wait(timeout=10)
                try:
                    return start_revision(warehouse_id=self.a.pk, actor=actor, expected_revision_id=None).pk
                except RevisionConflict:
                    return None
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(start) for _ in range(2)]
            results = [future.result(timeout=40) for future in futures]
        self.assertEqual(sum(result is not None for result in results), 1)
        self.assertEqual(WarehouseRevision.objects.filter(warehouse=self.a).count(), 1)
