from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from warehouse.models import CDWarehouseStock, TechWarehouseStock

from .models import Brand, CD, Platform, ProductType, Tech
from .nomenclature_services import create_product


def permission(codename):
    return Permission.objects.get(content_type__app_label="catalog", codename=codename)


class ProductCreationTests(TestCase):
    def setUp(self):
        self.platform = Platform.objects.create(name="PlayStation 5")
        self.brand = Brand.objects.create(name="Sony")
        self.product_type = ProductType.objects.create(name="Консоли")
        self.user = User.objects.create_user("creator", password="StrongWorker!123")
        self.user.user_permissions.add(permission("view_nomenclature"), permission("add_cd"))
        self.client.force_login(self.user)

    def test_add_cd_permission_shows_only_allowed_kind_and_creates_zero_stock_card(self):
        list_response = self.client.get(reverse("nomenclature:list"))
        self.assertContains(list_response, "Новое наименование")
        choice_response = self.client.get(reverse("nomenclature:create"))
        self.assertContains(choice_response, ">CD</a>", html=False)
        self.assertNotContains(choice_response, ">Tech</a>", html=False)

        response = self.client.post(reverse("nomenclature:create"), {
            "product_kind": "cd",
            "platform": self.platform.pk,
            "name": "Новая игра",
            "description": "Описание",
            "sku": "NEW-CD-1",
            "barcode": "460000000001",
            "cusa_ppsa_code": "PPSA-NEW-1",
            "comment": "Создано для теста",
            "cost": "9999",
            "stock_1": "8",
        })
        product = CD.objects.get(sku="NEW-CD-1")
        self.assertRedirects(response, reverse("nomenclature:cd_detail", args=(product.pk,)))
        self.assertEqual(product.cost, Decimal("0.00"))
        self.assertEqual(product.quantity_on_consignment, 0)
        self.assertFalse(CDWarehouseStock.objects.filter(cd=product).exists())
        event = product.change_events.get()
        self.assertEqual(event.actor, self.user)
        self.assertTrue(event.field_changes.filter(field_name="created", field_label="Товар создан").exists())

    def test_superuser_creates_tech_without_stock_or_prices(self):
        admin = User.objects.create_superuser("admin", password="StrongAdmin!123")
        self.client.force_login(admin)
        response = self.client.post(reverse("nomenclature:create"), {
            "product_kind": "tech",
            "brand": self.brand.pk,
            "product_type": self.product_type.pk,
            "name": "Новая консоль",
            "description": "",
            "sku": "NEW-TECH-1",
            "barcode": "",
            "comment": "",
            "retail_price": "1000",
        })
        product = Tech.objects.get(sku="NEW-TECH-1")
        self.assertRedirects(response, reverse("nomenclature:tech_detail", args=(product.pk,)))
        self.assertIsNone(product.retail_price)
        self.assertEqual(product.cost, Decimal("0.00"))
        self.assertFalse(TechWarehouseStock.objects.filter(tech=product).exists())

    def test_wrong_kind_and_missing_add_permission_are_forbidden(self):
        self.assertEqual(
            self.client.get(reverse("nomenclature:create"), {"kind": "tech"}).status_code,
            403,
        )
        viewer = User.objects.create_user("viewer", password="StrongWorker!123")
        viewer.user_permissions.add(permission("view_nomenclature"))
        self.client.force_login(viewer)
        self.assertNotContains(self.client.get(reverse("nomenclature:list")), "Новое наименование")
        self.assertEqual(self.client.get(reverse("nomenclature:create")).status_code, 403)
        self.assertEqual(self.client.post(reverse("nomenclature:create"), {"product_kind": "cd"}).status_code, 403)

    def test_creation_and_audit_are_atomic(self):
        with patch("catalog.nomenclature_services.record_product_changes", side_effect=RuntimeError("audit failed")):
            with self.assertRaisesMessage(RuntimeError, "audit failed"):
                create_product(
                    actor=self.user,
                    product_kind="cd",
                    data={
                        "platform": self.platform,
                        "name": "Откат",
                        "description": "",
                        "sku": "ROLLBACK-CD",
                        "barcode": "",
                        "cusa_ppsa_code": "",
                        "comment": "",
                    },
                )
        self.assertFalse(CD.objects.filter(sku="ROLLBACK-CD").exists())
