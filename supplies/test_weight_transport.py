from decimal import Decimal

from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from catalog.models import Brand, CD, Platform, ProductType, Tech
from partners.models import Supplier
from warehouse.models import Warehouse

from .services import accept_supply, cancel_supply


class SupplyWeightTransportTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("transport-admin", password="StrongAdmin!123")
        platform = Platform.objects.create(name="PS5")
        brand = Brand.objects.create(name="Sony")
        product_type = ProductType.objects.create(name="Консоль")
        self.cd = CD.objects.create(
            platform=platform, name="Лёгкий товар", sku="CD-W", weight_grams=100, cost=0,
        )
        self.tech = Tech.objects.create(
            brand=brand, product_type=product_type, name="Тяжёлый товар", sku="T-W",
            weight_grams=500, cost=0,
        )
        self.warehouse = Warehouse.objects.create(name="Склад")
        self.supplier = Supplier.objects.create(
            name="Поставщик", letter="A", highlight_color="#37A7BA",
            legal_entity="ООО", phone_1="1",
        )

    def line(self, product, quantity, cost="100"):
        return {
            "product_type": "cd" if isinstance(product, CD) else "tech",
            "product_id": product.pk,
            "supplier_id": self.supplier.pk,
            "quantity": quantity,
            "purchase_unit_cost": cost,
        }

    def test_product_without_weight_cannot_be_accepted(self):
        self.tech.weight_grams = None
        self.tech.save(update_fields=("weight_grams",))
        with self.assertRaisesMessage(ValidationError, "без веса"):
            accept_supply(
                accepted_by=self.user,
                warehouse_id=self.warehouse.pk,
                lines=[self.line(self.tech, 1)],
                weight_transport_cost="0",
            )

    def test_transport_is_distributed_by_line_weight_and_enters_cost(self):
        supply = accept_supply(
            accepted_by=self.user,
            warehouse_id=self.warehouse.pk,
            lines=[self.line(self.cd, 10), self.line(self.tech, 2, "200")],
            expenses=[{"name": "Упаковка", "amount": "300"}],
            weight_transport_cost="10000",
        )
        cd_item = supply.cd_items.get()
        tech_item = supply.tech_items.get()
        self.assertEqual(supply.total_weight_grams, 2000)
        self.assertEqual(supply.weight_transport_cost, Decimal("10000.00"))
        self.assertEqual(supply.grand_total, Decimal("11700.00"))
        self.assertEqual(cd_item.weight_grams_snapshot, 100)
        self.assertEqual(tech_item.weight_grams_snapshot, 500)
        self.assertEqual(cd_item.line_weight_grams, 1000)
        self.assertEqual(tech_item.line_weight_grams, 1000)
        self.assertEqual(cd_item.allocated_transport_cost, Decimal("5000.00"))
        self.assertEqual(tech_item.allocated_transport_cost, Decimal("5000.00"))
        self.assertEqual(cd_item.transport_cost_per_unit, Decimal("500.000000"))
        self.assertEqual(tech_item.transport_cost_per_unit, Decimal("2500.000000"))
        self.assertEqual(cd_item.allocated_expense_per_unit, Decimal("25.000000"))
        self.assertEqual(cd_item.effective_unit_cost, Decimal("625.000000"))
        self.assertEqual(tech_item.effective_unit_cost, Decimal("2725.000000"))
        self.cd.refresh_from_db()
        self.tech.refresh_from_db()
        self.assertEqual(self.cd.cost, Decimal("625.00"))
        self.assertEqual(self.tech.cost, Decimal("2725.00"))

    def test_different_shares_and_rounding_sum_exactly(self):
        self.tech.weight_grams = 300
        self.tech.save(update_fields=("weight_grams",))
        supply = accept_supply(
            accepted_by=self.user,
            warehouse_id=self.warehouse.pk,
            lines=[self.line(self.cd, 1), self.line(self.tech, 1)],
            weight_transport_cost="400",
        )
        self.assertEqual(supply.cd_items.get().allocated_transport_cost, Decimal("100.00"))
        self.assertEqual(supply.tech_items.get().allocated_transport_cost, Decimal("300.00"))

        third = CD.objects.create(
            platform=self.cd.platform, name="Третий", sku="CD-3", weight_grams=100,
        )
        rounded = accept_supply(
            accepted_by=self.user,
            warehouse_id=self.warehouse.pk,
            lines=[self.line(self.cd, 1), self.line(third, 1), self.line(self.tech, 1)],
            weight_transport_cost="0.01",
        )
        allocations = list(rounded.cd_items.values_list("allocated_transport_cost", flat=True))
        allocations += list(rounded.tech_items.values_list("allocated_transport_cost", flat=True))
        self.assertEqual(sum(allocations, Decimal("0")), Decimal("0.01"))

    def test_cancel_excludes_transport_but_keeps_later_supply(self):
        first = accept_supply(
            accepted_by=self.user,
            warehouse_id=self.warehouse.pk,
            lines=[self.line(self.cd, 10, "100")],
            weight_transport_cost="1000",
        )
        accept_supply(
            accepted_by=self.user,
            warehouse_id=self.warehouse.pk,
            lines=[self.line(self.cd, 10, "300")],
            weight_transport_cost="0",
        )
        cancel_supply(actor=self.user, supply_id=first.pk, comment="Исключить транспорт")
        self.cd.refresh_from_db()
        self.assertEqual(self.cd.cost, Decimal("300.00"))

    def test_weight_endpoint_saves_product_then_allows_future_use(self):
        self.tech.weight_grams = None
        self.tech.save(update_fields=("weight_grams",))
        worker = User.objects.create_user("receiver", password="StrongWorker!123")
        worker.user_permissions.add(
            Permission.objects.get(content_type__app_label="supplies", codename="add_supply"),
            Permission.objects.get(content_type__app_label="catalog", codename="change_tech_weight"),
        )
        self.client.force_login(worker)
        response = self.client.post(reverse("supplies:product_weight"), {
            "product_type": "tech", "product_id": self.tech.pk, "weight_grams": "450",
        })
        self.assertEqual(response.status_code, 200)
        self.tech.refresh_from_db()
        self.assertEqual(self.tech.weight_grams, 450)
        supply = accept_supply(
            accepted_by=worker,
            warehouse_id=self.warehouse.pk,
            lines=[self.line(self.tech, 1)],
            weight_transport_cost="0",
        )
        self.assertEqual(supply.tech_items.get().weight_grams_snapshot, 450)

    def test_create_page_requires_transport_and_contains_weight_prompt_script(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("supplies:create"))
        self.assertContains(response, "Транспортные расходы по весу")
        self.assertContains(response, 'name="weight_transport_cost"')
        self.assertContains(response, "creditors-sales-search-1")
