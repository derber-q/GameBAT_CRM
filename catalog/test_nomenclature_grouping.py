"""Эталонная иерархия номенклатуры и сохранение строк документов."""
from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from .nomenclature_grouping import get_nomenclature_grouping, nomenclature_product_groups


def reference(pk, name):
    return SimpleNamespace(pk=pk, name=name)


def product(pk, name, *, platform=None, series=None, brand=None, product_type=None):
    return SimpleNamespace(
        pk=pk, name=name, platform=platform, platform_id=platform.pk if platform else None,
        game_series=series, brand=brand, brand_id=brand.pk if brand else None,
        product_type=product_type, product_type_id=product_type.pk if product_type else None,
    )


class NomenclatureGroupingTests(SimpleTestCase):
    def test_excel_groups_cd_only_by_platform_and_keeps_page_series_groups(self):
        sony = reference(1, "Sony")
        gamepad, console = reference(1, "Геймпад"), reference(2, "Игровая консоль")
        white = product(1, "Геймпад PS5 Белый (Original White)", brand=sony, product_type=gamepad)
        edge = product(2, "Геймпад Dualsense Edge", brand=sony, product_type=gamepad)
        ps5 = product(3, "PS5 Console", brand=sony, product_type=console)
        ns, ns2 = reference(1, "Nintendo Switch"), reference(2, "Nintendo Switch 2")
        alpha, zelda = reference(1, "Assassin's Creed"), reference(2, "Zelda")
        cds = [
            product(10, "AAA без серии", platform=ns),
            product(11, "A Zelda", platform=ns, series=zelda),
            product(12, "Z Assassin", platform=ns, series=alpha),
            product(13, "B Assassin", platform=ns, series=alpha),
            product(14, "A Switch 2", platform=ns2, series=zelda),
        ]
        groups = nomenclature_product_groups([edge, white, ps5], list(reversed(cds)))
        self.assertEqual([(kind, title, [p.pk for p in items]) for kind, title, items in groups], [
            ("tech", "Tech · Sony · Игровая консоль", [3]),
            ("tech", "Tech · Sony · Геймпад", [1, 2]),
            ("cd", "CD · Платформа: Nintendo Switch 2", [14]),
            ("cd", "CD · Платформа: Nintendo Switch", [11, 10, 13, 12]),
        ])
        grouping = get_nomenclature_grouping([edge, white, ps5], cds)
        self.assertEqual(grouping["tech_brand_groups"][0]["count"], 3)
        ns_group = next(group for platform, group in grouping['cd_groups'] if platform.pk == ns.pk)
        self.assertEqual(ns_group['count'], 4)
        self.assertEqual([
            (series.name if series else None, [item.pk for item in items])
            for series, items in ns_group['series_groups']
        ], [("Assassin's Creed", [13, 12]), ("Zelda", [11]), (None, [10])])

    def test_duplicate_distribution_rows_and_missing_references_are_preserved(self):
        item = product(1, "Товар без справочников")
        first = SimpleNamespace(product=item, quantity=2, price=Decimal("77.123456"))
        second = SimpleNamespace(product=item, quantity=3, price=Decimal("80.00"))
        groups = nomenclature_product_groups([second, first], [], product_of=lambda row: row.product)
        self.assertEqual(groups[0][:2], ("tech", "Tech · Без бренда · Без типа"))
        self.assertEqual(groups[0][2], [second, first])
        self.assertIs(groups[0][2][0], second)
        self.assertEqual([(row.quantity, row.price) for row in groups[0][2]], [
            (3, Decimal("80.00")), (2, Decimal("77.123456")),
        ])
        cd_groups = nomenclature_product_groups([], [item])
        self.assertEqual(cd_groups[0][1], "CD · Платформа: Без платформы")
        self.assertEqual(cd_groups[0][2], [item])
        cd_rows = nomenclature_product_groups([], [second, first], product_of=lambda row: row.product)
        self.assertEqual(cd_rows[0][2], [second, first])
