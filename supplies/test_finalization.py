from dataclasses import replace
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from cash.models import CashRegister, Safe
from catalog.models import Brand, CD, Platform, ProductChangeEvent, ProductType, Tech
from partners.models import Supplier
from warehouse.models import CDWarehouseStock, Warehouse

from .finalization import (
    apply_supply_finalization, auto_distribute_penalty,
    calculate_finalization_penalty, get_supply_finalization_context,
)
from .models import Supply, SupplyFinalization, SupplyFinalizationItem
from .services import accept_supply, revise_supply


class SupplyFinalizationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_superuser("admin", password="pass")
        cls.worker = get_user_model().objects.create_user("worker", password="pass")
        cls.warehouse = Warehouse.objects.create(name="Основной склад")
        cls.supplier = Supplier.objects.create(
            name="Поставщик", letter="Z", highlight_color="#ffffff",
            legal_entity="ООО", phone_1="1",
        )
        platform = Platform.objects.create(name="PS5")
        brand = Brand.objects.create(name="Sony")
        product_type = ProductType.objects.create(name="Аксессуар")
        cls.a = CD.objects.create(platform=platform, name="A", sku="A", cost=0, weight_grams=120)
        cls.b = CD.objects.create(platform=platform, name="B", sku="B", cost=0, weight_grams=120)
        cls.c = CD.objects.create(platform=platform, name="C", sku="C", cost=0, weight_grams=120)
        cls.d = Tech.objects.create(
            brand=brand, product_type=product_type, name="D", sku="D", cost=0, weight_grams=500,
        )

    def setUp(self):
        self.supply = accept_supply(
            accepted_by=self.user,
            warehouse_id=self.warehouse.pk,
            lines=self.supply_lines(),
            expenses=[],
            weight_transport_cost="0",
        )

    def supply_lines(self):
        return [
            {"product_type": "cd", "product_id": self.a.pk, "supplier_id": self.supplier.pk, "quantity": 10, "purchase_unit_cost": "100"},
            {"product_type": "cd", "product_id": self.b.pk, "supplier_id": self.supplier.pk, "quantity": 20, "purchase_unit_cost": "100"},
            {"product_type": "cd", "product_id": self.c.pk, "supplier_id": self.supplier.pk, "quantity": 5, "purchase_unit_cost": "100"},
            {"product_type": "tech", "product_id": self.d.pk, "supplier_id": self.supplier.pk, "quantity": 1, "purchase_unit_cost": "400"},
        ]

    def context_rows(self, changes=None, sources=None):
        changes = changes or {}
        sources = sources or {}
        return [
            replace(
                row,
                corrected_cost=Decimal(changes.get(row.key, row.corrected_cost)),
                change_source=sources.get(row.key, "unchanged"),
            )
            for row in get_supply_finalization_context(supply=self.supply)
        ]

    def raw_rows(self, changes=None, sources=None, baseline_rows=None):
        changes = changes or {}
        sources = sources or {}
        baseline_rows = baseline_rows or get_supply_finalization_context(supply=self.supply)
        return [
            {
                "product_type": row.product_type,
                "product_id": row.product_id,
                "baseline_quantity": row.global_quantity,
                "baseline_cost": str(row.current_cost),
                "corrected_cost": str(changes.get(row.key, row.current_cost)),
                "change_source": sources.get(row.key, "unchanged"),
            }
            for row in baseline_rows
        ]

    def apply(self, changes, sources=None, baseline_rows=None):
        return apply_supply_finalization(
            actor=self.user,
            supply_id=self.supply.pk,
            expected_revision_number=self.supply.revision_number,
            raw_rows=self.raw_rows(changes, sources, baseline_rows),
        )

    def test_initial_manual_signs_quantity_and_zero_total(self):
        initial = self.context_rows()
        self.assertEqual(calculate_finalization_penalty(initial), Decimal("0.00"))
        down = self.context_rows({("cd", self.a.pk): "99.00"})
        self.assertEqual(calculate_finalization_penalty(down), Decimal("10.00"))
        up = self.context_rows({("cd", self.a.pk): "101.00"})
        self.assertEqual(calculate_finalization_penalty(up), Decimal("-10.00"))
        balanced = self.context_rows({
            ("cd", self.a.pk): "99.00", ("cd", self.c.pk): "102.00",
        })
        self.assertEqual(calculate_finalization_penalty(balanced), Decimal("0.00"))

    def test_auto_distribution_uses_total_quantity_and_exact_residual(self):
        rows = self.context_rows(
            {("tech", self.d.pk): "100.00"},
            {("tech", self.d.pk): "manual"},
        )
        result = auto_distribute_penalty(
            rows=rows,
            selected_keys={("cd", self.a.pk), ("cd", self.b.pk), ("cd", self.c.pk)},
        )
        by_key = {row.key: row for row in result}
        self.assertEqual(by_key[("cd", self.a.pk)].corrected_cost, Decimal("108.57"))
        self.assertEqual(by_key[("cd", self.b.pk)].corrected_cost, Decimal("108.57"))
        self.assertEqual(by_key[("cd", self.c.pk)].corrected_cost, Decimal("108.58"))
        self.assertEqual(calculate_finalization_penalty(result), Decimal("0.00"))

    def test_negative_and_partial_auto_distribution(self):
        negative = self.context_rows(
            {("tech", self.d.pk): "700.00"}, {("tech", self.d.pk): "manual"},
        )
        negative_result = auto_distribute_penalty(
            rows=negative,
            selected_keys={("cd", self.a.pk), ("cd", self.b.pk), ("cd", self.c.pk)},
        )
        self.assertEqual(calculate_finalization_penalty(negative_result), Decimal("0.00"))
        partial = self.context_rows(
            {("tech", self.d.pk): "100.00"}, {("tech", self.d.pk): "manual"},
        )
        partial_result = auto_distribute_penalty(
            rows=partial,
            selected_keys={("cd", self.a.pk), ("cd", self.c.pk)},
        )
        by_key = {row.key: row for row in partial_result}
        self.assertEqual(by_key[("cd", self.a.pk)].corrected_cost, Decimal("120.00"))
        self.assertEqual(by_key[("cd", self.b.pk)].corrected_cost, Decimal("100.00"))
        self.assertEqual(by_key[("cd", self.c.pk)].corrected_cost, Decimal("120.00"))

    def test_manual_and_zero_stock_rows_are_not_auto_distributed(self):
        CDWarehouseStock.objects.filter(cd=self.c).update(quantity=0)
        rows = self.context_rows(
            {("tech", self.d.pk): "100.00", ("cd", self.a.pk): "99.00"},
            {("tech", self.d.pk): "manual", ("cd", self.a.pk): "manual"},
        )
        result = auto_distribute_penalty(
            rows=rows,
            selected_keys={
                ("tech", self.d.pk), ("cd", self.a.pk),
                ("cd", self.b.pk), ("cd", self.c.pk),
            },
        )
        by_key = {row.key: row for row in result}
        self.assertEqual(by_key[("tech", self.d.pk)].corrected_cost, Decimal("100.00"))
        self.assertEqual(by_key[("cd", self.a.pk)].corrected_cost, Decimal("99.00"))
        self.assertEqual(by_key[("cd", self.c.pk)].corrected_cost, Decimal("100.00"))
        self.assertEqual(calculate_finalization_penalty(result), Decimal("0.00"))

    def test_no_selection_and_impossible_cent_precision_are_rejected(self):
        rows = self.context_rows({("cd", self.a.pk): "99.00"}, {("cd", self.a.pk): "manual"})
        with self.assertRaisesMessage(ValidationError, "Выберите товары"):
            auto_distribute_penalty(rows=rows, selected_keys=set())
        artificial = []
        for row in self.context_rows():
            if row.key == ("tech", self.d.pk):
                artificial.append(replace(
                    row, global_quantity=1, corrected_cost=Decimal("399.99"), change_source="manual"
                ))
            elif row.key == ("cd", self.a.pk):
                artificial.append(replace(row, global_quantity=2))
            elif row.key == ("cd", self.b.pk):
                artificial.append(replace(row, global_quantity=4))
            else:
                artificial.append(row)
        with self.assertRaisesMessage(ValidationError, "Точную неустойку 0,00"):
            auto_distribute_penalty(
                rows=artificial,
                selected_keys={("cd", self.a.pk), ("cd", self.b.pk)},
            )

    def test_zero_stock_cost_can_change_without_penalty(self):
        stock = CDWarehouseStock.objects.get(warehouse=self.warehouse, cd=self.c)
        stock.quantity = 0
        stock.save(update_fields=("quantity",))
        finalization = self.apply(
            {("cd", self.c.pk): "500.00"}, {("cd", self.c.pk): "manual"},
        )
        self.c.refresh_from_db()
        self.assertEqual(self.c.cost, Decimal("500.00"))
        self.assertEqual(finalization.items.get().global_quantity_snapshot, 0)

    def test_apply_updates_only_cost_and_writes_immutable_history_and_product_audit(self):
        quantities_before = dict(CDWarehouseStock.objects.values_list("cd_id", "quantity"))
        cash = CashRegister.objects.get(warehouse=self.warehouse)
        safe = Safe.objects.get(warehouse=self.warehouse)
        cash.balance = Decimal("1000.00")
        safe.balance = Decimal("2000.00")
        cash.save(update_fields=("balance",))
        safe.save(update_fields=("balance",))
        finalization = self.apply(
            {("cd", self.a.pk): "99.00", ("cd", self.c.pk): "102.00"},
            {("cd", self.a.pk): "manual", ("cd", self.c.pk): "manual"},
        )
        self.a.refresh_from_db()
        self.c.refresh_from_db()
        cash.refresh_from_db()
        safe.refresh_from_db()
        self.assertEqual((self.a.cost, self.c.cost), (Decimal("99.00"), Decimal("102.00")))
        self.assertEqual(dict(CDWarehouseStock.objects.values_list("cd_id", "quantity")), quantities_before)
        self.assertEqual((cash.balance, safe.balance), (Decimal("1000.00"), Decimal("2000.00")))
        self.assertEqual(finalization.items.count(), 2)
        item = finalization.items.get(cd=self.a)
        self.assertEqual(item.change_source, SupplyFinalizationItem.ChangeSource.MANUAL)
        self.assertEqual(item.value_difference, Decimal("-10.00"))
        event = ProductChangeEvent.objects.filter(cd=self.a).latest("id")
        self.assertEqual(event.action_kind, ProductChangeEvent.ActionKind.SUPPLY_FINALIZATION)
        self.assertEqual(event.action_label, f"Финализация прихода №{self.supply.pk}")

    def test_apply_rejects_nonzero_and_non_cent_cost(self):
        with self.assertRaisesMessage(ValidationError, "неустойка равна"):
            self.apply({("cd", self.a.pk): "99.99"}, {("cd", self.a.pk): "manual"})
        with self.assertRaisesMessage(ValidationError, "точностью до копейки"):
            self.apply({("cd", self.a.pk): "99.999"}, {("cd", self.a.pk): "manual"})
        self.assertEqual(SupplyFinalization.objects.count(), 0)

    def test_stale_quantity_cost_and_second_apply_are_rejected(self):
        baseline = get_supply_finalization_context(supply=self.supply)
        CDWarehouseStock.objects.filter(warehouse=self.warehouse, cd=self.a).update(quantity=9)
        with self.assertRaisesMessage(ValidationError, "Данные товаров изменились"):
            self.apply(
                {("cd", self.a.pk): "99.00", ("cd", self.c.pk): "102.00"},
                baseline_rows=baseline,
            )
        CDWarehouseStock.objects.filter(warehouse=self.warehouse, cd=self.a).update(quantity=10)
        baseline = get_supply_finalization_context(supply=self.supply)
        CD.objects.filter(pk=self.a.pk).update(cost=Decimal("101.00"))
        with self.assertRaisesMessage(ValidationError, "Данные товаров изменились"):
            self.apply(
                {("cd", self.a.pk): "99.00", ("cd", self.c.pk): "102.00"},
                baseline_rows=baseline,
            )
        CD.objects.filter(pk=self.a.pk).update(cost=Decimal("100.00"))
        baseline = get_supply_finalization_context(supply=self.supply)
        raw = self.raw_rows(
            {("cd", self.a.pk): "99.00", ("cd", self.c.pk): "102.00"},
            baseline_rows=baseline,
        )
        apply_supply_finalization(
            actor=self.user, supply_id=self.supply.pk,
            expected_revision_number=1, raw_rows=raw,
        )
        with self.assertRaisesMessage(ValidationError, "Данные товаров изменились"):
            apply_supply_finalization(
                actor=self.user, supply_id=self.supply.pk,
                expected_revision_number=1, raw_rows=raw,
            )

    def test_atomic_rollback_on_product_save_failure(self):
        original_save = CD.save

        def failing_save(instance, *args, **kwargs):
            if instance.pk == self.c.pk:
                raise RuntimeError("failure")
            return original_save(instance, *args, **kwargs)

        with patch.object(CD, "save", new=failing_save):
            with self.assertRaises(RuntimeError):
                self.apply({("cd", self.a.pk): "99.00", ("cd", self.c.pk): "102.00"})
        self.a.refresh_from_db()
        self.c.refresh_from_db()
        self.assertEqual((self.a.cost, self.c.cost), (Decimal("100.00"), Decimal("100.00")))
        self.assertEqual(SupplyFinalization.objects.count(), 0)
        self.assertFalse(ProductChangeEvent.objects.filter(
            action_kind=ProductChangeEvent.ActionKind.SUPPLY_FINALIZATION
        ).exists())

    def test_revising_finalized_supply_supersedes_history_and_replays_cost(self):
        finalization = self.apply(
            {("cd", self.a.pk): "99.00", ("cd", self.c.pk): "102.00"}
        )
        revise_supply(
            actor=self.user,
            supply_id=self.supply.pk,
            expected_revision_number=1,
            warehouse_id=self.warehouse.pk,
            lines=self.supply_lines(),
            expenses=[],
            weight_transport_cost="0",
            reason="Исправление прихода",
        )
        finalization.refresh_from_db()
        self.a.refresh_from_db()
        self.assertEqual(finalization.status, SupplyFinalization.Status.SUPERSEDED)
        self.assertEqual(finalization.superseded_by_revision_number, 2)
        self.assertEqual(self.a.cost, Decimal("100.00"))
        self.assertEqual(finalization.items.count(), 2)

    def test_current_supply_products_are_unique_even_with_duplicate_items(self):
        item = self.supply.cd_items.get(product=self.a)
        item.pk = None
        item._state.adding = True
        item.save()
        rows = get_supply_finalization_context(supply=self.supply)
        self.assertEqual([row.key for row in rows].count(("cd", self.a.pk)), 1)

    def test_permission_button_endpoint_cancelled_supply_and_ui(self):
        view_permission = Permission.objects.get(codename="view_supply")
        finalize_permission = Permission.objects.get(codename="finalize_supply")
        self.worker.user_permissions.add(view_permission)
        self.client.force_login(self.worker)
        detail_url = reverse("supplies:detail", args=(self.supply.pk,))
        finalization_url = reverse("supplies:finalization", args=(self.supply.pk,))
        response = self.client.get(detail_url)
        self.assertNotContains(response, finalization_url)
        self.assertEqual(self.client.get(finalization_url).status_code, 403)
        self.worker.user_permissions.add(finalize_permission)
        self.worker = get_user_model().objects.get(pk=self.worker.pk)
        self.client.force_login(self.worker)
        response = self.client.get(finalization_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Выбрать все CD")
        self.assertContains(response, "Выбрать все Tech")
        self.assertContains(response, "Распределить текущую неустойку")
        self.assertContains(response, 'data-quantity="10"')
        Supply.objects.filter(pk=self.supply.pk).update(
            status=Supply.Status.CANCELLED,
            cancelled_at="2026-09-14T00:00:00Z",
            cancelled_by=self.user,
            cancellation_comment="Отмена",
        )
        response = self.client.get(finalization_url, follow=True)
        self.assertContains(response, "Финализировать можно только действующий принятый приход")

    def test_auto_endpoint_recalculates_and_direct_nonzero_post_is_rejected(self):
        finalize_permission = Permission.objects.get(codename="finalize_supply")
        self.worker.user_permissions.add(finalize_permission)
        self.client.force_login(self.worker)
        rows = self.raw_rows(
            {("tech", self.d.pk): "100.00"}, {("tech", self.d.pk): "manual"},
        )
        post = {
            "revision_number": "1",
            "selected_product": [f"cd:{self.a.pk}", f"cd:{self.b.pk}", f"cd:{self.c.pk}"],
        }
        for field in (
            "product_type", "product_id", "baseline_quantity", "baseline_cost",
            "corrected_cost", "change_source",
        ):
            post[field] = [str(row[field]) for row in rows]
        response = self.client.post(reverse("supplies:finalization_auto", args=(self.supply.pk,)), post)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["penalty"], "0.00")
        bad_rows = self.raw_rows({("cd", self.a.pk): "99.99"})
        bad_post = {"revision_number": "1"}
        for field in post.keys() - {"revision_number", "selected_product"}:
            bad_post[field] = [str(row[field]) for row in bad_rows]
        response = self.client.post(reverse("supplies:finalization", args=(self.supply.pk,)), bad_post)
        self.assertRedirects(response, reverse("supplies:finalization", args=(self.supply.pk,)))
        self.assertEqual(SupplyFinalization.objects.count(), 0)
