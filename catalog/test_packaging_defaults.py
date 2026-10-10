"""Стандартные размеры при создании и сохранение ручных габаритов."""
from decimal import Decimal

from django.test import TestCase

from .models import Brand, CD, Platform, ProductType, Tech
from .nomenclature_forms import CDCreateForm, TechCreateForm, product_version


class PackagingDefaultTests(TestCase):
    def setUp(self):
        self.platform = Platform.objects.create(name="PS5")
        self.brand = Brand.objects.create(name="Sony")
        self.gamepad_type = ProductType.objects.create(name="Геймпад")

    def dimensions(self, product):
        return (product.length_cm, product.width_cm, product.height_cm)

    def test_cd_defaults_and_version_survive_database_reload(self):
        product = CD.objects.create(platform=self.platform, name="Игра", sku="CD-DEFAULT")
        version = product_version(product)
        self.assertEqual(self.dimensions(product), (23, 15, 4))
        product.refresh_from_db()
        self.assertEqual(self.dimensions(product), (23, 15, 4))
        self.assertEqual(product_version(product), version)

    def test_cd_create_form_fills_only_missing_dimensions(self):
        form = CDCreateForm(data={
            "platform": self.platform.pk, "name": "Игра", "sku": "CD-FORM",
            "length_cm": "25.5", "width_cm": "", "height_cm": "",
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(self.dimensions(form.save()), (Decimal("25.5"), 15, 4))

    def test_gamepad_create_form_fills_only_missing_dimensions(self):
        form = TechCreateForm(data={
            "brand": self.brand.pk, "product_type": self.gamepad_type.pk,
            "name": "DualSense", "sku": "TECH-FORM", "height_cm": "12",
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(self.dimensions(form.save()), (21, 20, 12))

    def test_gamepad_defaults_and_manual_dimensions(self):
        product = Tech.objects.create(
            brand=self.brand, product_type=self.gamepad_type,
            name="DualSense", sku="TECH-DEFAULT", width_cm=Decimal("22"),
        )
        self.assertEqual(self.dimensions(product), (21, 22, 11))

    def test_other_tech_has_no_gamepad_defaults(self):
        product = Tech.objects.create(
            brand=self.brand, product_type=ProductType.objects.create(name="Зарядная станция для геймпадов"),
            name="Зарядная станция", sku="TECH-OTHER",
        )
        self.assertEqual(self.dimensions(product), (None, None, None))

    def test_existing_product_dimensions_are_not_refilled(self):
        product = CD.objects.create(platform=self.platform, name="Игра", sku="CD-EXISTING")
        product.length_cm = None
        product.full_clean()
        product.save(update_fields=["length_cm"])
        product.refresh_from_db()
        self.assertEqual(self.dimensions(product), (None, 15, 4))
