from datetime import timedelta
from decimal import Decimal
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import User
from catalog.models import Brand, CD, Platform, ProductType, Tech
from warehouse.models import CDWarehouseStock, TechWarehouseStock, Warehouse

from .google_sheets import build_price_rows, extract_spreadsheet_id
from .google_tasks import enqueue_google_sheets_sync, ensure_periodic_google_sheets_job
from .models import GoogleSheetsSyncJob


@override_settings(
    GOOGLE_SERVICE_ACCOUNT_FILE="fake-service-account.json",
    GOOGLE_SHEETS_DEFAULT_URL="https://docs.google.com/spreadsheets/d/test-sheet-id/edit",
    GOOGLE_SHEETS_DEFAULT_TAB="Прайс CRM",
)
class GoogleSheetsPriceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("sheets-admin", password="StrongAdmin!123")
        self.warehouse = Warehouse.objects.create(name="Склад Google")
        self.brand = Brand.objects.create(name="Nintendo")
        self.product_type = ProductType.objects.create(name="Консоли")
        self.platform = Platform.objects.create(name="Switch")

    def test_extracts_spreadsheet_id_from_shared_url(self):
        url = "https://docs.google.com/spreadsheets/d/1bNKeWmFyoWZOQDEuhCXxltv0YkK6ykW20tXI9uI2tiI/edit?usp=sharing"
        self.assertEqual(extract_spreadsheet_id(url), "1bNKeWmFyoWZOQDEuhCXxltv0YkK6ykW20tXI9uI2tiI")

    def test_rows_use_physical_stock_and_keep_only_recent_zero_products(self):
        tech = Tech.objects.create(
            brand=self.brand, product_type=self.product_type, name="Switch 2",
            sku="SW2", cost=Decimal("40000.25"), wholesale_price=Decimal("45000.00"),
        )
        TechWarehouseStock.objects.create(warehouse=self.warehouse, tech=tech, quantity=3)
        recent = CD.objects.create(
            platform=self.platform, name="Recent zero", sku="ZERO-NEW",
            cost=Decimal("100.00"), zero_stock_since=timezone.now() - timedelta(days=10),
        )
        old = CD.objects.create(
            platform=self.platform, name="Old zero", sku="ZERO-OLD",
            cost=Decimal("200.00"), zero_stock_since=timezone.now() - timedelta(days=40),
        )
        CDWarehouseStock.objects.create(warehouse=self.warehouse, cd=recent, quantity=0)
        CDWarehouseStock.objects.create(warehouse=self.warehouse, cd=old, quantity=0)

        rows, _, zero_rows = build_price_rows()
        names = [row[0].strip() for row in rows]
        self.assertLess(names.index("Техника"), names.index("Диски"))
        self.assertIn("Nintendo", names)
        self.assertIn("Консоли", names)
        self.assertIn("Switch 2", names)
        self.assertIn("Recent zero", names)
        self.assertNotIn("Old zero", names)
        self.assertEqual(rows[names.index("Switch 2")][2], 3)
        self.assertIn(names.index("Recent zero") + 1, zero_rows)

    def test_manual_queue_is_deduplicated_and_periodic_error_is_retried(self):
        first = enqueue_google_sheets_sync(requested_by=self.user, manual=True)
        second = enqueue_google_sheets_sync(requested_by=self.user, manual=True)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(GoogleSheetsSyncJob.objects.filter(dedupe_key="manual").count(), 1)

        periodic = enqueue_google_sheets_sync()
        periodic.status = GoogleSheetsSyncJob.Status.ERROR
        periodic.run_after = timezone.now() - timedelta(seconds=1)
        periodic.attempts = 5
        periodic.save()
        ensure_periodic_google_sheets_job()
        periodic.refresh_from_db()
        self.assertEqual(periodic.status, GoogleSheetsSyncJob.Status.PENDING)
        self.assertEqual(periodic.attempts, 0)
