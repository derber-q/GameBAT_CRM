from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from catalog.models import CD, Platform
from sales.models import Sale
from sales.services import create_sale
from warehouse.models import CDWarehouseStock, Warehouse


class SaleInvoiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("invoice-admin", password="StrongAdmin!123")
        self.warehouse = Warehouse.objects.create(name="Основной склад")
        self.platform = Platform.objects.create(name="PS5")
        self.cd = CD.objects.create(
            platform=self.platform, name="Тестовый диск", sku="CD-INV-1", barcode="INV-1",
            cost=Decimal("100.00"), avito_price=Decimal("250.00"),
        )
        CDWarehouseStock.objects.create(warehouse=self.warehouse, cd=self.cd, quantity=3)
        self.client.force_login(self.user)

    def test_invoice_download_is_available_for_unfinished_sale(self):
        sale = create_sale(
            actor=self.user, warehouse_id=self.warehouse.pk,
            price_type=Sale.PriceType.RETAIL, sale_type=Sale.SaleType.RETAIL,
            payment_method=Sale.PaymentMethod.CASH_POSTPAY,
            lines=[{"product_type": "cd", "product_id": self.cd.pk, "quantity": 2}],
        )
        response = self.client.get(reverse("sales:invoice", args=(sale.pk,)))
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment; filename=\"nakladnaya-", response["Content-Disposition"])
        body = response.content.decode("utf-8")
        self.assertIn("Тестовый диск", body)
        self.assertIn("2", body)
        self.assertIn("500,00", body)
        self.assertEqual(sale.order_status, Sale.OrderStatus.CREATED)
        self.assertEqual(sale.payment_status, Sale.PaymentStatus.UNPAID)
