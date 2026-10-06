from io import BytesIO
from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase
from openpyxl import load_workbook

from accounts.models import User
from catalog.models import Brand, CD, Platform, ProductType, Tech
from warehouse.models import CDWarehouseStock, TechWarehouseStock, Warehouse

from .excel import HEADER_ROW, MAIN_SHEET, generate_retail_price_xlsx, generate_wholesale_price_xlsx
from .sony_gamepad_sorting import (
    BLACK,
    CAMOUFLAGE,
    GAME_THEMED,
    LIMITED,
    METALLIC,
    PS4,
    STANDARD_MATTE,
    TWO_TONE,
    UNKNOWN,
    WHITE,
    classify_sony_gamepad,
    normalize_product_name,
    sony_gamepad_sort_key,
)


def stub_product(name, pk=1):
    return SimpleNamespace(name=name, pk=pk)


class SonyGamepadClassificationTests(SimpleTestCase):
    def test_real_name_patterns_follow_required_category_order(self):
        cases = (
            ("PS4 DualShock Black", PS4),
            ("Геймпад PS5 Белый (Original White)", WHITE),
            ("Геймпад PS5 Черный (Midnight Black)", BLACK),
            ("Геймпад PS5 Камуфляж (Grey Camouflage)", CAMOUFLAGE),
            ("Геймпад PS5 Альпийский зеленый (Alpine Green)", STANDARD_MATTE),
            ("Геймпад PS5 HyperPop Зеленый (Remix Green)", TWO_TONE),
            ("Геймпад PS5 Бирюзовый Хром (Chroma Teal)", METALLIC),
            ("Геймпад PS5 Death Stranding 2", GAME_THEMED),
            ("Геймпад PS5 30th Anniversary Limited Edition", LIMITED),
        )

        for name, expected in cases:
            with self.subTest(name=name):
                self.assertEqual(classify_sony_gamepad(stub_product(name)), expected)
        self.assertEqual(
            [category.priority for _name, category in cases],
            sorted(category.priority for _name, category in cases),
        )

    def test_limited_wins_over_metallic_and_game_theme(self):
        self.assertEqual(
            classify_sony_gamepad(stub_product("Геймпад PS5 Chroma Limited Edition")),
            LIMITED,
        )
        self.assertEqual(
            classify_sony_gamepad(stub_product("Геймпад PS5 Astro Bot Limited Edition")),
            LIMITED,
        )

    def test_normalization_handles_case_spaces_hyphens_and_cyrillic(self):
        self.assertEqual(
            normalize_product_name("  ГЕЙМПАД---PS5   КАМУФЛЯЖ  "),
            "геймпад ps5 камуфляж",
        )
        self.assertEqual(
            classify_sony_gamepad(stub_product("PS5-GREY-CAMOUFLAGE")),
            CAMOUFLAGE,
        )

    def test_unknown_uses_safe_fallback_before_game_themed_and_limited(self):
        category = classify_sony_gamepad(stub_product("Геймпад Dualsense Edge"))
        self.assertEqual(category, UNKNOWN)
        self.assertGreater(category.priority, METALLIC.priority)
        self.assertLess(category.priority, GAME_THEMED.priority)
        self.assertLess(category.priority, LIMITED.priority)

    def test_ps4_has_one_category_and_keeps_stable_name_order(self):
        products = [
            stub_product("PS4 Dualshock White Glacier", 2),
            stub_product("PS4 DualShock Black", 1),
        ]
        self.assertTrue(all(classify_sony_gamepad(product) == PS4 for product in products))
        self.assertEqual(
            [product.name for product in sorted(products, key=sony_gamepad_sort_key)],
            ["PS4 DualShock Black", "PS4 Dualshock White Glacier"],
        )


class SonyGamepadExcelSortingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("sony-sort-admin", password="StrongAdmin!123")
        self.warehouse = Warehouse.objects.create(name="Sony sorting")
        self.sony = Brand.objects.create(name="Sony")
        self.other_brand = Brand.objects.create(name="Other Brand")
        self.gamepad = ProductType.objects.create(name="Геймпад")
        self.headset = ProductType.objects.create(name="Игровая гарнитура")

    def add_tech(self, name, *, brand=None, product_type=None):
        product = Tech.objects.create(
            brand=brand or self.sony,
            product_type=product_type or self.gamepad,
            name=name,
            avito_price=100,
            wholesale_price=90,
        )
        TechWarehouseStock.objects.create(warehouse=self.warehouse, tech=product, quantity=1)
        return product

    def exported_names(self, content, expected_names):
        workbook = load_workbook(BytesIO(content), data_only=False)
        sheet = workbook[MAIN_SHEET]
        names = [
            sheet.cell(row, 1).value
            for row in range(HEADER_ROW + 1, sheet.max_row + 1)
            if sheet.cell(row, 1).value in expected_names
        ]
        workbook.close()
        return names

    def test_retail_and_wholesale_share_order_without_loss_or_duplicates(self):
        expected = [
            "Геймпад Dualsense Edge",
            "PS4 DualShock Black",
            "Геймпад PS5 Белый (Original White)",
            "Геймпад PS5 Черный (Midnight Black)",
            "Геймпад PS5 Камуфляж (Grey Camouflage)",
            "Геймпад PS5 Альпийский зеленый (Alpine Green)",
            "Геймпад PS5 HyperPop Зеленый (Remix Green)",
            "Геймпад PS5 Бирюзовый Хром (Chroma Teal)",
            "Геймпад PS5 Death Stranding 2",
            "Геймпад PS5 Astro Bot Limited Edition",
        ]
        for name in reversed(expected):
            self.add_tech(name)

        retail, skipped = generate_retail_price_xlsx(
            warehouse_id=self.warehouse.pk,
            actor=self.user,
        )
        wholesale = generate_wholesale_price_xlsx(
            warehouse_id=self.warehouse.pk,
            actor=self.user,
        )

        self.assertEqual(skipped, 0)
        for content in (retail, wholesale):
            with self.subTest(export="retail" if content is retail else "wholesale"):
                names = self.exported_names(content, set(expected))
                self.assertEqual(names, expected)
                self.assertEqual(len(names), len(set(names)))

    def test_other_sony_types_other_brands_and_cd_keep_existing_name_order(self):
        sony_names = ["Limited Alpha Headset", "Zulu Headset"]
        other_brand_names = ["Limited Alpha Gamepad", "Zulu Gamepad"]
        for name in reversed(sony_names):
            self.add_tech(name, product_type=self.headset)
        for name in reversed(other_brand_names):
            self.add_tech(name, brand=self.other_brand)

        platform = Platform.objects.create(name="Test Platform")
        cd_names = ["Alpha CD", "Zulu CD"]
        for name in reversed(cd_names):
            product = CD.objects.create(
                platform=platform,
                name=name,
                avito_price=100,
                wholesale_price=90,
            )
            CDWarehouseStock.objects.create(warehouse=self.warehouse, cd=product, quantity=1)

        content, _skipped = generate_retail_price_xlsx(
            warehouse_id=self.warehouse.pk,
            actor=self.user,
        )
        all_names = set(sony_names + other_brand_names + cd_names)
        exported = self.exported_names(content, all_names)

        for unchanged_names in (sony_names, other_brand_names, cd_names):
            self.assertEqual(
                [name for name in exported if name in unchanged_names],
                unchanged_names,
            )
