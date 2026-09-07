from decimal import Decimal

from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from warehouse.models import Warehouse
from .models import CashRegister, CashTransaction
from .services import collect_cash, deposit_cash


class CashRegisterTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("admin", password="StrongAdmin!123")
        self.warehouse = Warehouse.objects.create(name="Склад")
        self.register = self.warehouse.cash_register

    def test_register_is_created_automatically_with_zero_balance(self):
        self.assertEqual(CashRegister.objects.filter(warehouse=self.warehouse).count(), 1)
        self.assertEqual(self.register.balance, Decimal("0.00"))

    def test_cash_has_a_separate_navigation_button(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("cash:register", args=(self.warehouse.pk,)))
        first_warehouse = Warehouse.objects.order_by("pk").first()
        first_register_url = reverse("cash:register", args=(first_warehouse.pk,))
        if Warehouse.objects.count() == 1:
            expected_cash_link = f'<a class="active" href="{first_register_url}">Касса</a>'
        else:
            expected_cash_link = (
                f'<a class="nav-dropdown-trigger active" href="{first_register_url}" '
                'aria-haspopup="true">Касса</a>'
            )
        self.assertContains(response, expected_cash_link, html=True)
        self.assertNotContains(
            response,
            '<a class="nav-dropdown-trigger active" href="/warehouse/" '
            'aria-haspopup="true">Склад</a>',
            html=True,
        )

    def test_one_register_per_warehouse(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            CashRegister.objects.create(warehouse=self.warehouse)

    def test_deposit_and_collection_create_auditable_transactions(self):
        deposit_cash(actor=self.user, warehouse_id=self.warehouse.pk, amount="1000", comment="Размен")
        collect_cash(actor=self.user, warehouse_id=self.warehouse.pk, amount="250", comment="Инкассация")
        self.register.refresh_from_db()
        self.assertEqual(self.register.balance, Decimal("750.00"))
        self.assertEqual(self.register.transactions.count(), 2)

    def test_collection_cannot_make_balance_negative(self):
        with self.assertRaisesMessage(ValidationError, "Недостаточно наличных"):
            collect_cash(actor=self.user, warehouse_id=self.warehouse.pk, amount="1", comment="Инкассация")
        self.assertEqual(CashTransaction.objects.count(), 0)

    def test_manual_comment_is_required(self):
        with self.assertRaisesMessage(ValidationError, "Комментарий обязателен"):
            deposit_cash(actor=self.user, warehouse_id=self.warehouse.pk, amount="10", comment="")


class CashPermissionTests(TestCase):
    def test_cash_balance_is_separate_permission(self):
        worker = User.objects.create_user("worker", password="StrongWorker!123")
        warehouse = Warehouse.objects.create(name="Склад")
        self.client.force_login(worker)
        url = reverse("cash:register", args=(warehouse.pk,))
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.get(reverse("cash:deposit", args=(warehouse.pk,))).status_code, 403)
        self.assertEqual(self.client.get(reverse("cash:collect", args=(warehouse.pk,))).status_code, 403)
        self.assertEqual(self.client.post(reverse("cash:deposit", args=(warehouse.pk,)), {
            "amount": "10", "comment": "Тест",
        }).status_code, 403)
        self.assertEqual(self.client.post(reverse("cash:collect", args=(warehouse.pk,)), {
            "amount": "10", "comment": "Тест",
        }).status_code, 403)
        worker.user_permissions.add(
            Permission.objects.get(content_type__app_label="cash", codename="view_cash_register")
        )
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_history_permission_does_not_reveal_balance(self):
        worker = User.objects.create_user("auditor", password="StrongWorker!123")
        warehouse = Warehouse.objects.create(name="Склад аудитора")
        register = warehouse.cash_register
        register.balance = Decimal("12345.67")
        register.save(update_fields=("balance",))
        worker.user_permissions.add(
            Permission.objects.get(content_type__app_label="cash", codename="view_cash_history")
        )
        self.client.force_login(worker)
        response = self.client.get(reverse("cash:register", args=(warehouse.pk,)))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "12345.67")
