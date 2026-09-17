from decimal import Decimal
from datetime import timedelta
from urllib import error, request
from unittest.mock import MagicMock, Mock, patch

from cryptography.fernet import Fernet
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from catalog.models import CD, Platform
from warehouse.models import CDWarehouseStock, Warehouse

from .crypto import decrypt_secret
from .client import AvitoAPIError, AvitoClient
from .models import (
    AvitoListingConnection,
    AvitoProductProfile,
    AvitoRemoteListing,
    AvitoSyncJob,
    IntegrationCredential,
)
from .services import _remote_snapshot, bind_listing, desired_state, rebind_listing, save_avito_credentials, sync_profile


TEST_KEY = Fernet.generate_key().decode("ascii")


class AvitoClientNetworkRetryTests(TestCase):
    def setUp(self):
        self.client = AvitoClient.__new__(AvitoClient)
        self.client.timeout = 1

    @patch("integrations.client.time.sleep")
    @patch("integrations.client.request.urlopen")
    def test_get_retries_transient_network_disconnect(self, urlopen, sleep):
        response = MagicMock()
        response.read.return_value = b'{"ok": true}'
        response.__enter__.return_value = response
        urlopen.side_effect = [error.URLError("TLS EOF"), response]
        req = request.Request("https://api.avito.ru/core/v1/items")

        self.assertEqual(self.client._execute(req), {"ok": True})
        self.assertEqual(urlopen.call_count, 2)
        sleep.assert_called_once()

    @patch("integrations.client.time.sleep")
    @patch("integrations.client.request.urlopen")
    def test_token_request_can_retry_but_price_update_cannot(self, urlopen, sleep):
        req = request.Request("https://api.avito.ru/token", data=b"grant_type=client_credentials")
        urlopen.side_effect = error.URLError("TLS EOF")
        with self.assertRaises(AvitoAPIError) as raised:
            self.client._execute(req, retry_network=True)
        self.assertEqual(raised.exception.category, "network")
        self.assertEqual(urlopen.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

        urlopen.reset_mock()
        sleep.reset_mock()
        with self.assertRaises(AvitoAPIError):
            self.client._execute(req)
        self.assertEqual(urlopen.call_count, 1)
        sleep.assert_not_called()


@override_settings(INTEGRATION_ENCRYPTION_KEY=TEST_KEY)
class IntegrationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("admin-avito", password="StrongAdmin!123")
        self.platform = Platform.objects.create(name="Avito test platform")
        self.warehouse = Warehouse.objects.first() or Warehouse.objects.create(name="Основной")
        self.cd = CD.objects.create(
            platform=self.platform, name="Товар A", sku="A-1", barcode="AVITO-A",
            avito_price=Decimal("4500.00"), description="Обычное описание",
        )
        CDWarehouseStock.objects.update_or_create(
            warehouse=self.warehouse, cd=self.cd, defaults={"quantity": 4}
        )

    @patch("integrations.services.AvitoClient")
    def test_credentials_are_encrypted_and_never_rendered(self, client_class):
        client_class.return_value.get_self.return_value = {"id": 123, "name": "Магазин"}
        credential = save_avito_credentials(client_id="public-id", client_secret="very-secret")
        self.assertNotEqual(credential.encrypted_client_id, "public-id")
        self.assertNotEqual(credential.encrypted_client_secret, "very-secret")
        self.assertEqual(decrypt_secret(credential.encrypted_client_secret), "very-secret")
        self.client.force_login(self.admin)
        response = self.client.get(reverse("integrations:api_keys"))
        self.assertNotContains(response, "public-id")
        self.assertNotContains(response, "very-secret")
        self.assertContains(response, "••••••••")

    def test_profile_requires_exactly_one_supported_product(self):
        with self.assertRaises(ValidationError):
            AvitoProductProfile(cd=self.cd, tech_id=999).full_clean()
        with self.assertRaises(ValidationError):
            AvitoProductProfile().full_clean()

    def test_database_enforces_one_product_and_one_listing(self):
        profile = AvitoProductProfile.objects.create(cd=self.cd)
        listing = AvitoRemoteListing.objects.create(avito_item_id=101, title="Объявление")
        AvitoListingConnection.objects.create(profile=profile, remote_listing=listing)
        other = CD.objects.create(platform=self.platform, name="Товар B", barcode="AVITO-B")
        other_profile = AvitoProductProfile.objects.create(cd=other)
        with self.assertRaises(IntegrityError), transaction.atomic():
            AvitoListingConnection.objects.create(profile=other_profile, remote_listing=listing)

    @patch("integrations.services.AvitoClient")
    def test_bind_snapshot_uses_recent_list_data_if_exact_item_details_confirm_it(self, client_class):
        IntegrationCredential.objects.create(provider="avito", account_id="123")
        listing = AvitoRemoteListing.objects.create(
            avito_item_id=202, title="Название Avito", category_name="Игры",
            status="active", remote_price=Decimal("3999.00"), last_seen_at=timezone.now(),
        )
        client_class.return_value.find_item.side_effect = AvitoAPIError(
            "Объявление больше не найдено в аккаунте Avito.", "validation", 404
        )
        client_class.return_value.get_item_details.return_value = {"status": "active"}

        snapshot = _remote_snapshot(listing)

        self.assertEqual(snapshot["title"], "Название Avito")
        self.assertEqual(snapshot["remote_price"], Decimal("3999.00"))
        client_class.return_value.get_item_details.assert_called_once_with("123", 202)

    @patch("integrations.services.AvitoClient")
    def test_bind_snapshot_accepts_old_listing_confirmed_by_exact_id(self, client_class):
        IntegrationCredential.objects.create(provider="avito", account_id="123")
        listing = AvitoRemoteListing.objects.create(
            avito_item_id=202, title="Старое объявление",
            last_seen_at=timezone.now() - timedelta(hours=2),
            remote_price=Decimal("2500.00"),
        )
        client_class.return_value.find_item.side_effect = AvitoAPIError(
            "Объявление больше не найдено в аккаунте Avito.", "validation", 404
        )
        client_class.return_value.get_item_details.return_value = {"status": "old"}

        snapshot = _remote_snapshot(listing)
        self.assertEqual(snapshot["status"], "old")
        self.assertEqual(snapshot["remote_price"], Decimal("2500.00"))
        client_class.return_value.get_item_details.assert_called_once_with("123", 202)

    @patch("integrations.services.AvitoClient")
    def test_bind_snapshot_skips_list_scan_for_listing_missing_from_current_list(self, client_class):
        IntegrationCredential.objects.create(provider="avito", account_id="123")
        listing = AvitoRemoteListing.objects.create(
            avito_item_id=205, title="Старое объявление", status="active",
            remote_price=Decimal("2500.00"),
            last_seen_at=timezone.now() - timedelta(hours=5),
            missing_since=timezone.now(),
        )
        client_class.return_value.get_item_details.return_value = {"status": "old"}

        snapshot = _remote_snapshot(listing)

        self.assertEqual(snapshot["status"], "old")
        client_class.return_value.find_item.assert_not_called()
        client_class.return_value.get_item_details.assert_called_once_with("123", 205)

    @patch("integrations.services.AvitoClient")
    def test_bind_snapshot_rejects_listing_not_found_by_exact_id(self, client_class):
        IntegrationCredential.objects.create(provider="avito", account_id="123")
        listing = AvitoRemoteListing.objects.create(
            avito_item_id=202, title="Название Avito", last_seen_at=timezone.now(),
        )
        client_class.return_value.find_item.side_effect = AvitoAPIError(
            "Объявление больше не найдено в аккаунте Avito.", "validation", 404
        )
        client_class.return_value.get_item_details.side_effect = AvitoAPIError(
            "Avito отклонил данные запроса.", "validation", 404
        )

        with self.assertRaises(AvitoAPIError) as raised:
            _remote_snapshot(listing)
        self.assertEqual(raised.exception.status, 404)

    @patch("integrations.services._remote_snapshot")
    def test_initial_bind_preserves_crm_price_stock_and_regular_fields(self, snapshot):
        snapshot.return_value = {
            "title": "Название Avito", "category_name": "Игры", "status": "active",
            "details": {"status": "active"}, "remote_price": Decimal("3999.00"),
        }
        listing = AvitoRemoteListing.objects.create(avito_item_id=202, title="Remote")
        with self.captureOnCommitCallbacks(execute=True):
            connection = bind_listing(
                listing=listing, product=self.cd, product_kind="cd", actor=self.admin
            )
        self.cd.refresh_from_db()
        connection.profile.refresh_from_db()
        self.assertEqual(self.cd.avito_price, Decimal("4500.00"))
        self.assertEqual(self.cd.description, "Обычное описание")
        self.assertEqual(self.cd.warehouse_stocks.get().quantity, 4)
        self.assertTrue(connection.profile.sell_on_avito)
        self.assertEqual(connection.profile.listing_title, "Название Avito")

    @patch("integrations.services._remote_snapshot")
    def test_initial_bind_imports_remote_price_only_when_crm_price_is_empty(self, snapshot):
        self.cd.avito_price = None
        self.cd.save(update_fields=("avito_price",))
        snapshot.return_value = {
            "title": "Название Avito", "category_name": "Игры", "status": "active",
            "details": {"status": "active"}, "remote_price": Decimal("3999.00"),
        }
        listing = AvitoRemoteListing.objects.create(avito_item_id=203, title="Remote")
        with self.captureOnCommitCallbacks(execute=True):
            bind_listing(listing=listing, product=self.cd, product_kind="cd", actor=self.admin)
        self.cd.refresh_from_db()
        self.assertEqual(self.cd.avito_price, Decimal("3999.00"))

    @patch("integrations.services._remote_snapshot")
    def test_binding_old_listing_keeps_avito_sale_disabled_and_updates_status(self, snapshot):
        snapshot.return_value = {
            "title": "Старое объявление", "category_name": "Игры", "status": "old",
            "details": {"status": "old"}, "remote_price": Decimal("2500.00"),
        }
        listing = AvitoRemoteListing.objects.create(
            avito_item_id=204, title="Старое объявление", status="active",
        )

        with self.captureOnCommitCallbacks(execute=True):
            connection = bind_listing(
                listing=listing, product=self.cd, product_kind="cd", actor=self.admin
            )

        listing.refresh_from_db()
        connection.profile.refresh_from_db()
        self.assertEqual(listing.status, "old")
        self.assertFalse(connection.profile.sell_on_avito)

    @patch("integrations.services._remote_snapshot")
    def test_rebind_clears_only_old_avito_data_and_keeps_listing_id(self, snapshot):
        snapshot.return_value = {
            "title": "Remote", "category_name": "Игры", "status": "active", "details": {},
        }
        old_profile = AvitoProductProfile.objects.create(
            cd=self.cd, sell_on_avito=True, listing_title="Old", attributes={"x": "y"}
        )
        listing = AvitoRemoteListing.objects.create(avito_item_id=303, title="Remote")
        connection = AvitoListingConnection.objects.create(profile=old_profile, remote_listing=listing)
        target = CD.objects.create(platform=self.platform, name="Товар B", barcode="AVITO-C")
        with self.captureOnCommitCallbacks(execute=True):
            rebind_listing(
                connection=connection, product=target, product_kind="cd", actor=self.admin
            )
        connection.refresh_from_db()
        old_profile.refresh_from_db()
        self.cd.refresh_from_db()
        self.assertEqual(connection.remote_listing.avito_item_id, 303)
        self.assertEqual(connection.profile.cd_id, target.pk)
        self.assertFalse(old_profile.sell_on_avito)
        self.assertEqual(old_profile.attributes, {})
        self.assertEqual(self.cd.avito_price, Decimal("4500.00"))
        self.assertEqual(self.cd.description, "Обычное описание")

    def test_desired_state_reads_current_global_stock_and_avito_price(self):
        profile = AvitoProductProfile.objects.create(cd=self.cd, sell_on_avito=True)
        state = desired_state(profile)
        self.assertEqual(state["stock"], 4)
        self.assertEqual(state["price"], "4500.00")

    def test_stock_change_is_enqueued_after_commit_and_coalesced(self):
        profile = AvitoProductProfile.objects.create(cd=self.cd)
        stock = self.cd.warehouse_stocks.get()
        with self.captureOnCommitCallbacks(execute=True):
            stock.quantity = 3
            stock.save()
            stock.quantity = 2
            stock.save()
        jobs = AvitoSyncJob.objects.filter(dedupe_key=f"product:{profile.pk}")
        self.assertEqual(jobs.count(), 1)
        self.assertEqual(jobs.get().status, AvitoSyncJob.Status.PENDING)

    def test_sell_true_without_listing_records_clear_autoload_error(self):
        profile = AvitoProductProfile.objects.create(cd=self.cd, sell_on_avito=True)
        sync_profile(profile.pk)
        profile.refresh_from_db()
        self.assertEqual(profile.sync_status, AvitoProductProfile.SyncStatus.ERROR)
        self.assertIn("Autoload", profile.last_error)

    @patch("integrations.services.AvitoClient")
    def test_missing_price_does_not_block_linked_stock_sync(self, client_class):
        self.cd.avito_price = None
        self.cd.save(update_fields=("avito_price",))
        client = Mock()
        client.update_stock.return_value = {"stocks": [{"success": True}]}
        client_class.return_value = client
        profile = AvitoProductProfile.objects.create(cd=self.cd, sell_on_avito=True)
        listing = AvitoRemoteListing.objects.create(avito_item_id=405, title="Remote")
        AvitoListingConnection.objects.create(profile=profile, remote_listing=listing)
        sync_profile(profile.pk)
        client.update_stock.assert_called_once_with(405, 4)
        client.update_price.assert_not_called()
        profile.refresh_from_db()
        self.assertEqual(profile.sync_status, AvitoProductProfile.SyncStatus.ERROR)
        self.assertIn("Цена Avito", profile.last_error)

    @patch("integrations.services.AvitoClient")
    def test_linked_sync_sends_current_stock_and_price(self, client_class):
        IntegrationCredential.objects.create(
            provider="avito", encrypted_client_id="x", encrypted_client_secret="y"
        )
        client = Mock()
        client.update_stock.return_value = {"stocks": [{"success": True}]}
        client.update_price.return_value = {"result": {"success": True}}
        client_class.return_value = client
        profile = AvitoProductProfile.objects.create(cd=self.cd, sell_on_avito=True)
        listing = AvitoRemoteListing.objects.create(avito_item_id=404, title="Remote")
        AvitoListingConnection.objects.create(profile=profile, remote_listing=listing)
        sync_profile(profile.pk)
        client.update_stock.assert_called_once_with(404, 4)
        client.update_price.assert_called_once_with(404, Decimal("4500.00"))
        profile.refresh_from_db()
        self.assertEqual(profile.sync_status, AvitoProductProfile.SyncStatus.OK)

    def test_direct_url_requires_permission(self):
        employee = User.objects.create_user("employee-avito", password="StrongPass!123")
        self.client.force_login(employee)
        self.assertEqual(self.client.get(reverse("integrations:avito")).status_code, 403)
        permission = Permission.objects.get(codename="view_avito_integration")
        employee.user_permissions.add(permission)
        self.assertEqual(self.client.get(reverse("integrations:avito")).status_code, 200)

    def test_product_card_contains_avito_block(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("nomenclature:cd_detail", args=(self.cd.pk,)))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Продаётся на Avito")
        self.assertContains(response, "Глобальный остаток CRM")
