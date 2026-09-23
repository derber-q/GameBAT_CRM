from unittest.mock import Mock, patch

from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from catalog.models import CD, Tech, Platform, Brand, ProductType
from warehouse.models import Warehouse, CDWarehouseStock, TechWarehouseStock
from .client import AvitoAPIError
from .models import AvitoListingConnection, AvitoProductProfile, AvitoRemoteListing, AvitoSyncJob
from .required_actions import RequiredAction, get_avito_required_actions, safe_listing_url
from .services import refresh_remote_listings
from .tasks import process_one_job


class RequiredActionsTests(TestCase):
    def setUp(self):
        self.warehouse = Warehouse.objects.first() or Warehouse.objects.create(name="Test warehouse")
        self.platform = Platform.objects.create(name="Test console")
        self.cd = CD.objects.create(name="Test disc", platform=self.platform, sku="ACTION-1", avito_price=100)
        CDWarehouseStock.objects.update_or_create(cd=self.cd, warehouse=self.warehouse, defaults={"quantity": 0})
        self.profile = AvitoProductProfile.objects.create(cd=self.cd, sell_on_avito=True)
        self.listing = AvitoRemoteListing.objects.create(
            avito_item_id=1001, title="Test listing", status="active",
            url="https://www.avito.ru/test_listing_1001", last_seen_at=timezone.now(),
        )
        self.connection = AvitoListingConnection.objects.create(profile=self.profile, remote_listing=self.listing)
        # Only our explicit read-only task should be processed in these tests.
        AvitoSyncJob.objects.all().delete()
        self.admin = User.objects.create_superuser("actions-admin", password="Test-password!1")

    def stock(self, quantity):
        CDWarehouseStock.objects.filter(cd=self.cd).update(quantity=quantity)

    def status(self, value):
        AvitoRemoteListing.objects.filter(pk=self.listing.pk).update(status=value)

    def job(self):
        return AvitoSyncJob.objects.create(
            dedupe_key="required-actions-refresh", job_type="status_refresh",
            run_after=timezone.now(), phase="Ожидает запуска обработчика",
        )

    def test_zero_published_red_and_safe_link(self):
        row, = get_avito_required_actions()
        self.assertEqual(row.action, RequiredAction.UNPUBLISH_MANUALLY)
        self.assertEqual(row.global_stock, 0)
        self.client.force_login(self.admin)
        response = self.client.get(reverse("integrations:avito"))
        self.assertContains(response, 'class="avito-action-unpublish"')
        self.assertContains(response, 'target="_blank" rel="noopener noreferrer"')
        self.assertContains(response, self.listing.url)
        self.assertContains(response, "Снять с публикации")

    def test_positive_archived_green(self):
        self.stock(5)
        self.status("old")
        row, = get_avito_required_actions()
        self.assertEqual(row.action, RequiredAction.PUBLISH_MANUALLY)
        self.client.force_login(self.admin)
        response = self.client.get(reverse("integrations:avito"))
        self.assertContains(response, 'class="avito-action-publish"')
        self.assertContains(response, "Опубликуйте объявление")

    def test_correct_states_and_unsupported_statuses(self):
        for quantity, status in [(5, "active"), (0, "old"), (5, "blocked"), (5, "rejected"),
                                 (5, "removed"), (5, "moderation"), (5, "unknown"), (0, "")]:
            with self.subTest(quantity=quantity, status=status):
                self.stock(quantity)
                self.status(status)
                self.assertEqual(get_avito_required_actions(), [])

    def test_sell_flag_preserves_existing_intent(self):
        self.stock(5)
        AvitoProductProfile.objects.filter(pk=self.profile.pk).update(sell_on_avito=False)
        self.status("old")
        self.assertEqual(get_avito_required_actions(), [])
        self.status("active")
        self.assertEqual(get_avito_required_actions()[0].action, RequiredAction.UNPUBLISH_MANUALLY)

    def test_unlinked_missing_and_archived_product_are_excluded(self):
        self.connection.delete()
        self.assertEqual(get_avito_required_actions(), [])
        AvitoListingConnection.objects.create(profile=self.profile, remote_listing=self.listing)
        AvitoRemoteListing.objects.filter(pk=self.listing.pk).update(missing_since=timezone.now())
        self.assertEqual(get_avito_required_actions(), [])
        AvitoRemoteListing.objects.filter(pk=self.listing.pk).update(missing_since=None)
        CD.objects.filter(pk=self.cd.pk).update(is_archived=True)
        self.assertEqual(get_avito_required_actions(), [])

    def test_global_stock_uses_all_warehouses_not_consignment(self):
        CD.objects.filter(pk=self.cd.pk).update(quantity_on_consignment=9)
        self.assertEqual(get_avito_required_actions()[0].global_stock, 0)
        other = Warehouse.objects.create(name="Other warehouse")
        CDWarehouseStock.objects.create(cd=self.cd, warehouse=other, quantity=3)
        self.assertEqual(get_avito_required_actions(), [])
        self.status("old")
        self.assertEqual(get_avito_required_actions()[0].global_stock, 3)

    def test_tech_and_query_count_do_not_scale(self):
        brand = Brand.objects.create(name="Test brand")
        product_type = ProductType.objects.create(name="Test device")
        for i in range(20):
            tech = Tech.objects.create(name=f"Device {i}", brand=brand, product_type=product_type)
            TechWarehouseStock.objects.update_or_create(tech=tech, warehouse=self.warehouse, defaults={"quantity": 2})
            profile = AvitoProductProfile.objects.create(tech=tech, sell_on_avito=True)
            listing = AvitoRemoteListing.objects.create(avito_item_id=2000+i, title=f"Device {i}", status="old")
            AvitoListingConnection.objects.create(profile=profile, remote_listing=listing)
        with self.assertNumQueries(3):
            rows = get_avito_required_actions()
        self.assertEqual(len(rows), 21)
        self.assertEqual(rows[0].action, RequiredAction.UNPUBLISH_MANUALLY)
        self.assertEqual(sum(row.action == RequiredAction.PUBLISH_MANUALLY for row in rows), 20)

    def test_url_safety_and_snapshot_fallback(self):
        for url in ("javascript:alert(1)", "https://avito.ru.evil.test/x", "https://evil.test/x",
                    "https://user@www.avito.ru/x", "//www.avito.ru/x", "https://www.avito.ru:999/x"):
            self.listing.url = url
            self.assertEqual(safe_listing_url(self.listing), "")
        self.listing.snapshot = {"url": "https://www.avito.ru/valid_1001"}
        self.assertEqual(safe_listing_url(self.listing), self.listing.snapshot["url"])

    def test_empty_message(self):
        self.stock(5)
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse("integrations:avito")), "Необходимых действий нет.")

    @patch("integrations.views.get_avito_credential")
    def test_refresh_is_post_permission_checked_and_deduplicated(self, credential):
        credential.return_value = Mock(is_configured=True)
        url = reverse("integrations:required_actions_refresh")
        user = User.objects.create_user("actions-viewer", password="Test-password!1")
        user.user_permissions.add(Permission.objects.get(codename="view_avito_integration"))
        self.client.force_login(user)
        self.assertEqual(self.client.post(url).status_code, 403)
        self.assertEqual(AvitoSyncJob.objects.filter(job_type="status_refresh").count(), 0)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertEqual(AvitoSyncJob.objects.filter(job_type="status_refresh").count(), 1)
        job = AvitoSyncJob.objects.get(job_type="status_refresh")
        job.status = "done"
        job.save()
        self.client.post(url)
        job.refresh_from_db()
        self.assertEqual(job.status, "pending")
        self.assertEqual(self.client.get(reverse("integrations:required_actions_status", args=[job.pk])).json()["status"], "pending")

    @patch("integrations.tasks.refresh_remote_listings")
    @patch("integrations.tasks.sync_profile")
    def test_background_task_only_refreshes_statuses(self, sync, refresh):
        job = self.job()
        self.assertTrue(process_one_job())
        refresh.assert_called_once_with(check_linked_statuses=True)
        sync.assert_not_called()
        job.refresh_from_db()
        self.assertEqual(job.status, "done")
        self.assertIsNotNone(job.finished_at)

    @patch("integrations.tasks.refresh_remote_listings")
    def test_api_error_keeps_old_data_and_reports_failure(self, refresh):
        refresh.side_effect = AvitoAPIError("Нет доступа: HTTP 403", "auth", 403)
        job = self.job()
        process_one_job()
        job.refresh_from_db()
        self.assertEqual(job.status, "error")
        self.assertIn("403", job.last_error)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, "active")
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse("integrations:avito")), "Обновление не завершено")

    @patch("integrations.services.get_avito_credential")
    @patch("integrations.services.AvitoClient")
    def test_real_refresh_fetches_archived_details_without_changing_product(self, client_class, credential):
        credential.return_value = Mock(account_id="123")
        client = client_class.return_value
        client.list_items.return_value = {"resources": [{"id": 9999, "status": "active"}]}
        client.get_item_details.return_value = {"status": "old", "url": self.listing.url, "price": 9999}
        original = CD.objects.filter(pk=self.cd.pk).values().get()
        self.assertEqual(len(get_avito_required_actions()), 1)
        refresh_remote_listings(check_linked_statuses=True)
        client.get_item_details.assert_called_once_with("123", 1001)
        self.assertEqual(get_avito_required_actions(), [])
        self.assertEqual(CD.objects.filter(pk=self.cd.pk).values().get(), original)
        self.assertEqual(self.cd.warehouse_stocks.get().quantity, 0)
        self.assertEqual([call[0] for call in client.method_calls], ["list_items", "list_items", "get_item_details"])
        self.stock(5)
        self.assertEqual(len(get_avito_required_actions()), 1)
        client.list_items.return_value = {"resources": [{"id": 1001, "status": "active", "url": self.listing.url}]}
        refresh_remote_listings(check_linked_statuses=True)
        self.assertEqual(get_avito_required_actions(), [])

    @patch("integrations.services.get_avito_credential")
    @patch("integrations.services.AvitoClient")
    def test_missing_item_is_not_guessed_as_archive(self, client_class, credential):
        credential.return_value = Mock(account_id="123")
        client_class.return_value.list_items.return_value = {"resources": [{"id": 9999, "status": "active"}]}
        client_class.return_value.get_item_details.side_effect = AvitoAPIError("Not found", "validation", 404)
        with self.assertRaises(AvitoAPIError):
            refresh_remote_listings(check_linked_statuses=True)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, "active")
        self.assertIsNotNone(self.listing.missing_since)
        self.assertEqual(get_avito_required_actions(), [])

    @patch("integrations.services.get_avito_credential")
    @patch("integrations.services.AvitoClient")
    def test_all_items_archived_empty_active_list_is_not_an_error(self, client_class, credential):
        credential.return_value = Mock(account_id="123")
        client_class.return_value.list_items.return_value = {"resources": []}
        client_class.return_value.get_item_details.return_value = {"status": "old"}
        refresh_remote_listings(check_linked_statuses=True)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, "old")
        self.assertIsNone(self.listing.missing_since)
        self.assertEqual(get_avito_required_actions(), [])

    @patch("integrations.tasks.refresh_remote_listings")
    def test_retryable_error_is_visible_and_bounded(self, refresh):
        refresh.side_effect = AvitoAPIError("Нет соединения", "network")
        job = self.job()
        process_one_job()
        job.refresh_from_db()
        self.assertEqual(job.status, "pending")
        self.assertEqual(job.attempts, 1)
        self.assertIn("Нет соединения", job.last_error)
        AvitoSyncJob.objects.filter(pk=job.pk).update(attempts=4, run_after=timezone.now())
        process_one_job()
        job.refresh_from_db()
        self.assertEqual(job.status, "error")
