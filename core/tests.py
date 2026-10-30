from django.test import TestCase
from django.contrib.auth.models import Permission
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
            "Продажа", "Импорт", "Контрагенты", "Номенклатура", "Склад", "Приход",
            "Реализация", "Ценообразование", "stuf",
        )
        positions = [nav_html.index(f">{label}</a>") for label in labels]

        self.assertEqual(positions, sorted(positions))
        self.assertContains(response, 'class="brand-logo"')
        self.assertContains(response, 'img/resource-logo.png?v=20261027-1')
        self.assertNotContains(response, '<span>Re<b>SOURCE</b></span>', html=True)
        self.assertNotContains(response, '<span class="brand-mark">RS</span>', html=True)
        self.assertNotContains(response, "GameBAT CRM")
        self.assertContains(response, 'class="nav-sale')
        self.assertContains(response, 'data-rate-symbol="USDT/RUB"')
        self.assertContains(response, 'data-rate-symbol="USDT/AED"')
        self.assertContains(response, 'class="header-status"')
        self.assertContains(response, 'class="admin-shortcut"')
        self.assertContains(response, 'aria-label="Админ-панель" title="Админ-панель"')
        self.assertNotContains(response, '>Админ-панель</a>')
        self.assertContains(response, 'payments-2-header-status-1')
        self.assertContains(response, 'css/navigation.css?v=20261027-2')
        self.assertContains(response, 'js/navigation.js?v=20261027-1')
        self.assertContains(response, 'aria-controls="nav-overflow-list"')
        self.assertContains(response, 'aria-controls="mobile-navigation"')
        self.assertNotContains(response, 'data-rate-symbol="AED/RUB"')
        self.assertNotContains(response, 'data-rate-symbol="USD/AED"')
        self.assertContains(response, 'data-notification-sound-enable', count=1)
        self.assertNotContains(response, 'data-market-sound-enable')
        self.assertNotContains(response, 'data-avito-sound-enable')

        warehouse_trigger = nav_html.index(">Склад</a>")
        menu_start = nav_html.index('<div class="nav-dropdown-menu">', warehouse_trigger)
        menu_end = nav_html.index("</div>", menu_start)
        warehouse_menu = nav_html[menu_start:menu_end]
        self.assertTrue(warehouse_menu.split('>', 1)[1].lstrip().startswith('<a class="" href="' + reverse('supplies:list') + '">Приход</a>'))
        self.assertEqual(nav_html.count('>Приход</a>'), 1)
        self.assertIn(">Общие остатки</a>", warehouse_menu)
        self.assertIn("Склад Варфоломеева 265", warehouse_menu)
        self.assertIn("Склад Резервный склад", warehouse_menu)
        self.assertTrue(warehouse_menu.rstrip().endswith(">Перемещения</a>"))
        self.assertEqual(nav_html.count(">Перемещения</a>"), 1)

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
        self.assertNotIn(">Поставщики</a>", stuf_menu)
        counterparties_trigger = nav_html.index(">Контрагенты</a>")
        counterparties_start = nav_html.index('<div class="nav-dropdown-menu">', counterparties_trigger)
        counterparties_end = nav_html.index('</div>', counterparties_start)
        counterparties_menu = nav_html[counterparties_start:counterparties_end]
        for label in ('Партнёры', 'Кредиторы', 'Поставщики'):
            self.assertIn(f'>{label}</a>', counterparties_menu)
            self.assertEqual(nav_html.count(f'>{label}</a>'), 1)
        sales_platform = SalesPlatform.objects.get(name="Площадка")
        self.assertContains(
            response,
            f'href="{reverse("consignment:platform", args=(sales_platform.pk,))}">Площадка</a>',
        )

    def test_counterparties_menu_respects_each_directory_permission(self):
        for app, codename, endpoint, label in [
            ('partners', 'view_partner', 'partners:partner_list', 'Партнёры'),
            ('creditors', 'view_creditors', 'creditors:list', 'Кредиторы'),
            ('partners', 'view_supplier', 'partners:list', 'Поставщики'),
        ]:
            with self.subTest(permission=codename):
                worker = User.objects.create_user('menu-' + codename)
                worker.user_permissions.add(Permission.objects.get(content_type__app_label=app, codename=codename))
                self.client.force_login(worker)
                response = self.client.get(reverse(endpoint))
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, 'class="admin-shortcut"')
                nav = response.content.decode().split('<nav class="main-nav"', 1)[1].split('</nav>', 1)[0]
                self.assertIn('data-counterparties-nav', nav)
                self.assertIn(f'href="{reverse(endpoint)}" aria-haspopup="true">Контрагенты</a>', nav)
                for candidate in ('Партнёры', 'Кредиторы', 'Поставщики'):
                    self.assertEqual(f'>{candidate}</a>' in nav, candidate == label)
                for other in ('partners:partner_list', 'creditors:list', 'partners:list'):
                    if other != endpoint:
                        self.assertEqual(self.client.get(reverse(other)).status_code, 403)
        self.client.force_login(User.objects.create_user('menu-without-directories'))
        self.assertNotContains(self.client.get(reverse('accounts:password_change')), 'data-counterparties-nav')

    def test_sound_icon_respects_notification_permissions_in_crm_and_admin(self):
        self.assertContains(self.client.get(reverse('admin:index')), 'data-notification-sound-enable', count=1)
        for app, codename, endpoint, engine in [
            ('sales', 'view_sales', 'sales:incomplete', 'market-notifications.js?v=3'),
            ('integrations', 'view_avito_integration', 'integrations:avito', 'avito-alert-sound.js?v=3'),
        ]:
            with self.subTest(permission=codename):
                worker = User.objects.create_user('sound-' + codename)
                worker.user_permissions.add(Permission.objects.get(content_type__app_label=app, codename=codename))
                self.client.force_login(worker)
                response = self.client.get(reverse(endpoint))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'data-notification-sound-enable', count=1)
                self.assertContains(response, engine)
        self.client.force_login(User.objects.create_user('no-notification-sound'))
        self.assertNotContains(self.client.get(reverse('accounts:password_change')), 'data-notification-sound-enable')

    def test_supply_only_user_keeps_warehouse_menu_without_stock_access(self):
        employee = User.objects.create_user('supply-menu-worker')
        employee.user_permissions.add(Permission.objects.get(content_type__app_label='supplies', codename='view_supply'))
        self.client.force_login(employee)
        response = self.client.get(reverse('supplies:list'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['nav']['warehouse'])
        self.assertFalse(response.context['nav']['warehouse_global'])
        self.assertFalse(response.context['nav']['warehouse_details'])
        self.assertContains(response, f'href="{reverse("supplies:list")}" aria-haspopup="true">Склад</a>')
        self.assertContains(response, '>Приход</a>', count=1)
        self.assertNotContains(response, '>Общие остатки</a>')
        self.assertNotContains(response, '>Перемещения</a>')
        self.assertEqual(self.client.get(reverse('warehouse:global_stock')).status_code, 403)

    def test_transfer_only_user_keeps_warehouse_menu_without_stock_access(self):
        employee = User.objects.create_user('transfer-menu-worker')
        employee.user_permissions.add(Permission.objects.get(content_type__app_label='warehouse', codename='view_transfers'))
        self.client.force_login(employee)
        response = self.client.get(reverse('warehouse:transfer_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['nav']['warehouse'])
        self.assertFalse(response.context['nav']['warehouse_global'])
        self.assertFalse(response.context['nav']['warehouse_details'])
        self.assertContains(response, '>Склад</a>')
        self.assertContains(response, '>Перемещения</a>', count=1)
        self.assertEqual(self.client.get(reverse('warehouse:global_stock')).status_code, 403)
        employee.user_permissions.set(Permission.objects.filter(
            content_type__app_label='warehouse', codename='view_global_stock'))
        response = self.client.get(reverse('warehouse:global_stock'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '>Перемещения</a>')
