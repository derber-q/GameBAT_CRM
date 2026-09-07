from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from cash.models import CashRegister, CashTransaction
from catalog.models import Brand, CD, Platform, ProductChangeEvent, ProductType, Tech
from partners.models import SalesPlatform
from sales.models import Sale
from warehouse.models import CDWarehouseStock, TechWarehouseStock, Warehouse
from .models import CDConsignmentStock, ConsignmentMovement, TechConsignmentStock
from .services import (
    record_consignment_sale,
    return_from_consignment,
    transfer_many_to_consignment,
    transfer_to_consignment,
)


class ConsignmentServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("admin", password="StrongAdmin!123")
        platform = Platform.objects.create(name="PS5")
        self.product = CD.objects.create(
            platform=platform, name="Игра", sku="CD-1", barcode="001", cost=2400
        )
        brand = Brand.objects.create(name="Sony")
        product_type = ProductType.objects.create(name="Геймпад")
        self.tech = Tech.objects.create(
            brand=brand, product_type=product_type, name="Геймпад", sku="TECH-1", cost=3000
        )
        self.warehouse = Warehouse.objects.create(name="Склад")
        self.warehouse_stock = CDWarehouseStock.objects.create(
            warehouse=self.warehouse, cd=self.product, quantity=10
        )
        self.tech_warehouse_stock = TechWarehouseStock.objects.create(
            warehouse=self.warehouse, tech=self.tech, quantity=5
        )
        self.sales_platform = SalesPlatform.objects.create(
            name="Магазин", address="Адрес", legal_entity="ООО Магазин", phone_1="+70000000000"
        )

    def transfer(self, quantity=3, amount="2500"):
        return transfer_to_consignment(
            actor=self.user, warehouse_id=self.warehouse.pk, platform_id=self.sales_platform.pk,
            product_type="cd", product_id=self.product.pk, quantity=quantity,
            receivable_per_unit=amount,
        )

    def test_transfer_updates_balances_and_creates_document_item(self):
        other = Warehouse.objects.create(name="Другой склад")
        other_stock = CDWarehouseStock.objects.create(warehouse=other, cd=self.product, quantity=6)

        stock = self.transfer()

        self.warehouse_stock.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(self.warehouse_stock.quantity, 7)
        self.assertEqual(self.product.quantity_on_consignment, 3)
        self.assertEqual(stock.quantity, 3)
        self.assertEqual(stock.warehouse, self.warehouse)
        self.assertEqual(stock.receivable_per_unit, Decimal("2500.00"))
        other_stock.refresh_from_db()
        self.assertEqual(other_stock.quantity, 6)

        movement = ConsignmentMovement.objects.get()
        item = movement.items.get()
        event = self.product.change_events.get()
        self.assertEqual(item.product, self.product)
        self.assertEqual(item.warehouse_quantity_before, 10)
        self.assertEqual(item.warehouse_quantity_after, 7)
        self.assertEqual(event.action_kind, ProductChangeEvent.ActionKind.CONSIGNMENT)
        self.assertEqual(event.action_label, movement.action_label)
        self.assertEqual(event.action_url, reverse("consignment:movement_detail", args=(movement.pk,)))
        self.assertEqual(event.field_changes.count(), 2)

        self.client.force_login(self.user)
        response = self.client.get(event.action_url)
        self.assertContains(response, movement.action_label)
        self.assertContains(response, "admin (CRM)")
        self.assertContains(response, "GameBAT получает / ед.")

    def test_multiple_products_are_transferred_in_one_atomic_document(self):
        movement = transfer_many_to_consignment(
            actor=self.user,
            warehouse_id=self.warehouse.pk,
            platform_id=self.sales_platform.pk,
            lines=[
                {"product_type": "cd", "product_id": self.product.pk, "quantity": 2,
                 "receivable_per_unit": "2500"},
                {"product_type": "tech", "product_id": self.tech.pk, "quantity": 3,
                 "receivable_per_unit": "3500"},
            ],
        )

        self.assertEqual(movement.items.count(), 2)
        self.assertEqual(movement.position_count, 2)
        self.assertEqual(movement.total_units, 5)
        self.assertEqual(CDConsignmentStock.objects.get().quantity, 2)
        self.assertEqual(TechConsignmentStock.objects.get().quantity, 3)

    def test_multiple_transfer_rolls_back_all_lines_when_one_is_invalid(self):
        with self.assertRaisesMessage(ValidationError, "недостаточно товара"):
            transfer_many_to_consignment(
                actor=self.user,
                warehouse_id=self.warehouse.pk,
                platform_id=self.sales_platform.pk,
                lines=[
                    {"product_type": "cd", "product_id": self.product.pk, "quantity": 2,
                     "receivable_per_unit": "2500"},
                    {"product_type": "tech", "product_id": self.tech.pk, "quantity": 6,
                     "receivable_per_unit": "3500"},
                ],
            )
        self.warehouse_stock.refresh_from_db()
        self.assertEqual(self.warehouse_stock.quantity, 10)
        self.assertEqual(ConsignmentMovement.objects.count(), 0)
        self.assertEqual(CDConsignmentStock.objects.count(), 0)

    def test_cannot_transfer_more_than_warehouse_balance(self):
        with self.assertRaisesMessage(ValidationError, "недостаточно товара"):
            self.transfer(quantity=11)
        self.warehouse_stock.refresh_from_db()
        self.assertEqual(self.warehouse_stock.quantity, 10)
        self.assertEqual(CDConsignmentStock.objects.count(), 0)

    def test_return_is_reverse_operation(self):
        self.transfer(quantity=4)
        stock = return_from_consignment(
            actor=self.user, warehouse_id=self.warehouse.pk, platform_id=self.sales_platform.pk,
            product_type="cd", product_id=self.product.pk, quantity=2,
        )
        self.warehouse_stock.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(stock.quantity, 2)
        self.assertEqual(self.warehouse_stock.quantity, 8)
        self.assertEqual(self.product.quantity_on_consignment, 2)
        movements = ConsignmentMovement.objects.order_by("id")
        self.assertEqual(movements.count(), 2)
        self.assertEqual(movements[1].operation_type, ConsignmentMovement.OperationType.RETURN)
        item = movements[1].items.get()
        self.assertEqual(item.warehouse_quantity_before, 6)
        self.assertEqual(item.warehouse_quantity_after, 8)

    def test_cannot_return_more_than_platform_balance(self):
        self.transfer(quantity=2)
        with self.assertRaisesMessage(ValidationError, "только 2 единиц"):
            return_from_consignment(
                actor=self.user, warehouse_id=self.warehouse.pk, platform_id=self.sales_platform.pk,
                product_type="cd", product_id=self.product.pk, quantity=3,
            )

    def test_different_receivable_does_not_overwrite_existing_stock(self):
        self.transfer(quantity=2, amount="2500")
        with self.assertRaisesMessage(ValidationError, "другая сумма к получению"):
            self.transfer(quantity=1, amount="2600")
        stock = CDConsignmentStock.objects.get()
        self.assertEqual(stock.quantity, 2)
        self.assertEqual(stock.receivable_per_unit, Decimal("2500.00"))

    def test_nonpositive_operations_are_rejected(self):
        with self.assertRaises(ValidationError):
            self.transfer(quantity=0)
        with self.assertRaises(ValidationError):
            self.transfer(amount="0")

    def test_cash_consignment_sale_creates_completed_sale_and_credits_register(self):
        stock = self.transfer(quantity=4)

        sale = record_consignment_sale(
            actor=self.user, product_type="cd", stock_id=stock.pk,
            quantity=2, payment_method=Sale.PaymentMethod.CASH,
        )

        stock.refresh_from_db()
        self.product.refresh_from_db()
        self.warehouse_stock.refresh_from_db()
        register = CashRegister.objects.get(warehouse=self.warehouse)
        self.assertEqual(stock.quantity, 2)
        self.assertEqual(self.product.quantity_on_consignment, 2)
        self.assertEqual(self.warehouse_stock.quantity, 6)
        self.assertEqual(sale.total_amount, Decimal("5000.00"))
        self.assertEqual(sale.sale_type, Sale.SaleType.CONSIGNMENT)
        self.assertEqual(sale.price_type, Sale.PriceType.CONSIGNMENT)
        self.assertEqual(sale.consignment_platform, self.sales_platform)
        self.assertTrue(sale.is_completed)
        self.assertEqual(sale.cd_items.get().quantity, 2)
        self.assertEqual(sale.cd_items.get().unit_price, Decimal("2500.00"))
        self.assertEqual(register.balance, Decimal("5000.00"))
        self.assertEqual(CashTransaction.objects.get(sale=sale).amount, Decimal("5000.00"))
        event = self.product.change_events.order_by("-pk").first()
        self.assertEqual(event.action_kind, ProductChangeEvent.ActionKind.SALE)
        self.assertEqual(event.action_url, reverse("sales:detail", args=(sale.pk,)))

    def test_bank_consignment_sale_does_not_credit_cash_register(self):
        stock = self.transfer(quantity=2)
        register = CashRegister.objects.get(warehouse=self.warehouse)

        sale = record_consignment_sale(
            actor=self.user, product_type="cd", stock_id=stock.pk,
            quantity=1, payment_method=Sale.PaymentMethod.BANK_ACCOUNT,
        )

        register.refresh_from_db()
        self.assertTrue(sale.is_completed)
        self.assertEqual(register.balance, Decimal("0.00"))
        self.assertFalse(CashTransaction.objects.filter(sale=sale).exists())

    def test_sale_page_and_post_are_available_from_consignment_table(self):
        stock = self.transfer(quantity=3)
        self.client.force_login(self.user)
        list_response = self.client.get(reverse("consignment:list"))
        sale_url = reverse("consignment:sale", args=("cd", stock.pk))
        self.assertContains(list_response, sale_url)
        self.assertContains(list_response, "Товар реализован")

        get_response = self.client.get(sale_url)
        self.assertContains(get_response, "Форма оплаты")
        response = self.client.post(sale_url, {
            "payment_method": Sale.PaymentMethod.CASH,
            "quantity": 1,
        })
        sale = Sale.objects.get(sale_type=Sale.SaleType.CONSIGNMENT)
        self.assertRedirects(response, reverse("sales:detail", args=(sale.pk,)))

    def test_transfer_accepts_product_with_blank_barcode(self):
        self.product.barcode = ""
        self.product.save(update_fields=("barcode",))

        stock = self.transfer(quantity=1)

        self.assertEqual(stock.quantity, 1)
        self.warehouse_stock.refresh_from_db()
        self.assertEqual(self.warehouse_stock.quantity, 9)
