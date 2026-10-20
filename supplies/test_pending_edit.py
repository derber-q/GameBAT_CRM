"""Редактирование прихода до приёмки без изменения физического учёта."""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from warehouse.models import Warehouse, CDWarehouseStock
from . import test_price_review as review_tests
from .models import Supply
from .services import edit_pending_supply, confirm_supply_price_review, accept_supply, cancel_supply


class PendingSupplyEditTests(TestCase):
    pending_supply = review_tests.SupplyPriceReviewTests._pending_supply

    def setUp(self):
        review_tests.SupplyPriceReviewTests.setUp(self)
        self.client.force_login(self.user)
        self.supply = self.pending_supply()

    def changes(self, **overrides):
        return {"actor": self.user, "supply_id": self.supply.pk, "expected_revision_number": 1,
                "warehouse_id": self.warehouse.pk, "lines": [{"product_type": "cd", "product_id": self.product.pk,
                "supplier_id": self.supplier.pk, "quantity": 3, "purchase_unit_cost": "150"}], **overrides}

    def test_save_keeps_pending_status_balance_and_history(self):
        supply = edit_pending_supply(**self.changes(expenses=[{"name": "Расход", "amount": "6"}]))
        self.stock.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual((self.stock.quantity, self.product.cost), (2, Decimal("100")))
        self.assertEqual((supply.status, supply.revision_number, supply.total_units), ("price_review", 2, 3))
        self.assertEqual(supply.grand_total, Decimal("456"))
        self.assertEqual(supply.cd_items.get().quantity, 3)
        self.assertEqual(supply.revisions.get().items.get().quantity, 2)
        self.assertEqual(supply.revisions.get().diff_summary, {"pending": True, "balance_changed": False})
        self.assertEqual((supply.cost_calculations.get().old_owned_quantity,
                          supply.cost_calculations.get().resulting_quantity), (2, 5))

    def test_validation_or_late_error_rolls_back_items_totals_and_revision(self):
        item_id = self.supply.cd_items.get().pk
        with patch("supplies.services.SupplyCostCalculation.objects.bulk_create", side_effect=ValidationError("Ошибка расчёта")):
            with self.assertRaisesMessage(ValidationError, "Ошибка расчёта"):
                edit_pending_supply(**self.changes())
        self.supply.refresh_from_db()
        self.assertEqual((self.supply.revision_number, self.supply.total_units), (1, 2))
        self.assertEqual(self.supply.cd_items.get().pk, item_id)
        self.assertFalse(self.supply.revisions.exists())
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 2)

    def test_repeated_edit_and_stale_review_cannot_accept_changed_contents(self):
        edit_pending_supply(**self.changes())
        with self.assertRaisesMessage(ValidationError, "изменён"):
            edit_pending_supply(**self.changes())
        response = self.client.post(reverse("supplies:price_review", args=(self.supply.pk,)), {
            "expected_revision_number": 1, f"cd_{self.product.pk}_wholesale_price": "999",
        })
        self.assertEqual(response.status_code, 200)
        self.supply.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(self.supply.status, "price_review")
        self.assertEqual(self.product.wholesale_price, Decimal("150"))
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 2)

    def test_confirmation_uses_edited_contents_once_and_then_disallows_pending_edit(self):
        edit_pending_supply(**self.changes())
        with patch("supplies.services._enqueue_google_sheets_after_supply"):
            confirm_supply_price_review(actor=self.user, supply_id=self.supply.pk, expected_revision_number=2)
            confirm_supply_price_review(actor=self.user, supply_id=self.supply.pk, expected_revision_number=2)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 5)
        with self.assertRaisesMessage(ValidationError, "уже принят"):
            edit_pending_supply(**self.changes(expected_revision_number=2))

    def test_pending_form_saves_without_historical_confirmation_and_has_review_link(self):
        url = reverse("supplies:edit", args=(self.supply.pk,))
        response = self.client.get(url)
        self.assertContains(response, "Сохранить без приёмки")
        self.assertContains(response, 'data-editing="false"')
        self.assertNotContains(response, 'id="supply-revision-dialog"')
        self.assertEqual(response.context["initial_supply_lines"][0]["product_id"], self.product.pk)
        self.assertContains(self.client.get(reverse("supplies:detail", args=(self.supply.pk,))), url)
        self.assertContains(self.client.get(reverse("supplies:price_review", args=(self.supply.pk,))), url)
        response = self.client.post(url, {"expected_revision_number": 1, "warehouse_id": self.warehouse.pk,
            "weight_transport_cost": "0", "product_type": "cd", "product_id": self.product.pk,
            "supplier_id": self.supplier.pk, "quantity": 3, "purchase_unit_cost": "150"})
        self.assertEqual(response.status_code, 302)
        self.supply.refresh_from_db()
        self.assertEqual((self.supply.status, self.supply.total_units), ("price_review", 3))
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 2)

    def test_permissions_separate_pending_and_accepted_editing(self):
        user = User.objects.create_user("pending-editor", password="Isolated123!")
        add = Permission.objects.get(content_type__app_label="supplies", codename="add_supply")
        historical = Permission.objects.get(content_type__app_label="supplies", codename="edit_accepted_supply")
        user.user_permissions.add(historical)
        self.client.force_login(user)
        url = reverse("supplies:edit", args=(self.supply.pk,))
        self.assertEqual(self.client.get(url).status_code, 403)
        with self.assertRaises(PermissionDenied):
            edit_pending_supply(**self.changes(actor=user))
        user.user_permissions.set([add])
        self.client.force_login(user)
        self.assertEqual(self.client.get(url).status_code, 200)
        confirm_supply_price_review(actor=self.user, supply_id=self.supply.pk)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_change_warehouse_does_not_move_existing_stocks(self):
        other = Warehouse.objects.create(name="Другой склад")
        other_stock = CDWarehouseStock.objects.create(warehouse=other, cd=self.product, quantity=7)
        result = edit_pending_supply(**self.changes(warehouse_id=other.pk))
        self.stock.refresh_from_db()
        other_stock.refresh_from_db()
        self.assertEqual((self.stock.quantity, other_stock.quantity), (2, 7))
        self.assertEqual(result.warehouse_id, other.pk)
        self.assertEqual(result.cost_calculations.get().old_owned_quantity, 9)

    def test_unreceived_and_cancelled_drafts_do_not_affect_cost_when_another_receipt_is_cancelled(self):
        for cancel_draft in (False, True):
            with self.subTest(cancel_draft=cancel_draft):
                accepted = accept_supply(accepted_by=self.user, warehouse_id=self.warehouse.pk,
                    lines=self.changes()["lines"])
                draft = self.pending_supply()
                if cancel_draft:
                    cancel_supply(actor=self.user, supply_id=draft.pk, comment="До приёмки")
                cancel_supply(actor=self.user, supply_id=accepted.pk, comment="Ошибка тестового прихода")
                self.stock.refresh_from_db()
                self.product.refresh_from_db()
                self.assertEqual((self.stock.quantity, self.product.cost), (2, Decimal("100")))
                if not cancel_draft:
                    cancel_supply(actor=self.user, supply_id=draft.pk, comment="До приёмки")

    def test_edit_preserves_but_supersedes_finalization_of_old_contents(self):
        from .models import SupplyFinalization
        finalization = SupplyFinalization.objects.create(supply=self.supply, created_by=self.user,
            supply_revision_number=1, total_penalty_before_distribution=0)
        edit_pending_supply(**self.changes())
        finalization.refresh_from_db()
        self.assertEqual((finalization.status, finalization.superseded_by_revision_number), ("superseded", 2))

    def test_later_confirmation_uses_receipt_time_for_history_after_other_deliveries(self):
        other = accept_supply(accepted_by=self.user, warehouse_id=self.warehouse.pk, lines=self.changes()["lines"])
        edit_pending_supply(**self.changes())
        confirmed, _ = confirm_supply_price_review(actor=self.user, supply_id=self.supply.pk, expected_revision_number=2)
        self.assertGreater(confirmed.accepted_at, other.accepted_at)
        cancel_supply(actor=self.user, supply_id=other.pk, comment="Отмена промежуточного прихода")
        self.stock.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual((self.stock.quantity, self.product.cost), (5, Decimal("130")))
