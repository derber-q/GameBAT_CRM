"""Заполнение локальной базы демонстрационными данными GameBAT CRM."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import PermissionSetMetadata, User
from catalog.models import Brand, CD, Platform, ProductType, Tech
from consignment.models import CDConsignmentStock, TechConsignmentStock
from consignment.services import transfer_to_consignment
from core.models import CurrencyRate
from partners.models import SalesPlatform, Supplier
from supplies.models import Supply
from supplies.services import accept_supply


class Command(BaseCommand):
    help = "Создаёт связанный демонстрационный набор данных без дублирования операций."

    def _permission(self, app_label, codename):
        return Permission.objects.get(content_type__app_label=app_label, codename=codename)

    def _reference(self, model, name):
        return model.objects.update_or_create(name=name, defaults={})[0]

    def _supplier(self, letter, **defaults):
        return Supplier.objects.update_or_create(letter=letter, defaults=defaults)[0]

    def _sales_platform(self, name, **defaults):
        obj = SalesPlatform.objects.filter(name=name).first()
        if obj is None:
            return SalesPlatform.objects.create(name=name, **defaults)
        for field, value in defaults.items():
            setattr(obj, field, value)
        obj.save()
        return obj

    def _product(self, model, sku, defaults):
        """Обновляет описание демо-товара, не повреждая рассчитанные остатки."""
        product = model.objects.filter(sku=sku).first()
        if product is None:
            return model.objects.create(sku=sku, quantity=0, cost=0, **defaults)
        for field, value in defaults.items():
            setattr(product, field, value)
        product.save(update_fields=tuple(defaults))
        return product

    def _worker(self, username, **defaults):
        worker = User.objects.filter(username=username).first()
        if worker is None:
            worker = User(username=username, **defaults)
            worker.set_unusable_password()
            worker.save()
        else:
            for field, value in defaults.items():
                setattr(worker, field, value)
            worker.save(update_fields=tuple(defaults))
        return worker

    @transaction.atomic
    def handle(self, *args, **options):
        admin = User.objects.filter(username="admin").first()
        if admin is None:
            self.stderr.write("Сначала создайте администратора командой createsuperuser.")
            return
        admin.full_name = admin.full_name or "Главный администратор"
        admin.email = admin.email or "admin@gamebat.local"
        admin.phone_1 = admin.phone_1 or "+7 999 100-00-01"
        admin.telegram = admin.telegram or "@gamebat_admin"
        admin.save(update_fields=("full_name", "email", "phone_1", "telegram"))

        # Внутренние курсы задаются вручную и не используют внешние API.
        for pair, rate in (
            (CurrencyRate.Pair.USD_RUB, Decimal("81.250000")),
            (CurrencyRate.Pair.AED_RUB, Decimal("22.120000")),
            (CurrencyRate.Pair.USD_AED, Decimal("3.672500")),
        ):
            CurrencyRate.objects.update_or_create(pair=pair, defaults={"rate": rate})

        ps5 = self._reference(Platform, "PlayStation 5")
        ps4 = self._reference(Platform, "PlayStation 4")
        switch = self._reference(Platform, "Nintendo Switch")
        xbox = self._reference(Platform, "Xbox Series X|S")

        sony = self._reference(Brand, "Sony")
        microsoft = self._reference(Brand, "Microsoft")
        nintendo = self._reference(Brand, "Nintendo")
        valve = self._reference(Brand, "Valve")
        logitech = self._reference(Brand, "Logitech")

        consoles = self._reference(ProductType, "Игровые консоли")
        gamepads = self._reference(ProductType, "Геймпады")
        handhelds = self._reference(ProductType, "Портативные консоли")
        headsets = self._reference(ProductType, "Гарнитуры")

        suppliers = {
            "A": self._supplier(
                "A", name="Альфа Дистрибуция", highlight_color="#8FD3C7",
                legal_entity="ООО «Альфа Дистрибуция»", email="sales@alpha-demo.local",
                phone_1="+7 495 100-10-10", phone_2="+7 495 100-10-11",
                phone_3="", website="https://example.com/alpha", telegram="@alpha_demo",
            ),
            "K": self._supplier(
                "K", name="Кибер Трейд", highlight_color="#F6D889",
                legal_entity="ООО «Кибер Трейд»", email="order@cyber-demo.local",
                phone_1="+7 812 200-20-20", phone_2="", phone_3="",
                website="https://example.com/cyber", telegram="@cyber_demo",
            ),
            "M": self._supplier(
                "M", name="Мир Консолей", highlight_color="#AFCBFF",
                legal_entity="ИП Демонстрационный М. В.", email="info@console-demo.local",
                phone_1="+7 999 300-30-30", phone_2="", phone_3="",
                website="", telegram="@console_demo",
            ),
            "R": self._supplier(
                "R", name="Ретро Склад", highlight_color="#F2B5D4",
                legal_entity="ООО «Ретро Склад»", email="retro@example.local",
                phone_1="+7 999 400-40-40", phone_2="", phone_3="",
                website="", telegram="",
            ),
            "V": self._supplier(
                "V", name="Вектор Электроникс", highlight_color="#C5E1A5",
                legal_entity="ООО «Вектор Электроникс»", email="b2b@vector-demo.local",
                phone_1="+7 999 500-50-50", phone_2="", phone_3="",
                website="https://example.com/vector", telegram="@vector_demo",
            ),
        }

        sales_platforms = {
            "north": self._sales_platform(
                "GamePoint Север", address="Москва, ул. Северная, 14",
                legal_entity="ООО «Геймпоинт Север»", phone_1="+7 495 700-10-10",
                phone_2="", phone_3="", email="north@gamepoint-demo.local", telegram="@gamepoint_north",
            ),
            "center": self._sales_platform(
                "Level Up Центр", address="Москва, пр-т Мира, 52",
                legal_entity="ООО «Левел Ап»", phone_1="+7 495 700-20-20",
                phone_2="", phone_3="", email="center@levelup-demo.local", telegram="@levelup_center",
            ),
            "spb": self._sales_platform(
                "Pixel СПб", address="Санкт-Петербург, Невский пр-т, 88",
                legal_entity="ООО «Пиксель»", phone_1="+7 812 700-30-30",
                phone_2="", phone_3="", email="spb@pixel-demo.local", telegram="@pixel_spb",
            ),
            "online": self._sales_platform(
                "Demo Marketplace", address="Демонстрационная онлайн-площадка",
                legal_entity="ООО «Демо Маркет»", phone_1="+7 800 700-40-40",
                phone_2="", phone_3="", email="market@demo.local", telegram="@demo_market",
            ),
        }

        cds = {
            "gta": self._product(CD, "DEMO-CD-001", {
                "platform": ps5, "name": "Grand Theft Auto V", "description": "Диск для PlayStation 5.",
                "barcode": "000000100001", "cusa_ppsa_code": "PPSA-01721", "comment": "Ходовая позиция",
            }),
            "spider": self._product(CD, "DEMO-CD-002", {
                "platform": ps5, "name": "Marvel’s Spider-Man 2", "description": "Диск для PlayStation 5.",
                "barcode": "000000100002", "cusa_ppsa_code": "PPSA-03016", "comment": "",
            }),
            "fc": self._product(CD, "DEMO-CD-003", {
                "platform": ps5, "name": "EA Sports FC 25", "description": "Спортивный симулятор.",
                "barcode": "000000100003", "cusa_ppsa_code": "PPSA-20008", "comment": "Сезонный спрос",
            }),
            "cyberpunk": self._product(CD, "DEMO-CD-004", {
                "platform": ps4, "name": "Cyberpunk 2077", "description": "Диск для PlayStation 4.",
                "barcode": "000000100004", "cusa_ppsa_code": "CUSA-16596", "comment": "",
            }),
            "witcher": self._product(CD, "DEMO-CD-005", {
                "platform": ps4, "name": "The Witcher 3: Wild Hunt", "description": "Полное издание.",
                "barcode": "000000100005", "cusa_ppsa_code": "CUSA-05574", "comment": "",
            }),
            "zelda": self._product(CD, "DEMO-CD-006", {
                "platform": switch, "name": "The Legend of Zelda: Tears of the Kingdom",
                "description": "Картридж Nintendo Switch.", "barcode": "000000100006",
                "cusa_ppsa_code": "", "comment": "",
            }),
            "mario": self._product(CD, "DEMO-CD-007", {
                "platform": switch, "name": "Mario Kart 8 Deluxe", "description": "Картридж Nintendo Switch.",
                "barcode": "000000100007", "cusa_ppsa_code": "", "comment": "",
            }),
            "forza": self._product(CD, "DEMO-CD-008", {
                "platform": xbox, "name": "Forza Horizon 5", "description": "Диск Xbox Series X.",
                "barcode": "000000100008", "cusa_ppsa_code": "", "comment": "",
            }),
        }

        tech = {
            "ps5": self._product(Tech, "DEMO-TECH-001", {
                "brand": sony, "product_type": consoles, "name": "PlayStation 5 Slim",
                "description": "Версия с дисководом, 1 ТБ.", "barcode": "000000200001", "comment": "Белая",
            }),
            "dualsense": self._product(Tech, "DEMO-TECH-002", {
                "brand": sony, "product_type": gamepads, "name": "DualSense White",
                "description": "Беспроводной контроллер.", "barcode": "000000200002", "comment": "",
            }),
            "xbox": self._product(Tech, "DEMO-TECH-003", {
                "brand": microsoft, "product_type": consoles, "name": "Xbox Series S 1TB",
                "description": "Цифровая консоль.", "barcode": "000000200003", "comment": "Чёрная",
            }),
            "xbox_pad": self._product(Tech, "DEMO-TECH-004", {
                "brand": microsoft, "product_type": gamepads, "name": "Xbox Wireless Controller",
                "description": "Беспроводной контроллер Xbox.", "barcode": "000000200004", "comment": "",
            }),
            "switch": self._product(Tech, "DEMO-TECH-005", {
                "brand": nintendo, "product_type": consoles, "name": "Nintendo Switch OLED",
                "description": "OLED-версия консоли.", "barcode": "000000200005", "comment": "Neon",
            }),
            "switch_pad": self._product(Tech, "DEMO-TECH-006", {
                "brand": nintendo, "product_type": gamepads, "name": "Nintendo Switch Pro Controller",
                "description": "Геймпад для Nintendo Switch.", "barcode": "000000200006", "comment": "",
            }),
            "steam": self._product(Tech, "DEMO-TECH-007", {
                "brand": valve, "product_type": handhelds, "name": "Steam Deck OLED 512GB",
                "description": "Портативная игровая система.", "barcode": "000000200007", "comment": "",
            }),
            "headset": self._product(Tech, "DEMO-TECH-008", {
                "brand": logitech, "product_type": headsets, "name": "Logitech G435",
                "description": "Беспроводная игровая гарнитура.", "barcode": "000000200008", "comment": "Black",
            }),
        }

        supply_worker = self._worker(
            "demo_supply", full_name="Анна Соколова", phone_1="+7 999 111-22-33",
            phone_2="", phone_3="", email="supply@gamebat.local", telegram="@anna_demo", is_active=True,
        )
        warehouse_worker = self._worker(
            "demo_warehouse", full_name="Иван Петров", phone_1="+7 999 222-33-44",
            phone_2="", phone_3="", email="warehouse@gamebat.local", telegram="@ivan_demo", is_active=True,
        )
        manager = self._worker(
            "demo_manager", full_name="Мария Орлова", phone_1="+7 999 333-44-55",
            phone_2="", phone_3="", email="manager@gamebat.local", telegram="@maria_demo", is_active=True,
        )

        group_specs = (
            ("Приёмка поставок", "Работа с приходом и просмотр склада", (
                ("supplies", "view_supply"), ("supplies", "add_supply"),
                ("catalog", "view_cd"), ("catalog", "view_tech"),
                ("partners", "view_supplier"),
            )),
            ("Склад и реализация", "Складские остатки, передача и возврат товара", (
                ("catalog", "view_cd"), ("catalog", "view_tech"),
                ("consignment", "view_cdconsignmentstock"),
                ("consignment", "view_techconsignmentstock"),
                ("consignment", "transfer_stock"), ("consignment", "return_stock"),
            )),
            ("Старший менеджер", "Полные реквизиты партнёров и расширенный просмотр", (
                ("partners", "view_supplier"), ("partners", "view_supplier_details"),
                ("partners", "add_supplier"), ("partners", "change_supplier"),
                ("supplies", "view_supply"), ("catalog", "view_cd"), ("catalog", "view_tech"),
            )),
        )
        groups = {}
        for name, description, permission_specs in group_specs:
            group, _ = Group.objects.get_or_create(name=name)
            group.permissions.set([self._permission(*spec) for spec in permission_specs])
            PermissionSetMetadata.objects.update_or_create(group=group, defaults={"description": description})
            groups[name] = group
        supply_worker.groups.add(groups["Приёмка поставок"])
        warehouse_worker.groups.add(groups["Склад и реализация"])
        manager.groups.add(groups["Приёмка поставок"], groups["Старший менеджер"])
        manager.user_permissions.add(self._permission("consignment", "view_cdconsignmentstock"))

        supply_specs = (
            ("DEMO-CD-001", supply_worker, 28, (
                {"product_type": "cd", "product_id": cds["gta"].pk, "supplier_id": suppliers["A"].pk, "quantity": 8, "purchase_unit_cost": "1580"},
                {"product_type": "cd", "product_id": cds["spider"].pk, "supplier_id": suppliers["A"].pk, "quantity": 6, "purchase_unit_cost": "3190"},
                {"product_type": "tech", "product_id": tech["ps5"].pk, "supplier_id": suppliers["V"].pk, "quantity": 3, "purchase_unit_cost": "51900"},
                {"product_type": "tech", "product_id": tech["dualsense"].pk, "supplier_id": suppliers["V"].pk, "quantity": 8, "purchase_unit_cost": "6450"},
            ), ({"name": "Доставка", "amount": "3500"}, {"name": "Страхование", "amount": "1200"})),
            ("DEMO-CD-003", warehouse_worker, 18, (
                {"product_type": "cd", "product_id": cds["fc"].pk, "supplier_id": suppliers["K"].pk, "quantity": 12, "purchase_unit_cost": "2480"},
                {"product_type": "cd", "product_id": cds["cyberpunk"].pk, "supplier_id": suppliers["R"].pk, "quantity": 5, "purchase_unit_cost": "1750"},
                {"product_type": "cd", "product_id": cds["witcher"].pk, "supplier_id": suppliers["R"].pk, "quantity": 7, "purchase_unit_cost": "1620"},
                {"product_type": "tech", "product_id": tech["xbox"].pk, "supplier_id": suppliers["M"].pk, "quantity": 4, "purchase_unit_cost": "37800"},
                {"product_type": "tech", "product_id": tech["xbox_pad"].pk, "supplier_id": suppliers["M"].pk, "quantity": 7, "purchase_unit_cost": "5980"},
            ), ({"name": "Перевозка", "amount": "2800"},)),
            ("DEMO-CD-006", manager, 10, (
                {"product_type": "cd", "product_id": cds["zelda"].pk, "supplier_id": suppliers["M"].pk, "quantity": 4, "purchase_unit_cost": "4150"},
                {"product_type": "cd", "product_id": cds["mario"].pk, "supplier_id": suppliers["M"].pk, "quantity": 5, "purchase_unit_cost": "3900"},
                {"product_type": "tech", "product_id": tech["switch"].pk, "supplier_id": suppliers["V"].pk, "quantity": 3, "purchase_unit_cost": "31800"},
                {"product_type": "tech", "product_id": tech["switch_pad"].pk, "supplier_id": suppliers["V"].pk, "quantity": 5, "purchase_unit_cost": "5480"},
            ), ({"name": "Таможенный сбор", "amount": "4600"}, {"name": "Доставка", "amount": "1900"})),
            ("DEMO-CD-008", supply_worker, 3, (
                {"product_type": "cd", "product_id": cds["forza"].pk, "supplier_id": suppliers["K"].pk, "quantity": 3, "purchase_unit_cost": "2850"},
                {"product_type": "tech", "product_id": tech["steam"].pk, "supplier_id": suppliers["A"].pk, "quantity": 2, "purchase_unit_cost": "64800"},
                {"product_type": "tech", "product_id": tech["headset"].pk, "supplier_id": suppliers["A"].pk, "quantity": 10, "purchase_unit_cost": "4420"},
            ), ({"name": "Курьерская доставка", "amount": "2100"},)),
        )
        for marker_sku, accepted_by, days_ago, lines, expenses in supply_specs:
            marker_exists = Supply.objects.filter(
                cd_items__product__sku=marker_sku
            ).exists() or Supply.objects.filter(tech_items__product__sku=marker_sku).exists()
            if not marker_exists:
                supply = accept_supply(accepted_by=accepted_by, lines=lines, expenses=expenses)
                Supply.objects.filter(pk=supply.pk).update(accepted_at=timezone.now() - timedelta(days=days_ago))

        transfer_specs = (
            (sales_platforms["north"], "cd", cds["gta"], 2, "650"),
            (sales_platforms["north"], "tech", tech["ps5"], 1, "4500"),
            (sales_platforms["center"], "cd", cds["fc"], 3, "700"),
            (sales_platforms["center"], "tech", tech["dualsense"], 2, "900"),
            (sales_platforms["spb"], "cd", cds["zelda"], 1, "1000"),
            (sales_platforms["spb"], "tech", tech["switch"], 1, "3500"),
            (sales_platforms["online"], "cd", cds["spider"], 2, "800"),
            (sales_platforms["online"], "tech", tech["headset"], 3, "650"),
        )
        for platform, product_type, product, quantity, reward in transfer_specs:
            stock_model = CDConsignmentStock if product_type == "cd" else TechConsignmentStock
            product_field = "cd" if product_type == "cd" else "tech"
            stock = stock_model.objects.filter(platform=platform, **{product_field: product}).first()
            if stock is None or stock.quantity == 0:
                transfer_to_consignment(
                    actor=admin, platform_id=platform.pk, product_type=product_type,
                    product_id=product.pk, quantity=quantity, reward_per_unit=reward,
                )

        self.stdout.write(self.style.SUCCESS("Демонстрационные данные созданы."))
        self.stdout.write(
            f"Пользователи: {User.objects.count()}, товары: {CD.objects.count() + Tech.objects.count()}, "
            f"поставщики: {Supplier.objects.count()}, поставки: {Supply.objects.count()}, "
            f"остатки реализации: {CDConsignmentStock.objects.count() + TechConsignmentStock.objects.count()}"
        )
