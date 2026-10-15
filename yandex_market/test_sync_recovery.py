"""Сверка продолжает независимые участки обмена при сбое одного метода API."""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import User
from catalog.models import CD, Platform
from warehouse.models import CDWarehouseStock, Warehouse
from .client import MarketError, YandexMarketClient, json_bytes
from .models import Integration, OfferConnection, OrderMetadata, RemoteOffer, SyncJob
from .services import refresh_trade_snapshots, sync_price_stock_batch
from .tasks import ensure_periodic_jobs, process_one_job, reconcile, reconcile_orders


@override_settings(YANDEX_MARKET_API_KEY="test-only", YANDEX_MARKET_ALLOW_TEST_TRANSACTION=True)
class SyncRecoveryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = User.objects.create_superuser("market-recovery", password="test-only")
        warehouse = Warehouse.objects.create(name="Склад проверки")
        cls.integration = Integration.objects.create(business_id=100, campaign_id=200,
            partner_warehouse_id=300, fulfillment_warehouse=warehouse, operator=user, enabled=True)
        cls.product = CD.objects.create(name="Товар", platform=Platform.objects.create(name="Платформа"),
            yandex_market_price=Decimal("99.99"))
        CDWarehouseStock.objects.create(cd=cls.product, warehouse=warehouse, quantity=5)
        cls.remote = RemoteOffer.objects.create(integration=cls.integration, offer_id="0007",
            remote_price=1, remote_stock=0, price_checked_at=timezone.now() - timedelta(days=1))
        cls.connection = OfferConnection.objects.create(integration=cls.integration, remote_offer=cls.remote,
            cd=cls.product, last_sent_state={"price": "88.00"}, state="error", last_error="Контент")

    def test_return_placeholder_is_not_polled_as_open_order(self):
        OrderMetadata.objects.create(integration=self.integration, order_id=1)
        OrderMetadata.objects.create(integration=self.integration, order_id=2, status="DELIVERED")
        client = Mock()
        client.pages.return_value = []
        reconcile_orders(self.integration, client)
        client.order.assert_not_called()
        self.assertEqual(OrderMetadata.objects.count(), 2)

    def test_missing_order_is_recorded_and_next_order_is_processed(self):
        missing = OrderMetadata.objects.create(integration=self.integration, order_id=2, status="PROCESSING")
        OrderMetadata.objects.create(integration=self.integration, order_id=1, status="PROCESSING")
        client = Mock()
        client.pages.return_value = []
        client.order.side_effect = [MarketError("Не найден", "ORDER_NOT_FOUND"), {"orderId": 1}]
        with patch("yandex_market.tasks.import_order") as importer:
            reconcile_orders(self.integration, client)
        importer.assert_called_once_with(self.integration, {"orderId": 1})
        missing.refresh_from_db()
        self.assertEqual(missing.last_error, "Не найден")
        self.assertIsNotNone(missing.last_sync_at)

    def test_old_order_uses_its_creation_window_and_all_pages(self):
        created = timezone.now() - timedelta(days=100)
        OrderMetadata.objects.create(integration=self.integration, order_id=7, status="PROCESSING", created_remote_at=created)
        client = YandexMarketClient(self.integration, key="test-only")
        client.call = Mock(side_effect=[{"orders": [], "paging": {"nextPageToken": "next"}},
            {"orders": [{"orderId": 7, "campaignId": 999}, {"orderId": 7, "campaignId": 200, "programType": "FBS"}]}])
        self.assertEqual(client.order(7)["campaignId"], 200)
        body = client.call.call_args.kwargs["body"]
        self.assertEqual(body["dates"]["creationDateFrom"], (created.date() - timedelta(days=1)).isoformat())
        self.assertEqual(body["dates"]["creationDateTo"], (created.date() + timedelta(days=2)).isoformat())
        self.assertEqual(client.call.call_args.kwargs["query"]["pageToken"], "next")

    def test_http_200_internal_error_and_unlisted_5xx_are_retryable(self):
        for status in (200, 503, 507):
            with self.subTest(status=status):
                response = Mock(status=status, headers={})
                response.read.return_value = json_bytes({"errors": [{"code": "INTERNAL_SERVER_ERROR", "message": "Сбой"}]})
                response.__enter__ = Mock(return_value=response)
                response.__exit__ = Mock(return_value=False)
                client = YandexMarketClient(self.integration, key="test-only", transport=Mock(return_value=response))
                with self.assertRaises(MarketError) as caught:
                    client.call("getDefaultPrices", body={})
                self.assertTrue(caught.exception.retryable)

    def failing_prices(self, operation, **kwargs):
        if operation == "getDefaultPrices":
            raise MarketError("Сбой цен", "INTERNAL_SERVER_ERROR", 500, True)
        if operation == "getStocksOnPartnerWarehouses":
            return [{"offerId": "0007", "stocks": [{"type": "AVAILABLE", "count": 0}]}]
        return []

    def test_price_failure_does_not_prevent_stock_snapshot(self):
        client = Mock()
        client.pages.side_effect = self.failing_prices
        with self.assertRaises(MarketError):
            refresh_trade_snapshots(self.integration, client=client)
        self.remote.refresh_from_db()
        self.assertIsNotNone(self.remote.stock_checked_at)
        self.assertEqual(self.remote.remote_stock, 0)
        self.assertEqual(self.remote.remote_price, Decimal("1.00"))

    def test_failed_orders_catalog_prices_still_queue_only_checked_stock(self):
        client = Mock()
        def pages(operation, **kwargs):
            if operation in {"getBusinessOrders", "getOfferMappings"}:
                raise MarketError("Временный сбой", "INTERNAL_SERVER_ERROR", 500, True)
            return self.failing_prices(operation, **kwargs)
        client.pages.side_effect = pages
        with self.assertRaises(MarketError) as caught:
            reconcile(self.integration, client)
        self.assertTrue(caught.exception.retryable)
        job = SyncJob.objects.get(kind="products")
        self.assertEqual(job.payload, {"connection_ids": [self.connection.pk], "sync_prices": False, "sync_stocks": True})
        self.assertIsNone(self.integration.last_sync_at)
        self.assertIn("getReturns", [c.args[0] for c in client.pages.call_args_list])

    def test_partial_batch_does_not_send_unchecked_price_or_clear_content_error(self):
        self.connection.dirty_fields = ["description"]
        self.connection.save(update_fields=["dirty_fields"])
        client = Mock()
        sync_price_stock_batch(self.integration, [self.connection.pk], client=client, sync_prices=False)
        client.call.assert_called_once()
        self.assertEqual(client.call.call_args.args[0], "updateStocksOnPartnerWarehouses")
        self.connection.refresh_from_db()
        self.assertEqual(self.connection.last_sent_state, {"price": "88.00", "quantity": 5})
        self.assertEqual(self.connection.last_error, "Контент")
        self.assertEqual(self.connection.dirty_fields, ["description"])
        self.assertFalse(SyncJob.objects.exists())

    def test_stock_failure_still_allows_checked_price_correction(self):
        client = Mock()
        def pages(operation, **kwargs):
            if operation == "getDefaultPrices":
                return [{"offerId": "0007", "price": {"value": "1.00"}}]
            if operation == "getStocksOnPartnerWarehouses":
                raise MarketError("Сбой остатков", "INTERNAL_SERVER_ERROR", 500, True)
            return []
        client.pages.side_effect = pages
        with self.assertRaises(MarketError):
            reconcile(self.integration, client)
        job = SyncJob.objects.get(kind="products")
        self.assertEqual(job.payload["sync_stocks"], False)
        self.assertEqual(job.payload["sync_prices"], True)
        writer = Mock()
        sync_price_stock_batch(self.integration, job.payload["connection_ids"], client=writer, sync_stocks=False)
        self.assertEqual(writer.call.call_args.args[0], "updateBusinessPrices")
        self.connection.refresh_from_db()
        self.assertNotIn("quantity", self.connection.last_sent_state)

    def test_periodic_task_recovers_and_does_not_stop_after_permanent_error(self):
        job = SyncJob.objects.create(integration=self.integration, key=f"ym:{self.integration.pk}:periodic",
            kind="reconcile", state="error", last_error="Старая ошибка")
        ensure_periodic_jobs()
        job.refresh_from_db()
        self.assertEqual(job.state, "pending")
        with patch("yandex_market.tasks.process", side_effect=MarketError("Не найден", "ORDER_NOT_FOUND")):
            process_one_job()
        job.refresh_from_db()
        self.assertEqual(job.state, "pending")
        self.assertGreater(job.run_after, timezone.now() + timedelta(minutes=14))
        self.assertEqual(job.last_error, "Не найден")
        self.assertEqual(job.attempts, 1)

    def test_complete_recovery_clears_error_and_schedules_next_poll(self):
        self.integration.last_error = "Сбой"
        self.integration.save(update_fields=["last_error"])
        SyncJob.objects.create(integration=self.integration, key=f"ym:{self.integration.pk}:periodic",
            kind="reconcile", state="error", last_error="Сбой", attempts=8)
        client = Mock()
        def pages(operation, **kwargs):
            if operation == "getDefaultPrices":
                return [{"offerId": "0007", "price": {"value": "99.99"}}]
            if operation == "getStocksOnPartnerWarehouses":
                return [{"offerId": "0007", "stocks": [{"type": "AVAILABLE", "count": 5}]}]
            return []
        client.pages.side_effect = pages
        with patch("yandex_market.tasks.YandexMarketClient", return_value=client):
            process_one_job()
        self.integration.refresh_from_db()
        self.assertEqual(self.integration.last_error, "")
        self.assertIsNotNone(self.integration.last_sync_at)
        job = SyncJob.objects.get(kind="reconcile")
        self.assertEqual(job.state, "pending")
        self.assertEqual(job.last_error, "")
        self.assertEqual(job.attempts, 0)
        self.assertGreater(job.run_after, timezone.now() + timedelta(minutes=14))

    def test_missing_trade_rows_do_not_report_success_using_old_snapshot(self):
        client = Mock()
        client.pages.return_value = []
        with self.assertRaises(MarketError) as caught:
            reconcile(self.integration, client)
        self.assertEqual(caught.exception.code, "RECONCILIATION_INCOMPLETE")
        self.assertTrue(caught.exception.retryable)
        self.assertIsNone(self.integration.last_sync_at)
        self.assertFalse(SyncJob.objects.exists())
