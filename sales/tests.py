from decimal import Decimal

from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from cash.models import CashRegister, CashTransaction
from catalog.models import CD, Platform, ProductChangeEvent
from warehouse.models import CDWarehouseStock, Warehouse
from .models import Sale
from .services import advance_order_status, create_sale, edit_postpay_sale_items, mark_sale_paid


class SaleServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("admin", password="StrongAdmin!123")
        self.warehouse = Warehouse.objects.create(name="Москва")
        self.other_warehouse = Warehouse.objects.create(name="СПб")
        platform = Platform.objects.create(name="PS5")
        self.cd = CD.objects.create(
            platform=platform, name="Игра", sku="CD-1", barcode="1", cost=100,
            retail_price=150, wholesale_price=130, yandex_market_price=170,
        )
        self.other_cd = CD.objects.create(
            platform=platform, name="Новая игра", sku="CD-2", barcode="2", cost=200,
            retail_price=300, wholesale_price=260, yandex_market_price=330,
        )
        self.stock = CDWarehouseStock.objects.create(warehouse=self.warehouse, cd=self.cd, quantity=10)
        self.other_stock = CDWarehouseStock.objects.create(
            warehouse=self.other_warehouse, cd=self.cd, quantity=20
        )
        self.new_stock = CDWarehouseStock.objects.create(
            warehouse=self.warehouse, cd=self.other_cd, quantity=5
        )

    def line(self, product=None, quantity=2):
        return {"product_type": "cd", "product_id": (product or self.cd).pk, "quantity": quantity}

    def create(self, payment_method, lines=None):
        return create_sale(
            actor=self.user, warehouse_id=self.warehouse.pk, price_type=Sale.PriceType.RETAIL,
            sale_type=Sale.SaleType.RETAIL, payment_method=payment_method, lines=lines or [self.line()],
        )

    def test_cash_sale_is_atomic_and_completed(self):
        register = self.warehouse.cash_register
        sale = self.create(Sale.PaymentMethod.CASH)
        self.stock.refresh_from_db()
        self.other_stock.refresh_from_db()
        register.refresh_from_db()
        self.assertEqual(self.stock.quantity, 8)
        self.assertEqual(self.other_stock.quantity, 20)
        self.assertEqual(register.balance, Decimal("300.00"))
        self.assertEqual(CashTransaction.objects.filter(sale=sale).count(), 1)
        self.assertTrue(sale.visible_id.startswith("SALE-"))
        self.assertTrue(sale.is_completed)
        self.assertIsNotNone(sale.completed_at)

    def test_sale_stock_change_is_linked_in_product_history(self):
        sale = self.create(Sale.PaymentMethod.BANK_ACCOUNT)
        event = self.cd.change_events.get()
        self.assertEqual(event.actor, self.user)
        self.assertEqual(event.executor_display, "admin (CRM)")
        self.assertEqual(event.action_kind, ProductChangeEvent.ActionKind.SALE)
        self.assertEqual(event.action_label, f"Продажа {sale.visible_id}")
        self.assertEqual(event.action_url, reverse("sales:detail", args=(sale.pk,)))
        change = event.field_changes.get()
        self.assertEqual((change.old_value, change.new_value), ("10", "8"))

    def test_cash_sale_without_register_rolls_back_stock(self):
        CashRegister.objects.filter(warehouse=self.warehouse).delete()
        with self.assertRaisesMessage(ValidationError, "не создана касса"):
            self.create(Sale.PaymentMethod.CASH)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 10)
        self.assertEqual(Sale.objects.count(), 0)

    def test_sale_checks_selected_warehouse_not_global_stock(self):
        with self.assertRaisesMessage(ValidationError, "недостаточно товара"):
            self.create(Sale.PaymentMethod.BANK_ACCOUNT, [self.line(quantity=11)])
        self.stock.refresh_from_db()
        self.other_stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 10)
        self.assertEqual(self.other_stock.quantity, 20)

    def test_cash_postpay_charges_only_when_marked_paid_and_only_once(self):
        register = self.warehouse.cash_register
        sale = self.create(Sale.PaymentMethod.CASH_POSTPAY)
        register.refresh_from_db()
        self.assertEqual(register.balance, 0)
        self.assertEqual(sale.payment_status, Sale.PaymentStatus.UNPAID)
        mark_sale_paid(actor=self.user, sale_id=sale.pk)
        register.refresh_from_db()
        self.assertEqual(register.balance, Decimal("300.00"))
        self.assertEqual(CashTransaction.objects.filter(sale=sale).count(), 1)
        with self.assertRaisesMessage(ValidationError, "уже оплачен"):
            mark_sale_paid(actor=self.user, sale_id=sale.pk)
        self.assertEqual(CashTransaction.objects.filter(sale=sale).count(), 1)

    def test_bank_payment_never_changes_cash_register(self):
        register = self.warehouse.cash_register
        sale = self.create(Sale.PaymentMethod.BANK_ACCOUNT)
        mark_sale_paid(actor=self.user, sale_id=sale.pk)
        register.refresh_from_db()
        self.assertEqual(register.balance, 0)
        self.assertFalse(CashTransaction.objects.filter(sale=sale).exists())

    def test_order_status_is_strict_and_completion_requires_delivery_and_payment(self):
        sale = self.create(Sale.PaymentMethod.BANK_ACCOUNT)
        with self.assertRaises(ValidationError):
            advance_order_status(actor=self.user, sale_id=sale.pk, next_status=Sale.OrderStatus.SHIPPED)
        advance_order_status(actor=self.user, sale_id=sale.pk, next_status=Sale.OrderStatus.ASSEMBLED)
        advance_order_status(actor=self.user, sale_id=sale.pk, next_status=Sale.OrderStatus.SHIPPED)
        mark_sale_paid(actor=self.user, sale_id=sale.pk)
        sale.refresh_from_db()
        self.assertIsNone(sale.completed_at)
        advance_order_status(actor=self.user, sale_id=sale.pk, next_status=Sale.OrderStatus.DELIVERED)
        sale.refresh_from_db()
        self.assertIsNotNone(sale.completed_at)

    def test_shipped_unpaid_postpay_is_editable_with_stock_deltas_and_snapshots(self):
        sale = self.create(Sale.PaymentMethod.CASH_POSTPAY)
        item = sale.cd_items.get()
        self.cd.retail_price = 999
        self.cd.save(update_fields=("retail_price",))
        advance_order_status(actor=self.user, sale_id=sale.pk, next_status=Sale.OrderStatus.ASSEMBLED)
        advance_order_status(actor=self.user, sale_id=sale.pk, next_status=Sale.OrderStatus.SHIPPED)
        edit_postpay_sale_items(actor=self.user, sale_id=sale.pk, lines=[
            self.line(quantity=3), self.line(product=self.other_cd, quantity=1),
        ])
        self.stock.refresh_from_db()
        self.new_stock.refresh_from_db()
        item.refresh_from_db()
        sale.refresh_from_db()
        self.assertEqual(self.stock.quantity, 7)
        self.assertEqual(self.new_stock.quantity, 4)
        self.assertEqual(item.unit_price, Decimal("150.00"))
        self.assertEqual(item.quantity, 3)
        self.assertEqual(sale.cd_items.get(cd=self.other_cd).unit_price, Decimal("300.00"))
        self.assertEqual(sale.total_amount, Decimal("750.00"))

    def test_postpay_edit_can_remove_an_item_and_return_it_to_stock(self):
        sale = self.create(Sale.PaymentMethod.CASH_POSTPAY)
        edit_postpay_sale_items(actor=self.user, sale_id=sale.pk, lines=[
            self.line(product=self.other_cd, quantity=1),
        ])
        self.stock.refresh_from_db()
        self.new_stock.refresh_from_db()
        sale.refresh_from_db()
        self.assertEqual(self.stock.quantity, 10)
        self.assertEqual(self.new_stock.quantity, 4)
        self.assertFalse(sale.cd_items.filter(cd=self.cd).exists())
        self.assertEqual(sale.total_amount, Decimal("300.00"))

    def test_failed_postpay_edit_rolls_back_every_stock_delta(self):
        sale = self.create(Sale.PaymentMethod.CASH_POSTPAY)
        with self.assertRaisesMessage(ValidationError, "недостаточно товара"):
            edit_postpay_sale_items(actor=self.user, sale_id=sale.pk, lines=[
                self.line(quantity=1), self.line(product=self.other_cd, quantity=6),
            ])
        self.stock.refresh_from_db()
        self.new_stock.refresh_from_db()
        sale.refresh_from_db()
        self.assertEqual(self.stock.quantity, 8)
        self.assertEqual(self.new_stock.quantity, 5)
        self.assertEqual(sale.cd_items.get(cd=self.cd).quantity, 2)
        self.assertFalse(sale.cd_items.filter(cd=self.other_cd).exists())
        self.assertEqual(sale.total_amount, Decimal("300.00"))

    def test_postpay_cash_credits_the_edited_total(self):
        register = self.warehouse.cash_register
        sale = self.create(Sale.PaymentMethod.CASH_POSTPAY)
        edit_postpay_sale_items(actor=self.user, sale_id=sale.pk, lines=[self.line(quantity=3)])
        mark_sale_paid(actor=self.user, sale_id=sale.pk)
        register.refresh_from_db()
        self.assertEqual(register.balance, Decimal("450.00"))
        self.assertEqual(CashTransaction.objects.get(sale=sale).amount, Decimal("450.00"))

    def test_visible_id_cannot_be_changed_after_creation(self):
        sale = self.create(Sale.PaymentMethod.BANK_ACCOUNT)
        sale.visible_id = "SALE-999999"
        with self.assertRaisesMessage(ValidationError, "Номер созданной продажи изменять нельзя"):
            sale.save(update_fields=("visible_id",))

    def test_paid_or_delivered_postpay_cannot_be_edited(self):
        paid_sale = self.create(Sale.PaymentMethod.CASH_POSTPAY)
        mark_sale_paid(actor=self.user, sale_id=paid_sale.pk)
        with self.assertRaisesMessage(ValidationError, "оплаченного"):
            edit_postpay_sale_items(actor=self.user, sale_id=paid_sale.pk, lines=[self.line(quantity=1)])
        delivered_sale = self.create(Sale.PaymentMethod.CASH_POSTPAY, [self.line(quantity=1)])
        for status in (Sale.OrderStatus.ASSEMBLED, Sale.OrderStatus.SHIPPED, Sale.OrderStatus.DELIVERED):
            advance_order_status(actor=self.user, sale_id=delivered_sale.pk, next_status=status)
        with self.assertRaisesMessage(ValidationError, "доставленного"):
            edit_postpay_sale_items(actor=self.user, sale_id=delivered_sale.pk, lines=[self.line(quantity=1)])


class SalesPermissionTests(TestCase):
    def test_list_create_and_payment_permissions_are_independent(self):
        worker = User.objects.create_user("worker", password="StrongWorker!123")
        self.client.force_login(worker)
        self.assertEqual(self.client.get(reverse("sales:list")).status_code, 403)
        worker.user_permissions.add(
            Permission.objects.get(content_type__app_label="sales", codename="view_sales")
        )
        self.assertEqual(self.client.get(reverse("sales:list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("sales:create")).status_code, 403)
        self.assertEqual(self.client.post(reverse("sales:create")).status_code, 403)
        self.assertEqual(self.client.get(reverse("sales:edit", args=(999,))).status_code, 403)
        self.assertEqual(self.client.post(reverse("sales:edit", args=(999,))).status_code, 403)
        self.assertEqual(self.client.post(reverse("sales:advance", args=(999,))).status_code, 403)
        self.assertEqual(self.client.post(reverse("sales:mark_paid", args=(999,))).status_code, 403)
