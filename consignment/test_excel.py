"""Проверки выгрузки реализации: права, реальные остатки, партии и отсутствие затрат."""
from decimal import Decimal
from io import BytesIO
from zipfile import ZipFile

from django.contrib.auth.models import Group, Permission
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from openpyxl import load_workbook

from accounts.models import User
from catalog.models import Brand, CD, Platform, ProductType, Tech
from partners.models import SalesPlatform
from warehouse.models import CDWarehouseStock, TechWarehouseStock, Warehouse
from .models import CDConsignmentStock, TechConsignmentStock
from .services import record_consignment_sale, return_from_consignment, transfer_to_consignment, update_consignment_reward


class ConsignmentExcelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser("excel-admin", password="StrongAdmin!123")
        cls.viewer = User.objects.create_user("excel-viewer")
        cls.warehouse = Warehouse.objects.create(name="Склад")
        cls.shop = SalesPlatform.objects.create(name="Магазин А", address="А", legal_entity="А", phone_1="1")
        cls.other = SalesPlatform.objects.create(name="Магазин Б", address="Б", legal_entity="Б", phone_1="2")
        cls.empty = SalesPlatform.objects.create(name="Пустая площадка", address="В", legal_entity="В", phone_1="3")
        cls.ps5 = Platform.objects.create(name="PlayStation 5")
        cls.ps4 = Platform.objects.create(name="PlayStation 4")
        cls.cd = CD.objects.create(platform=cls.ps5, name="Зета", sku="000123", barcode="123", cost="9876543.21")
        cls.alpha = CD.objects.create(platform=cls.ps5, name="Альфа", sku="CD-A", cost="8765432.10")
        cls.old = CD.objects.create(platform=cls.ps4, name="Игра PS4", sku="CD-4", cost="7654321.09")
        brand = Brand.objects.create(name="Sony")
        cls.tech = Tech.objects.create(brand=brand, product_type=ProductType.objects.create(name="Геймпад"),
                                      name="Контроллер", sku="TECH-C", cost="6543210.98")
        cls.console = Tech.objects.create(brand=brand, product_type=ProductType.objects.create(name="Консоль"),
                                         name="Консоль", sku="TECH-S", cost="5432109.87")
        for item in (cls.cd, cls.alpha, cls.old):
            CDWarehouseStock.objects.create(warehouse=cls.warehouse, cd=item, quantity=100)
        for item in (cls.tech, cls.console):
            TechWarehouseStock.objects.create(warehouse=cls.warehouse, tech=item, quantity=100)
        cls.cd_stock = cls.transfer(cls.cd, 4, "123.45")
        alpha_stock = cls.transfer(cls.alpha, 2, "1")
        update_consignment_reward(actor=cls.admin, product_type="cd", stock_id=alpha_stock.pk, value="0")
        cls.transfer(cls.old, 1, "7.89")
        cls.tech_stock = cls.transfer(cls.tech, 3, "678.91")
        cls.transfer(cls.console, 1, "99.99")
        cls.transfer(cls.cd, 20, "777.77", platform=cls.other)

    @classmethod
    def transfer(cls, product, quantity, reward, platform=None):
        return transfer_to_consignment(
            actor=cls.admin, warehouse_id=cls.warehouse.pk, platform_id=(platform or cls.shop).pk,
            product_type="cd" if isinstance(product, CD) else "tech", product_id=product.pk,
            quantity=quantity, reward_per_unit=reward,
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def export(self, sales_platform=None, **params):
        return self.client.get(reverse("consignment:platform_export", args=((sales_platform or self.shop).pk,)), params)

    def workbook(self, response):
        self.assertEqual(response.status_code, 200)
        return load_workbook(BytesIO(response.content), data_only=False)

    def products(self, sheet):
        return [row for row in sheet.iter_rows(values_only=True)
                if isinstance(row[2], (int, float)) and row[1] is not None]

    def test_buttons_on_all_platform_panels_and_separate_page_even_with_empty_search(self):
        response = self.client.get(reverse("consignment:list"), {"q": "Ничего не найдено"})
        self.assertContains(response, "Скачать Excel", count=3)
        for platform in (self.shop, self.other, self.empty):
            url = reverse("consignment:platform_export", args=(platform.pk,))
            self.assertContains(response, f'href="{url}"')
        page = self.client.get(reverse("consignment:platform", args=(self.shop.pk,)))
        self.assertContains(page, "Скачать Excel", count=1)
        self.assertNotContains(page, reverse("consignment:platform_export", args=(self.other.pk,)))

    def test_download_mime_filename_freshness_and_request_method(self):
        response = self.export()
        self.assertEqual(response["Content-Type"], "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        self.assertRegex(response["Content-Disposition"], rf'attachment; filename="realization_{self.shop.pk}_\d{{4}}-\d{{2}}-\d{{2}}\.xlsx"')
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("private", response["Cache-Control"])
        self.workbook(response)
        url = reverse("consignment:platform_export", args=(self.shop.pk,))
        self.assertEqual(self.client.post(url).status_code, 405)
        self.assertEqual(self.client.get(reverse("consignment:platform_export", args=(999999,))).status_code, 404)

    def test_only_selected_platform_current_cd_and_tech_and_decimal_totals(self):
        sheet = self.workbook(self.export()).active
        self.assertEqual(self.products(sheet), [
            ("Игра PS4", "CD-4", 1, 7.89, 7.89),
            ("Альфа", "CD-A", 2, 0, 0),
            ("Зета", "000123", 4, 123.45, 493.8),
            ("Контроллер", "TECH-C", 3, 678.91, 2036.73),
            ("Консоль", "TECH-S", 1, 99.99, 99.99),
        ])
        self.assertEqual(sheet.cell(sheet.max_row, 3).value, 11)
        expected = Decimal("7.89") + 4 * Decimal("123.45") + 3 * Decimal("678.91") + Decimal("99.99")
        self.assertEqual(Decimal(str(sheet.cell(sheet.max_row, 5).value)), expected)
        other = self.workbook(self.export(self.other)).active
        self.assertEqual(self.products(other), [("Зета", "000123", 20, 777.77, 15555.4)])

    def test_grouping_sorting_headers_and_numeric_formats(self):
        sheet = self.workbook(self.export()).active
        labels = [sheet.cell(area.min_row, 1).value for area in sorted(sheet.merged_cells.ranges, key=lambda area: area.min_row)]
        headings = [label for label in labels if label in (
            "CD · Диски", "PlayStation 4", "PlayStation 5", "Tech · Техника", "Геймпад", "Консоль",
        )]
        self.assertEqual(headings, ["CD · Диски", "PlayStation 4", "PlayStation 5", "Tech · Техника", "Геймпад", "Консоль"])
        self.assertIn(self.shop.name, sheet["A1"].value)
        self.assertRegex(sheet["A2"].value, r"Дата формирования: \d{2}\.\d{2}\.\d{4} \d{2}:\d{2}:\d{2}")
        self.assertEqual([cell.value for cell in sheet[4]], [
            "Наименование", "Артикул", "Количество", "Вознаграждение за единицу, ₽", "Общая сумма, ₽",
        ])
        self.assertEqual(sheet.freeze_panes, "A5")
        for row in sheet:
            if row[1].value == "000123":
                self.assertEqual(row[1].data_type, "s")
                self.assertEqual(row[2].number_format, "0")
                self.assertIn("₽", row[3].number_format)
                self.assertIn("₽", row[4].number_format)
                self.assertTrue(row[0].alignment.wrap_text)

    def test_export_ignores_all_interface_filters_and_pagination(self):
        sheet = self.workbook(self.export(q="не существует", page=99, platform=999999,
                                          product_type=999999, kind="tech")).active
        self.assertEqual(len(self.products(sheet)), 5)

    def test_distinct_lots_and_warehouses_are_not_merged_or_multiplied_by_barcodes(self):
        from catalog.product_identifiers import add_product_barcode
        add_product_barcode(actor=self.admin, product_kind="cd", product_id=self.cd.pk, value="001999")
        CDConsignmentStock.objects.create(platform=self.shop, warehouse=self.warehouse, cd=self.cd,
                                          lot_key="historical:1", quantity=2, receivable_per_unit="222.22")
        second = Warehouse.objects.create(name="Другой склад")
        CDConsignmentStock.objects.create(platform=self.shop, warehouse=second, cd=self.cd,
                                          quantity=1, receivable_per_unit="123.45")
        rows = [row for row in self.products(self.workbook(self.export()).active) if row[1] == self.cd.sku]
        self.assertCountEqual(rows, [("Зета", "000123", 4, 123.45, 493.8),
                                    ("Зета", "000123", 1, 123.45, 123.45),
                                    ("Зета", "000123", 2, 222.22, 444.44)])

    def test_zero_and_fully_sold_or_returned_stocks_are_excluded(self):
        for product, kind, stock in ((self.cd, "cd", self.cd_stock), (self.tech, "tech", self.tech_stock)):
            record_consignment_sale(actor=self.admin, product_type=kind, stock_id=stock.pk,
                                    quantity=stock.quantity, payment_method="bank_account")
        stock = CDConsignmentStock.objects.get(cd=self.old, platform=self.shop)
        return_from_consignment(actor=self.admin, warehouse_id=self.warehouse.pk, platform_id=self.shop.pk,
                                product_type="cd", product_id=self.old.pk, quantity=1, stock_id=stock.pk)
        remaining = {row[1] for row in self.products(self.workbook(self.export()).active)}
        self.assertEqual(remaining, {"CD-A", "TECH-S"})

    def test_new_download_reflects_partial_sale_return_and_reward_edit(self):
        self.assertEqual(len(self.products(self.workbook(self.export()).active)), 5)
        record_consignment_sale(actor=self.admin, product_type="cd", stock_id=self.cd_stock.pk,
                                quantity=1, payment_method="bank_account")
        return_from_consignment(actor=self.admin, warehouse_id=self.warehouse.pk, platform_id=self.shop.pk,
                                product_type="tech", product_id=self.tech.pk, quantity=1, stock_id=self.tech_stock.pk)
        update_consignment_reward(actor=self.admin, product_type="cd", stock_id=self.cd_stock.pk, value="111.11")
        rows = {row[1]: row for row in self.products(self.workbook(self.export()).active)}
        self.assertEqual(rows["000123"][2:], (3, 111.11, 333.33))
        self.assertEqual(rows["TECH-C"][2:], (2, 678.91, 1357.82))

    def test_no_cost_profit_hidden_data_formulas_or_writes(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.export()
        for query in queries:
            sql = query["sql"].lower()
            self.assertNotRegex(sql, r"\b(insert|update|delete|replace)\b")
            self.assertNotIn('"cost"', sql)
            self.assertNotIn('"unit_cost"', sql)
            self.assertNotIn("unit_cost_snapshot", sql)
        workbook = self.workbook(response)
        self.assertEqual(workbook.sheetnames, ["Реализация"])
        self.assertFalse(workbook.defined_names)
        for sheet in workbook:
            self.assertEqual(sheet.sheet_state, "visible")
            self.assertFalse(any(column.hidden for column in sheet.column_dimensions.values()))
            self.assertFalse(any(row.hidden for row in sheet.row_dimensions.values()))
            self.assertFalse(sheet._charts)
            self.assertFalse(sheet._images)
            for row in sheet:
                for cell in row:
                    self.assertNotEqual(cell.data_type, "f")
                    self.assertIsNone(cell.comment)
        with ZipFile(BytesIO(response.content)) as archive:
            payload = "\n".join(archive.read(name).decode("utf-8") for name in archive.namelist()).casefold()
        for forbidden in ("себестоимость", "закупочная", "прибыль", "маржинальность", "наценка", "unit_cost",
                          "9876543.21", "8765432.1", "7654321.09", "6543210.98", "5432109.87"):
            self.assertNotIn(forbidden, payload)

    def test_empty_platform_has_headers_message_and_zero_totals(self):
        sheet = self.workbook(self.export(self.empty)).active
        self.assertEqual(sheet["A5"].value, "Нет товаров на реализации")
        self.assertEqual(sheet.cell(sheet.max_row, 1).value, "Итого")
        self.assertEqual(sheet.cell(sheet.max_row, 3).value, 0)
        self.assertEqual(sheet.cell(sheet.max_row, 5).value, 0)
        self.assertEqual(self.products(sheet), [])

    def test_permissions_anonymous_forbidden_and_type_scoped_including_groups(self):
        self.client.logout()
        self.assertEqual(self.export().status_code, 302)
        self.client.force_login(self.viewer)
        self.assertEqual(self.export().status_code, 403)
        for kind, expected in (("cd", {"000123", "CD-A", "CD-4"}), ("tech", {"TECH-C", "TECH-S"})):
            with self.subTest(kind=kind):
                group = Group.objects.create(name=f"Excel {kind}")
                group.permissions.add(Permission.objects.get(content_type__app_label="consignment",
                                                            codename=f"view_{kind}consignmentstock"))
                self.viewer.groups.set([group])
                self.client.force_login(self.viewer)
                rows = self.products(self.workbook(self.export()).active)
                self.assertEqual({row[1] for row in rows}, expected)
                self.assertContains(self.client.get(reverse("consignment:list")), "Скачать Excel", count=3)

    def test_user_text_is_exported_as_text_not_excel_formula(self):
        self.alpha.name = '=HYPERLINK("https://example.com","Игра")'
        self.alpha.sku = "=1+1"
        self.alpha.save(update_fields=("name", "sku"))
        rows = self.products(self.workbook(self.export()).active)
        row = next(row for row in rows if row[1] == "'=1+1")
        self.assertEqual(row[0], "'" + self.alpha.name)
