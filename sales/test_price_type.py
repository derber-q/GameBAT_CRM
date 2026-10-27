"""Оптовая цена доступна только при создании оптовой продажи."""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from cash.models import CashTransaction
from catalog.models import CD, Platform
from warehouse.models import CDWarehouseStock, Warehouse
from .forms import SaleCreateForm
from .models import Sale
from .services import create_sale


class SalePriceTypeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor = User.objects.create_superuser("wholesale-price-admin")
        cls.warehouse = Warehouse.objects.create(name="Склад оптовых продаж")
        cls.product = CD.objects.create(name="Игра", platform=Platform.objects.create(name="PS5"),
            cost=100, avito_price=200, wholesale_price=150, yandex_market_price=220)
        cls.stock = CDWarehouseStock.objects.create(warehouse=cls.warehouse, cd=cls.product, quantity=10)

    def data(self, sale_type="wholesale", price_type="wholesale"):
        return {"warehouse": self.warehouse.pk, "sale_type": sale_type, "price_type": price_type,
                "payment_method": "cash_postpay", 'customer': 'custom', 'custom_partner_name': 'Тестовый заказчик'}

    def test_service_rejects_wholesale_price_for_other_channels_without_side_effects(self):
        for sale_type in ("retail", "avito", "consignment"):
            with self.subTest(sale_type=sale_type), self.assertRaisesMessage(ValidationError, "только для оптовой продажи"):
                create_sale(actor=self.actor, warehouse_id=self.warehouse.pk,
                    sale_type=sale_type, price_type="wholesale", payment_method="cash",
                    lines=[{"product_type": "cd", "product_id": self.product.pk, "quantity": 1}], partner_name='Тестовый заказчик' if sale_type == 'wholesale' else '')
        self.stock.refresh_from_db()
        self.warehouse.cash_register.refresh_from_db()
        self.assertEqual(self.stock.quantity, 10)
        self.assertEqual(self.warehouse.cash_register.balance, 0)
        self.assertFalse(Sale.objects.exists())
        self.assertFalse(CashTransaction.objects.exists())

    def test_wholesale_sale_records_wholesale_price(self):
        sale = create_sale(actor=self.actor, warehouse_id=self.warehouse.pk,
            sale_type="wholesale", price_type="wholesale", payment_method="cash_postpay",
            lines=[{"product_type": "cd", "product_id": self.product.pk, "quantity": 2}], partner_name='Тестовый заказчик')
        self.assertEqual(sale.cd_items.get().unit_price, Decimal("150.00"))
        self.assertEqual(sale.total_amount, Decimal("300.00"))

    def test_form_rejects_wholesale_price_for_other_channels(self):
        for channel in ("retail", "avito"):
            with self.subTest(channel=channel):
                form = SaleCreateForm(data=self.data(sale_type=channel))
                self.assertFalse(form.is_valid())
                self.assertIn("только для оптовой продажи", form.errors["price_type"][0])
        self.assertTrue(SaleCreateForm(data=self.data()).is_valid())

    def test_wholesale_import_keeps_sale_type_and_price_fixed(self):
        form = SaleCreateForm(data=self.data(sale_type="retail", price_type="retail"),
            initial=self.data(), imported_wholesale=True)
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["sale_type"], "wholesale")
        self.assertEqual(form.cleaned_data["price_type"], "wholesale")

    def test_tampered_post_does_not_create_nonwholesale_sale(self):
        self.client.force_login(self.actor)
        response = self.client.post(reverse("sales:create"), {
            **self.data(sale_type="avito"), "product_type": ["cd"],
            "product_id": [self.product.pk], "quantity": [1],
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "только для оптовой продажи")
        self.assertFalse(Sale.objects.exists())
