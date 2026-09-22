from decimal import Decimal
from datetime import timedelta
from urllib import error, request
from unittest.mock import MagicMock, Mock, patch

from cryptography.fernet import Fernet
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import IntegrityError, OperationalError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from catalog.models import CD, Platform
from warehouse.models import CDWarehouseStock, Warehouse

from .crypto import decrypt_secret
from .client import AvitoAPIError, AvitoClient
from .manual_sync import reconcile_active_listings
from .models import (
    AvitoListingConnection,
    AvitoProductProfile,
    AvitoRemoteListing,
    AvitoSyncJob,
    IntegrationCredential,
)
from .services import (
    _remote_snapshot, bind_listing, desired_state, rebind_listing,
    refresh_remote_listings, save_avito_credentials, sync_profile,
)
from .tasks import process_one_job
from .verification import MISMATCH_FIXED, fetch_remote_stocks, verify_avito_connections


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
    def test_get_can_recover_after_several_transient_disconnects(self, urlopen, sleep):
        response = MagicMock()
        response.read.return_value = b'{"ok": true}'
        response.__enter__.return_value = response
        urlopen.side_effect = [error.URLError("TLS EOF")] * 4 + [response]
        req = request.Request("https://api.avito.ru/core/v1/items")

        self.assertEqual(self.client._execute(req), {"ok": True})
        self.assertEqual(urlopen.call_count, 5)
        self.assertEqual(sleep.call_count, 4)

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

    @patch("integrations.client.time.sleep")
    @patch("integrations.client.request.urlopen")
    def test_read_only_stock_post_retries_network_disconnect(self, urlopen, sleep):
        response = MagicMock()
        response.read.return_value = b'{"stocks": [{"item_id": 1, "quantity": 2}]}'
        response.__enter__.return_value = response
        urlopen.side_effect = [error.URLError("TLS EOF"), response]
        self.client.base_url = "https://api.avito.ru"
        self.client._token = Mock(return_value="test-token")

        self.assertEqual(self.client.get_stocks([1])["stocks"][0]["quantity"], 2)
        self.assertEqual(urlopen.call_count, 2)
        sleep.assert_called_once()

    @patch("integrations.client.time.sleep")
    @patch("integrations.client.request.urlopen")
    def test_network_timeout_is_explained_to_user(self, urlopen, sleep):
        urlopen.side_effect = error.URLError(TimeoutError("TLS handshake timed out"))
        req = request.Request("https://api.avito.ru/core/v1/items")

        with self.assertRaises(AvitoAPIError) as raised:
            self.client._execute(req)

        self.assertIn("время ожидания", str(raised.exception))
        self.assertEqual(raised.exception.category, "network")


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

    @patch("integrations.services.AvitoClient")
    def test_listing_refresh_unites_two_api_scans_before_marking_missing(self, client_class):
        old = AvitoRemoteListing.objects.create(
            avito_item_id=203, title="Старое", status="active", last_seen_at=timezone.now(),
        )
        client_class.return_value.list_items.side_effect = [
            {"resources": [{"id": 201, "title": "Первое", "status": "active", "price": 1000}]},
            {"resources": [{"id": 202, "title": "Второе", "status": "active", "price": 2000}]},
        ]

        self.assertEqual(refresh_remote_listings(), 2)

        self.assertFalse(AvitoRemoteListing.objects.get(avito_item_id=201).missing_since)
        self.assertFalse(AvitoRemoteListing.objects.get(avito_item_id=202).missing_since)
        old.refresh_from_db()
        self.assertIsNotNone(old.missing_since)

    @patch("integrations.services.AvitoClient")
    def test_refresh_hides_confirmed_removed_but_preserves_archived_and_unknown(self, client_class):
        IntegrationCredential.objects.create(provider="avito", account_id="123")
        listings = [AvitoRemoteListing.objects.create(avito_item_id=i, title=str(i), status="active")
                    for i in (701, 702, 703, 704)]
        client = client_class.return_value
        client.list_items.return_value = {"resources": []}
        def details(account, item_id):
            if item_id == 704:
                raise AvitoAPIError("Не найдено", "validation", 404)
            return {"status": {701: "removed", 702: "archived", 703: "old"}[item_id]}
        client.get_item_details.side_effect = details
        refresh_remote_listings()
        self.client.force_login(self.admin)
        response = self.client.get(reverse("integrations:connections"))
        visible = {item.avito_item_id for item in response.context["unlinked_page"]}
        self.assertEqual(visible, {702, 703, 704})
        self.assertTrue(AvitoRemoteListing.objects.filter(avito_item_id=701, status="removed").exists())
        self.assertFalse(AvitoRemoteListing.objects.get(avito_item_id=702).missing_since)

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

    @patch("integrations.services.AvitoClient")
    def test_unbind_preserves_listing_product_and_stops_outbound_sync(self, client_class):
        profile = AvitoProductProfile.objects.create(cd=self.cd, sell_on_avito=True)
        listing = AvitoRemoteListing.objects.create(avito_item_id=304, title="Remote")
        connection = AvitoListingConnection.objects.create(profile=profile, remote_listing=listing)
        self.client.force_login(self.admin)
        url = reverse("integrations:unbind", args=(connection.pk,))
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertTrue(AvitoListingConnection.objects.filter(pk=connection.pk).exists())
        response = self.client.post(url)
        self.assertRedirects(response, reverse("integrations:connections"))
        self.assertFalse(AvitoListingConnection.objects.filter(pk=connection.pk).exists())
        self.assertTrue(AvitoRemoteListing.objects.filter(pk=listing.pk, connection__isnull=True).exists())
        profile.refresh_from_db()
        self.assertFalse(profile.sell_on_avito)
        self.cd.refresh_from_db()
        self.assertEqual(self.cd.avito_price, Decimal("4500.00"))
        self.assertEqual(self.cd.warehouse_stocks.get().quantity, 4)
        sync_profile(profile.pk)
        client_class.assert_not_called()

    def test_unbind_requires_rebind_permission(self):
        profile = AvitoProductProfile.objects.create(cd=self.cd, sell_on_avito=True)
        listing = AvitoRemoteListing.objects.create(avito_item_id=305, title="Remote")
        connection = AvitoListingConnection.objects.create(profile=profile, remote_listing=listing)
        worker = User.objects.create_user("no-unbind-permission")
        self.client.force_login(worker)
        response = self.client.post(reverse("integrations:unbind", args=(connection.pk,)))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(AvitoListingConnection.objects.filter(pk=connection.pk).exists())

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
        listing = AvitoRemoteListing.objects.create(avito_item_id=405, title="Remote", status="active")
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
        listing = AvitoRemoteListing.objects.create(avito_item_id=404, title="Remote", status="active")
        AvitoListingConnection.objects.create(profile=profile, remote_listing=listing)
        sync_profile(profile.pk)
        client.update_stock.assert_called_once_with(404, 4)
        client.update_price.assert_called_once_with(404, Decimal("4500.00"))
        profile.refresh_from_db()
        self.assertEqual(profile.sync_status, AvitoProductProfile.SyncStatus.OK)

    @patch("integrations.services.AvitoClient")
    def test_zero_stock_is_success_without_autoload_publication_action(self, client_class):
        stock = self.cd.warehouse_stocks.get()
        stock.quantity = 0
        stock.save(update_fields=("quantity",))
        client = Mock()
        client.update_stock.return_value = {"stocks": [{"success": True}]}
        client.update_price.return_value = {"result": {"success": True}}
        client_class.return_value = client
        profile = AvitoProductProfile.objects.create(
            cd=self.cd, sell_on_avito=True,
            sync_status=AvitoProductProfile.SyncStatus.ERROR,
            last_error=(
                "Остаток Avito установлен в 0, но полное снятие объявления требует "
                "недоступного для аккаунта Autoload API."
            ),
        )
        listing = AvitoRemoteListing.objects.create(
            avito_item_id=406, title="Remote", status="active",
        )
        AvitoListingConnection.objects.create(profile=profile, remote_listing=listing)

        sync_profile(profile.pk, force_remote_check=True)

        client.update_stock.assert_called_once_with(406, 0)
        client.update_price.assert_called_once_with(406, Decimal("4500.00"))
        self.assertEqual(
            [call[0] for call in client.method_calls], ["update_stock", "update_price"],
        )
        profile.refresh_from_db()
        self.assertEqual(profile.sync_status, AvitoProductProfile.SyncStatus.OK)
        self.assertEqual(profile.last_error, "")

    @patch("integrations.services.AvitoClient")
    def test_real_zero_stock_api_error_is_not_suppressed(self, client_class):
        stock = self.cd.warehouse_stocks.get()
        stock.quantity = 0
        stock.save(update_fields=("quantity",))
        client_class.return_value.update_stock.side_effect = AvitoAPIError(
            "Avito отклонил нулевой остаток.", "validation", 400,
        )
        profile = AvitoProductProfile.objects.create(cd=self.cd, sell_on_avito=True)
        listing = AvitoRemoteListing.objects.create(
            avito_item_id=407, title="Remote", status="active",
        )
        AvitoListingConnection.objects.create(profile=profile, remote_listing=listing)

        with self.assertRaises(AvitoAPIError):
            sync_profile(profile.pk, force_remote_check=True)

        profile.refresh_from_db()
        self.assertEqual(profile.sync_status, AvitoProductProfile.SyncStatus.ERROR)
        self.assertIn("отклонил нулевой остаток", profile.last_error)

    @patch("integrations.services.AvitoClient")
    def test_product_sync_does_not_send_to_listing_missing_from_current_list(self, client_class):
        profile = AvitoProductProfile.objects.create(cd=self.cd, sell_on_avito=True)
        listing = AvitoRemoteListing.objects.create(
            avito_item_id=409, title="Старое объявление", status="active",
            missing_since=timezone.now(),
        )
        AvitoListingConnection.objects.create(profile=profile, remote_listing=listing)

        sync_profile(profile.pk, force_remote_check=True)

        client_class.assert_not_called()
        profile.refresh_from_db()
        self.assertEqual(profile.sync_status, AvitoProductProfile.SyncStatus.ERROR)
        self.assertIn("отсутствует", profile.last_error)

    @patch("integrations.verification.sync_profile")
    @patch("integrations.verification._fresh_remote_prices")
    @patch("integrations.verification.fetch_remote_stocks")
    def test_verification_fix_rechecks_remote_without_modifying_crm(
        self, fetch_stocks, fetch_prices, sync,
    ):
        profile = AvitoProductProfile.objects.create(cd=self.cd, sell_on_avito=True)
        listing = AvitoRemoteListing.objects.create(
            avito_item_id=408, title="Remote", status="active",
        )
        AvitoListingConnection.objects.create(profile=profile, remote_listing=listing)
        fetch_stocks.side_effect = [{408: 3}, {408: 4}]
        fetch_prices.side_effect = [
            {408: Decimal("4600.00")}, {408: Decimal("4500.00")},
        ]
        original_price = self.cd.avito_price
        original_stock = self.cd.warehouse_stocks.get().quantity

        rows = verify_avito_connections(fix=True, client=Mock())

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].stock_status, MISMATCH_FIXED)
        self.assertEqual(rows[0].price_status, MISMATCH_FIXED)
        self.assertEqual(rows[0].final_result, MISMATCH_FIXED)
        sync.assert_called_once_with(profile.pk, force_remote_check=True)
        self.cd.refresh_from_db()
        self.assertEqual(self.cd.avito_price, original_price)
        self.assertEqual(self.cd.warehouse_stocks.get().quantity, original_stock)

    def test_remote_stock_verification_uses_small_supported_batches(self):
        client = Mock()
        client.get_stocks.side_effect = lambda ids: {
            "stocks": [{"item_id": item_id, "quantity": item_id % 5} for item_id in ids]
        }

        progress = Mock()
        result = fetch_remote_stocks(range(1, 22), client=client, progress=progress)

        self.assertEqual([len(call.args[0]) for call in client.get_stocks.call_args_list], [10, 10, 1])
        self.assertEqual(result[21], 1)
        self.assertEqual([call.args[0] for call in progress.call_args_list], [10, 20, 21])

    def test_stock_read_can_report_failed_batch_and_continue(self):
        client = Mock()
        client.get_stocks.side_effect = [
            AvitoAPIError("Нет соединения с Avito.", "network"),
            {"stocks": [{"item_id": 11, "quantity": 4}]},
        ]
        errors = []

        stocks = fetch_remote_stocks(
            range(1, 12), client=client, tolerate_errors=True,
            on_error=lambda ids, exc: errors.append((list(ids), str(exc))),
        )

        self.assertEqual(stocks, {11: 4})
        self.assertEqual(errors, [(list(range(1, 11)), "Нет соединения с Avito.")])

    @patch("integrations.verification.time.sleep")
    def test_stock_read_retries_only_failed_batch(self, sleep):
        client = Mock()
        client.get_stocks.side_effect = [
            AvitoAPIError("Нет соединения с Avito.", "network"),
            {"stocks": [{"item_id": item_id, "quantity": 2} for item_id in range(1, 11)]},
            {"stocks": [{"item_id": 11, "quantity": 4}]},
        ]
        errors = []

        stocks = fetch_remote_stocks(
            range(1, 12), client=client, tolerate_errors=True, batch_retries=2,
            on_error=lambda ids, exc: errors.append((list(ids), str(exc))),
        )

        self.assertEqual(len(stocks), 11)
        self.assertEqual(stocks[11], 4)
        self.assertEqual(errors, [])
        self.assertEqual([len(call.args[0]) for call in client.get_stocks.call_args_list], [10, 10, 1])
        sleep.assert_called_once_with(1.5)

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

    def test_manual_sync_creates_trackable_job_and_reuses_active_run(self):
        IntegrationCredential.objects.create(
            provider="avito", encrypted_client_id="encrypted", encrypted_client_secret="encrypted",
        )
        self.client.force_login(self.admin)
        response = self.client.post(reverse("integrations:manual_sync"))
        job = AvitoSyncJob.objects.get(job_type=AvitoSyncJob.JobType.MANUAL)
        self.assertRedirects(response, f"{reverse('integrations:avito')}?run={job.pk}")
        self.assertEqual(job.status, AvitoSyncJob.Status.PENDING)
        self.assertRedirects(
            self.client.post(reverse("integrations:manual_sync")),
            f"{reverse('integrations:avito')}?run={job.pk}",
        )
        self.assertEqual(AvitoSyncJob.objects.filter(job_type=AvitoSyncJob.JobType.MANUAL).count(), 1)
        dashboard = self.client.get(reverse("integrations:avito"), {"run": job.pk})
        self.assertContains(dashboard, "Проверено")
        self.assertContains(dashboard, reverse("integrations:manual_sync_status", args=(job.pk,)))
        status = self.client.get(reverse("integrations:manual_sync_status", args=(job.pk,))).json()
        self.assertEqual(status["status"], "pending")
        self.assertEqual(status["checked"], 0)

    @patch("integrations.manual_sync.refresh_remote_listings")
    @patch("integrations.manual_sync.fetch_remote_stocks")
    def test_manual_sync_changes_only_differences_and_verifies_both_fields(self, fetch_stocks, refresh):
        profile = AvitoProductProfile.objects.create(cd=self.cd, sell_on_avito=True)
        listing = AvitoRemoteListing.objects.create(
            avito_item_id=501, title="Объявление", status="active",
            remote_price=Decimal("4000.00"), last_seen_at=timezone.now(),
        )
        AvitoListingConnection.objects.create(profile=profile, remote_listing=listing)
        fetch_stocks.side_effect = [{501: 3}, {501: 4}]
        def refresh_list():
            AvitoRemoteListing.objects.filter(pk=listing.pk).update(
                remote_price=Decimal("4500.00") if refresh.call_count == 2 else Decimal("4000.00"),
                last_seen_at=timezone.now(),
            )
        refresh.side_effect = refresh_list
        client = Mock()
        client.update_stock.return_value = {"stocks": [{"success": True}]}
        client.update_price.return_value = {"result": {"success": True}}
        job = AvitoSyncJob.objects.create(
            dedupe_key="manual:test", job_type="manual", run_after=timezone.now(),
        )

        result = reconcile_active_listings(job=job, client=client)

        self.assertEqual((result["checked"], result["changed"], result["failed"]), (1, 1, 0))
        self.assertEqual((result["stock_changed"], result["price_changed"]), (1, 1))
        client.update_stock.assert_called_once_with(501, 4)
        client.update_price.assert_called_once_with(501, Decimal("4500.00"))
        job.refresh_from_db()
        self.assertEqual(job.checked_count, 1)
        self.assertEqual(job.changed_count, 1)
        self.assertEqual(job.phase, "Завершено")
        profile.refresh_from_db()
        self.assertEqual(profile.sync_status, AvitoProductProfile.SyncStatus.OK)

    @patch("integrations.manual_sync.refresh_remote_listings")
    @patch("integrations.manual_sync.fetch_remote_stocks")
    def test_matching_stock_is_not_read_twice(self, fetch_stocks, refresh):
        profile = AvitoProductProfile.objects.create(cd=self.cd, sell_on_avito=True)
        listing = AvitoRemoteListing.objects.create(
            avito_item_id=502, title="Объявление", status="active",
            remote_price=self.cd.avito_price, last_seen_at=timezone.now(),
        )
        AvitoListingConnection.objects.create(profile=profile, remote_listing=listing)
        fetch_stocks.return_value = {502: 4}

        result = reconcile_active_listings(client=Mock())

        self.assertEqual((result["changed"], result["failed"]), (0, 0))
        fetch_stocks.assert_called_once()

    @patch("integrations.manual_sync.refresh_remote_listings")
    @patch("integrations.manual_sync.fetch_remote_stocks")
    def test_manual_sync_continues_after_one_listing_fails(self, fetch_stocks, refresh):
        first_profile = AvitoProductProfile.objects.create(cd=self.cd, sell_on_avito=True)
        first_listing = AvitoRemoteListing.objects.create(
            avito_item_id=601, title="Первое", status="active",
            remote_price=Decimal("4500.00"), last_seen_at=timezone.now(),
        )
        AvitoListingConnection.objects.create(profile=first_profile, remote_listing=first_listing)
        second_cd = CD.objects.create(
            platform=self.platform, name="Товар B", sku="B-1", avito_price=Decimal("4500.00"),
        )
        CDWarehouseStock.objects.create(warehouse=self.warehouse, cd=second_cd, quantity=4)
        second_profile = AvitoProductProfile.objects.create(cd=second_cd, sell_on_avito=True)
        second_listing = AvitoRemoteListing.objects.create(
            avito_item_id=602, title="Второе", status="active",
            remote_price=Decimal("4500.00"), last_seen_at=timezone.now(),
        )
        AvitoListingConnection.objects.create(profile=second_profile, remote_listing=second_listing)
        fetch_stocks.side_effect = [{601: 3, 602: 4}, {601: 3, 602: 4}]
        refresh.side_effect = lambda: AvitoRemoteListing.objects.filter(
            pk__in=(first_listing.pk, second_listing.pk)
        ).update(last_seen_at=timezone.now())
        client = Mock()
        client.update_stock.side_effect = AvitoAPIError("Нет соединения с Avito.", "network")

        result = reconcile_active_listings(client=client)

        self.assertEqual((result["checked"], result["failed"], result["changed"]), (2, 1, 0))
        self.assertEqual(result["details"][0]["avito_id"], 601)
        self.assertIn("Нет соединения", result["details"][0]["error"])
        first_profile.refresh_from_db()
        second_profile.refresh_from_db()
        self.assertEqual(first_profile.sync_status, AvitoProductProfile.SyncStatus.ERROR)
        self.assertEqual(second_profile.sync_status, AvitoProductProfile.SyncStatus.OK)
        self.assertEqual(refresh.call_count, 1)

    @patch("integrations.tasks.sync_profile", side_effect=AvitoAPIError("Нет соединения с Avito.", "network"))
    def test_network_error_jobs_keep_retrying_after_initial_attempts(self, sync):
        job = AvitoSyncJob.objects.create(
            dedupe_key="product:999", job_type="product", profile_id=None,
            status="pending", attempts=4, run_after=timezone.now() - timedelta(minutes=1),
        )
        # В реальной задаче указан профиль; здесь проверяем именно политику повторов.
        job.profile = AvitoProductProfile.objects.create(cd=self.cd, sell_on_avito=True)
        job.save(update_fields=("profile",))

        self.assertTrue(process_one_job())

        job.refresh_from_db()
        self.assertEqual(job.status, AvitoSyncJob.Status.PENDING)
        self.assertEqual(job.attempts, 4)
        self.assertIn("Нет соединения", job.last_error)

    @patch("integrations.tasks.reconcile_all", side_effect=OperationalError("database is locked"))
    def test_database_lock_requeues_sync_instead_of_losing_it(self, reconcile):
        job = AvitoSyncJob.objects.create(
            dedupe_key="reconcile", job_type="reconcile", status="pending",
            run_after=timezone.now() - timedelta(minutes=1),
        )

        self.assertTrue(process_one_job())

        job.refresh_from_db()
        self.assertEqual(job.status, AvitoSyncJob.Status.PENDING)
        self.assertGreater(job.run_after, timezone.now())
        self.assertIn("автоматически повторяется", job.last_error)

    @patch("integrations.tasks.reconcile_active_listings")
    def test_manual_job_reports_partial_failure_instead_of_success(self, reconcile):
        job = AvitoSyncJob.objects.create(
            dedupe_key="manual:partial", job_type="manual", status="pending",
            run_after=timezone.now() - timedelta(minutes=1),
        )
        reconcile.return_value = {"total": 2, "failed": 1}

        self.assertTrue(process_one_job())

        job.refresh_from_db()
        self.assertEqual(job.status, AvitoSyncJob.Status.ERROR)
        self.assertIn("1 из 2", job.last_error)
        self.assertIsNotNone(job.finished_at)

    def test_manual_job_has_priority_over_due_periodic_jobs(self):
        from .tasks import claim_next_job

        periodic = AvitoSyncJob.objects.create(
            dedupe_key="reconcile", job_type="reconcile", status="pending",
            run_after=timezone.now() - timedelta(minutes=2),
        )
        manual = AvitoSyncJob.objects.create(
            dedupe_key="manual:priority", job_type="manual", status="pending",
            run_after=timezone.now() - timedelta(minutes=1),
        )

        self.assertEqual(claim_next_job().pk, manual.pk)
        periodic.refresh_from_db()
        self.assertEqual(periodic.status, AvitoSyncJob.Status.PENDING)

    def test_interrupted_running_job_is_requeued(self):
        from .tasks import ensure_periodic_jobs

        job = AvitoSyncJob.objects.create(
            dedupe_key="manual:interrupted", job_type="manual", status="running",
            run_after=timezone.now() - timedelta(minutes=20),
        )
        AvitoSyncJob.objects.filter(pk=job.pk).update(
            updated_at=timezone.now() - timedelta(minutes=20),
        )

        ensure_periodic_jobs()

        job.refresh_from_db()
        self.assertEqual(job.status, AvitoSyncJob.Status.PENDING)
        self.assertIn("прервался", job.last_error)

    @patch("integrations.manual_sync.refresh_remote_listings")
    @patch("integrations.manual_sync.fetch_remote_stocks")
    def test_manual_sync_reports_unconfirmed_price_after_update(self, fetch_stocks, refresh):
        profile = AvitoProductProfile.objects.create(cd=self.cd, sell_on_avito=True)
        listing = AvitoRemoteListing.objects.create(
            avito_item_id=701, title="Объявление", status="active",
            remote_price=Decimal("4000.00"), last_seen_at=timezone.now(),
        )
        AvitoListingConnection.objects.create(profile=profile, remote_listing=listing)
        fetch_stocks.side_effect = [{701: 4}, {701: 4}]
        refresh.side_effect = lambda: AvitoRemoteListing.objects.filter(pk=listing.pk).update(
            last_seen_at=timezone.now(),
        )
        client = Mock()
        client.update_price.return_value = {"result": {"success": True}}

        result = reconcile_active_listings(client=client)

        self.assertEqual((result["changed"], result["failed"]), (0, 1))
        self.assertIn("Цена не подтверждена", result["details"][0]["error"])

    @patch("integrations.manual_sync.refresh_remote_listings")
    @patch("integrations.manual_sync.fetch_remote_stocks")
    def test_price_refresh_failure_is_reported_per_listing(self, fetch_stocks, refresh):
        profile = AvitoProductProfile.objects.create(cd=self.cd, sell_on_avito=True)
        listing = AvitoRemoteListing.objects.create(
            avito_item_id=702, title="Объявление", status="active",
            remote_price=Decimal("4000.00"), last_seen_at=timezone.now(),
        )
        AvitoListingConnection.objects.create(profile=profile, remote_listing=listing)
        fetch_stocks.side_effect = [{702: 4}, {702: 4}]
        refresh.side_effect = [None, AvitoAPIError("Нет соединения с Avito.", "network")]
        client = Mock()
        client.update_price.return_value = {"result": {"success": True}}

        result = reconcile_active_listings(client=client)

        self.assertEqual((result["checked"], result["failed"]), (1, 1))
        self.assertIn("Повторная проверка цены", result["details"][0]["error"])
