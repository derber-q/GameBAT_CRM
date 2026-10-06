from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from catalog.models import CD, Platform, Tech, Brand, ProductType
from warehouse.models import CDWarehouseStock, TechWarehouseStock, Warehouse

from .models import Sale, SaleCustomItem
from .services import cancel_sale, create_sale, edit_postpay_sale_items
from .statistics_service import build_sales_statistics_report


class CustomSaleItemTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("custom-admin", password="StrongAdmin!123")
        self.warehouse = Warehouse.objects.create(name="Custom warehouse")
        self.platform = Platform.objects.create(name="PS5")
        self.brand = Brand.objects.create(name="Sony")
        self.product_type = ProductType.objects.create(name="РљРѕРЅСЃРѕР»Рё")
        self.cd = CD.objects.create(platform=self.platform, name="Game", sku="CD-1", cost=100, avito_price=500)
        self.tech = Tech.objects.create(brand=self.brand, product_type=self.product_type, name="Console", sku="T-1", cost=200, avito_price=1000)
        CDWarehouseStock.objects.create(warehouse=self.warehouse, cd=self.cd, quantity=2)
        TechWarehouseStock.objects.create(warehouse=self.warehouse, tech=self.tech, quantity=2)

    def custom(self, name="Setup", price="2000", quantity="1", cost="500"):
        return {"product_type": "custom", "name": name, "unit_price": price, "quantity": quantity, "unit_cost": cost}

    def test_create_view_accepts_custom_only_form_submission(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("sales:create"), {
            "warehouse": self.warehouse.pk,
            "price_type": Sale.PriceType.RETAIL,
            "sale_type": Sale.SaleType.RETAIL,
            "payment_method": Sale.PaymentMethod.BANK_ACCOUNT,
            "product_type": "",
            "product_id": "",
            "quantity": "",
            "custom_name": "Manual only",
            "custom_unit_price": "1200.00",
            "custom_quantity": "1",
            "custom_unit_cost": "300.00",
            "note": "",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Sale.objects.count(), 1)
        self.assertEqual(Sale.objects.get().custom_items.count(), 1)

    def test_custom_only_sale_is_snapshot_and_does_not_create_product_or_stock(self):
        sale = create_sale(actor=self.user, warehouse_id=self.warehouse.pk, price_type=Sale.PriceType.RETAIL,
                           sale_type=Sale.SaleType.RETAIL, payment_method=Sale.PaymentMethod.BANK_ACCOUNT,
                           lines=[self.custom()])
        item = sale.custom_items.get()
        self.assertEqual((sale.total_amount, item.line_total, item.unit_cost_snapshot), (Decimal("2000.00"), Decimal("2000.00"), Decimal("500.00")))
        self.assertEqual(CDWarehouseStock.objects.get().quantity, 2)
        self.assertEqual(TechWarehouseStock.objects.get().quantity, 2)
        self.assertEqual(CD.objects.count(), 1)
        self.assertEqual(Tech.objects.count(), 1)

    def test_mixed_sale_deducts_only_real_products_and_cancel_refunds_full_total(self):
        sale = create_sale(actor=self.user, warehouse_id=self.warehouse.pk, price_type=Sale.PriceType.RETAIL,
                           sale_type=Sale.SaleType.RETAIL, payment_method=Sale.PaymentMethod.BANK_ACCOUNT,
                           lines=[{"product_type": "cd", "product_id": self.cd.pk, "quantity": 1}, self.custom(price="1500")])
        self.assertEqual(sale.total_amount, Decimal("2000.00"))
        self.assertEqual(CDWarehouseStock.objects.get().quantity, 1)
        cancel_sale(actor=self.user, sale_id=sale.pk, comment="mixed cancel")
        self.assertEqual(CDWarehouseStock.objects.get().quantity, 2)
        self.assertEqual(sale.__class__.objects.get(pk=sale.pk).refunded_amount, Decimal("0.00"))

    def test_custom_postpay_can_be_changed(self):
        sale = create_sale(actor=self.user, warehouse_id=self.warehouse.pk, price_type=Sale.PriceType.RETAIL,
                           sale_type=Sale.SaleType.RETAIL, payment_method=Sale.PaymentMethod.CASH_POSTPAY,
                           lines=[self.custom()])
        edit_postpay_sale_items(actor=self.user, sale_id=sale.pk, lines=[self.custom(price="1000", quantity="2", cost="200")])
        item = SaleCustomItem.objects.get(sale=sale)
        self.assertEqual((item.quantity, item.unit_price, item.unit_cost_snapshot, sale.__class__.objects.get(pk=sale.pk).total_amount), (2, Decimal("1000.00"), Decimal("200.00"), Decimal("2000.00")))

    def test_custom_item_is_in_statistics_and_exact_name_is_aggregate_key(self):
        sale = create_sale(actor=self.user, warehouse_id=self.warehouse.pk, price_type=Sale.PriceType.RETAIL,
                           sale_type=Sale.SaleType.RETAIL, payment_method=Sale.PaymentMethod.CASH,
                           lines=[self.custom()])
        report = build_sales_statistics_report({})
        self.assertEqual(report.totals.actual_revenue, Decimal("2000.00"))
        self.assertEqual(report.products[0].kind, "custom")
        self.assertEqual(report.products[0].profit, Decimal("1500.00"))
