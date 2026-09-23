from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from catalog.models import Brand, CD, Platform, ProductType, Tech
from partners.models import SalesPlatform, Supplier
from warehouse.models import Warehouse


class InternalPageSmokeTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("admin", password="StrongAdmin!123")
        platform = Platform.objects.create(name="PS5")
        brand = Brand.objects.create(name="Sony")
        product_type = ProductType.objects.create(name="Консоль")
        CD.objects.create(platform=platform, name="Игра", sku="CD-1", barcode="001")
        Tech.objects.create(brand=brand, product_type=product_type, name="Консоль", sku="T-1", barcode="002")
        Supplier.objects.create(
            name="Поставщик", letter="A", highlight_color="#37A7BA",
            legal_entity="ООО Поставщик", phone_1="+70000000000",
        )
        SalesPlatform.objects.create(
            name="Площадка", address="Адрес", legal_entity="ООО Площадка", phone_1="+70000000001"
        )
        self.warehouse = Warehouse.objects.get(name="Варфоломеева 265")
        Warehouse.objects.create(name="Резервный склад")
        self.client.force_login(self.admin)

    def test_primary_get_pages_render(self):
        urls = (
            reverse("catalog:warehouse"),
            reverse("warehouse:global_stock"),
            reverse("warehouse:detail", args=(self.warehouse.pk,)),
            reverse("warehouse:transfer_list"),
            reverse("warehouse:transfer_start"),
            reverse("warehouse:transfer_create", args=(self.warehouse.pk,)),
            reverse("cash:register", args=(self.warehouse.pk,)),
            reverse("cash:deposit", args=(self.warehouse.pk,)),
            reverse("cash:collect", args=(self.warehouse.pk,)),
            reverse("cash:safe_deposit", args=(self.warehouse.pk,)),
            reverse("cash:safe_collect", args=(self.warehouse.pk,)),
            reverse("cash:cash_to_safe", args=(self.warehouse.pk,)),
            reverse("cash:safe_to_cash", args=(self.warehouse.pk,)),
            reverse("pricing:list"),
            reverse("sales:list"),
            reverse("sales:create"),
            reverse("partners:list"),
            reverse("partners:create"),
            reverse("supplies:list"),
            reverse("supplies:create"),
            reverse("consignment:list"),
            reverse("consignment:transfer"),
            reverse("accounts:user_list"),
            reverse("accounts:staff_by_group"),
            reverse("accounts:permission_sets"),
            reverse("accounts:password_change"),
            reverse("admin:index"),
        )
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_admin_is_forced_to_light_theme(self):
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "admin/js/theme.js")
        self.assertNotContains(response, "theme-toggle")

    def test_navigation_brand_order_and_warehouse_dropdown(self):
        response = self.client.get(reverse("warehouse:global_stock"))
        html = response.content.decode()
        nav_html = html[html.index('<nav class="main-nav"'):html.index("</nav>")]
        labels = (
            "Продажа", "Номенклатура", "Склад", "Приход",
            "Перемещения", "Реализация", "Ценообразование", "stuf",
        )
        positions = [nav_html.index(f">{label}</a>") for label in labels]

        self.assertEqual(positions, sorted(positions))
        self.assertContains(response, '<span>Re<b>SOURCE</b></span>', html=True)
        self.assertNotContains(response, "GameBAT CRM")
        self.assertContains(response, 'class="nav-sale')
        self.assertContains(response, 'data-rate-symbol="USDT/RUB"')
        self.assertContains(response, 'data-rate-symbol="USDT/AED"')
        self.assertNotContains(response, 'data-rate-symbol="AED/RUB"')
        self.assertNotContains(response, 'data-rate-symbol="USD/AED"')

        warehouse_trigger = nav_html.index(">Склад</a>")
        menu_start = nav_html.index('<div class="nav-dropdown-menu">', warehouse_trigger)
        menu_end = nav_html.index("</div>", menu_start)
        warehouse_menu = nav_html[menu_start:menu_end]
        self.assertIn(">Общие остатки</a>", warehouse_menu)
        self.assertIn("Склад Варфоломеева 265", warehouse_menu)
        self.assertIn("Склад Резервный склад", warehouse_menu)
        self.assertNotIn(">Перемещения</a>", warehouse_menu)

        sales_trigger = nav_html.index(">Продажа</a>")
        sales_menu_start = nav_html.index('<div class="nav-dropdown-menu">', sales_trigger)
        sales_menu_end = nav_html.index("</div>", sales_menu_start)
        sales_menu = nav_html[sales_menu_start:sales_menu_end]
        self.assertIn(">Новая продажа</a>", sales_menu)
        self.assertIn(">Незавершённые продажи</a>", sales_menu)
        self.assertIn(">Завершённые продажи</a>", sales_menu)
        self.assertIn(">Отменённые продажи</a>", sales_menu)
        self.assertIn(">Касса</a>", sales_menu)

        stuf_trigger = nav_html.index(">stuf</a>")
        stuf_menu_start = nav_html.index('<div class="nav-dropdown-menu">', stuf_trigger)
        stuf_menu_end = nav_html.index("</div>", stuf_menu_start)
        stuf_menu = nav_html[stuf_menu_start:stuf_menu_end]
        self.assertIn(">Статистика</a>", stuf_menu)
        self.assertIn(">Пользователи</a>", stuf_menu)
        self.assertIn(">Поставщики</a>", stuf_menu)
        sales_platform = SalesPlatform.objects.get(name="Площадка")
        self.assertContains(
            response,
            f'href="{reverse("consignment:platform", args=(sales_platform.pk,))}">Площадка</a>',
        )
