from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from warehouse.models import Warehouse
from .models import BarcodeRegistry, Brand, CD, Platform, ProductChangeEvent, ProductType, Tech
from .nomenclature_forms import barcode_formset, product_version
from .product_identifiers import generate_unique_barcode
from .removal import HAS_BARCODE, evaluate_product_removal


def barcode_data(values, *, initial=0):
    result = {
        "barcodes-TOTAL_FORMS": str(len(values)),
        "barcodes-INITIAL_FORMS": str(initial),
        "barcodes-MIN_NUM_FORMS": "0",
        "barcodes-MAX_NUM_FORMS": "1000",
    }
    for index, item in enumerate(values):
        if isinstance(item, tuple):
            pk, value, delete = item
            result[f"barcodes-{index}-id"] = str(pk)
            if delete:
                result[f"barcodes-{index}-DELETE"] = "on"
        else:
            value = item
        result[f"barcodes-{index}-value"] = value
    return result


class MultipleBarcodeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("barcode-admin", password="TestPassword123!")
        self.client.force_login(self.user)
        self.platform = Platform.objects.create(name="PS5")
        self.brand = Brand.objects.create(name="Sony")
        self.product_type = ProductType.objects.create(name="Консоль")

    def create_cd(self, name="Игра"):
        return CD.objects.create(platform=self.platform, name=name, sku=f"SKU-{name}")

    def card_data(self, product, barcodes):
        data = {
            "version": product_version(product), "platform": product.platform_id,
            "name": product.name, "sku": product.sku,
            "description": product.description, "comment": product.comment,
            **barcodes,
        }
        for warehouse in Warehouse.objects.all():
            data[f"stock_{warehouse.pk}"] = "0"
            data[f"storage_location_{warehouse.pk}"] = ""
        return data

    def test_create_cd_three_and_tech_two_preserve_leading_zero(self):
        cd_payload = {
            "product_kind": "cd", "platform": self.platform.pk, "name": "Три кода",
            "sku": "CD-THREE", **barcode_data(["111", "00123456", "333"]),
        }
        response = self.client.post(reverse("nomenclature:create"), cd_payload)
        self.assertEqual(response.status_code, 302)
        cd = CD.objects.get(sku="CD-THREE")
        self.assertEqual(list(cd.barcodes.order_by("id").values_list("value", flat=True)), ["111", "00123456", "333"])

        tech_payload = {
            "product_kind": "tech", "brand": self.brand.pk,
            "product_type": self.product_type.pk, "name": "Два кода",
            "sku": "TECH-TWO", **barcode_data(["444", "555"]),
        }
        response = self.client.post(reverse("nomenclature:create"), tech_payload)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(list(Tech.objects.get(sku="TECH-TWO").barcodes.values_list("value", flat=True)), ["444", "555"])

    def test_duplicate_rejected_without_partial_create(self):
        self.create_cd().barcodes.create(value="already-used", product_kind="cd")
        url = reverse("nomenclature:create")
        for values, expected in ((["same", "same"], "указан несколько раз"),
                                 (["fresh", "already-used"], "уже используется")):
            response = self.client.post(url, {
                "product_kind": "tech", "brand": self.brand.pk,
                "product_type": self.product_type.pk, "name": "Не создавать",
                "sku": "TECH-FAILED", **barcode_data(values),
            })
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, expected)
            self.assertFalse(Tech.objects.exists())
            self.assertFalse(BarcodeRegistry.objects.filter(value="fresh").exists())

    def test_edit_add_change_delete_and_audit(self):
        cd = self.create_cd()
        first = cd.barcodes.create(value="one", product_kind="cd")
        second = cd.barcodes.create(value="two", product_kind="cd")
        data = self.card_data(cd, barcode_data([
            (first.pk, "changed", False), (second.pk, "two", True), "new",
        ], initial=2))
        data["name"] = "Игра новая"
        response = self.client.post(reverse("nomenclature:cd_detail", args=(cd.pk,)), data)
        self.assertEqual(response.status_code, 302)
        cd.refresh_from_db()
        self.assertEqual(cd.name, "Игра новая")
        self.assertEqual(set(cd.barcodes.values_list("value", flat=True)), {"changed", "new"})
        changes = ProductChangeEvent.objects.filter(cd=cd).last().field_changes
        self.assertEqual(set(changes.values_list("field_name", flat=True)), {
            "name", "barcode_changed", "barcode_removed", "barcode_added",
        })

    def test_invalid_edit_keeps_card_and_barcode_unchanged(self):
        cd = self.create_cd()
        other = self.create_cd("Другая")
        existing = cd.barcodes.create(value="one", product_kind="cd")
        other.barcodes.create(value="occupied", product_kind="cd")
        data = self.card_data(cd, barcode_data([(existing.pk, "occupied", False)], initial=1))
        data["name"] = "Изменённое имя"
        response = self.client.post(reverse("nomenclature:cd_detail", args=(cd.pk,)), data)
        self.assertEqual(response.status_code, 200)
        cd.refresh_from_db()
        self.assertEqual(cd.name, "Игра")
        self.assertEqual(list(cd.barcodes.values_list("value", flat=True)), ["one"])

    def test_cannot_delete_other_products_barcode_by_id(self):
        cd = self.create_cd()
        other = self.create_cd("Другая")
        foreign = other.barcodes.create(value="foreign", product_kind="cd")
        data = barcode_data([(foreign.pk, "foreign", True)], initial=1)
        formset = barcode_formset(product=cd, data=data)
        self.assertFalse(formset.is_valid())
        self.assertIn("не принадлежит", str(formset.non_form_errors()))
        self.assertTrue(BarcodeRegistry.objects.filter(pk=foreign.pk).exists())

    def test_generate_appends_and_print_targets_specific_row(self):
        cd = self.create_cd()
        first = cd.barcodes.create(value="111", product_kind="cd")
        second = cd.barcodes.create(value="222", product_kind="cd")
        generate_unique_barcode(actor=self.user, product_kind="cd", product_id=cd.pk)
        self.assertEqual(cd.barcodes.count(), 3)
        for row in (first, second):
            response = self.client.get(reverse("nomenclature:barcode_print", args=(row.pk,)))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "size: 58mm 40mm")
            self.assertContains(response, 'class="barcode-label"', count=1)
            self.assertNotContains(response, row.value)
        detail = self.client.get(reverse("nomenclature:cd_detail", args=(cd.pk,)))
        self.assertContains(detail, reverse("nomenclature:barcode_print", args=(second.pk,)))
        self.assertContains(detail, "Сгенерировать штрихкод")

    def test_every_code_searches_same_product(self):
        cd = self.create_cd()
        for value in ("111ABC", "222ABC", "00333ABC"):
            cd.barcodes.create(value=value, product_kind="cd")
            response = self.client.get(reverse("nomenclature:list"), {"search": value})
            self.assertContains(response, cd.name)
            result = self.client.get(reverse("supplies:autocomplete"), {"q": value}).json()["results"]
            self.assertEqual([row["id"] for row in result if row["type"] == "cd"], [cd.pk])

    def test_permission_does_not_allow_barcode_post(self):
        cd = self.create_cd()
        worker = User.objects.create_user("barcode-viewer", password="TestPassword123!")
        worker.user_permissions.add(Permission.objects.get(
            content_type__app_label="catalog", codename="view_nomenclature",
        ))
        self.client.force_login(worker)
        response = self.client.post(reverse("nomenclature:cd_detail", args=(cd.pk,)),
                                    self.card_data(cd, barcode_data(["unauthorized"])))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(cd.barcodes.exists())

    def test_removal_remains_blocked_until_last_barcode_is_deleted(self):
        cd = self.create_cd()
        first = cd.barcodes.create(value="one", product_kind="cd")
        second = cd.barcodes.create(value="two", product_kind="cd")
        self.assertIn(HAS_BARCODE, evaluate_product_removal(cd).reasons)
        first.delete()
        self.assertIn(HAS_BARCODE, evaluate_product_removal(cd).reasons)
        second.delete()
        self.assertNotIn(HAS_BARCODE, evaluate_product_removal(cd).reasons)

    def test_admin_inline_rejects_barcode_used_by_other_product(self):
        cd = self.create_cd()
        other = self.create_cd("Другая")
        other.barcodes.create(value="occupied", product_kind="cd")
        response = self.client.post(reverse("admin:catalog_cd_change", args=(cd.pk,)), {
            "platform": self.platform.pk, "name": cd.name, "sku": cd.sku,
            "weight_grams": "120", "description": "", "comment": "",
            "barcodes-TOTAL_FORMS": "1", "barcodes-INITIAL_FORMS": "0",
            "barcodes-MIN_NUM_FORMS": "0", "barcodes-MAX_NUM_FORMS": "1000",
            "barcodes-0-value": "occupied", "_save": "Сохранить",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(cd.barcodes.exists())
