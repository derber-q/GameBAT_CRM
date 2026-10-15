from io import BytesIO
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from openpyxl import load_workbook

from accounts.models import User
from catalog.models import Brand, CD, Platform, ProductType, Tech
from partners.models import Supplier
from pricing.models import SupplierCDPrice, SupplierTechPrice

from .excel import (
    MAIN_SHEET, META_SHEET, generate_supplier_template, import_supplier_price,
    import_supplier_price_files,
)
from .tests import uploaded, workbook_bytes


class SupplierTemplateImportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser("supplier-admin", password="StrongAdmin!123")
        cls.supplier = Supplier.objects.create(
            name="M", letter="M", highlight_color="#37A7BA", legal_entity="M", phone_1="1",
        )
        cls.cd = CD.objects.create(platform=Platform.objects.create(name="PS5"), name="Игра", sku="CD-1")
        cls.tech = Tech.objects.create(
            brand=Brand.objects.create(name="Sony"),
            product_type=ProductType.objects.create(name="Консоли"), name="Консоль", sku="TECH-1",
        )

    def template(self, kind):
        return load_workbook(BytesIO(generate_supplier_template(actor=self.user, product_kind=kind)))

    def fill(self, workbook, kind, product_id, price):
        sheet = workbook[MAIN_SHEET]
        row = next(
            row for row in range(2, sheet.max_row + 1)
            if sheet.cell(row, 1).value == kind.upper() and sheet.cell(row, 2).value == product_id
        )
        sheet.cell(row, 6, price)
        return row

    def import_file(self, workbook, kind):
        return import_supplier_price(
            supplier_id=self.supplier.pk, upload=uploaded(workbook_bytes(workbook)),
            actor=self.user, product_kind=kind,
        )

    def test_old_files_update_both_types_and_preserve_missing_new_products(self):
        workbooks = {kind: self.template(kind) for kind in ("cd", "tech")}
        self.fill(workbooks["cd"], "cd", self.cd.pk, 100.25)
        self.fill(workbooks["tech"], "tech", self.tech.pk, 200)
        new_cd = CD.objects.create(platform=self.cd.platform, name="Новая игра", sku="CD-2")
        new_tech = Tech.objects.create(
            brand=self.tech.brand, product_type=self.tech.product_type, name="Новая консоль", sku="TECH-2",
        )
        SupplierCDPrice.objects.create(supplier=self.supplier, cd=new_cd, price=77)
        SupplierTechPrice.objects.create(supplier=self.supplier, tech=new_tech, price=88)
        self.client.force_login(self.user)
        response = self.client.post(reverse("price:supplier_upload"), {
            "supplier": self.supplier.pk,
            **{f"{kind}_file": uploaded(workbook_bytes(book), f"M-{kind}.xlsx") for kind, book in workbooks.items()},
        })
        self.assertRedirects(response, reverse("price:imports"))
        self.assertEqual(SupplierCDPrice.objects.get(supplier=self.supplier, cd=self.cd).price, Decimal("100.25"))
        self.assertEqual(SupplierTechPrice.objects.get(supplier=self.supplier, tech=self.tech).price, Decimal("200"))
        self.assertEqual(SupplierCDPrice.objects.get(supplier=self.supplier, cd=new_cd).price, Decimal("77"))
        self.assertEqual(SupplierTechPrice.objects.get(supplier=self.supplier, tech=new_tech).price, Decimal("88"))

    def test_archived_rows_with_or_without_price_are_skipped(self):
        for kind, product, price_model, field in (
            ("cd", self.cd, SupplierCDPrice, "cd"), ("tech", self.tech, SupplierTechPrice, "tech"),
        ):
            for price in (None, 99):
                with self.subTest(kind=kind, price=price):
                    product.is_archived = False
                    product.save(update_fields=("is_archived",))
                    workbook = self.template(kind)
                    if price is not None:
                        self.fill(workbook, kind, product.pk, price)
                    offer, _ = price_model.objects.get_or_create(
                        supplier=self.supplier, **{field: product}, defaults={"price": 77},
                    )
                    product.is_archived = True
                    product.save(update_fields=("is_archived",))
                    self.assertEqual(self.import_file(workbook, kind), 0)
                    offer.refresh_from_db()
                    self.assertEqual(offer.price, Decimal("77"))

    def test_blank_price_removes_only_offer_present_in_file(self):
        workbook = self.template("cd")
        SupplierCDPrice.objects.create(supplier=self.supplier, cd=self.cd, price=77)
        SupplierTechPrice.objects.create(supplier=self.supplier, tech=self.tech, price=88)
        self.assertEqual(self.import_file(workbook, "cd"), 0)
        self.assertFalse(SupplierCDPrice.objects.filter(supplier=self.supplier).exists())
        self.assertEqual(SupplierTechPrice.objects.get(supplier=self.supplier).price, Decimal("88"))

    def test_hidden_product_absent_from_file_keeps_price(self):
        self.cd.exclude_from_supplier_template = True
        self.cd.save(update_fields=("exclude_from_supplier_template",))
        workbook = self.template("cd")
        offer = SupplierCDPrice.objects.create(supplier=self.supplier, cd=self.cd, price=77)
        self.assertEqual(self.import_file(workbook, "cd"), 0)
        offer.refresh_from_db()
        self.assertEqual(offer.price, Decimal("77"))

    def test_hidden_product_present_in_old_file_is_updated(self):
        workbook = self.template("cd")
        self.fill(workbook, "cd", self.cd.pk, 99)
        self.cd.exclude_from_supplier_template = True
        self.cd.save(update_fields=("exclude_from_supplier_template",))
        self.assertEqual(self.import_file(workbook, "cd"), 1)
        self.assertEqual(SupplierCDPrice.objects.get(supplier=self.supplier).price, Decimal("99"))

    def test_row_shift_or_identity_change_is_rejected_without_changing_price(self):
        offer = SupplierCDPrice.objects.create(supplier=self.supplier, cd=self.cd, price=77)
        for changed_column, changed_value in ((1, "TECH"), (2, self.cd.pk + 1), (3, "OTHER-SKU")):
            with self.subTest(column=changed_column):
                workbook = self.template("cd")
                row = self.fill(workbook, "cd", self.cd.pk, 99)
                workbook[MAIN_SHEET].cell(row, changed_column, changed_value)
                with self.assertRaisesMessage(ValidationError, "не соответствует техническому листу"):
                    self.import_file(workbook, "cd")
                offer.refresh_from_db()
                self.assertEqual(offer.price, Decimal("77"))

    def test_removed_metadata_or_added_unmapped_price_is_rejected(self):
        for mutation in ("metadata", "unmapped_price"):
            with self.subTest(mutation=mutation):
                workbook = self.template("cd")
                if mutation == "metadata":
                    meta = workbook[META_SHEET]
                    meta.delete_rows(meta.max_row)
                else:
                    sheet = workbook[MAIN_SHEET]
                    sheet.cell(sheet.max_row + 1, 6, 99)
                with self.assertRaisesMessage(ValidationError, "неполна"):
                    self.import_file(workbook, "cd")

    def test_unknown_product_is_rejected_even_with_blank_price(self):
        workbook = self.template("cd")
        sheet = workbook[MAIN_SHEET]
        row = self.fill(workbook, "cd", self.cd.pk, None)
        sheet.cell(row, 2, 999999)
        meta = workbook[META_SHEET]
        meta.cell(meta.max_row, 3, 999999)
        with self.assertRaisesMessage(ValidationError, "товар не найден"):
            self.import_file(workbook, "cd")

    def test_second_file_error_rolls_back_first_file(self):
        offer = SupplierCDPrice.objects.create(supplier=self.supplier, cd=self.cd, price=77)
        cd_book, tech_book = self.template("cd"), self.template("tech")
        self.fill(cd_book, "cd", self.cd.pk, 99)
        self.fill(tech_book, "tech", self.tech.pk, -1)
        with self.assertRaisesMessage(ValidationError, "больше нуля"):
            import_supplier_price_files(supplier_id=self.supplier.pk, actor=self.user, uploads={
                "cd": uploaded(workbook_bytes(cd_book)), "tech": uploaded(workbook_bytes(tech_book)),
            })
        offer.refresh_from_db()
        self.assertEqual(offer.price, Decimal("77"))
        self.assertFalse(SupplierTechPrice.objects.filter(supplier=self.supplier).exists())

    def test_legacy_combined_template_updates_only_selected_type(self):
        workbook = self.template(None)
        self.fill(workbook, "cd", self.cd.pk, 99)
        self.fill(workbook, "tech", self.tech.pk, 100)
        offer = SupplierTechPrice.objects.create(supplier=self.supplier, tech=self.tech, price=88)
        CD.objects.create(platform=self.cd.platform, name="Новая игра", sku="CD-2")
        self.assertEqual(self.import_file(workbook, "cd"), 1)
        self.assertEqual(SupplierCDPrice.objects.get(supplier=self.supplier).price, Decimal("99"))
        offer.refresh_from_db()
        self.assertEqual(offer.price, Decimal("88"))
