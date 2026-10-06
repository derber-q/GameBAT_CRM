from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from catalog.models import CD, Platform, Tech, Brand, ProductType, ProductChangeEvent
from integrations.models import AvitoManualPrice, AvitoProductProfile, AvitoRemoteListing, AvitoListingConnection
from warehouse.models import Warehouse, CDWarehouseStock, TechWarehouseStock


class AvitoCheckListTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(username="avito-list-admin", password="test")
        self.client.force_login(self.user)
        self.cd = CD.objects.create(name="NS2 Cronos", platform=Platform.objects.create(name="Nintendo Switch 2"),
                                    cost=Decimal("3000"), wholesale_price=Decimal("4000"), avito_price=Decimal("4500"))
        self.profile = self.link(self.cd, 123)
        self.warehouse = Warehouse.objects.create(name="Склад проверки цен")
        CDWarehouseStock.objects.create(cd=self.cd, warehouse=self.warehouse, quantity=1)

    def link(self, product, remote_id):
        profile = AvitoProductProfile.objects.create(**{product._meta.model_name: product})
        AvitoListingConnection.objects.create(profile=profile, remote_listing=AvitoRemoteListing.objects.create(avito_item_id=remote_id))
        return profile

    def save_price(self, price="3499.50", **extra):
        return self.client.post(reverse("pricing:avito_check_found_price"), {
            "kind": "cd", "product_id": self.cd.pk, "price": price, **extra,
        })

    def test_list_includes_only_linked_products_with_physical_stock(self):
        archived = CD.objects.create(name="Archived game", platform=self.cd.platform, is_archived=True)
        self.link(archived, 124)
        tech = Tech.objects.create(name="Sony Device", brand=Brand.objects.create(name="Sony"), product_type=ProductType.objects.create(name="Техника"))
        self.link(tech, 125)
        TechWarehouseStock.objects.create(tech=tech, warehouse=self.warehouse, quantity=2)
        CD.objects.create(name="Unlinked game", platform=self.cd.platform)
        with patch("integrations.avito_check.ReefApiClient") as api:
            response = self.client.get(reverse("pricing:avito_check"))
        api.assert_not_called()
        self.assertEqual(response.context["total"], 1)
        for title in (self.cd.name, "Автоматическая проверка", "Обновлена", "Ручной поиск"):
            self.assertContains(response, title)
        self.assertNotContains(response, tech.name)
        self.assertNotContains(response, archived.name)
        self.assertNotContains(response, "Unlinked game")
        self.assertNotContains(response, 'id="avito-check-run"')
        self.assertContains(response, 'target="_blank"')

    def test_save_price_sets_date_and_audit_without_changing_selling_prices(self):
        with patch("integrations.signals.enqueue_profile_sync_after_commit") as sync:
            response = self.save_price()
        self.assertEqual(response.status_code, 200)
        sync.assert_not_called()
        result = AvitoManualPrice.objects.get(profile=self.profile)
        self.assertEqual(result.price, Decimal("3499.50"))
        self.assertEqual(result.recorded_by, self.user)
        self.assertTrue(response.json()["recorded_at"])
        self.cd.refresh_from_db()
        self.assertEqual(self.cd.avito_price, Decimal("4500"))
        self.assertEqual(self.cd.wholesale_price, Decimal("4000"))
        self.assertTrue(ProductChangeEvent.objects.filter(cd=self.cd, actor=self.user).exists())
        old_time = result.recorded_at
        self.assertEqual(self.save_price().status_code, 200)
        result.refresh_from_db()
        self.assertGreater(result.recorded_at, old_time)
        self.assertContains(self.client.get(reverse("pricing:avito_check")), 'value="3499.50"')

    def test_invalid_prices_do_not_overwrite_saved_price(self):
        self.save_price()
        before = AvitoManualPrice.objects.get(profile=self.profile)
        for value in ("", "0", "-5", "NaN", "Infinity", "1.234", "1000000000000000000"):
            self.assertEqual(self.save_price(value).status_code, 400, value)
        after = AvitoManualPrice.objects.get(profile=self.profile)
        self.assertEqual((before.price, before.recorded_at), (after.price, after.recorded_at))

    def test_view_permission_does_not_allow_writing(self):
        viewer = get_user_model().objects.create_user(username="avito-viewer", password="test")
        viewer.user_permissions.add(Permission.objects.get(content_type__app_label="pricing", codename="view_pricing"))
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(reverse("pricing:avito_check")).status_code, 200)
        self.assertEqual(self.save_price().status_code, 403)
        self.assertFalse(AvitoManualPrice.objects.exists())

    def test_unlinked_and_unknown_product_cannot_be_saved(self):
        self.profile.connection.delete()
        self.assertEqual(self.save_price().status_code, 404)
        self.assertEqual(self.save_price(kind="unknown").status_code, 400)

    def test_search_filters_table_and_old_workflow_has_separate_route(self):
        response = self.client.get(reverse("pricing:avito_check"), {"q": "absent"})
        self.assertEqual(response.context["total"], 0)
        self.assertEqual(self.client.get(reverse("pricing:avito_check_automatic")).status_code, 200)
