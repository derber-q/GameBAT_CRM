from decimal import Decimal

from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from cash.models import CashTransaction
from cash.services import collect_cash, deposit_cash
from catalog.models import CD, Platform
from warehouse.models import CDWarehouseStock, Warehouse
from .models import Sale
from .services import cancel_sale, create_sale, mark_sale_paid, update_sale_note


class SaleCashReceivedTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_superuser("admin", password="StrongAdmin!123")
        self.warehouse = Warehouse.objects.create(name="Склад")
        platform = Platform.objects.create(name="PS5")
        self.product = CD.objects.create(
            platform=platform, name="Игра", sku="CD-1", barcode="001",
            avito_price=Decimal("4500.00"),
        )
        self.stock = CDWarehouseStock.objects.create(
            warehouse=self.warehouse, cd=self.product, quantity=10,
        )

    def create(self, payment_method, received=None, note=""):
        return create_sale(
            actor=self.actor, warehouse_id=self.warehouse.pk,
            price_type=Sale.PriceType.RETAIL, sale_type=Sale.SaleType.RETAIL,
            payment_method=payment_method,
            lines=[{"product_type": "cd", "product_id": self.product.pk, "quantity": 1}],
            cash_received_amount=received, note=note,
        )

    def test_blank_cash_received_uses_goods_total(self):
        sale = self.create(Sale.PaymentMethod.CASH)
        self.warehouse.cash_register.refresh_from_db()
        self.assertEqual((sale.total_amount, sale.cash_received_amount, sale.extra_cash_amount), (
            Decimal("4500.00"), Decimal("4500.00"), Decimal("0.00"),
        ))
        self.assertEqual(self.warehouse.cash_register.balance, Decimal("4500.00"))

    def test_cash_overpayment_is_stored_separately_and_fully_credited(self):
        sale = self.create(Sale.PaymentMethod.CASH, "5000")
        self.warehouse.cash_register.refresh_from_db()
        payment = CashTransaction.objects.get(sale=sale, operation_type="sale_payment")
        self.assertEqual((sale.total_amount, sale.cash_received_amount, sale.extra_cash_amount), (
            Decimal("4500.00"), Decimal("5000.00"), Decimal("500.00"),
        ))
        self.assertEqual((self.warehouse.cash_register.balance, payment.amount), (
            Decimal("5000.00"), Decimal("5000.00"),
        ))

    def test_received_below_total_rejects_entire_sale(self):
        with self.assertRaisesMessage(ValidationError, "не может быть меньше"):
            self.create(Sale.PaymentMethod.CASH, "4000")
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 10)
        self.assertFalse(Sale.objects.exists())

    def test_postpay_accepts_received_when_marked_paid(self):
        sale = self.create(Sale.PaymentMethod.CASH_POSTPAY, "9999")
        self.assertIsNone(sale.cash_received_amount)
        mark_sale_paid(actor=self.actor, sale_id=sale.pk, cash_received_amount="5000")
        sale.refresh_from_db()
        self.warehouse.cash_register.refresh_from_db()
        self.assertEqual((sale.total_amount, sale.cash_received_amount, sale.extra_cash_amount), (
            Decimal("4500.00"), Decimal("5000.00"), Decimal("500.00"),
        ))
        self.assertEqual(self.warehouse.cash_register.balance, Decimal("5000.00"))

    def test_postpay_blank_uses_current_total_and_below_total_is_rejected(self):
        sale = self.create(Sale.PaymentMethod.CASH_POSTPAY)
        with self.assertRaisesMessage(ValidationError, "не может быть меньше"):
            mark_sale_paid(actor=self.actor, sale_id=sale.pk, cash_received_amount="4000")
        sale.refresh_from_db()
        self.assertEqual(sale.payment_status, Sale.PaymentStatus.UNPAID)
        mark_sale_paid(actor=self.actor, sale_id=sale.pk)
        sale.refresh_from_db()
        self.assertEqual(sale.cash_received_amount, Decimal("4500.00"))

    def test_bank_ignores_cash_received_and_does_not_touch_register(self):
        sale = self.create(Sale.PaymentMethod.BANK_ACCOUNT, "9000")
        mark_sale_paid(actor=self.actor, sale_id=sale.pk, cash_received_amount="9000")
        sale.refresh_from_db()
        self.warehouse.cash_register.refresh_from_db()
        self.assertIsNone(sale.cash_received_amount)
        self.assertEqual(sale.extra_cash_amount, Decimal("0.00"))
        self.assertEqual(self.warehouse.cash_register.balance, Decimal("0.00"))

    def test_cancel_refunds_actual_received_not_goods_total(self):
        sale = self.create(Sale.PaymentMethod.CASH, "5000")
        cancel_sale(actor=self.actor, sale_id=sale.pk, comment="Возврат")
        sale.refresh_from_db()
        self.warehouse.cash_register.refresh_from_db()
        self.assertEqual(sale.refunded_amount, Decimal("5000.00"))
        self.assertEqual(self.warehouse.cash_register.balance, Decimal("0.00"))

    def test_paid_postpay_cancel_refunds_extra_and_insufficient_cash_blocks_cancel(self):
        sale = self.create(Sale.PaymentMethod.CASH_POSTPAY)
        mark_sale_paid(actor=self.actor, sale_id=sale.pk, cash_received_amount="5000")
        collect_cash(
            actor=self.actor, warehouse_id=self.warehouse.pk, amount="500",
            comment="Часть денег инкассирована",
        )
        with self.assertRaisesMessage(ValidationError, "Недостаточно наличных"):
            cancel_sale(actor=self.actor, sale_id=sale.pk, comment="Возврат")
        sale.refresh_from_db()
        self.stock.refresh_from_db()
        self.assertFalse(sale.is_cancelled)
        self.assertEqual(self.stock.quantity, 9)
        deposit_cash(
            actor=self.actor, warehouse_id=self.warehouse.pk, amount="500",
            comment="Средства возвращены в кассу",
        )
        cancel_sale(actor=self.actor, sale_id=sale.pk, comment="Возврат")
        sale.refresh_from_db()
        self.warehouse.cash_register.refresh_from_db()
        self.assertEqual(sale.refunded_amount, Decimal("5000.00"))
        self.assertEqual(self.warehouse.cash_register.balance, Decimal("0.00"))


class SaleNoteAndUiTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_superuser("admin", password="StrongAdmin!123")
        self.warehouse = Warehouse.objects.create(name="Склад")
        platform = Platform.objects.create(name="PS5")
        self.product = CD.objects.create(
            platform=platform, name="Игра", sku="CD-1", barcode="001", avito_price=1000,
        )
        CDWarehouseStock.objects.create(warehouse=self.warehouse, cd=self.product, quantity=5)

    def sale(self, note=""):
        return create_sale(
            actor=self.actor, warehouse_id=self.warehouse.pk,
            price_type="retail", sale_type="retail", payment_method="cash_postpay",
            lines=[{"product_type": "cd", "product_id": self.product.pk, "quantity": 1}],
            note=note,
        )

    def test_note_create_empty_and_service_edit_do_not_change_sale_logic(self):
        sale = self.sale("Клиент Иван, заберёт вечером")
        before = (sale.total_amount, sale.order_status, sale.payment_status)
        update_sale_note(actor=self.actor, sale_id=sale.pk, note="Новое примечание")
        sale.refresh_from_db()
        self.assertEqual(sale.note, "Новое примечание")
        self.assertEqual((sale.total_amount, sale.order_status, sale.payment_status), before)
        empty = self.sale("")
        self.assertEqual(empty.note, "")

    def test_note_endpoint_uses_existing_change_sale_permission(self):
        sale = self.sale()
        worker = User.objects.create_user("worker", password="StrongWorker!123")
        worker.user_permissions.add(
            Permission.objects.get(content_type__app_label="sales", codename="view_sale_detail"),
        )
        self.client.force_login(worker)
        url = reverse("sales:note_update", args=(sale.pk,))
        self.assertEqual(self.client.post(url, {"note": "Нет доступа"}).status_code, 403)
        worker.user_permissions.add(
            Permission.objects.get(content_type__app_label="sales", codename="change_sale"),
        )
        self.client.force_login(worker)
        self.assertRedirects(self.client.post(url, {"note": "Разрешено"}), reverse("sales:detail", args=(sale.pk,)))
        sale.refresh_from_db()
        self.assertEqual(sale.note, "Разрешено")

    def test_create_page_contains_dynamic_total_received_and_note(self):
        self.client.force_login(self.actor)
        response = self.client.get(reverse("sales:create"))
        self.assertContains(response, "Стоимость товаров")
        self.assertContains(response, "Получено от покупателя")
        self.assertContains(response, "Примечание")
        self.assertContains(response, "data-sale-intermediate-total")
        self.assertContains(response, "sale-local-inventory-1")

    def test_sale_list_shows_note_next_to_id(self):
        sale = self.sale("Отличительный текст")
        self.client.force_login(self.actor)
        response = self.client.get(reverse("sales:list"))
        self.assertContains(response, "Примечание")
        self.assertContains(response, sale.note)
