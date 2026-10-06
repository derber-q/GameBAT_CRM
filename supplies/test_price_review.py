from decimal import Decimal

from django.test import TestCase

from accounts.models import User
from catalog.models import CD, Platform
from partners.models import Supplier
from warehouse.models import CDWarehouseStock, Warehouse

from .models import Supply
from .services import accept_supply, cancel_supply, confirm_supply_price_review


class SupplyPriceReviewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("review-admin", password="StrongAdmin!123")
        self.warehouse = Warehouse.objects.create(name="Склад проверки цен")
        platform = Platform.objects.create(name="PS5")
        self.product = CD.objects.create(
            platform=platform, name="Игра", sku="REVIEW-1", cost=Decimal("100.00"),
            wholesale_price=Decimal("150.00"),
        )
        self.stock = CDWarehouseStock.objects.create(
            warehouse=self.warehouse, cd=self.product, quantity=2,
        )
        self.supplier = Supplier.objects.create(
            name="Поставщик", letter="R", highlight_color="#123456",
            legal_entity="ООО Поставщик", phone_1="+70000000000",
        )

    def _pending_supply(self):
        return accept_supply(
            accepted_by=self.user, warehouse_id=self.warehouse.pk,
            lines=[{
                "product_type": "cd", "product_id": self.product.pk,
                "supplier_id": self.supplier.pk, "quantity": 2,
                "purchase_unit_cost": "200.00",
            }],
            defer_balance=True,
        )

    def test_pending_review_does_not_change_stock_or_cost(self):
        supply = self._pending_supply()
        self.stock.refresh_from_db()
        self.product.refresh_from_db()
        calculation = supply.cost_calculations.get()
        self.assertEqual(supply.status, Supply.Status.PRICE_REVIEW_REQUIRED)
        self.assertEqual(self.stock.quantity, 2)
        self.assertEqual(self.product.cost, Decimal("100.00"))
        self.assertEqual(calculation.old_owned_quantity, 2)
        self.assertEqual(calculation.resulting_quantity, 4)
        self.assertEqual(calculation.resulting_unit_cost, Decimal("150.00"))

    def test_confirm_is_atomic_and_idempotent(self):
        supply = self._pending_supply()
        confirmed, changed = confirm_supply_price_review(
            actor=self.user, supply_id=supply.pk,
            price_changes={("cd", self.product.pk): {"wholesale_price": "225.50"}},
        )
        self.assertTrue(changed)
        self.stock.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(confirmed.status, Supply.Status.ACCEPTED)
        self.assertEqual(self.stock.quantity, 4)
        self.assertEqual(self.product.cost, Decimal("150.00"))
        self.assertEqual(self.product.wholesale_price, Decimal("225.50"))

        _, changed_again = confirm_supply_price_review(actor=self.user, supply_id=supply.pk)
        self.stock.refresh_from_db()
        self.assertFalse(changed_again)
        self.assertEqual(self.stock.quantity, 4)

    def test_pending_supply_cancel_does_not_touch_balance(self):
        supply = self._pending_supply()
        result = cancel_supply(actor=self.user, supply_id=supply.pk, comment="Не подтверждаем цены")
        self.stock.refresh_from_db()
        self.product.refresh_from_db()
        supply.refresh_from_db()
        self.assertTrue(result.cancelled)
        self.assertEqual(supply.status, Supply.Status.CANCELLED)
        self.assertEqual(self.stock.quantity, 2)
        self.assertEqual(self.product.cost, Decimal("100.00"))
