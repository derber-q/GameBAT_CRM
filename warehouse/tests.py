from decimal import Decimal

from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from catalog.models import Brand, CD, Platform, ProductChangeEvent, ProductType, Tech
from .models import CDWarehouseStock, TechWarehouseStock, Warehouse, WarehouseTransfer
from .services import advance_transfer_status, create_transfer


class WarehouseTransferTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("admin", password="StrongAdmin!123")
        self.source = Warehouse.objects.create(name="Москва")
        self.destination = Warehouse.objects.create(name="Санкт-Петербург")
        self.platform = Platform.objects.create(name="PS5")
        brand = Brand.objects.create(name="Sony")
        self.product_type = ProductType.objects.create(name="Консоль")
        self.cd = CD.objects.create(
            platform=self.platform, name="Игра", sku="CD-1", barcode="00000001",
            cusa_ppsa_code="PPSA-10001", cost=100,
        )
        self.tech = Tech.objects.create(
            brand=brand, product_type=self.product_type,
            name="Приставка", sku="T-1", barcode="2", cost=500,
        )
        self.cd_stock = CDWarehouseStock.objects.create(warehouse=self.source, cd=self.cd, quantity=10)
        self.tech_stock = TechWarehouseStock.objects.create(warehouse=self.source, tech=self.tech, quantity=4)

    def make_transfer(self):
        return create_transfer(
            actor=self.user, source_warehouse_id=self.source.pk, destination_warehouse_id=self.destination.pk,
            lines=[
                {"product_type": "cd", "product_id": self.cd.pk, "quantity": 3},
                {"product_type": "tech", "product_id": self.tech.pk, "quantity": 1},
            ],
        )

    def test_different_warehouses_have_independent_stock_and_unique_rows(self):
        CDWarehouseStock.objects.create(warehouse=self.destination, cd=self.cd, quantity=2)
        self.assertEqual(self.cd.warehouse_stocks.count(), 2)
        with self.assertRaises(IntegrityError), transaction.atomic():
            CDWarehouseStock.objects.create(warehouse=self.source, cd=self.cd, quantity=1)

    def test_creation_deducts_source_only_and_counts_transit(self):
        transfer = self.make_transfer()
        self.cd_stock.refresh_from_db()
        self.tech_stock.refresh_from_db()
        self.assertEqual(self.cd_stock.quantity, 7)
        self.assertEqual(self.tech_stock.quantity, 3)
        self.assertFalse(CDWarehouseStock.objects.filter(warehouse=self.destination, cd=self.cd).exists())
        self.assertEqual(transfer.total_units, 4)
        self.assertEqual(self.cd.cost, Decimal("100"))

        event = self.cd.change_events.get()
        self.assertEqual(event.action_kind, ProductChangeEvent.ActionKind.WAREHOUSE_TRANSFER)
        self.assertEqual(event.action_label, f"Перемещение №{transfer.pk}")
        self.assertEqual(event.action_url, reverse("warehouse:transfer_detail", args=(transfer.pk,)))
        change = event.field_changes.get()
        self.assertEqual((change.old_value, change.new_value), ("10", "7"))

    def test_strict_status_chain_and_acceptance(self):
        transfer = self.make_transfer()
        with self.assertRaisesMessage(ValidationError, "недопустим"):
            advance_transfer_status(
                actor=self.user, transfer_id=transfer.pk, next_status=WarehouseTransfer.Status.SHIPPED
            )
        advance_transfer_status(
            actor=self.user, transfer_id=transfer.pk, next_status=WarehouseTransfer.Status.ASSEMBLED
        )
        advance_transfer_status(
            actor=self.user, transfer_id=transfer.pk, next_status=WarehouseTransfer.Status.SHIPPED
        )
        advance_transfer_status(
            actor=self.user, transfer_id=transfer.pk, next_status=WarehouseTransfer.Status.ACCEPTED
        )
        self.assertEqual(CDWarehouseStock.objects.get(warehouse=self.destination, cd=self.cd).quantity, 3)
        events = self.cd.change_events.order_by("created_at", "id")
        self.assertEqual(events.count(), 2)
        accepted_change = events[1].field_changes.get()
        self.assertEqual(accepted_change.field_label, f"Остаток: {self.destination.name}")
        self.assertEqual((accepted_change.old_value, accepted_change.new_value), ("0", "3"))
        self.assertEqual(events[1].action_url, reverse("warehouse:transfer_detail", args=(transfer.pk,)))
        with self.assertRaisesMessage(ValidationError, "недопустим"):
            advance_transfer_status(
                actor=self.user, transfer_id=transfer.pk, next_status=WarehouseTransfer.Status.ACCEPTED
            )

    def test_cannot_transfer_too_much_or_to_same_warehouse(self):
        with self.assertRaises(ValidationError):
            create_transfer(
                actor=self.user, source_warehouse_id=self.source.pk, destination_warehouse_id=self.destination.pk,
                lines=[{"product_type": "cd", "product_id": self.cd.pk, "quantity": 11}],
            )
        with self.assertRaises(ValidationError):
            create_transfer(
                actor=self.user, source_warehouse_id=self.source.pk, destination_warehouse_id=self.source.pk,
                lines=[{"product_type": "cd", "product_id": self.cd.pk, "quantity": 1}],
            )
        self.cd_stock.refresh_from_db()
        self.assertEqual(self.cd_stock.quantity, 10)
        self.assertEqual(WarehouseTransfer.objects.count(), 0)

    def test_all_stock_and_transfer_pages_are_grouped(self):
        second_platform = Platform.objects.create(name="Xbox Series")
        accessory_type = ProductType.objects.create(name="Аксессуары")
        second_cd = CD.objects.create(
            platform=second_platform, name="Вторая игра", sku="CD-2", barcode="3", cost=200
        )
        second_tech = Tech.objects.create(
            brand=self.tech.brand, product_type=accessory_type,
            name="Геймпад", sku="T-2", barcode="4", cost=300,
        )
        CDWarehouseStock.objects.create(warehouse=self.source, cd=second_cd, quantity=2)
        TechWarehouseStock.objects.create(warehouse=self.source, tech=second_tech, quantity=3)
        future_warehouse = Warehouse.objects.create(name="Будущий склад")
        self.client.force_login(self.user)

        global_response = self.client.get(reverse("warehouse:global_stock"))
        self.assertEqual(
            [group.name for group, _ in global_response.context["cd_groups"]],
            ["PS5", "Xbox Series"],
        )
        self.assertEqual(
            [group.name for group, _ in global_response.context["tech_groups"]],
            ["Аксессуары", "Консоль"],
        )

        future_response = self.client.get(reverse("warehouse:detail", args=(future_warehouse.pk,)))
        self.assertEqual(future_response.context["cd_groups"], [])
        self.assertEqual(future_response.context["tech_groups"], [])

        create_response = self.client.get(reverse("warehouse:transfer_create", args=(self.source.pk,)))
        self.assertEqual(
            [group.name for group, _ in create_response.context["cd_groups"]],
            ["PS5", "Xbox Series"],
        )
        transfer = create_transfer(
            actor=self.user,
            source_warehouse_id=self.source.pk,
            destination_warehouse_id=self.destination.pk,
            lines=[
                {"product_type": "cd", "product_id": self.cd.pk, "quantity": 1},
                {"product_type": "cd", "product_id": second_cd.pk, "quantity": 1},
                {"product_type": "tech", "product_id": self.tech.pk, "quantity": 1},
                {"product_type": "tech", "product_id": second_tech.pk, "quantity": 1},
            ],
        )
        detail_response = self.client.get(reverse("warehouse:transfer_detail", args=(transfer.pk,)))
        self.assertEqual(
            [group.name for group, _ in detail_response.context["cd_groups"]],
            ["PS5", "Xbox Series"],
        )
        self.assertEqual(
            [group.name for group, _ in detail_response.context["tech_groups"]],
            ["Аксессуары", "Консоль"],
        )

    def test_stock_tables_follow_interface_contract(self):
        self.client.force_login(self.user)
        global_response = self.client.get(reverse("warehouse:global_stock"))
        self.assertContains(
            global_response,
            '<th>ID</th><th>Артикул</th><th>Название</th>'
            '<th class="numeric-center">Всего на складах</th>'
            '<th class="numeric-center">На реализации</th>'
            '<th class="numeric-center">В перемещении</th>',
            html=True,
        )
        self.assertNotContains(
            global_response,
            f'<th class="numeric"><a href="{reverse("warehouse:detail", args=(self.source.pk,))}">'
            f'{self.source.name}</a></th>',
            html=True,
        )

        detail_response = self.client.get(reverse("warehouse:detail", args=(self.source.pk,)))
        self.assertContains(
            detail_response,
            '<th>ID</th><th>Артикул</th><th>Место хранения</th><th>Название</th>'
            '<th class="numeric-center">CUSA/PPSA</th>'
            '<th class="numeric-center">Количество</th>',
            html=True,
        )
        self.assertContains(
            detail_response,
            '<th>ID</th><th>Артикул</th><th>Место хранения</th><th>Название</th><th>Бренд</th>'
            '<th class="numeric-center">Количество</th>',
            html=True,
        )
        self.assertNotContains(detail_response, "Касса склада")
        self.assertNotContains(detail_response, "<th>На реализации</th>", html=True)

    def test_stock_search_uses_all_supported_fields_and_keeps_groups(self):
        self.cd.name = "NS2 Elden Ring Tarnished Edition"
        self.cd.sku = "OLD-CD-0143"
        self.cd.barcode = "0004600000143"
        self.cd.cusa_ppsa_code = "PPSA-ELDEN-143"
        self.cd.save()
        self.tech.name = "ИГРОВАЯ Приставка"
        self.tech.save(update_fields=("name",))
        self.client.force_login(self.user)
        urls = (
            reverse("warehouse:global_stock"),
            reverse("warehouse:detail", args=(self.source.pk,)),
        )

        for url in urls:
            for query in ("elden", "0143", "PPSA-ELDEN", "0004600000143", str(self.cd.pk)):
                with self.subTest(url=url, query=query):
                    response = self.client.get(url, {"search": query})
                    self.assertContains(response, self.cd.name)
                    self.assertEqual([group.name for group, _ in response.context["cd_groups"]], ["PS5"])

            unicode_response = self.client.get(url, {"search": "игровая приставка"})
            self.assertContains(unicode_response, self.tech.name)
            self.assertEqual(
                [group.name for group, _ in unicode_response.context["tech_groups"]], ["Консоль"]
            )

            empty_response = self.client.get(url, {"search": "NO-SUCH-PRODUCT"})
            self.assertContains(empty_response, "Ничего не найдено")
            self.assertEqual(empty_response.context["cd_groups"], [])
            self.assertEqual(empty_response.context["tech_groups"], [])
            self.assertEqual(empty_response.context["query"], "NO-SUCH-PRODUCT")

    def test_warehouse_hides_zero_local_stock_even_if_another_warehouse_has_stock(self):
        other_cd = CD.objects.create(
            platform=self.platform, name="Товар другого склада", sku="ONLY-OTHER", barcode="0099"
        )
        other_tech = Tech.objects.create(
            brand=self.tech.brand, product_type=self.product_type,
            name="Техника другого склада", sku="TECH-ONLY-OTHER", barcode="0100",
        )
        CDWarehouseStock.objects.create(warehouse=self.destination, cd=other_cd, quantity=9)
        TechWarehouseStock.objects.create(warehouse=self.destination, tech=other_tech, quantity=5)
        CDWarehouseStock.objects.create(warehouse=self.source, cd=other_cd, quantity=0)
        TechWarehouseStock.objects.create(warehouse=self.source, tech=other_tech, quantity=0)
        self.client.force_login(self.user)

        source_response = self.client.get(reverse("warehouse:detail", args=(self.source.pk,)))
        self.assertNotContains(source_response, other_cd.name)
        self.assertNotContains(source_response, other_tech.name)

        destination_response = self.client.get(reverse("warehouse:detail", args=(self.destination.pk,)))
        self.assertContains(destination_response, other_cd.name)
        self.assertContains(destination_response, other_tech.name)

        search_response = self.client.get(
            reverse("warehouse:detail", args=(self.source.pk,)), {"search": "ONLY-OTHER"}
        )
        self.assertEqual(search_response.context["cd_groups"], [])
        self.assertEqual(search_response.context["tech_groups"], [])
        self.assertContains(search_response, "Ничего не найдено")

        nomenclature_response = self.client.get(reverse("nomenclature:list"))
        self.assertContains(nomenclature_response, other_cd.name)
        self.assertContains(nomenclature_response, other_tech.name)

    def test_transfer_table_ignores_blank_quantities(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("warehouse:transfer_create", args=(self.source.pk,)),
            {
                "destination_warehouse": self.destination.pk,
                f"line_cd_{self.cd.pk}": "2",
                f"line_tech_{self.tech.pk}": "",
            },
        )
        transfer = WarehouseTransfer.objects.get()
        self.assertRedirects(response, reverse("warehouse:transfer_detail", args=(transfer.pk,)))
        self.assertEqual(transfer.cd_items.get().quantity, 2)
        self.assertFalse(transfer.tech_items.exists())

    def test_new_transfer_button_selects_source_warehouse(self):
        self.client.force_login(self.user)
        list_response = self.client.get(reverse("warehouse:transfer_list"))
        self.assertContains(list_response, reverse("warehouse:transfer_start"))
        self.assertContains(list_response, "Новое перемещение")

        start_url = reverse("warehouse:transfer_start")
        self.assertEqual(self.client.get(start_url).status_code, 200)
        response = self.client.post(start_url, {"source_warehouse": self.source.pk})
        self.assertRedirects(response, reverse("warehouse:transfer_create", args=(self.source.pk,)))


class WarehousePermissionTests(TestCase):
    def setUp(self):
        self.worker = User.objects.create_user("worker", password="StrongWorker!123")
        self.warehouse = Warehouse.objects.create(name="Склад")
        self.client.force_login(self.worker)

    def test_direct_urls_require_permissions(self):
        self.assertEqual(self.client.get(reverse("warehouse:global_stock")).status_code, 403)
        self.assertEqual(self.client.get(reverse("warehouse:detail", args=(self.warehouse.pk,))).status_code, 403)
        self.assertEqual(self.client.get(reverse("warehouse:transfer_list")).status_code, 403)
        self.assertEqual(self.client.get(reverse("warehouse:transfer_start")).status_code, 403)
        self.assertEqual(
            self.client.get(reverse("warehouse:transfer_create", args=(self.warehouse.pk,))).status_code, 403
        )
        self.assertEqual(
            self.client.post(reverse("warehouse:transfer_create", args=(self.warehouse.pk,))).status_code, 403
        )
        self.assertEqual(
            self.client.post(reverse("warehouse:transfer_advance", args=(999,)), {"next_status": "assembled"}).status_code,
            403,
        )

    def test_global_permission_grants_global_page_only(self):
        self.worker.user_permissions.add(
            Permission.objects.get(content_type__app_label="warehouse", codename="view_global_stock")
        )
        response = self.client.get(reverse("warehouse:global_stock"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, reverse("warehouse:detail", args=(self.warehouse.pk,)))
        self.assertEqual(self.client.get(reverse("warehouse:detail", args=(self.warehouse.pk,))).status_code, 403)

    def test_transfer_only_permission_has_a_working_navigation_destination(self):
        self.worker.user_permissions.add(
            Permission.objects.get(content_type__app_label="warehouse", codename="view_transfers")
        )
        self.assertRedirects(self.client.get(reverse("core:home")), reverse("warehouse:transfer_list"))
        response = self.client.get(reverse("warehouse:transfer_list"))
        self.assertContains(response, '>Перемещения</a>', count=1)
        self.assertNotContains(response, "Новое перемещение")
