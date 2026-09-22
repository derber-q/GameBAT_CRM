from decimal import Decimal

from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from accounts.models import User

from .models import BarcodeRegistry, Brand, CD, Platform, ProductType, Tech
from .nomenclature_forms import TechCreateForm
from .nomenclature_services import create_product
from .product_identifiers import generate_unique_barcode


class ProductWeightAndIdentifierTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("identifier-admin", password="StrongAdmin!123")
        self.platform = Platform.objects.create(name="PS5")
        self.brand = Brand.objects.create(name="Sony")
        self.product_type = ProductType.objects.create(name="Консоль")

    def cd_data(self, **changes):
        data = {
            "platform": self.platform,
            "name": "Игра",
            "description": "",
            "sku": "",
            "barcode": "",
            "cusa_ppsa_code": "",
            "weight_grams": 140,
            "comment": "",
        }
        data.update(changes)
        return data

    def tech_data(self, **changes):
        data = {
            "brand": self.brand,
            "product_type": self.product_type,
            "name": "Консоль",
            "description": "",
            "sku": "",
            "barcode": "",
            "weight_grams": None,
            "comment": "",
        }
        data.update(changes)
        return data

    def test_cd_defaults_to_120_and_tech_may_have_no_weight(self):
        cd = CD.objects.create(platform=self.platform, name="Диск")
        tech = Tech.objects.create(
            brand=self.brand, product_type=self.product_type, name="Техника"
        )
        self.assertEqual(cd.weight_grams, 120)
        self.assertIsNone(tech.weight_grams)

    def test_invalid_tech_weights_are_rejected(self):
        base = {
            "brand": self.brand.pk,
            "product_type": self.product_type.pk,
            "name": "Техника",
            "description": "",
            "sku": "T-1",
            "barcode": "",
            "comment": "",
        }
        for invalid in ("0", "-1", "1.5", "abc"):
            form = TechCreateForm({**base, "weight_grams": invalid})
            self.assertFalse(form.is_valid(), invalid)
            self.assertIn("weight_grams", form.errors)

    def test_article_is_generated_only_when_blank(self):
        automatic = create_product(
            actor=self.user, product_kind="cd", data=self.cd_data(name="Авто"),
        )
        manual = create_product(
            actor=self.user,
            product_kind="tech",
            data=self.tech_data(name="Вручную", sku="MANUAL-ARTICLE"),
        )
        self.assertEqual(automatic.sku, f"CD-{automatic.pk:06d}")
        self.assertEqual(manual.sku, "MANUAL-ARTICLE")

    def test_manual_barcode_is_registered_and_cross_model_duplicate_is_rejected(self):
        product = create_product(
            actor=self.user,
            product_kind="cd",
            data=self.cd_data(barcode="012345678901"),
        )
        registry = BarcodeRegistry.objects.get(value="012345678901")
        self.assertEqual(registry.cd, product)
        with self.assertRaisesMessage(ValidationError, "уже используется"):
            create_product(
                actor=self.user,
                product_kind="tech",
                data=self.tech_data(barcode="012345678901"),
            )
        self.assertEqual(Tech.objects.count(), 0)

    def test_registry_unique_constraint_is_the_last_race_protection(self):
        cd = CD.objects.create(platform=self.platform, name="CD", barcode="")
        tech = Tech.objects.create(
            brand=self.brand, product_type=self.product_type, name="Tech", barcode=""
        )
        BarcodeRegistry.objects.create(value="111111111111", product_kind="cd", cd=cd)
        with self.assertRaises(IntegrityError), transaction.atomic():
            BarcodeRegistry.objects.create(
                value="111111111111", product_kind="tech", tech=tech
            )

    def test_random_barcode_generation_and_button_state(self):
        product = create_product(
            actor=self.user, product_kind="cd", data=self.cd_data(name="Без кода"),
        )
        self.client.force_login(self.user)
        detail_url = reverse("nomenclature:cd_detail", args=(product.pk,))
        self.assertContains(self.client.get(detail_url), "Сгенерировать штрихкод")
        generated = generate_unique_barcode(
            actor=self.user, product_kind="cd", product_id=product.pk,
        )
        self.assertRegex(generated.barcode, r"^\d{12}$")
        self.assertTrue(BarcodeRegistry.objects.filter(value=generated.barcode, cd=generated).exists())
        response = self.client.get(detail_url)
        self.assertContains(response, "Сгенерировать штрихкод")
        self.assertContains(response, "Напечатать")

    def test_print_page_is_one_58_by_40_barcode_only_label(self):
        product = create_product(
            actor=self.user,
            product_kind="cd",
            data=self.cd_data(
                name="Скрытое название",
                sku="HIDDEN-SKU",
                barcode="987654321098",
            ),
        )
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("nomenclature:barcode_print", args=("cd", product.pk))
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "size: 58mm 40mm")
        self.assertContains(response, "data:image/svg+xml;base64,")
        self.assertContains(response, 'class="barcode-label"', count=1)
        self.assertNotContains(response, product.name)
        self.assertNotContains(response, product.sku)
        self.assertNotContains(response, product.barcode)
        self.assertNotContains(response, str(Decimal("0.00")))

    def test_weight_field_uses_existing_field_permission_system(self):
        product = create_product(
            actor=self.user, product_kind="tech", data=self.tech_data(weight_grams=450),
        )
        worker = User.objects.create_user("weight-viewer", password="StrongWorker!123")
        worker.user_permissions.add(Permission.objects.get(
            content_type__app_label="catalog", codename="view_nomenclature"
        ))
        self.client.force_login(worker)
        response = self.client.get(reverse("nomenclature:tech_detail", args=(product.pk,)))
        self.assertTrue(response.context["form"].fields["weight_grams"].disabled)
