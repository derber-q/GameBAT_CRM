from decimal import Decimal

from cryptography.fernet import Fernet
from django.test import TestCase, override_settings
from django.urls import reverse

from catalog.models import Brand, CD, Platform, ProductType, Tech
from warehouse.models import CDWarehouseStock, TechWarehouseStock, Warehouse
from .catalogue import visible_product_rows
from .models import StorefrontSettings, WholesaleContact, StorefrontProduct, StorefrontNews
from .templatetags.resource_format import rubles
from .security import issue_link


@override_settings(RESOURCE_TOKEN_ENCRYPTION_KEY=Fernet.generate_key().decode())
class RefinementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.warehouse = Warehouse.objects.first()
        StorefrontSettings.objects.update_or_create(pk=1, defaults={"warehouse": cls.warehouse})
        cls.platform = Platform.objects.create(name="Refinement PS5")
        cls.brand = Brand.objects.create(name="Refinement Sony")
        cls.product_type, _ = ProductType.objects.get_or_create(name="Геймпад")
        cls.cd = CD.objects.create(name="Игра & + Кириллица", platform=cls.platform, wholesale_price=Decimal("1000.25"))
        cls.tech = Tech.objects.create(name="Контроллер", brand=cls.brand, product_type=cls.product_type, wholesale_price=Decimal("900"))
        CDWarehouseStock.objects.create(warehouse=cls.warehouse, cd=cls.cd, quantity=5)
        TechWarehouseStock.objects.create(warehouse=cls.warehouse, tech=cls.tech, quantity=3)
        contact = WholesaleContact.objects.create(name="Проверка", phone="+79990000000")
        _, cls.token = issue_link(contact, None)

    def setUp(self):
        self.client.get(reverse("resource_storefront:access", args=[self.token]))

    def test_platform_excludes_tech(self):
        self.assertEqual([r["kind"] for r in visible_product_rows(platform=str(self.platform.pk))], ["cd"])

    def test_unicode_search(self):
        self.assertEqual(len(visible_product_rows(query="игра & + кириллица")), 1)

    def test_invalid_price_is_explained(self):
        response = self.client.get(reverse("resource_storefront:catalogue"), {"price_min": "NaN"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Введите корректную цену")

    def catalogue(self, **params):
        return self.client.get(reverse("resource_storefront:catalogue"), params, follow=True)

    def test_invalid_values_do_not_crash_or_expose_products(self):
        for params in ({"platform": "nope"}, {"brand": "999999999999999999999999999999"},
                       {"category": "bogus"}, {"sort": "sql"}, {"price_min": "-1"},
                       {"price_max": "Infinity"}, {"price_min": "2000", "price_max": "1000"}):
            with self.subTest(params=params):
                response = self.catalogue(**params)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["filter_form"].errors)
                self.assertEqual(response.context["page_obj"].paginator.count, 0)

    def test_price_inclusive_and_zero_bound(self):
        self.assertEqual(self.catalogue(price_min="1000.25", price_max="1000.25").context["page_obj"].paginator.count, 1)
        self.assertEqual(self.catalogue(price_max="0").context["page_obj"].paginator.count, 0)
        self.assertEqual(self.catalogue(price_min="900").context["page_obj"].paginator.count, 2)
        self.assertEqual(self.catalogue(price_min="1 000,25", price_max="1\u00a0000,25").context["page_obj"].paginator.count, 1)

    def test_tech_brand_type_intersection_and_category_mapping(self):
        response = self.catalogue(category="gamepads", brand=str(self.brand.pk), product_type=str(self.product_type.pk))
        self.assertEqual([row["product"] for row in response.context["page_obj"]], [self.tech])
        self.assertEqual(self.catalogue(category="consoles").context["page_obj"].paginator.count, 0)

    def test_switch_category_clears_inapplicable_fields_and_page(self):
        response = self.catalogue(category="cd", brand=str(self.brand.pk), product_type=str(self.product_type.pk), page=10, q="игра", sort="price_desc")
        self.assertEqual(response.context["page_obj"].number, 1)
        self.assertEqual(response.context["query"]["brand"], "")
        self.assertContains(response, 'value="price_desc" selected')
        self.assertContains(response, 'value="игра"')
        self.assertNotIn("page=", response.redirect_chain[-1][0])

    def test_numeric_sort_and_newest_uses_slot_timestamp(self):
        self.assertEqual([r["product"] for r in self.catalogue(sort="price").context["page_obj"]], [self.tech, self.cd])
        self.assertEqual([r["product"] for r in self.catalogue(sort="price_desc").context["page_obj"]], [self.cd, self.tech])
        StorefrontProduct.objects.create(placement="new", tech=self.tech)
        self.assertEqual(self.catalogue(sort="newest").context["page_obj"][0]["product"], self.tech)

    def test_new_arrivals_obeys_category_filters(self):
        StorefrontProduct.objects.create(placement="new", tech=self.tech)
        StorefrontProduct.objects.create(placement="new", cd=self.cd)
        response = self.client.get(reverse("resource_storefront:new"), {"category": "cd"})
        self.assertEqual([row["kind"] for row in response.context["page_obj"]], ["cd"])

    def test_pagination_preserves_search_and_has_single_page_parameter(self):
        from urllib.parse import parse_qs, urlsplit
        for index in range(14):
            product = CD.objects.create(name=f"Игра & + {index}", platform=self.platform, wholesale_price=1000)
            CDWarehouseStock.objects.create(warehouse=self.warehouse, cd=product, quantity=1)
        response = self.catalogue(category="cd", q="игра & +", sort="price_desc", page=2)
        self.assertEqual(response.context["page_obj"].paginator.count, 15)
        for item in response.context["pagination"]:
            params = parse_qs(urlsplit(item["url"]).query)
            self.assertEqual(len(params["page"]), 1)
            self.assertEqual(params["q"], ["игра & +"])
            self.assertEqual(params["sort"], ["price_desc"])
        self.assertNotContains(response, 'name="page"')

    def test_stock_visibility_and_filter_choices_are_live(self):
        stock = TechWarehouseStock.objects.get(tech=self.tech, warehouse=self.warehouse)
        stock.quantity = 0
        stock.save()
        response = self.catalogue()
        self.assertEqual(response.context["page_obj"].paginator.count, 1)
        self.assertFalse(response.context["filters"]["brands"].exists())
        self.assertEqual(self.client.get(reverse("resource_storefront:product", args=["tech", self.tech.pk])).status_code, 404)

    def test_repeated_addition_never_exceeds_stock(self):
        for _ in range(2):
            self.client.post(reverse("resource_storefront:cart_add"), {"kind": "tech", "product_id": self.tech.pk, "quantity": 2})
        self.assertEqual(self.client.session["resource_cart"][f"tech:{self.tech.pk}"], 3)

    def test_home_real_cms_blocks_and_no_fake_content(self):
        response = self.client.get(reverse("resource_storefront:home"))
        self.assertContains(response, 'class="rs-category-copy"', count=4)
        self.assertNotContains(response, "rs-editor-hints")
        self.assertNotContains(response, "Все новинки")
        StorefrontProduct.objects.create(placement="new", cd=self.cd)
        StorefrontNews.objects.create(title="Не опубликовано", slug="draft", status="draft")
        response = self.client.get(reverse("resource_storefront:home"))
        self.assertContains(response, "Все новинки")
        self.assertContains(response, "rs-button-outline")
        self.assertNotContains(response, "Не опубликовано")

    def test_localized_price(self):
        self.assertEqual(rubles(Decimal("69000.00")), "69\u00a0000")
        self.assertEqual(rubles(Decimal("1000.25")), "1\u00a0000,25")

    def test_pages_render_without_encoding_damage_or_duplicate_ids(self):
        from html.parser import HTMLParser
        class IDs(HTMLParser):
            def __init__(self):
                super().__init__()
                self.ids = []
            def handle_starttag(self, tag, attrs):
                self.ids.extend(v for k, v in attrs if k == "id")
        self.client.post(reverse("resource_storefront:cart_add"), {"kind": "cd", "product_id": self.cd.pk})
        for url in (reverse("resource_storefront:home"), reverse("resource_storefront:catalogue"),
                    reverse("resource_storefront:product", args=["cd", self.cd.pk]), reverse("resource_storefront:cart")):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, "???")
            parser = IDs()
            parser.feed(response.content.decode())
            self.assertEqual(len(parser.ids), len(set(parser.ids)))
