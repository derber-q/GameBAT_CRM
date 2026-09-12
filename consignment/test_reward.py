from decimal import Decimal

from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from catalog.models import CD, Platform
from partners.models import SalesPlatform
from warehouse.models import CDWarehouseStock, Warehouse

from .models import CDConsignmentStock
from .services import transfer_to_consignment, update_consignment_reward


class ConsignmentRewardTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_superuser("admin", password="StrongAdmin!123")
        self.platform = Platform.objects.create(name="PS5")
        self.product = CD.objects.create(platform=self.platform, name="Игра", sku="CD-1", barcode="1")
        self.warehouse = Warehouse.objects.create(name="Склад")
        CDWarehouseStock.objects.create(warehouse=self.warehouse, cd=self.product, quantity=10)
        self.shop_a = SalesPlatform.objects.create(name="A", address="A", legal_entity="A", phone_1="1")
        self.shop_b = SalesPlatform.objects.create(name="B", address="B", legal_entity="B", phone_1="2")
        self.stock_a = transfer_to_consignment(
            actor=self.actor, warehouse_id=self.warehouse.pk, platform_id=self.shop_a.pk,
            product_type="cd", product_id=self.product.pk, quantity=2, receivable_per_unit="500",
        )
        self.stock_b = transfer_to_consignment(
            actor=self.actor, warehouse_id=self.warehouse.pk, platform_id=self.shop_b.pk,
            product_type="cd", product_id=self.product.pk, quantity=3, receivable_per_unit="800",
        )

    def test_reward_changes_only_selected_platform_without_quantity_change_and_is_audited(self):
        update_consignment_reward(
            actor=self.actor, product_type="cd", stock_id=self.stock_a.pk, value="600",
        )
        self.stock_a.refresh_from_db()
        self.stock_b.refresh_from_db()
        self.assertEqual((self.stock_a.receivable_per_unit, self.stock_a.quantity), (Decimal("600.00"), 2))
        self.assertEqual((self.stock_b.receivable_per_unit, self.stock_b.quantity), (Decimal("800.00"), 3))
        change = self.product.change_events.order_by("-pk").first().field_changes.get()
        self.assertEqual((change.old_value, change.new_value), ("500.00", "600.00"))
        self.assertIn(self.shop_a.name, change.field_label)

    def test_zero_is_allowed_but_negative_and_inactive_stock_are_rejected(self):
        update_consignment_reward(actor=self.actor, product_type="cd", stock_id=self.stock_a.pk, value="0")
        self.stock_a.refresh_from_db()
        self.assertEqual(self.stock_a.receivable_per_unit, Decimal("0.00"))
        with self.assertRaisesMessage(ValidationError, "не может быть отрицательным"):
            update_consignment_reward(actor=self.actor, product_type="cd", stock_id=self.stock_b.pk, value="-1")
        self.stock_b.quantity = 0
        self.stock_b.save(update_fields=("quantity",))
        with self.assertRaisesMessage(ValidationError, "только у товара на реализации"):
            update_consignment_reward(actor=self.actor, product_type="cd", stock_id=self.stock_b.pk, value="700")

    def test_permission_controls_ui_and_post(self):
        worker = User.objects.create_user("worker", password="StrongWorker!123")
        worker.user_permissions.add(Permission.objects.get(
            content_type__app_label="consignment", codename="view_cdconsignmentstock"
        ))
        self.client.force_login(worker)
        response = self.client.get(reverse("consignment:list"))
        self.assertNotContains(response, "Изменить вознаграждение")
        url = reverse("consignment:reward_update", args=("cd", self.stock_a.pk))
        self.assertEqual(self.client.post(url, {"receivable_per_unit": "700"}).status_code, 403)
        worker.user_permissions.add(Permission.objects.get(
            content_type__app_label="consignment", codename="change_consignment_reward"
        ))
        self.client.force_login(worker)
        self.assertContains(self.client.get(reverse("consignment:list")), "Изменить вознаграждение")
        self.assertRedirects(
            self.client.post(url, {"receivable_per_unit": "700"}), reverse("consignment:list")
        )
        self.stock_a.refresh_from_db()
        self.assertEqual(self.stock_a.receivable_per_unit, Decimal("700.00"))
        self.assertEqual(self.client.get(url).status_code, 405)
