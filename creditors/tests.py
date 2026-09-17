from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from cash.models import CashTransaction
from warehouse.models import Warehouse
from .models import Creditor, CreditorTransaction
from .services import adjust_creditor_debt


class CreditorServiceTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_superuser("admin", password="StrongAdmin!123")
        self.warehouse = Warehouse.objects.create(name="Склад")
        self.creditor = Creditor.objects.create(name="Test")
        self.register = self.warehouse.cash_register
        self.safe = self.warehouse.safe
        self.register.balance = Decimal("2000.00")
        self.register.save(update_fields=("balance",))
        self.safe.balance = Decimal("2000.00")
        self.safe.save(update_fields=("balance",))

    def adjust(self, new_debt, source):
        return adjust_creditor_debt(
            actor=self.actor, creditor_id=self.creditor.pk, warehouse_id=self.warehouse.pk,
            money_source_type=source, new_debt=new_debt, comment="Тест",
        )

    def test_creditor_starts_with_zero_debt(self):
        self.assertEqual(self.creditor.current_debt, Decimal("0.00"))

    def test_debt_increase_and_decrease_through_cash(self):
        increased = self.adjust("1500", CreditorTransaction.MoneySourceType.CASH)
        self.creditor.refresh_from_db()
        self.register.refresh_from_db()
        self.assertEqual((self.creditor.current_debt, self.register.balance), (
            Decimal("1500.00"), Decimal("500.00"),
        ))
        self.assertEqual(increased.delta, Decimal("1500.00"))
        repaid = self.adjust("1000", CreditorTransaction.MoneySourceType.CASH)
        self.register.refresh_from_db()
        self.assertEqual(self.register.balance, Decimal("1000.00"))
        self.assertEqual(repaid.delta, Decimal("-500.00"))
        self.assertEqual(repaid.cash_transaction.operation_type, CashTransaction.OperationType.CREDITOR_REPAYMENT)

    def test_debt_increase_and_decrease_through_safe(self):
        self.adjust("1500", CreditorTransaction.MoneySourceType.SAFE)
        self.safe.refresh_from_db()
        self.register.refresh_from_db()
        self.assertEqual((self.safe.balance, self.register.balance), (Decimal("500.00"), Decimal("2000.00")))
        operation = self.adjust("1000", CreditorTransaction.MoneySourceType.SAFE)
        self.safe.refresh_from_db()
        self.assertEqual(self.safe.balance, Decimal("1000.00"))
        self.assertEqual(operation.cash_transaction.safe, self.safe)

    def test_insufficient_cash_and_safe_leave_everything_unchanged(self):
        self.register.balance = Decimal("500.00")
        self.register.save(update_fields=("balance",))
        self.safe.balance = Decimal("500.00")
        self.safe.save(update_fields=("balance",))
        for source, message in (
            (CreditorTransaction.MoneySourceType.CASH, "выбранной кассе"),
            (CreditorTransaction.MoneySourceType.SAFE, "выбранном сейфе"),
        ):
            with self.subTest(source=source), self.assertRaisesMessage(ValidationError, message):
                self.adjust("1000", source)
        self.creditor.refresh_from_db()
        self.register.refresh_from_db()
        self.safe.refresh_from_db()
        self.assertEqual((self.creditor.current_debt, self.register.balance, self.safe.balance), (
            Decimal("0.00"), Decimal("500.00"), Decimal("500.00"),
        ))
        self.assertFalse(CreditorTransaction.objects.exists())

    def test_journal_failure_rolls_back_balance_and_debt(self):
        with patch("creditors.services.CreditorTransaction.objects.create", side_effect=RuntimeError("audit failed")):
            with self.assertRaisesMessage(RuntimeError, "audit failed"):
                self.adjust("1000", CreditorTransaction.MoneySourceType.CASH)
        self.creditor.refresh_from_db()
        self.register.refresh_from_db()
        self.assertEqual((self.creditor.current_debt, self.register.balance), (
            Decimal("0.00"), Decimal("2000.00"),
        ))
        self.assertFalse(CashTransaction.objects.exists())

    def test_creditor_operation_appears_in_common_money_journal(self):
        operation = self.adjust("500", CreditorTransaction.MoneySourceType.CASH)
        self.client.force_login(self.actor)
        response = self.client.get(reverse("cash:register", args=(self.warehouse.pk,)))
        self.assertContains(response, "Кредитор: увеличение задолженности")
        self.assertContains(response, self.creditor.name)
        self.assertEqual(operation.cash_transaction.signed_amount, Decimal("-500.00"))


class CreditorPermissionAndUiTests(TestCase):
    def setUp(self):
        self.worker = User.objects.create_user("worker", password="StrongWorker!123")
        self.warehouse = Warehouse.objects.create(name="Склад")
        self.creditor = Creditor.objects.create(name="Кредитор")
        self.client.force_login(self.worker)

    def permission(self, codename):
        return Permission.objects.get(content_type__app_label="creditors", codename=codename)

    def test_endpoints_use_independent_permissions(self):
        self.assertEqual(self.client.get(reverse("creditors:list")).status_code, 403)
        self.assertEqual(self.client.get(reverse("creditors:create")).status_code, 403)
        self.assertEqual(self.client.get(reverse("creditors:debt", args=(self.creditor.pk,))).status_code, 403)
        self.worker.user_permissions.add(self.permission("view_creditors"))
        self.assertEqual(self.client.get(reverse("creditors:list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("creditors:detail", args=(self.creditor.pk,))).status_code, 200)
        self.assertNotContains(self.client.get(reverse("creditors:detail", args=(self.creditor.pk,))), "История операций")

    def test_create_form_accepts_only_name_and_sets_zero(self):
        self.worker.user_permissions.add(
            self.permission("add_creditor"), self.permission("view_creditors"),
        )
        response = self.client.post(reverse("creditors:create"), {
            "name": "Новый", "current_debt": "999", "description": "Скрыто",
        })
        creditor = Creditor.objects.get(name="Новый")
        self.assertRedirects(response, reverse("creditors:detail", args=(creditor.pk,)))
        self.assertEqual(creditor.current_debt, Decimal("0.00"))
        self.assertEqual(creditor.description, "")

    def test_history_permission_reveals_immutable_operations(self):
        admin = User.objects.create_superuser("admin", password="StrongAdmin!123")
        register = self.warehouse.cash_register
        register.balance = Decimal("1000.00")
        register.save(update_fields=("balance",))
        adjust_creditor_debt(
            actor=admin, creditor_id=self.creditor.pk, warehouse_id=self.warehouse.pk,
            money_source_type="cash", new_debt="100", comment="Выдача",
        )
        self.worker.user_permissions.add(self.permission("view_creditors"), self.permission("view_history"))
        response = self.client.get(reverse("creditors:detail", args=(self.creditor.pk,)))
        self.assertContains(response, "История операций")
        self.assertContains(response, "Выдача")
