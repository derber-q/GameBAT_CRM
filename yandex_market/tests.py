"""Проверки на изолированной БД и подменённом API; рабочие ключи не используются."""
import copy
import json
import tempfile
from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from unittest.mock import Mock, patch

from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from catalog.models import CD, Platform, BarcodeRegistry, Tech, Brand, ProductType
from catalog.removal import evaluate_product_removal
from sales.models import Sale
from sales.services import advance_order_status, cancel_sale
from warehouse.models import CDWarehouseStock, Warehouse
from .client import MarketError, YandexMarketClient, json_bytes
from .content import build_content, public_https, validate_parameters, valid_gtin
from .documents import process_label, save_image
from .models import ApiLog, CategorySchema, Integration, LabelDocument, OfferConnection, OrderMetadata, RemoteOffer, ReturnMetadata, SyncJob, WebhookEvent
from .orders import accept_return, import_order, item_amount, save_return
from .packing import validate_boxes
from .queue import enqueue, enqueue_product
from .services import activate, bind_offer, create_offer, sync_product, unlink_offer, refresh_trade_snapshots, sync_price_stock_batch, connections_with_stock, refresh_catalog, store_api_key
from .tasks import process_one_job


@override_settings(YANDEX_MARKET_API_KEY="test-key-never-live", YANDEX_MARKET_ALLOW_TEST_TRANSACTION=True)
class MarketTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser("ym-admin", password="Test-password-123")
        cls.worker = User.objects.create_user("ym-worker", password="Test-password-123")
        cls.warehouse = Warehouse.objects.create(name="Выполнение")
        cls.other = Warehouse.objects.create(name="Другой склад")
        cls.integration = Integration.objects.create(business_id=100, campaign_id=200, partner_warehouse_id=300,
            fulfillment_warehouse=cls.warehouse, operator=cls.user, checked_at=timezone.now(), import_orders_from=timezone.now() - timedelta(days=1))
        cls.product = CD.objects.create(platform=Platform.objects.create(name="Тестовая платформа"), name="Тестовый диск", sku="CD-YM", cost=Decimal("20.00"), yandex_market_price=Decimal("99.99"))
        cls.stock = CDWarehouseStock.objects.create(warehouse=cls.warehouse, cd=cls.product, quantity=10)
        CDWarehouseStock.objects.create(warehouse=cls.other, cd=cls.product, quantity=7)
        cls.remote = RemoteOffer.objects.create(integration=cls.integration, offer_id="0007-old", name="Название Маркета", category_id=50,
            snapshot={"offer": {"offerId": "0007-old", "name": "Название Маркета", "pictures": ["https://example.com/old.jpg"]}})
        cls.connection = bind_offer(remote_id=cls.remote.pk, product_kind="cd", product_id=cls.product.pk, actor=cls.user)
        CategorySchema.objects.create(category_id=50, schema={"categoryId": 50, "parameters": []})

    def payload(self, **changes):
        value = {"orderId": 123, "campaignId": 200, "programType": "FBS", "status": "PROCESSING", "substatus": "STARTED",
            "creationDate": timezone.now().isoformat(), "updateDate": timezone.now().isoformat(), "paymentType": "PREPAID", "paymentMethod": "YANDEX",
            "items": [{"id": 789, "offerId": "0007-old", "offerName": "Товар", "count": 3,
                "prices": {"payment": {"value": "100.00", "currencyId": "RUR"}, "cashback": {"value": "0.01", "currencyId": "RUR"}, "subsidy": {"value": "50.00", "currencyId": "RUR"}}}]}
        value.update(changes)
        return value

    def enable(self, sell=True):
        self.integration.enabled = True
        self.integration.save(update_fields=["enabled"])
        self.connection.managed = True
        self.connection.sell_on_yandex = sell
        self.connection.save(update_fields=["managed", "sell_on_yandex"])

    def stock_quantity(self):
        self.stock.refresh_from_db()
        return self.stock.quantity

    def test_binding_preserves_offer_and_does_not_activate(self):
        self.assertEqual(self.connection.remote_offer.offer_id, "0007-old")
        self.assertFalse(self.connection.managed)
        self.assertEqual(self.connection.content, {})
        self.assertFalse(SyncJob.objects.exists())
        self.assertEqual(build_content(self.connection), {"offerId": "0007-old"})

    def test_duplicate_links_rejected(self):
        with self.assertRaises(ValidationError):
            bind_offer(remote_id=self.remote.pk, product_kind="cd", product_id=self.product.pk, actor=self.user)
        with self.assertRaises(IntegrityError), transaction.atomic():
            OfferConnection.objects.create(integration=self.integration, remote_offer=self.remote, cd=self.product)

    def test_active_link_blocks_product_removal(self):
        self.assertIn("HAS_YANDEX_CONNECTION", evaluate_product_removal(self.product).reasons)

    def test_unlink_preserves_history_and_external_offer(self):
        unlink_offer(self.connection.pk, self.user)
        self.connection.refresh_from_db()
        self.assertFalse(self.connection.active)
        self.assertTrue(RemoteOffer.objects.filter(pk=self.remote.pk).exists())

    def test_no_sync_before_activation(self):
        client = Mock()
        sync_product(self.connection.pk, client=client)
        client.call.assert_not_called()

    def test_sync_uses_global_physical_stock_and_crm_price(self):
        self.enable()
        client = Mock()
        sync_product(self.connection.pk, client=client)
        calls = {c.args[0]: c.kwargs["body"] for c in client.call.call_args_list}
        self.assertNotIn("updateOfferMappings", calls)
        self.assertEqual(calls["updateStocksOnPartnerWarehouses"]["skuItems"][0]["count"], 17)
        self.assertEqual(calls["updateBusinessPrices"]["offers"][0]["price"]["value"], Decimal("99.99"))
        self.assertEqual(calls["updateStocksOnPartnerWarehouses"]["skuItems"][0]["sku"], "0007-old")

    def test_disabled_sale_sends_zero_despite_invalid_content(self):
        self.enable(sell=False)
        self.connection.content = {"barcodes": ["invalid"]}
        self.connection.dirty_fields = ["barcodes"]
        self.connection.save()
        client = Mock()
        sync_product(self.connection.pk, client=client)
        self.assertEqual(client.call.call_count, 1)
        self.assertEqual(client.call.call_args.kwargs["body"]["skuItems"][0]["count"], 0)
        self.connection.refresh_from_db()
        self.assertEqual(self.connection.dirty_fields, ["barcodes"])

    def test_latest_generation_is_not_lost_during_worker(self):
        self.enable()
        job = enqueue(self.integration, "product", self.connection.pk, {"connection_id": self.connection.pk})
        def during(_job):
            enqueue(self.integration, "product", self.connection.pk, {"connection_id": self.connection.pk, "latest": True})
        with patch("yandex_market.tasks.process", side_effect=during):
            process_one_job()
        job.refresh_from_db()
        self.assertEqual(job.state, "pending")
        self.assertTrue(job.payload["latest"])
        self.assertEqual(job.generation, 2)

    def test_worker_retry_preserves_task(self):
        self.enable()
        job = enqueue(self.integration, "product", self.connection.pk, {"connection_id": self.connection.pk})
        with patch("yandex_market.tasks.process", side_effect=MarketError("Лимит", "429", retryable=True, retry_after=90)):
            process_one_job()
        job.refresh_from_db()
        self.assertEqual(job.state, "pending")
        self.assertGreater(job.run_after, timezone.now() + timedelta(seconds=80))

    def test_order_import_idempotent_with_exact_snapshot(self):
        payload = self.payload()
        first = import_order(self.integration, payload)
        second = import_order(self.integration, payload)
        self.assertEqual(first.sale_id, second.sale_id)
        self.assertEqual(Sale.objects.count(), 1)
        self.assertEqual(self.stock_quantity(), 7)
        line = first.sale.cd_items.get()
        self.assertEqual(line.line_total, Decimal("100.01"))
        self.assertEqual(line.unit_price, Decimal("33.34"))
        self.assertEqual(first.sale.payment_status, Sale.PaymentStatus.UNPAID)
        self.product.yandex_market_price = Decimal("500")
        self.product.cost = Decimal("80")
        self.product.save()
        import_order(self.integration, payload)
        line.refresh_from_db()
        self.assertEqual(line.line_total, Decimal("100.01"))

    def test_unknown_offer_does_not_create_product_or_deduct(self):
        payload = self.payload()
        payload["items"][0]["offerId"] = "UNKNOWN"
        with self.assertRaisesMessage(ValidationError, "не связан"):
            import_order(self.integration, payload)
        self.assertEqual(self.stock_quantity(), 10)
        self.assertEqual(CD.objects.count(), 1)
        order = OrderMetadata.objects.get(order_id=123)
        self.assertEqual(order.items[0]["offerId"], "UNKNOWN")
        self.assertIsNone(order.sale_id)

    def test_fulfillment_shortage_does_not_use_other_warehouse(self):
        payload = self.payload()
        payload["items"][0]["count"] = 12
        with self.assertRaisesMessage(ValidationError, "перемещение"):
            import_order(self.integration, payload)
        self.assertEqual(self.stock_quantity(), 10)
        self.assertFalse(Sale.objects.exists())

    def test_fake_and_historical_orders_do_not_deduct(self):
        import_order(self.integration, self.payload(fake=True))
        import_order(self.integration, self.payload(orderId=124, creationDate=(timezone.now() - timedelta(days=10)).isoformat()))
        self.assertEqual(self.stock_quantity(), 10)
        self.assertFalse(Sale.objects.exists())

    def test_cancel_before_shipment_restores_once(self):
        import_order(self.integration, self.payload())
        payload = self.payload(status="CANCELLED", substatus="SHOP_FAILED")
        import_order(self.integration, payload)
        import_order(self.integration, payload)
        self.assertEqual(self.stock_quantity(), 10)
        self.assertTrue(Sale.objects.get().is_cancelled)

    def test_cancel_after_shipment_does_not_restore(self):
        import_order(self.integration, self.payload())
        import_order(self.integration, self.payload(status="DELIVERY", substatus=""))
        import_order(self.integration, self.payload(status="CANCELLED", substatus=""))
        self.assertEqual(self.stock_quantity(), 7)

    def test_missed_delivery_event_does_not_restore_unredeemed_order(self):
        import_order(self.integration, self.payload())
        order = import_order(self.integration, self.payload(status="CANCELLED", substatus="PICKUP_EXPIRED"))
        self.assertTrue(order.shipped_once)
        self.assertEqual(self.stock_quantity(), 7)

    def test_manual_sale_status_and_cancel_blocked(self):
        order = import_order(self.integration, self.payload())
        with self.assertRaises(ValidationError):
            advance_order_status(actor=self.user, sale_id=order.sale_id, next_status=Sale.OrderStatus.ASSEMBLED)
        with self.assertRaises(ValidationError):
            cancel_sale(actor=self.user, sale_id=order.sale_id, comment="Ручная отмена")

    def test_unlink_order_in_progress_rejected(self):
        import_order(self.integration, self.payload())
        with self.assertRaises(ValidationError):
            unlink_offer(self.connection.pk, self.user)

    def test_stale_status_does_not_roll_back_delivery(self):
        old = self.payload()
        order = import_order(self.integration, self.payload(status="DELIVERED", substatus=""))
        import_order(self.integration, old)
        order.refresh_from_db()
        self.assertEqual(order.status, "DELIVERED")

    def test_return_requires_physical_acceptance_and_cannot_repeat(self):
        order = import_order(self.integration, self.payload(status="DELIVERED", substatus=""))
        returned = save_return(order, {"id": 8, "orderId": 123, "shipmentStatus": "RECEIVED", "items": [{"shopSku": "0007-old", "count": 2}]})
        self.assertEqual(self.stock_quantity(), 7)
        accept_return(return_pk=returned.pk, warehouse_id=self.warehouse.pk, actor=self.user)
        self.assertEqual(self.stock_quantity(), 9)
        with self.assertRaises(ValidationError):
            accept_return(return_pk=returned.pk, warehouse_id=self.warehouse.pk, actor=self.user)
        excess = save_return(order, {"id": 9, "orderId": 123, "shipmentStatus": "RECEIVED", "items": [{"shopSku": "0007-old", "count": 2}]})
        with self.assertRaises(ValidationError):
            accept_return(return_pk=excess.pk, warehouse_id=self.warehouse.pk, actor=self.user)
        excess.refresh_from_db()
        self.assertIsNone(excess.accepted_at)
        self.assertEqual(self.stock_quantity(), 9)

    def test_boxes_must_match_counts_and_parts(self):
        order = import_order(self.integration, self.payload())
        validate_boxes(order, [{"items": [{"id": 789, "fullCount": 2}]}, {"items": [{"id": 789, "fullCount": 1}]}])
        with self.assertRaises(ValidationError):
            validate_boxes(order, [{"items": [{"id": 789, "fullCount": 4}]}])
        order.items[0]["count"] = 1
        validate_boxes(order, [{"items": [{"id": 789, "partialCount": {"current": 1, "total": 2}}]}, {"items": [{"id": 789, "partialCount": {"current": 2, "total": 2}}]}])

    def test_webhook_ip_and_duplicate_inbox(self):
        url = reverse("yandex_market:notifications")
        payload = {"notificationType": "ORDER_CREATED", "campaignId": 200, "orderId": 123}
        denied = self.client.post(url, payload, content_type="application/json", REMOTE_ADDR="127.0.0.1", HTTP_X_FORWARDED_FOR="5.45.207.1")
        self.assertEqual(denied.status_code, 403)
        with self.captureOnCommitCallbacks(execute=True):
            for _ in range(2):
                response = self.client.post(url, payload, content_type="application/json", REMOTE_ADDR="5.45.207.1")
                self.assertEqual(response.status_code, 200)
        self.assertEqual(WebhookEvent.objects.count(), 1)
        self.assertEqual(SyncJob.objects.count(), 1)
        self.assertFalse(Sale.objects.exists())

    def test_ping_does_not_access_external_api(self):
        with patch("yandex_market.client.YandexMarketClient.call") as call:
            response = self.client.post(reverse("yandex_market:notifications"), {"notificationType": "PING"}, content_type="application/json", REMOTE_ADDR="5.45.207.1")
        self.assertEqual(response.status_code, 200)
        call.assert_not_called()

    def test_mutations_permission_and_confirmation(self):
        self.client.force_login(self.worker)
        self.assertEqual(self.client.post(reverse("yandex_market:unlink", args=[self.connection.pk]), {"confirm": "yes"}).status_code, 403)
        self.client.force_login(self.user)
        self.client.post(reverse("yandex_market:unlink", args=[self.connection.pk]), {})
        self.connection.refresh_from_db()
        self.assertTrue(self.connection.active)
        self.assertEqual(self.client.get(reverse("yandex_market:unlink", args=[self.connection.pk])).status_code, 405)

    def test_pages_render_without_external_requests(self):
        self.client.force_login(self.user)
        order = import_order(self.integration, self.payload())
        document = LabelDocument.objects.create(integration=self.integration, order=order, created_by=self.user)
        urls = [reverse("yandex_market:dashboard") + "?tab=" + tab for tab in ("overview", "offers", "connections", "orders", "returns", "errors", "mismatches", "log")]
        urls += [reverse("yandex_market:connection", args=[self.connection.pk]), reverse("yandex_market:bind", args=[self.remote.pk]),
                 reverse("yandex_market:settings", args=[self.integration.pk]), reverse("yandex_market:order", args=[order.pk]),
                 reverse("yandex_market:label", args=[document.pk]), reverse("nomenclature:cd_detail", args=[self.product.pk]), reverse("sales:detail", args=[order.sale_id])]
        with patch("yandex_market.client.YandexMarketClient.call") as call:
            for url in urls:
                with self.subTest(url=url):
                    self.assertEqual(self.client.get(url).status_code, 200)
        call.assert_not_called()

    def test_locked_card_price_stock_still_allowed(self):
        self.remote.card_status = "HAS_CARD_CAN_NOT_UPDATE"
        self.remote.save()
        self.connection.refresh_from_db()
        self.enable()
        sync_product(self.connection.pk, client=Mock())
        self.connection.content = {"name": "Замена"}
        self.connection.dirty_fields = ["name"]
        with self.assertRaises(ValidationError):
            build_content(self.connection)

    def test_category_parameters_ids_required_units_and_multivalue(self):
        schema = {"parameters": [{"id": 1, "name": "Цвет", "type": "ENUM", "required": True, "values": [{"id": 10, "value": "Красный"}]}]}
        validate_parameters([{"parameterId": 1, "valueId": 10}], schema)
        for values in ([], [{"parameterId": 1, "valueId": 11}], [{"parameterId": 1, "valueId": 10}] * 2):
            with self.assertRaises(ValidationError):
                validate_parameters(values, schema)

    def test_gtin_and_public_urls(self):
        self.assertTrue(valid_gtin("4006381333931"))
        self.assertFalse(valid_gtin("123"))
        for url in ("http://example.com/a", "https://127.0.0.1/a", "https://a.local/a", "https://user:pass@example.com/a"):
            with self.assertRaises(ValidationError):
                public_https(url)

    def response(self, payload, status=200, headers=None):
        response = Mock()
        response.status, response.headers = status, headers or {}
        response.read.return_value = payload if isinstance(payload, bytes) else json_bytes(payload)
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        return response

    def test_client_redacts_errors_and_retries_429(self):
        transport = Mock(return_value=self.response({"errors": [{"code": "LIMIT", "message": "Api-Key=test-key-never-live"}]}, 429, {"Retry-After": "42"}))
        client = YandexMarketClient(self.integration, key="test-key-never-live", transport=transport)
        with self.assertRaises(MarketError) as caught:
            client.call("getCampaigns")
        self.assertTrue(caught.exception.retryable)
        self.assertEqual(caught.exception.retry_after, 42)
        self.assertNotIn("test-key-never-live", ApiLog.objects.get().message)

    def test_http_200_partial_error_is_failure(self):
        transport = Mock(return_value=self.response({"results": [{"errors": [{"code": "BAD", "message": "Ошибка строки"}]}]}))
        with self.assertRaises(MarketError):
            YandexMarketClient(self.integration, key="test", transport=transport).call("updateOfferMappings", body={"offerMappings": []})

    def test_pagination_preserves_leading_zero_ids(self):
        client = YandexMarketClient(self.integration, key="test")
        client.call = Mock(side_effect=[{"result": {"offerMappings": [{"offerId": "0007"}], "paging": {"nextPageToken": "two"}}}, {"result": {"offerMappings": [{"offerId": "08"}]}}])
        self.assertEqual(list(client.pages("getOfferMappings", body={}, key="offerMappings")), [{"offerId": "0007"}, {"offerId": "08"}])
        self.assertEqual(client.call.call_args.kwargs["query"]["pageToken"], "two")

    @override_settings(YANDEX_MARKET_ALLOW_TEST_TRANSACTION=False)
    def test_http_inside_transaction_forbidden(self):
        with self.assertRaises(RuntimeError):
            YandexMarketClient(self.integration, key="test", transport=Mock()).call("getCampaigns")

    def test_exact_decimal_json(self):
        self.assertEqual(json_bytes({"price": Decimal("99999999.99")}), b'{"price":99999999.99}')
        with self.assertRaises(ValidationError):
            json_bytes(Decimal("NaN"))

    def test_pdf_must_be_official_and_private(self):
        order = import_order(self.integration, self.payload())
        document = LabelDocument.objects.create(integration=self.integration, order=order, created_by=self.user)
        with tempfile.TemporaryDirectory() as folder, override_settings(MEDIA_ROOT=folder):
            client = Mock()
            client.call.return_value = b"%PDF-1.7\nfixture"
            process_label(document.pk, client)
            self.client.force_login(self.worker)
            self.assertEqual(self.client.get(reverse("yandex_market:label_file", args=[document.pk])).status_code, 403)
            self.client.force_login(self.user)
            response = self.client.get(reverse("yandex_market:label_file", args=[document.pk]))
            self.assertEqual(response["Content-Type"], "application/pdf")
            self.assertIn("no-store", response["Cache-Control"])
            response.close()

    def test_async_mass_labels_wait_without_regenerating_report(self):
        document = LabelDocument.objects.create(integration=self.integration, order_ids=[123, 124], created_by=self.user)
        client = Mock()
        client.call.side_effect = [{"result": {"reportId": "report"}}, {"result": {"status": "PROCESSING"}}]
        with self.assertRaises(MarketError):
            process_label(document.pk, client)
        document.refresh_from_db()
        self.assertEqual(document.report_id, "report")
        self.assertEqual(document.state, "processing")

    def test_uploaded_image_has_separate_public_identifier(self):
        from PIL import Image
        upload = BytesIO()
        Image.new("RGB", (10, 10), "red").save(upload, "PNG")
        upload.seek(0)
        with tempfile.TemporaryDirectory() as folder, override_settings(MEDIA_ROOT=folder):
            media = save_image(self.connection, upload)
            response = self.client.get(reverse("yandex_market:media", args=[media.public_id]))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Content-Type"], "image/jpeg")
            response.close()

    def test_unchanged_state_is_not_sent_twice(self):
        self.enable()
        client = Mock()
        sync_product(self.connection.pk, client=client)
        client.reset_mock()
        sync_product(self.connection.pk, client=client)
        client.call.assert_not_called()

    def test_reconciliation_forces_correction_after_remote_drift(self):
        self.enable()
        sync_product(self.connection.pk, client=Mock())
        client = Mock()
        sync_product(self.connection.pk, client=client, force=True)
        self.assertEqual(client.call.call_count, 2)

    def test_trade_snapshots_use_available_not_fit_and_do_not_edit_crm(self):
        client = Mock()
        def pages(operation, **kwargs):
            if operation == "getDefaultPrices":
                return [{"offerId": "0007-old", "price": {"value": "1.00"}}]
            return [{"offerId": "0007-old", "stocks": [{"type": "FIT", "count": 12}, {"type": "FREEZE", "count": 5}]}]
        client.pages.side_effect = pages
        refresh_trade_snapshots(self.integration, client=client)
        self.remote.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(self.remote.remote_stock, 7)
        self.assertEqual(self.remote.remote_price, Decimal("1.00"))
        self.assertEqual(self.product.yandex_market_price, Decimal("99.99"))
        self.assertEqual(self.stock_quantity(), 10)

    def test_batch_uses_current_values_not_queued_snapshot(self):
        self.enable()
        tech = Tech.objects.create(brand=Brand.objects.create(name="Тест"), product_type=ProductType.objects.create(name="Техника"), name="Тестовый Tech", sku="T-YM", yandex_market_price=10)
        remote = RemoteOffer.objects.create(integration=self.integration, offer_id="T-old")
        link = bind_offer(remote_id=remote.pk, product_kind="tech", product_id=tech.pk, actor=self.user)
        link.managed = True
        link.sell_on_yandex = True
        link.save()
        self.stock.quantity = 2
        self.stock.save()
        client = Mock()
        sync_price_stock_batch(self.integration, [self.connection.pk, link.pk], client=client)
        stock_call = next(c for c in client.call.call_args_list if c.args[0] == "updateStocksOnPartnerWarehouses")
        self.assertEqual({row["sku"]: row["count"] for row in stock_call.kwargs["body"]["skuItems"]}, {"0007-old": 9, "T-old": 0})
        self.assertEqual(client.call.call_count, 2)

    def test_product_change_queues_supported_fields_only_after_commit(self):
        self.enable()
        with self.captureOnCommitCallbacks(execute=True):
            self.product.name = "Новое название"
            self.product.save(update_fields=["name"])
        self.connection.refresh_from_db()
        self.assertEqual(self.connection.content["name"], "Новое название")
        self.assertIn("name", self.connection.dirty_fields)
        self.assertEqual(SyncJob.objects.get(kind="product").state, "pending")

    def test_rollback_does_not_enqueue_stock(self):
        self.enable()
        with self.captureOnCommitCallbacks(execute=True):
            try:
                with transaction.atomic():
                    self.stock.quantity = 9
                    self.stock.save()
                    raise ValidationError("Откат")
            except ValidationError:
                pass
        self.assertFalse(SyncJob.objects.exists())
        self.assertEqual(self.stock_quantity(), 10)

    def test_transfer_without_global_change_does_not_send_again(self):
        self.enable()
        sync_product(self.connection.pk, client=Mock())
        self.stock.quantity -= 1
        self.stock.save()
        other = CDWarehouseStock.objects.get(warehouse=self.other, cd=self.product)
        other.quantity += 1
        other.save()
        client = Mock()
        sync_product(self.connection.pk, client=client)
        client.call.assert_not_called()

    def test_new_offer_has_stable_id_and_requires_category(self):
        product = CD.objects.create(platform=self.product.platform, name="Новый", sku="NEW-YM", yandex_market_price=100)
        link = create_offer(integration=self.integration, product_kind="cd", product_id=product.pk, actor=self.user)
        self.assertEqual(link.remote_offer.offer_id, f"GB-CD-{product.pk}")
        self.assertTrue(link.is_new)
        with self.assertRaises(ValidationError):
            activate(link.pk, self.user, sell=True)
        self.assertFalse(SyncJob.objects.exists())

    def test_parameters_cleared_when_category_changes(self):
        from .forms import ContentForm
        self.connection.remote_offer.card = {"parameterValues": [{"parameterId": 44, "value": "old"}]}
        self.connection.parameters = []
        self.connection.dirty_fields = ["parameterValues"]
        self.assertEqual(ContentForm(connection=self.connection).initial_parameters, [])

    def test_photo_order_and_main_photo_are_preserved(self):
        from .models import Media
        Media.objects.create(connection=self.connection, image="first.jpg", position=2)
        main = Media.objects.create(connection=self.connection, image="main.jpg", position=0)
        self.connection.content = {"pictures": []}
        self.connection.dirty_fields = ["pictures"]
        with override_settings(YANDEX_MARKET_PUBLIC_URL="https://crm.example.com"):
            payload = build_content(self.connection)
        self.assertIn(str(main.public_id), payload["pictures"][0])
        self.assertEqual(len(payload["pictures"]), 2)

    def test_multibarcode_search_and_signed_binding_preview(self):
        BarcodeRegistry.objects.create(cd=self.product, value="00123456789")
        self.client.force_login(self.user)
        response = self.client.get(reverse("yandex_market:bind", args=[self.remote.pk]), {"q": "00123456789"})
        self.assertContains(response, self.product.name)
        self.assertEqual(len(response.context["products"]), 1)
        response = self.client.get(reverse("yandex_market:bind", args=[self.remote.pk]), {"kind": "cd", "product": self.product.pk})
        self.assertTrue(response.context["token"])
        response = self.client.post(reverse("yandex_market:bind", args=[self.remote.pk]), {"confirm": "yes", "token": "tampered"})
        self.assertEqual(response.status_code, 302)

    def test_list_reads_stock_in_one_query(self):
        with self.assertNumQueries(1):
            rows = list(connections_with_stock(OfferConnection.objects.select_related("cd", "tech", "remote_offer")))
            self.assertEqual(rows[0].physical_stock, 17)
            self.assertEqual(rows[0].product.name, self.product.name)

    def test_api_key_is_encrypted_and_never_rendered(self):
        from pathlib import Path
        from .client import api_key
        with tempfile.TemporaryDirectory() as folder, override_settings(YANDEX_MARKET_API_KEY="", YANDEX_MARKET_KEY_FILE=Path(folder)/"secret", INTEGRATION_ENCRYPTION_KEY_FILE=Path(folder)/"encryption"):
            store_api_key("new-test-key-only")
            self.assertNotIn("new-test-key-only", (Path(folder)/"secret").read_text())
            self.assertEqual(api_key(), "new-test-key-only")
            self.client.force_login(self.user)
            self.assertNotContains(self.client.get(reverse("yandex_market:settings", args=[self.integration.pk])), "new-test-key-only")

    def test_catalog_import_handles_all_pages_and_preserves_no_connections(self):
        client = Mock()
        def pages(operation, **kwargs):
            if operation == "getOfferMappings":
                return iter([{"offer": {"offerId": "0008", "name": "Первый"}}, {"offer": {"offerId": "0009", "name": "Второй"}}])
            return iter([])
        client.pages.side_effect = pages
        self.assertEqual(refresh_catalog(self.integration, client=client), 2)
        self.assertEqual(OfferConnection.objects.count(), 1)
        self.assertEqual(CD.objects.count(), 1)

    def test_return_before_shipment_cannot_be_accepted(self):
        order = import_order(self.integration, self.payload())
        returned = save_return(order, {"id": 8, "orderId": 123, "shipmentStatus": "RECEIVED", "items": [{"shopSku": "0007-old", "count": 1}]})
        with self.assertRaises(ValidationError):
            accept_return(return_pk=returned.pk, warehouse_id=self.warehouse.pk, actor=self.user)
        import_order(self.integration, self.payload(status="CANCELLED", substatus="SHOP_FAILED"))
        self.assertEqual(self.stock_quantity(), 10)

    def test_empty_complex_widget_does_not_clear_remote_field(self):
        from .forms import ContentForm
        form = ContentForm(data={"revision": 1, "content_name": "Товар", "content_manuals": "[]", "content_commodityCodes": "[]"}, connection=self.connection)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertNotIn("manuals", form.cleaned_data["content"])

    def test_clear_omits_value_and_sends_explicit_delete(self):
        self.connection.content = {"description": "Было"}
        self.connection.dirty_fields = ["description"]
        self.connection.delete_fields = ["DESCRIPTION"]
        payload = build_content(self.connection)
        self.assertNotIn("description", payload)
        self.assertEqual(payload["deleteParameters"], ["DESCRIPTION"])

    def test_dimensions_are_numbers_after_database_roundtrip(self):
        self.product.weight_grams = 150
        self.product.save(update_fields=["weight_grams"])
        self.connection.content = {"weightDimensions": {"length": Decimal("10.50"), "width": Decimal("15.0"), "height": Decimal("2.0")}}
        self.connection.dirty_fields = ["weightDimensions"]
        self.connection.save()
        self.connection.refresh_from_db()
        payload = build_content(self.connection)
        self.assertEqual(payload["weightDimensions"]["weight"], Decimal("0.15"))
        self.assertIsInstance(payload["weightDimensions"]["length"], Decimal)

    def test_parameter_update_always_includes_category(self):
        self.connection.dirty_fields = ["parameterValues"]
        self.assertEqual(build_content(self.connection)["marketCategoryId"], 50)

    def test_rate_limit_is_shared_between_clients(self):
        from .models import ApiBudget
        ApiBudget.objects.create(key="100:updateStocksOnPartnerWarehouses", used=50)
        client = YandexMarketClient(self.integration, key="test", transport=Mock())
        with self.assertRaises(MarketError) as caught:
            client.call("updateStocksOnPartnerWarehouses", body={"skuItems": []})
        self.assertEqual(caught.exception.code, "LOCAL_RATE_LIMIT")
        client.transport.assert_not_called()

    def test_claim_is_exclusive(self):
        from .tasks import claim_job
        self.enable()
        enqueue(self.integration, "order", 123, {"order_id": 123})
        first = claim_job()
        self.assertIsNotNone(first)
        self.assertIsNone(claim_job())

    def test_rebind_preserves_old_line_reference(self):
        order = import_order(self.integration, self.payload(status="DELIVERED", substatus=""))
        other = CD.objects.create(platform=self.product.platform, name="Другой", sku="OTHER-YM")
        replacement = unlink_offer(self.connection.pk, self.user, replacement={"product_kind": "cd", "product_id": other.pk})
        self.assertNotEqual(replacement.pk, self.connection.pk)
        self.assertEqual(order.lines.get().connection_id, self.connection.pk)
        self.assertFalse(replacement.managed)
