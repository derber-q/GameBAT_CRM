from decimal import Decimal

from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from catalog.models import Brand, CD, Platform, ProductType, Tech
from partners.models import Supplier
from warehouse.models import CDWarehouseStock, TechWarehouseStock, Warehouse
from .models import SupplierCDPrice
from .services import update_product_prices, update_supplier_price


class PricingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("admin", password="StrongAdmin!123")
        self.platform = Platform.objects.create(name="PS5")
        self.cd = CD.objects.create(
            platform=self.platform, name="Игра", sku="CD-1", barcode="1",
            cusa_ppsa_code="PPSA-PRICE-1", cost=100,
        )
        self.warehouse = Warehouse.objects.create(name="Тестовый склад")
        self.cd_stock = CDWarehouseStock.objects.create(
            warehouse=self.warehouse, cd=self.cd, quantity=1,
        )
        self.supplier = Supplier.objects.create(
            name="Секретный поставщик", letter="A", highlight_color="#37A7BA",
            legal_entity="ООО Секрет", phone_1="+70000000000",
        )

    def test_three_sales_prices_and_supplier_price(self):
        update_product_prices(actor=self.user, product_type="cd", product_id=self.cd.pk, changes={
            "avito_price": "150", "wholesale_price": "130", "yandex_market_price": "170",
        })
        update_supplier_price(
            actor=self.user, product_type="cd", product_id=self.cd.pk,
            supplier_id=self.supplier.pk, value="95.123456",
        )
        self.cd.refresh_from_db()
        self.assertEqual(self.cd.avito_price, Decimal("150.00"))
        self.assertEqual(self.cd.wholesale_price, Decimal("130.00"))
        self.assertEqual(self.cd.yandex_market_price, Decimal("170.00"))
        self.assertEqual(SupplierCDPrice.objects.get().price, Decimal("95.123456"))

    def test_ajax_save_returns_json_without_redirect(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("pricing:product_update"), {
            "product_type": "cd", "product_id": self.cd.pk,
            "avito_price": "150", "wholesale_price": "", "yandex_market_price": "0",
        }, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True, "message": "Сохранено"})
        self.assertNotIn("Location", response)
        self.cd.refresh_from_db()
        self.assertEqual(self.cd.avito_price, Decimal("150"))
        self.assertIsNone(self.cd.wholesale_price)
        self.assertEqual(self.cd.yandex_market_price, Decimal("0"))

    def test_ajax_validation_error_keeps_prices_unchanged(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("pricing:product_update"), {
            "product_type": "cd", "product_id": self.cd.pk, "avito_price": "-1",
        }, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])
        self.assertTrue(response.json()["message"])
        self.cd.refresh_from_db()
        self.assertIsNone(self.cd.avito_price)

    def test_ajax_respects_field_permissions(self):
        worker = User.objects.create_user("ajax-worker")
        worker.user_permissions.add(Permission.objects.get(codename="change_retail_price"))
        self.client.force_login(worker)
        response = self.client.post(reverse("pricing:product_update"), {
            "product_type": "cd", "product_id": self.cd.pk, "wholesale_price": "123",
        }, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.json()["ok"])
        self.cd.refresh_from_db()
        self.assertIsNone(self.cd.wholesale_price)

    def test_prices_can_be_saved_for_legacy_product_with_blank_barcode(self):
        self.cd.barcode = ""
        self.cd.save(update_fields=("barcode",))

        update_product_prices(
            actor=self.user,
            product_type="cd",
            product_id=self.cd.pk,
            changes={
                "avito_price": "150",
                "wholesale_price": "",
                "yandex_market_price": "170",
            },
        )

        self.cd.refresh_from_db()
        self.assertEqual(self.cd.avito_price, Decimal("150.00"))
        self.assertIsNone(self.cd.wholesale_price)
        self.assertEqual(self.cd.yandex_market_price, Decimal("170.00"))

    def test_negative_price_and_duplicate_supplier_pair_are_rejected(self):
        with self.assertRaises(ValidationError):
            update_product_prices(
                actor=self.user, product_type="cd", product_id=self.cd.pk, changes={"avito_price": "-1"}
            )
        SupplierCDPrice.objects.create(supplier=self.supplier, cd=self.cd, price=1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            SupplierCDPrice.objects.create(supplier=self.supplier, cd=self.cd, price=2)

    def test_supplier_price_defaults_to_zero_and_blank_is_rejected(self):
        price = SupplierCDPrice.objects.create(supplier=self.supplier, cd=self.cd)
        self.assertEqual(price.price, Decimal("0"))
        with self.assertRaisesMessage(ValidationError, "Укажите корректную цену"):
            update_supplier_price(
                actor=self.user,
                product_type="cd",
                product_id=self.cd.pk,
                supplier_id=self.supplier.pk,
                value="",
            )
        price.refresh_from_db()
        self.assertEqual(price.price, Decimal("0"))

    def test_page_groups_cd_by_platform_and_tech_by_product_type(self):
        second_platform = Platform.objects.create(name="Xbox Series")
        CD.objects.create(platform=second_platform, name="Вторая игра", sku="CD-2", barcode="2")
        brand = Brand.objects.create(name="Sony")
        console_type = ProductType.objects.create(name="Консоли")
        accessory_type = ProductType.objects.create(name="Аксессуары")
        Tech.objects.create(
            brand=brand, product_type=console_type, name="PlayStation 5", sku="T-1", barcode="3"
        )
        Tech.objects.create(
            brand=brand, product_type=accessory_type, name="DualSense", sku="T-2", barcode="4"
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("pricing:list"), {"in_stock": "0"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [group.name for group, _ in response.context["cd_groups"]],
            ["PS5", "Xbox Series"],
        )
        self.assertEqual(
            [group.name for group, _ in response.context["tech_groups"]],
            ["Аксессуары", "Консоли"],
        )

    def test_page_shows_narrow_global_stock_column_between_name_and_cost(self):
        reserve = Warehouse.objects.create(name="Резерв")
        self.cd_stock.quantity = 2
        self.cd_stock.save(update_fields=("quantity",))
        CDWarehouseStock.objects.create(warehouse=reserve, cd=self.cd, quantity=3)
        brand = Brand.objects.create(name="Sony")
        product_type = ProductType.objects.create(name="Консоли")
        tech = Tech.objects.create(
            brand=brand, product_type=product_type, name="PlayStation 5", sku="T-STOCK", barcode="5"
        )
        TechWarehouseStock.objects.create(warehouse=self.warehouse, tech=tech, quantity=4)

        self.client.force_login(self.user)
        response = self.client.get(reverse("pricing:list"))

        cd_row = response.context["cd_groups"][0][1][0]
        tech_row = response.context["tech_groups"][0][1][0]
        self.assertEqual(cd_row["product"].global_stock, 5)
        self.assertEqual(tech_row["product"].global_stock, 4)
        content = response.content.decode()
        name_heading = "<th>Название</th>"
        stock_heading = '<th class="numeric-center pricing-global-stock-column">Глобальный остаток</th>'
        cost_heading = '<th class="numeric">Себестоимость</th>'
        self.assertLess(content.index(name_heading), content.index(stock_heading))
        self.assertLess(content.index(stock_heading), content.index(cost_heading))
        self.assertContains(response, "pricing-global-stock-column")

    def test_in_stock_filter_is_enabled_by_default_and_can_be_disabled(self):
        zero_stock_product = CD.objects.create(
            platform=self.platform, name="Товар без остатка", sku="CD-ZERO", barcode="0",
        )
        CDWarehouseStock.objects.create(
            warehouse=self.warehouse, cd=zero_stock_product, quantity=0,
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("pricing:list"))

        self.assertTrue(response.context["in_stock_only"])
        self.assertContains(response, self.cd.name)
        self.assertNotContains(response, zero_stock_product.name)
        self.assertContains(response, 'value="1" checked data-in-stock-toggle')

        response = self.client.get(reverse("pricing:list"), {"in_stock": "0"})

        self.assertFalse(response.context["in_stock_only"])
        self.assertContains(response, self.cd.name)
        self.assertContains(response, zero_stock_product.name)
        self.assertNotContains(response, 'value="1" checked data-in-stock-toggle')

    def test_supplier_prices_stay_in_database_but_are_not_rendered(self):
        supplier_price = SupplierCDPrice.objects.create(supplier=self.supplier, cd=self.cd, price=95)
        self.client.force_login(self.user)
        response = self.client.get(reverse("pricing:list"))
        self.assertNotContains(response, 'name="price"')
        self.assertNotContains(response, "supplier-price-heading")
        self.assertNotContains(response, self.supplier.name)
        self.assertContains(response, '<td class="numeric">100</td>', html=True)
        self.assertTrue(SupplierCDPrice.objects.filter(pk=supplier_price.pk, price=95).exists())

    def test_inline_price_update_returns_to_the_filtered_view(self):
        self.client.force_login(self.user)
        response = self.client.post(
            f'{reverse("pricing:product_update")}?search=CD-1&platform={self.platform.pk}&in_stock=0',
            {
                "product_type": "cd",
                "product_id": self.cd.pk,
                "avito_price": "250",
            },
        )
        self.assertRedirects(
            response,
            f'{reverse("pricing:list")}?search=CD-1&platform={self.platform.pk}&in_stock=0',
        )
        self.cd.refresh_from_db()
        self.assertEqual(self.cd.avito_price, Decimal("250.00"))

    def test_supplier_confidentiality_and_post_permissions(self):
        worker = User.objects.create_user("worker", password="StrongWorker!123")
        worker.user_permissions.add(
            Permission.objects.get(content_type__app_label="pricing", codename="view_pricing"),
            Permission.objects.get(content_type__app_label="pricing", codename="view_supplier_prices"),
        )
        self.client.force_login(worker)
        response = self.client.get(reverse("pricing:list"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.supplier.name)
        response = self.client.post(reverse("pricing:product_update"), {
            "product_type": "cd", "product_id": self.cd.pk, "avito_price": "200",
        })
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.post(reverse("pricing:supplier_update"), {
            "product_type": "cd", "product_id": self.cd.pk, "supplier_id": self.supplier.pk, "price": "1",
        }).status_code, 403)

    def test_avito_wholesale_markup_warning_is_strict_and_does_not_block_save(self):
        self.client.force_login(self.user)
        self.cd.wholesale_price = Decimal("100.00")
        self.cd.save(update_fields=("wholesale_price",))
        for price, expected in (("288.99", True), ("289.00", False), ("90.00", True)):
            self.cd.avito_price = Decimal(price)
            self.cd.save(update_fields=("avito_price",))
            response = self.client.get(reverse("pricing:list"))
            row = response.context["cd_groups"][0][1][0]
            self.assertEqual(bool(row["warnings"]["avito_price"]), expected)
        response = self.client.post(reverse("pricing:product_update"), {
            "product_type": "cd", "product_id": self.cd.pk, "avito_price": "150.00",
        })
        self.assertEqual(response.status_code, 302)
        self.cd.refresh_from_db()
        self.assertEqual(self.cd.avito_price, Decimal("150.00"))

    def test_pricing_page_uses_avito_name_and_dynamic_warning_script(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("pricing:list"))
        self.assertContains(response, "Цена Avito")
        self.assertContains(response, 'name="avito_price"')
        self.assertContains(response, "pricing.js?v=price-control-2")
        self.assertNotContains(response, 'name="retail_price"')

    def test_group_collapse_uses_unique_shared_controls_after_filtering(self):
        brand = Brand.objects.create(name="Sony")
        product_type = ProductType.objects.create(name="Консоли")
        Tech.objects.create(
            brand=brand, product_type=product_type, name="PlayStation 5", sku="T-1", barcode="3"
        )
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("pricing:list"), {"search": "PlayStation", "in_stock": "0"},
        )
        html = response.content.decode()

        control_id = f"pricing-tech-{brand.pk}-{product_type.pk}"
        self.assertContains(response, f'aria-controls="{control_id}"')
        self.assertContains(response, f'id="{control_id}"')
        self.assertEqual(html.count(f'id="{control_id}"'), 1)
        self.assertContains(response, f'aria-controls="pricing-brand-{brand.pk}"')
        self.assertContains(response, "app.js?v=collapse-fix-3")
        self.assertContains(response, "data-global-barcode-search")
