import importlib
import uuid
from decimal import Decimal
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from sales.models import Sale
from warehouse.models import Warehouse
from . import services as cash_services
from .models import CashRegister, CashTransaction, Safe
from .services import (
    collect_cash,
    collect_safe,
    credit_sale_payment,
    deposit_cash,
    deposit_safe,
    transfer_cash_to_safe,
    transfer_safe_to_cash,
)


class CashRegisterTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("admin", password="StrongAdmin!123")
        self.warehouse = Warehouse.objects.create(name="Склад")
        self.register = self.warehouse.cash_register
        self.safe = self.warehouse.safe

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

    def test_one_safe_per_warehouse_and_different_warehouses_have_different_safes(self):
        self.assertEqual(Safe.objects.filter(warehouse=self.warehouse).count(), 1)
        self.assertEqual(self.safe.balance, Decimal("0.00"))
        with self.assertRaises(IntegrityError), transaction.atomic():
            Safe.objects.create(warehouse=self.warehouse)
        other = Warehouse.objects.create(name="Другой склад")
        self.assertNotEqual(self.safe.pk, other.safe.pk)

    def test_safe_data_migration_backfills_missing_safe(self):
        self.safe.delete()
        migration = importlib.import_module("cash.migrations.0004_ensure_warehouse_safes")
        migration.ensure_warehouse_safes(apps, None)
        restored = Safe.objects.get(warehouse=self.warehouse)
        self.assertEqual(restored.balance, Decimal("0.00"))

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

    def test_safe_deposit_and_collection_are_audited(self):
        deposited = deposit_safe(
            actor=self.user, warehouse_id=self.warehouse.pk, amount="100", comment="Резерв"
        )
        collected = collect_safe(
            actor=self.user, warehouse_id=self.warehouse.pk, amount="25", comment="Инкассация"
        )
        self.safe.refresh_from_db()
        self.assertEqual(self.safe.balance, Decimal("75.00"))
        self.assertEqual(deposited.operation_type, CashTransaction.OperationType.SAFE_DEPOSIT)
        self.assertEqual(collected.operation_type, CashTransaction.OperationType.SAFE_COLLECTION)
        self.assertEqual(deposited.safe, self.safe)

    def test_safe_rejects_nonpositive_amount_and_excessive_collection(self):
        for amount in ("0", "-1"):
            with self.subTest(amount=amount), self.assertRaisesMessage(ValidationError, "больше нуля"):
                deposit_safe(
                    actor=self.user, warehouse_id=self.warehouse.pk, amount=amount, comment="Тест"
                )
        with self.assertRaisesMessage(ValidationError, "Недостаточно наличных в сейфе"):
            collect_safe(
                actor=self.user, warehouse_id=self.warehouse.pk, amount="1", comment="Тест"
            )
        self.assertEqual(CashTransaction.objects.count(), 0)

    def test_database_rejects_negative_safe_balance(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Safe.objects.filter(pk=self.safe.pk).update(balance=Decimal("-0.01"))

    def test_cash_to_safe_preserves_total_balance(self):
        self.register.balance = Decimal("100.00")
        self.register.save(update_fields=("balance",))
        self.safe.balance = Decimal("50.00")
        self.safe.save(update_fields=("balance",))
        operation = transfer_cash_to_safe(
            actor=self.user, warehouse_id=self.warehouse.pk, amount="30", comment="В сейф"
        )
        self.register.refresh_from_db()
        self.safe.refresh_from_db()
        self.assertEqual(self.register.balance, Decimal("70.00"))
        self.assertEqual(self.safe.balance, Decimal("80.00"))
        self.assertEqual(self.register.balance + self.safe.balance, Decimal("150.00"))
        self.assertEqual(operation.operation_type, CashTransaction.OperationType.CASH_TO_SAFE)

    def test_safe_to_cash_preserves_total_balance(self):
        self.register.balance = Decimal("70.00")
        self.register.save(update_fields=("balance",))
        self.safe.balance = Decimal("80.00")
        self.safe.save(update_fields=("balance",))
        transfer_safe_to_cash(
            actor=self.user, warehouse_id=self.warehouse.pk, amount="20", comment="В кассу"
        )
        self.register.refresh_from_db()
        self.safe.refresh_from_db()
        self.assertEqual(self.register.balance, Decimal("90.00"))
        self.assertEqual(self.safe.balance, Decimal("60.00"))
        self.assertEqual(self.register.balance + self.safe.balance, Decimal("150.00"))

    def test_transfers_reject_insufficient_source_balance_without_changes(self):
        self.register.balance = Decimal("10.00")
        self.register.save(update_fields=("balance",))
        self.safe.balance = Decimal("20.00")
        self.safe.save(update_fields=("balance",))
        with self.assertRaisesMessage(ValidationError, "Недостаточно наличных в кассе"):
            transfer_cash_to_safe(
                actor=self.user, warehouse_id=self.warehouse.pk, amount="11", comment="Тест"
            )
        with self.assertRaisesMessage(ValidationError, "Недостаточно наличных в сейфе"):
            transfer_safe_to_cash(
                actor=self.user, warehouse_id=self.warehouse.pk, amount="21", comment="Тест"
            )
        self.register.refresh_from_db()
        self.safe.refresh_from_db()
        self.assertEqual((self.register.balance, self.safe.balance), (Decimal("10.00"), Decimal("20.00")))
        self.assertEqual(CashTransaction.objects.count(), 0)

    def test_transfer_rolls_back_both_balances_if_journal_write_fails(self):
        self.register.balance = Decimal("100.00")
        self.register.save(update_fields=("balance",))
        self.safe.balance = Decimal("50.00")
        self.safe.save(update_fields=("balance",))
        with patch("cash.services.CashTransaction.objects.create", side_effect=RuntimeError("journal failed")):
            with self.assertRaisesMessage(RuntimeError, "journal failed"):
                transfer_cash_to_safe(
                    actor=self.user, warehouse_id=self.warehouse.pk, amount="30", comment="Тест"
                )
        self.register.refresh_from_db()
        self.safe.refresh_from_db()
        self.assertEqual((self.register.balance, self.safe.balance), (Decimal("100.00"), Decimal("50.00")))

    def test_transfer_uses_locking_helpers_for_both_balances(self):
        self.register.balance = Decimal("100.00")
        self.register.save(update_fields=("balance",))
        with (
            patch("cash.services._locked_register", wraps=cash_services._locked_register) as register_lock,
            patch("cash.services._locked_safe", wraps=cash_services._locked_safe) as safe_lock,
        ):
            transfer_cash_to_safe(
                actor=self.user, warehouse_id=self.warehouse.pk, amount="10", comment="Тест"
            )
        register_lock.assert_called_once_with(self.warehouse.pk)
        safe_lock.assert_called_once_with(self.warehouse.pk)

    def test_repeated_transfer_operation_key_is_idempotent(self):
        self.register.balance = Decimal("100.00")
        self.register.save(update_fields=("balance",))
        operation_key = uuid.uuid4()
        first = transfer_cash_to_safe(
            actor=self.user, warehouse_id=self.warehouse.pk, amount="30", comment="Тест",
            operation_key=operation_key,
        )
        second = transfer_cash_to_safe(
            actor=self.user, warehouse_id=self.warehouse.pk, amount="30", comment="Тест",
            operation_key=operation_key,
        )
        self.register.refresh_from_db()
        self.safe.refresh_from_db()
        self.assertEqual(first.pk, second.pk)
        self.assertEqual((self.register.balance, self.safe.balance), (Decimal("70.00"), Decimal("30.00")))
        self.assertEqual(CashTransaction.objects.count(), 1)

    def test_repeated_form_post_is_processed_once(self):
        self.client.force_login(self.user)
        url = reverse("cash:safe_deposit", args=(self.warehouse.pk,))
        operation_key = self.client.get(url).context["form"]["operation_key"].value()
        data = {"operation_key": operation_key, "amount": "40", "comment": "Двойной клик"}
        destination = reverse("cash:register", args=(self.warehouse.pk,))
        self.assertRedirects(self.client.post(url, data), destination)
        self.assertRedirects(self.client.post(url, data), destination)
        self.safe.refresh_from_db()
        self.assertEqual(self.safe.balance, Decimal("40.00"))
        self.assertEqual(CashTransaction.objects.filter(operation_key=operation_key).count(), 1)

    def test_cash_sale_payment_does_not_change_safe(self):
        sale = Sale.objects.create(
            warehouse=self.warehouse,
            price_type=Sale.PriceType.RETAIL,
            sale_type=Sale.SaleType.RETAIL,
            payment_method=Sale.PaymentMethod.CASH,
            order_status=Sale.OrderStatus.DELIVERED,
            payment_status=Sale.PaymentStatus.PAID,
            total_amount=Decimal("125.00"),
            created_by=self.user,
        )
        credit_sale_payment(sale=sale, actor=self.user)
        self.register.refresh_from_db()
        self.safe.refresh_from_db()
        self.assertEqual(self.register.balance, Decimal("125.00"))
        self.assertEqual(self.safe.balance, Decimal("0.00"))

    def test_common_journal_contains_all_operation_kinds_newest_first(self):
        deposit_cash(actor=self.user, warehouse_id=self.warehouse.pk, amount="100", comment="Касса")
        deposit_safe(actor=self.user, warehouse_id=self.warehouse.pk, amount="50", comment="Сейф")
        transfer_cash_to_safe(actor=self.user, warehouse_id=self.warehouse.pk, amount="10", comment="Перевод")
        transfer_safe_to_cash(actor=self.user, warehouse_id=self.warehouse.pk, amount="5", comment="Возврат")
        collect_cash(actor=self.user, warehouse_id=self.warehouse.pk, amount="5", comment="Инкассация кассы")
        collect_safe(actor=self.user, warehouse_id=self.warehouse.pk, amount="5", comment="Инкассация сейфа")
        self.client.force_login(self.user)
        response = self.client.get(reverse("cash:register", args=(self.warehouse.pk,)))
        transactions = list(response.context["transactions"])
        self.assertEqual([item.pk for item in transactions], sorted((item.pk for item in transactions), reverse=True))
        for label in (
            "Внесение наличных", "Внесение в сейф", "Перевод: касса → сейф",
            "Перевод: сейф → касса", "Инкассация", "Инкассация из сейфа",
        ):
            self.assertContains(response, label)
        self.assertContains(response, "Касса <b>→</b> Сейф", html=True)


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

    def test_safe_action_permission_without_view_safe_cannot_reveal_safe(self):
        worker = User.objects.create_user("safe-action-only", password="StrongWorker!123")
        warehouse = Warehouse.objects.create(name="Закрытый сейф")
        worker.user_permissions.add(
            Permission.objects.get(content_type__app_label="cash", codename="deposit_safe")
        )
        self.client.force_login(worker)
        url = reverse("cash:safe_deposit", args=(warehouse.pk,))
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(
            self.client.post(url, {"amount": "10", "comment": "Тест"}).status_code,
            403,
        )
        self.assertEqual(warehouse.safe.balance, Decimal("0.00"))

    def test_safe_permissions_control_balance_buttons_and_endpoints_separately(self):
        worker = User.objects.create_user("safe-worker", password="StrongWorker!123")
        warehouse = Warehouse.objects.create(name="Склад сейфа")
        view_safe = Permission.objects.get(content_type__app_label="cash", codename="view_safe")
        worker.user_permissions.add(view_safe)
        self.client.force_login(worker)
        register_url = reverse("cash:register", args=(warehouse.pk,))
        response = self.client.get(register_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Сейф")
        for route, codename in (
            ("cash:safe_deposit", "deposit_safe"),
            ("cash:safe_collect", "collect_safe"),
            ("cash:cash_to_safe", "transfer_cash_to_safe"),
            ("cash:safe_to_cash", "transfer_safe_to_cash"),
        ):
            url = reverse(route, args=(warehouse.pk,))
            with self.subTest(codename=codename):
                self.assertNotContains(response, f'href="{url}"')
                self.assertEqual(self.client.get(url).status_code, 403)
                self.assertEqual(self.client.post(url, {"amount": "1", "comment": "Тест"}).status_code, 403)
                worker.user_permissions.add(
                    Permission.objects.get(content_type__app_label="cash", codename=codename)
                )
                worker = User.objects.get(pk=worker.pk)
                self.client.force_login(worker)
                self.assertEqual(self.client.get(url).status_code, 200)
                self.assertContains(self.client.get(register_url), f'href="{url}"')

    def test_history_without_view_safe_hides_safe_operations(self):
        worker = User.objects.create_user("cash-auditor", password="StrongWorker!123")
        warehouse = Warehouse.objects.create(name="Склад журнала")
        admin = User.objects.create_superuser("cash-admin", password="StrongAdmin!123")
        deposit_cash(actor=admin, warehouse_id=warehouse.pk, amount="10", comment="В кассу")
        deposit_safe(actor=admin, warehouse_id=warehouse.pk, amount="20", comment="В сейф")
        worker.user_permissions.add(
            Permission.objects.get(content_type__app_label="cash", codename="view_cash_history")
        )
        self.client.force_login(worker)
        response = self.client.get(reverse("cash:register", args=(warehouse.pk,)))
        self.assertContains(response, "В кассу")
        self.assertNotContains(response, "В сейф")
        self.assertNotContains(response, "20.00")
