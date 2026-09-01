from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.models import User
from catalog.models import CD, Platform
from partners.models import SalesPlatform
from .models import CDConsignmentStock
from .services import return_from_consignment, transfer_to_consignment


class ConsignmentServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("admin", password="StrongAdmin!123")
        platform = Platform.objects.create(name="PS5")
        self.product = CD.objects.create(
            platform=platform, name="Игра", sku="CD-1", barcode="001", quantity=10, cost=100
        )
        self.sales_platform = SalesPlatform.objects.create(
            name="Магазин", address="Адрес", legal_entity="ООО Магазин", phone_1="+70000000000"
        )

    def transfer(self, quantity=3, reward="50"):
        return transfer_to_consignment(
            actor=self.user, platform_id=self.sales_platform.pk, product_type="cd",
            product_id=self.product.pk, quantity=quantity, reward_per_unit=reward,
        )

    def test_transfer_updates_all_three_balances(self):
        stock = self.transfer()
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, 7)
        self.assertEqual(self.product.quantity_on_consignment, 3)
        self.assertEqual(stock.quantity, 3)
        self.assertEqual(stock.reward_per_unit, Decimal("50.00"))

    def test_cannot_transfer_more_than_warehouse_balance(self):
        with self.assertRaisesMessage(ValidationError, "Недостаточно товара на складе"):
            self.transfer(quantity=11)
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, 10)
        self.assertEqual(CDConsignmentStock.objects.count(), 0)

    def test_return_is_reverse_operation(self):
        self.transfer(quantity=4)
        stock = return_from_consignment(
            actor=self.user, platform_id=self.sales_platform.pk, product_type="cd",
            product_id=self.product.pk, quantity=2,
        )
        self.product.refresh_from_db()
        self.assertEqual(stock.quantity, 2)
        self.assertEqual(self.product.quantity, 8)
        self.assertEqual(self.product.quantity_on_consignment, 2)

    def test_cannot_return_more_than_platform_balance(self):
        self.transfer(quantity=2)
        with self.assertRaisesMessage(ValidationError, "только 2 единиц"):
            return_from_consignment(
                actor=self.user, platform_id=self.sales_platform.pk, product_type="cd",
                product_id=self.product.pk, quantity=3,
            )

    def test_different_reward_does_not_overwrite_existing_nonzero_stock(self):
        self.transfer(quantity=2, reward="50")
        with self.assertRaisesMessage(ValidationError, "уже задано другое вознаграждение"):
            self.transfer(quantity=1, reward="60")
        stock = CDConsignmentStock.objects.get()
        self.assertEqual(stock.quantity, 2)
        self.assertEqual(stock.reward_per_unit, Decimal("50.00"))

    def test_nonpositive_operations_are_rejected(self):
        with self.assertRaises(ValidationError):
            self.transfer(quantity=0)
