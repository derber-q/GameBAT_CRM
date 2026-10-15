from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from catalog.models import Brand, CD, Platform, ProductType, Tech
from consignment.models import CDConsignmentStock
from consignment.services import transfer_to_consignment
from partners.models import SalesPlatform
from warehouse.models import CDWarehouseStock, TechWarehouseStock, Warehouse

from .models import Sale
from .services import cancel_sale, create_sale, edit_postpay_sale_items
from .statistics_service import build_sales_statistics_report


class SaleDiscountTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("discount-admin", password="StrongAdmin!123")
        self.warehouse = Warehouse.objects.create(name="Склад скидок")
        platform = Platform.objects.create(name="PS5")
        self.product = CD.objects.create(
            platform=platform, name="Игра", sku="DISC-1", cost=Decimal("100.01"),
            avito_price=Decimal("500.00"),
        )
        self.stock = CDWarehouseStock.objects.create(
            warehouse=self.warehouse, cd=self.product, quantity=5,
        )

    def _line(self, *, quantity=2, discount="50"):
        return {
            "product_type": "cd", "product_id": self.product.pk,
            "quantity": quantity, "unit_discount": discount,
        }

    def test_discount_is_snapshotted_and_used_by_total_and_statistics(self):
        sale = create_sale(
            actor=self.user, warehouse_id=self.warehouse.pk,
            price_type=Sale.PriceType.RETAIL, sale_type=Sale.SaleType.RETAIL,
            payment_method=Sale.PaymentMethod.CASH,
            lines=[self._line()], note="Скидка по согласованию",
        )

        item = sale.cd_items.get()
        report = build_sales_statistics_report({})
        self.assertEqual(item.unit_price, Decimal("500.00"))
        self.assertEqual(item.unit_discount, Decimal("50.00"))
        self.assertEqual(item.effective_unit_price, Decimal("450.00"))
        self.assertEqual(item.line_total, Decimal("900.00"))
        self.assertEqual(sale.total_amount, Decimal("900.00"))
        self.assertEqual(report.totals.actual_revenue, Decimal("900.00"))

    def test_discount_requires_note_and_rolls_back_stock(self):
        with self.assertRaisesMessage(ValidationError, "примечание"):
            create_sale(
                actor=self.user, warehouse_id=self.warehouse.pk,
                price_type=Sale.PriceType.RETAIL, sale_type=Sale.SaleType.RETAIL,
                payment_method=Sale.PaymentMethod.BANK_ACCOUNT,
                lines=[self._line()], note="",
            )
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 5)
        self.assertEqual(Sale.objects.count(), 0)

    def test_discount_cannot_exceed_base_price(self):
        with self.assertRaisesMessage(ValidationError, "не может превышать цену"):
            create_sale(
                actor=self.user, warehouse_id=self.warehouse.pk,
                price_type=Sale.PriceType.RETAIL, sale_type=Sale.SaleType.RETAIL,
                payment_method=Sale.PaymentMethod.BANK_ACCOUNT,
                lines=[self._line(discount="500.01")], note="Ошибка",
            )

    def test_postpay_edit_recalculates_discount_and_note(self):
        sale = create_sale(
            actor=self.user, warehouse_id=self.warehouse.pk,
            price_type=Sale.PriceType.RETAIL, sale_type=Sale.SaleType.RETAIL,
            payment_method=Sale.PaymentMethod.CASH_POSTPAY,
            lines=[self._line(quantity=1, discount="0")],
        )
        edit_postpay_sale_items(
            actor=self.user, sale_id=sale.pk,
            lines=[self._line(quantity=2, discount="25")], note="Скидка при выдаче",
        )
        sale.refresh_from_db()
        item = sale.cd_items.get()
        self.assertEqual((item.unit_discount, item.line_total), (Decimal("25.00"), Decimal("950.00")))
        self.assertEqual((sale.total_amount, sale.note), (Decimal("950.00"), "Скидка при выдаче"))

    def test_surcharge_is_snapshotted_paid_and_included_in_commission_and_statistics(self):
        sale = create_sale(
            actor=self.user, warehouse_id=self.warehouse.pk,
            price_type=Sale.PriceType.RETAIL, sale_type=Sale.SaleType.AVITO,
            payment_method=Sale.PaymentMethod.CASH,
            lines=[self._line(discount="-50.01")], note="Доплата за единицу",
        )
        item = sale.cd_items.get()
        item.full_clean()
        self.assertEqual(item.unit_discount, Decimal("-50.01"))
        self.assertEqual(item.effective_unit_price, Decimal("550.01"))
        self.assertEqual(item.price_adjustment_display, "+50.01")
        self.assertEqual(item.avito_commission_amount, Decimal("5.50"))
        self.assertEqual((sale.total_amount, sale.cash_received_amount, sale.extra_cash_amount),
                         (Decimal("1100.02"), Decimal("1100.02"), Decimal("0")))
        self.warehouse.cash_register.refresh_from_db()
        self.assertEqual(self.warehouse.cash_register.balance, Decimal("1100.02"))
        report = build_sales_statistics_report({})
        self.assertEqual((report.totals.actual_revenue, report.totals.profit),
                         (Decimal("1100.02"), Decimal("894.50")))
        self.client.force_login(self.user)
        self.assertContains(self.client.get(reverse("sales:detail", args=(sale.pk,))), "+50.01")

    def test_surcharge_for_tech_and_custom_items_and_postpay_edit(self):
        tech = Tech.objects.create(
            brand=Brand.objects.create(name="Бренд"), product_type=ProductType.objects.create(name="Техника"),
            name="Приставка", sku="SURCHARGE-TECH", cost=50, avito_price=100,
        )
        TechWarehouseStock.objects.create(warehouse=self.warehouse, tech=tech, quantity=5)
        lines = [
            {"product_type": "tech", "product_id": tech.pk, "quantity": 2, "unit_discount": "-10.01"},
            {"product_type": "custom", "name": "Услуга", "quantity": 3,
             "unit_price": "80", "unit_cost": "0", "unit_discount": "-20"},
        ]
        sale = create_sale(
            actor=self.user, warehouse_id=self.warehouse.pk,
            price_type=Sale.PriceType.RETAIL, sale_type=Sale.SaleType.RETAIL,
            payment_method=Sale.PaymentMethod.CASH_POSTPAY, lines=lines, note="Доплата",
        )
        sale.tech_items.get().full_clean()
        sale.custom_items.get().full_clean()
        self.assertEqual(sale.total_amount, Decimal("520.02"))
        self.client.force_login(self.user)
        response = self.client.get(reverse("sales:edit", args=(sale.pk,)))
        self.assertContains(response, '"unit_discount": "-10.01"')
        lines[0]["unit_discount"] = "5"
        lines[1]["unit_discount"] = "-0.01"
        edit_postpay_sale_items(actor=self.user, sale_id=sale.pk, lines=lines, note="Изменение доплаты")
        sale.refresh_from_db()
        self.assertEqual(sale.total_amount, Decimal("430.03"))
        self.assertEqual(sale.tech_items.get().unit_discount, Decimal("5"))
        self.assertEqual(sale.custom_items.get().unit_discount, Decimal("-0.01"))

    def test_surcharge_requires_note_and_nonfinite_values_are_rejected(self):
        for value in ("-1", "NaN", "-Infinity"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                create_sale(
                    actor=self.user, warehouse_id=self.warehouse.pk,
                    price_type=Sale.PriceType.RETAIL, sale_type=Sale.SaleType.RETAIL,
                    payment_method=Sale.PaymentMethod.CASH, lines=[self._line(discount=value)],
                )
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 5)
        self.assertFalse(Sale.objects.exists())

    def test_http_create_accepts_signed_discount(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("sales:create"), {
            "warehouse": self.warehouse.pk, "price_type": Sale.PriceType.RETAIL,
            "sale_type": Sale.SaleType.RETAIL, "payment_method": Sale.PaymentMethod.CASH,
            "product_type": "cd", "product_id": self.product.pk, "quantity": "2",
            "unit_discount": "-1.01", "note": "Доплата",
        })
        self.assertEqual(response.status_code, 302)
        sale = Sale.objects.get()
        self.assertEqual(sale.total_amount, Decimal("1002.02"))
        self.assertEqual(sale.cd_items.get().unit_discount, Decimal("-1.01"))


class MixedConsignmentSaleTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("consignment-sale-admin", password="StrongAdmin!123")
        self.warehouse = Warehouse.objects.create(name="Склад реализации")
        platform = Platform.objects.create(name="Switch")
        self.product = CD.objects.create(
            platform=platform, name="Nintendo Switch 2", sku="NS2", cost=Decimal("40000.00"),
            avito_price=Decimal("50000.00"),
        )
        self.warehouse_stock = CDWarehouseStock.objects.create(
            warehouse=self.warehouse, cd=self.product, quantity=5,
        )
        self.sales_platform = SalesPlatform.objects.create(
            name="Джогстик", address="Адрес", legal_entity="ООО Джогстик", phone_1="+70000000000",
        )
        self.consignment_stock = transfer_to_consignment(
            actor=self.user, warehouse_id=self.warehouse.pk, platform_id=self.sales_platform.pk,
            product_type="cd", product_id=self.product.pk, quantity=2,
            receivable_per_unit="47500",
        )

    def test_create_page_does_not_expose_consignment_cost(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("sales:create"))

        self.assertEqual(response.status_code, 200)
        option = next(
            row for row in response.context["consignment_options"]
            if row["stock_id"] == self.consignment_stock.pk
        )
        self.assertNotIn("unit_cost", option)
        script = (settings.STATICFILES_DIRS[0] / "js" / "stock-lines.js").read_text(encoding="utf-8")
        consignment_script = script.split("function addConsignmentLine", 1)[1].split(
            "function selectedPrice", 1
        )[0]
        self.assertNotIn("dataset.unitCost", consignment_script)
        self.assertIn('costCell.className = "numeric muted"; costCell.textContent = "—";', consignment_script)
        self.assertContains(response, "stock-lines.js?v=global-barcode-1-sale-discounts-2-avito-commission-9-barcode-focus-2-signed-discount-1")

    def test_mixed_sale_consumes_each_inventory_source_once_and_cancel_restores_it(self):
        sale = create_sale(
            actor=self.user, warehouse_id=self.warehouse.pk,
            price_type=Sale.PriceType.RETAIL, sale_type=Sale.SaleType.RETAIL,
            payment_method=Sale.PaymentMethod.BANK_ACCOUNT,
            lines=[
                {"product_type": "cd", "product_id": self.product.pk, "quantity": 1},
                {"product_type": "consignment", "product_kind": "cd",
                 "stock_id": self.consignment_stock.pk, "quantity": 1},
            ],
        )
        self.warehouse_stock.refresh_from_db()
        self.consignment_stock.refresh_from_db()
        snapshot = sale.consignment_items.get()
        self.assertEqual(self.warehouse_stock.quantity, 2)
        self.assertEqual(self.consignment_stock.quantity, 1)
        self.assertEqual(snapshot.unit_price, Decimal("47500.00"))
        self.assertEqual(snapshot.unit_cost_snapshot, Decimal("40000.00"))
        self.assertEqual(sale.total_amount, Decimal("97500.00"))

        cancel_sale(actor=self.user, sale_id=sale.pk, comment="Отмена смешанной продажи")
        self.warehouse_stock.refresh_from_db()
        self.consignment_stock.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(self.warehouse_stock.quantity, 3)
        self.assertEqual(self.consignment_stock.quantity, 2)
        self.assertEqual(self.product.quantity_on_consignment, 2)

    def test_excess_consignment_quantity_rolls_back_whole_sale(self):
        with self.assertRaisesMessage(ValidationError, "осталось только 2"):
            create_sale(
                actor=self.user, warehouse_id=self.warehouse.pk,
                price_type=Sale.PriceType.RETAIL, sale_type=Sale.SaleType.RETAIL,
                payment_method=Sale.PaymentMethod.BANK_ACCOUNT,
                lines=[
                    {"product_type": "cd", "product_id": self.product.pk, "quantity": 1},
                    {"product_type": "consignment", "product_kind": "cd",
                     "stock_id": self.consignment_stock.pk, "quantity": 3},
                ],
            )
        self.warehouse_stock.refresh_from_db()
        self.consignment_stock.refresh_from_db()
        self.assertEqual((self.warehouse_stock.quantity, self.consignment_stock.quantity), (3, 2))
        self.assertEqual(Sale.objects.count(), 0)
