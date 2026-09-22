from decimal import Decimal
from io import BytesIO

from openpyxl import load_workbook

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils.html import escape

from consignment.models import CDConsignmentStock
from consignment.services import transfer_many_to_consignment
from integrations.models import AvitoListingConnection, AvitoProductProfile, AvitoRemoteListing
from partners.models import SalesPlatform, Supplier
from price.excel import generate_supplier_template
from pricing.models import SupplierCDPrice
from sales.models import Sale, SaleCDItem
from sales.services import create_sale
from supplies.services import accept_supply, cancel_supply
from warehouse.models import (
    CDWarehouseStock, CDWarehouseTransferItem, TechWarehouseStock, Warehouse, WarehouseTransfer,
)
from warehouse.services import create_transfer

from .models import CD, GameSeries, Platform, ProductChangeEvent, ProductFieldChange, ProductRemovalEvent, Tech, Brand, ProductType
from .removal import (
    HAS_AVITO_CONNECTION, HAS_BARCODE, HAS_STOCK, evaluate_product_removal,
    has_product_history, remove_product,
)


class ProductRemovalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_superuser("removal-admin", "r@example.com", "password")
        cls.platform = Platform.objects.create(name="PlayStation 5")
        cls.ps4 = Platform.objects.create(name="PlayStation 4")
        cls.series = GameSeries.objects.create(name="Assassin's Creed")
        cls.other_series = GameSeries.objects.create(name="Resident Evil")
        cls.brand = Brand.objects.create(name="Sony")
        cls.product_type = ProductType.objects.create(name="Консоли")
        cls.warehouse = Warehouse.objects.create(name="Тестовый склад удаления")
        cls.other_warehouse = Warehouse.objects.create(name="Другой склад удаления")
        cls.sales_platform = SalesPlatform.objects.create(name="Тестовая площадка")
        cls.supplier = Supplier.objects.create(
            name="Поставщик", letter="X", highlight_color="#123456", legal_entity="Тест",
            phone_1="1",
        )

    def setUp(self):
        self.client.force_login(self.user)

    def cd(self, name="Тестовая игра", **kwargs):
        return CD.objects.create(platform=self.platform, name=name, **kwargs)

    def sale_history(self, product):
        sale = Sale.objects.create(
            warehouse=self.warehouse, price_type=Sale.PriceType.RETAIL,
            sale_type=Sale.SaleType.RETAIL, payment_method=Sale.PaymentMethod.BANK_ACCOUNT,
            created_by=self.user,
        )
        SaleCDItem.objects.create(
            sale=sale, cd=product, quantity=1, unit_price=Decimal("100.00"),
            line_total=Decimal("100.00"), product_name_snapshot=product.name,
            article_snapshot=product.sku,
        )
        return sale

    def test_game_series_filter_platform_search_and_without_series(self):
        ps5_ac = self.cd("Assassin's Creed Mirage", game_series=self.series)
        ps4_ac = CD.objects.create(platform=self.ps4, name="Assassin's Creed Odyssey", game_series=self.series)
        other = self.cd("Resident Evil 4", game_series=self.other_series)
        no_series = self.cd("Одиночная игра")
        Tech.objects.create(name="Техника", brand=self.brand, product_type=self.product_type)

        response = self.client.get(reverse("nomenclature:list"), {"game_series": self.series.pk})
        self.assertEqual([p.pk for _, group in response.context["cd_groups"] for _, products in group["series_groups"] for p in products], [ps4_ac.pk, ps5_ac.pk])
        self.assertFalse(response.context["tech_groups"])
        self.assertContains(response, f'<option value="{self.series.pk}" selected>')
        response = self.client.get(reverse("nomenclature:list"), {
            "game_series": self.series.pk, "platform": self.platform.pk, "search": "Mirage",
        })
        self.assertContains(response, escape(ps5_ac.name))
        self.assertNotContains(response, escape(ps4_ac.name))
        self.assertNotContains(response, other.name)
        response = self.client.get(reverse("nomenclature:list"), {"game_series": "none"})
        self.assertContains(response, no_series.name)
        self.assertNotContains(response, escape(ps5_ac.name))

    def test_avito_highlight_uses_connection_not_sell_flag_and_toggle_only_changes_color(self):
        linked = self.cd("Привязанный товар")
        flagged = self.cd("Только флаг")
        profile = AvitoProductProfile.objects.create(cd=linked, sell_on_avito=False)
        AvitoProductProfile.objects.create(cd=flagged, sell_on_avito=True)
        listing = AvitoRemoteListing.objects.create(avito_item_id=123456789)
        AvitoListingConnection.objects.create(profile=profile, remote_listing=listing)
        url = reverse("nomenclature:list")
        on = self.client.get(url)
        off = self.client.get(url, {"avito_highlight": "0"})
        self.assertContains(on, 'class="avito-connected-row"', count=1)
        self.assertNotContains(off, 'class="avito-connected-row"')
        self.assertEqual(on.context["cd_groups"][0][1]["count"], off.context["cd_groups"][0][1]["count"])
        self.assertTrue(on.context["avito_highlight"])
        self.assertFalse(off.context["avito_highlight"])

        with CaptureQueriesContext(connection) as few:
            self.client.get(url)
        for index in range(12):
            self.cd(f"Ещё товар {index}")
        with CaptureQueriesContext(connection) as many:
            self.client.get(url)
        self.assertLessEqual(len(many), len(few) + 1)

    def test_tech_avito_connection_is_highlighted(self):
        tech = Tech.objects.create(name="Связанная техника", brand=self.brand, product_type=self.product_type)
        profile = AvitoProductProfile.objects.create(tech=tech, sell_on_avito=False)
        AvitoListingConnection.objects.create(
            profile=profile,
            remote_listing=AvitoRemoteListing.objects.create(avito_item_id=123456791),
        )
        response = self.client.get(reverse("nomenclature:list"))
        self.assertContains(response, 'class="avito-connected-row"', count=1)
        self.assertContains(response, tech.name)

    def test_zero_stock_highlight_defaults_on_and_avito_has_priority_for_cd_and_tech(self):
        cd_zero = self.cd("CD без остатка")
        cd_positive = self.cd("CD с остатком")
        cd_linked_zero = self.cd("CD Avito без остатка")
        tech_zero = Tech.objects.create(
            name="Tech без остатка", brand=self.brand, product_type=self.product_type,
        )
        tech_linked_positive = Tech.objects.create(
            name="Tech Avito с остатком", brand=self.brand, product_type=self.product_type,
        )
        CDWarehouseStock.objects.create(warehouse=self.warehouse, cd=cd_positive, quantity=3)
        TechWarehouseStock.objects.create(warehouse=self.warehouse, tech=tech_linked_positive, quantity=2)

        cd_profile = AvitoProductProfile.objects.create(cd=cd_linked_zero, sell_on_avito=False)
        tech_profile = AvitoProductProfile.objects.create(tech=tech_linked_positive, sell_on_avito=False)
        AvitoListingConnection.objects.create(
            profile=cd_profile,
            remote_listing=AvitoRemoteListing.objects.create(avito_item_id=123456792),
        )
        AvitoListingConnection.objects.create(
            profile=tech_profile,
            remote_listing=AvitoRemoteListing.objects.create(avito_item_id=123456793),
        )

        response = self.client.get(reverse("nomenclature:list"))
        self.assertTrue(response.context["avito_highlight"])
        self.assertTrue(response.context["zero_stock_highlight"])
        self.assertContains(response, 'name="zero_stock_highlight" value="1" checked')
        self.assertContains(response, 'class="zero-stock-row"', count=2)
        self.assertContains(response, 'class="avito-connected-row"', count=2)
        self.assertRegex(response.content.decode(), rf'(?s)class="zero-stock-row"[^>]*>.*?{cd_zero.name}')
        self.assertRegex(response.content.decode(), rf'(?s)class="zero-stock-row"[^>]*>.*?{tech_zero.name}')
        self.assertRegex(response.content.decode(), rf'(?s)class="avito-connected-row"[^>]*>.*?{cd_linked_zero.name}')

    def test_highlight_toggles_only_change_row_colors(self):
        linked_zero = self.cd("Связанный товар с нулём")
        unlinked_zero = self.cd("Несвязанный товар с нулём")
        profile = AvitoProductProfile.objects.create(cd=linked_zero, sell_on_avito=False)
        AvitoListingConnection.objects.create(
            profile=profile,
            remote_listing=AvitoRemoteListing.objects.create(avito_item_id=123456794),
        )
        url = reverse("nomenclature:list")

        avito_off = self.client.get(url, {"avito_highlight": "0"})
        self.assertNotContains(avito_off, 'class="avito-connected-row"')
        self.assertContains(avito_off, 'class="zero-stock-row"', count=2)
        self.assertEqual(len(avito_off.context["cd_groups"][0][1]["series_groups"][0][1]), 2)

        zero_off = self.client.get(url, {"zero_stock_highlight": "0"})
        self.assertContains(zero_off, 'class="avito-connected-row"', count=1)
        self.assertNotContains(zero_off, 'class="zero-stock-row"')

        both_off = self.client.get(url, {"avito_highlight": "0", "zero_stock_highlight": "0"})
        self.assertNotContains(both_off, 'class="avito-connected-row"')
        self.assertNotContains(both_off, 'class="zero-stock-row"')
        self.assertContains(both_off, linked_zero.name)
        self.assertContains(both_off, unlinked_zero.name)

    def test_barcode_and_avito_connection_block_even_without_sell_flag(self):
        product = self.cd(barcode="001234567890")
        self.assertIn(HAS_BARCODE, evaluate_product_removal(product).reasons)
        response = self.client.post(reverse("nomenclature:product_delete", args=("cd", product.pk)))
        self.assertRedirects(response, reverse("nomenclature:cd_detail", args=(product.pk,)))
        self.assertTrue(CD.objects.filter(pk=product.pk).exists())

        product = self.cd("Avito товар")
        profile = AvitoProductProfile.objects.create(cd=product, sell_on_avito=False)
        connection = AvitoListingConnection.objects.create(
            profile=profile, remote_listing=AvitoRemoteListing.objects.create(avito_item_id=123456790),
        )
        self.assertIn(HAS_AVITO_CONNECTION, evaluate_product_removal(product).reasons)
        self.client.post(reverse("nomenclature:product_delete", args=("cd", product.pk)))
        self.assertTrue(CD.objects.filter(pk=product.pk).exists())
        self.assertTrue(AvitoListingConnection.objects.filter(pk=connection.pk).exists())

    def test_owned_stock_and_transit_block_removal(self):
        product = self.cd()
        stock = CDWarehouseStock.objects.create(warehouse=self.warehouse, cd=product, quantity=3)
        self.assertIn(HAS_STOCK, evaluate_product_removal(product).reasons)
        stock.quantity = 0
        stock.save(update_fields=["quantity"])
        consignment = CDConsignmentStock.objects.create(
            warehouse=self.warehouse, platform=self.sales_platform, cd=product, quantity=2,
        )
        self.assertIn(HAS_STOCK, evaluate_product_removal(product).reasons)
        consignment.quantity = 0
        consignment.save(update_fields=["quantity"])
        transfer = WarehouseTransfer.objects.create(
            source_warehouse=self.warehouse, destination_warehouse=self.other_warehouse,
            created_by=self.user,
        )
        CDWarehouseTransferItem.objects.create(transfer=transfer, cd=product, quantity=1)
        self.assertIn(HAS_STOCK, evaluate_product_removal(product).reasons)

    def test_hard_delete_keeps_independent_audit_and_removes_only_technical_rows(self):
        product = self.cd()
        product_id = product.pk
        CDWarehouseStock.objects.create(warehouse=self.warehouse, cd=product, quantity=0)
        CDConsignmentStock.objects.create(
            warehouse=self.warehouse, platform=self.sales_platform, cd=product, quantity=0,
        )
        SupplierCDPrice.objects.create(supplier=self.supplier, cd=product, price=Decimal("1"))
        ProductChangeEvent.objects.create(
            actor=self.user, source=ProductChangeEvent.Source.NOMENCLATURE,
            product_kind="cd", cd=product,
        )
        AvitoProductProfile.objects.create(cd=product)
        self.assertFalse(has_product_history(product))
        result = remove_product(product_kind="cd", product_id=product_id, actor=self.user)
        self.assertEqual(result.action, "HARD_DELETED")
        self.assertFalse(CD.objects.filter(pk=product_id).exists())
        event = ProductRemovalEvent.objects.get(product_kind="cd", product_id=product_id)
        self.assertEqual(event.action, ProductRemovalEvent.Action.HARD_DELETE)

    def test_manual_stock_adjustment_audit_is_history(self):
        product = self.cd()
        event = ProductChangeEvent.objects.create(
            actor=self.user, source=ProductChangeEvent.Source.NOMENCLATURE,
            product_kind="cd", cd=product,
        )
        ProductFieldChange.objects.create(
            event=event, field_name=f"warehouse_stock_{self.warehouse.pk}",
            field_label="Остаток", old_value="1", new_value="0",
        )
        self.assertIn("change_events:stock_adjustment", has_product_history(product))
        self.assertEqual(remove_product(product_kind="cd", product_id=product.pk, actor=self.user).action, "ARCHIVED")

    def test_sale_history_archives_and_old_sale_remains_readable(self):
        product = self.cd("Исторический диск")
        product_id = product.pk
        sale = self.sale_history(product)
        self.assertIn("sale_items", has_product_history(product))
        result = remove_product(product_kind="cd", product_id=product_id, actor=self.user)
        self.assertEqual(result.action, "ARCHIVED")
        product.refresh_from_db()
        self.assertTrue(product.is_archived)
        self.assertEqual(product.archived_by, self.user)
        self.assertIsNotNone(product.archived_at)
        self.assertEqual(sale.cd_items.get().cd_id, product_id)
        self.assertEqual(self.client.get(reverse("sales:detail", args=(sale.pk,))).status_code, 200)
        self.assertNotContains(self.client.get(reverse("nomenclature:list")), product.name)
        self.assertNotContains(self.client.get(reverse("pricing:list")), product.name)
        self.assertNotContains(self.client.get(reverse("warehouse:global_stock")), product.name)
        self.assertNotContains(self.client.get(reverse("warehouse:detail", args=(self.warehouse.pk,))), product.name)
        self.assertContains(self.client.get(reverse("nomenclature:cd_detail", args=(product_id,))), "Товар удалён из активной номенклатуры")
        self.assertEqual(ProductRemovalEvent.objects.get(product_id=product_id).action, ProductRemovalEvent.Action.ARCHIVE)
        self.assertEqual(remove_product(product_kind="cd", product_id=product_id, actor=self.user).action, "BLOCKED")

        workbook = load_workbook(BytesIO(generate_supplier_template(actor=self.user)))
        names = [cell.value for row in workbook.active for cell in row]
        self.assertNotIn(product.name, names)
        workbook.close()

    def test_archived_cannot_be_searched_or_used_by_direct_operations(self):
        product = self.cd("Архивная игра", sku="ARCHIVE-1", avito_price=Decimal("100"))
        self.sale_history(product)
        remove_product(product_kind="cd", product_id=product.pk, actor=self.user)
        response = self.client.get(reverse("supplies:autocomplete"), {"q": "ARCHIVE-1", "context": "sale"})
        self.assertEqual(response.json()["results"], [])
        with self.assertRaises(ValidationError):
            create_sale(
                actor=self.user, warehouse_id=self.warehouse.pk,
                price_type=Sale.PriceType.RETAIL, sale_type=Sale.SaleType.RETAIL,
                payment_method=Sale.PaymentMethod.BANK_ACCOUNT,
                lines=[{"product_type": "cd", "product_id": product.pk, "quantity": 1}],
            )
        with self.assertRaises(ValidationError):
            accept_supply(
                accepted_by=self.user, warehouse_id=self.warehouse.pk,
                lines=[{"product_type": "cd", "product_id": product.pk, "supplier_id": self.supplier.pk,
                        "quantity": 1, "purchase_unit_cost": "10"}],
            )
        with self.assertRaises(ValidationError):
            create_transfer(
                actor=self.user, source_warehouse_id=self.warehouse.pk,
                destination_warehouse_id=self.other_warehouse.pk,
                lines=[{"product_type": "cd", "product_id": product.pk, "quantity": 1}],
            )
        with self.assertRaises(ValidationError):
            transfer_many_to_consignment(
                actor=self.user, warehouse_id=self.warehouse.pk,
                platform_id=self.sales_platform.pk,
                lines=[{"product_type": "cd", "product_id": product.pk, "quantity": 1,
                        "receivable_per_unit": "100"}],
            )

    def test_cancelled_supply_history_remains_readable_after_archive(self):
        product = self.cd("Историческая поставка")
        supply = accept_supply(
            accepted_by=self.user, warehouse_id=self.warehouse.pk,
            lines=[{"product_type": "cd", "product_id": product.pk, "supplier_id": self.supplier.pk,
                    "quantity": 1, "purchase_unit_cost": "10"}],
        )
        cancel_supply(actor=self.user, supply_id=supply.pk, comment="Возврат поставки")
        self.assertEqual(evaluate_product_removal(product).action, "ARCHIVED")
        remove_product(product_kind="cd", product_id=product.pk, actor=self.user)
        self.assertTrue(CD.objects.get(pk=product.pk).is_archived)
        self.assertEqual(supply.cd_items.get().product_id, product.pk)
        self.assertEqual(self.client.get(reverse("supplies:detail", args=(supply.pk,))).status_code, 200)

    def test_delete_endpoint_requires_post_and_permission_and_admin_cannot_bypass(self):
        product = self.cd()
        url = reverse("nomenclature:product_delete", args=("cd", product.pk))
        self.assertEqual(self.client.get(url).status_code, 405)
        worker = get_user_model().objects.create_user("no-delete", password="password")
        worker.user_permissions.add(Permission.objects.get(codename="view_nomenclature"))
        self.client.force_login(worker)
        self.assertEqual(self.client.post(url).status_code, 403)
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(reverse("admin:catalog_cd_delete", args=(product.pk,)), {"post": "yes"}).status_code, 403)
        self.assertTrue(CD.objects.filter(pk=product.pk).exists())

    def test_tech_hard_delete_uses_same_rules(self):
        tech = Tech.objects.create(name="Пустая техника", brand=self.brand, product_type=self.product_type)
        tech_id = tech.pk
        result = remove_product(product_kind="tech", product_id=tech.pk, actor=self.user)
        self.assertEqual(result.action, "HARD_DELETED")
        self.assertFalse(Tech.objects.filter(pk=tech_id).exists())
