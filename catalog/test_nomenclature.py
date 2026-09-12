from unittest.mock import patch

from django.contrib.auth.models import Group, Permission
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from warehouse.models import CDWarehouseStock, TechWarehouseStock, Warehouse
from warehouse.storage_services import update_storage_locations
from .models import Brand, CD, Platform, ProductChangeEvent, ProductType, Tech
from .nomenclature_forms import product_version
from .nomenclature_services import update_product_card


def permission(codename, app_label="catalog"):
    return Permission.objects.get(content_type__app_label=app_label, codename=codename)


class NomenclatureDataMixin:
    def create_products(self):
        self.ps5 = Platform.objects.create(name="PlayStation 5")
        self.switch = Platform.objects.create(name="Nintendo Switch")
        self.brand = Brand.objects.create(name="Sony")
        self.console_type = ProductType.objects.create(name="Консоли")
        self.accessory_type = ProductType.objects.create(name="Аксессуары")
        self.cd = CD.objects.create(
            platform=self.ps5,
            name="Игра без остатка",
            description="Описание диска",
            sku="CD-ZERO",
            barcode="460000000001",
            cusa_ppsa_code="PPSA-00001",
            comment="Комментарий CD",
        )
        self.tech = Tech.objects.create(
            brand=self.brand,
            product_type=self.console_type,
            name="Техника без остатка",
            description="Описание техники",
            sku="TECH-ZERO",
            barcode="460000000002",
            comment="Комментарий Tech",
        )


class NomenclatureListTests(NomenclatureDataMixin, TestCase):
    def setUp(self):
        self.create_products()
        self.worker = User.objects.create_user("catalog-reader", password="StrongWorker!123")
        self.worker.user_permissions.add(permission("view_nomenclature"))
        self.client.force_login(self.worker)

    def test_zero_stock_products_are_grouped_by_platform_and_product_type(self):
        response = self.client.get(reverse("nomenclature:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.cd.name)
        self.assertContains(response, self.tech.name)
        self.assertContains(response, self.ps5.name)
        self.assertContains(response, self.console_type.name)
        self.assertFalse(self.cd.warehouse_stocks.exists())
        self.assertFalse(self.tech.warehouse_stocks.exists())

    def test_new_dynamic_groups_appear_and_empty_references_do_not(self):
        empty_platform = Platform.objects.create(name="Пустая платформа")
        empty_type = ProductType.objects.create(name="Пустой тип")
        new_platform = Platform.objects.create(name="Новая платформа")
        new_type = ProductType.objects.create(name="Новый тип")
        CD.objects.create(platform=new_platform, name="Новый диск", sku="CD-NEW", barcode="3")
        Tech.objects.create(
            brand=self.brand, product_type=new_type, name="Новая техника", sku="TECH-NEW", barcode="4"
        )

        response = self.client.get(reverse("nomenclature:list"))

        self.assertIn(new_platform, [group for group, _ in response.context["cd_groups"]])
        self.assertIn(new_type, [group for group, _ in response.context["tech_groups"]])
        self.assertNotIn(empty_platform, [group for group, _ in response.context["cd_groups"]])
        self.assertNotIn(empty_type, [group for group, _ in response.context["tech_groups"]])
        self.assertIn(empty_platform, response.context["platform_options"])
        self.assertIn(empty_type, response.context["product_type_options"])

    def test_search_uses_name_sku_barcode_and_cusa_ppsa(self):
        for query, expected in (
            ("PPSA-00001", self.cd.name),
            ("TECH-ZERO", self.tech.name),
            ("460000000001", self.cd.name),
            ("техника без", self.tech.name),
        ):
            response = self.client.get(reverse("nomenclature:list"), {"q": query})
            self.assertContains(response, expected)

    def test_tables_keep_groups_but_remove_duplicate_columns(self):
        response = self.client.get(reverse("nomenclature:list"))

        self.assertContains(
            response,
            '<th>ID</th><th>Артикул</th><th>Название</th><th>CUSA/PPSA</th><th></th>',
            html=True,
        )
        self.assertContains(
            response,
            '<th>ID</th><th>Артикул</th><th>Название</th><th>Бренд</th><th></th>',
            html=True,
        )
        self.assertNotContains(response, "<th>Платформа</th>", html=True)
        self.assertNotContains(response, "<th>Тип товара</th>", html=True)
        self.assertContains(response, f'<span class="section-name">{self.ps5.name}</span>', html=True)
        self.assertContains(response, f'<span class="section-name">{self.console_type.name}</span>', html=True)


class NomenclatureSecurityTests(NomenclatureDataMixin, TestCase):
    def setUp(self):
        self.create_products()
        self.worker = User.objects.create_user("no-catalog", password="StrongWorker!123")
        self.urls = (
            reverse("nomenclature:list"),
            reverse("nomenclature:cd_detail", args=(self.cd.pk,)),
            reverse("nomenclature:tech_detail", args=(self.tech.pk,)),
        )

    def test_anonymous_user_is_redirected_to_login_for_all_urls(self):
        for url in self.urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertIn(reverse("accounts:login"), response.url)

    def test_user_without_view_permission_gets_403_for_get_and_post(self):
        self.client.force_login(self.worker)
        for url in self.urls:
            self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(
            self.client.post(reverse("nomenclature:cd_detail", args=(self.cd.pk,)), {}).status_code,
            403,
        )

    def test_navigation_button_depends_on_view_permission(self):
        self.client.force_login(self.worker)
        response = self.client.get(reverse("accounts:password_change"))
        self.assertNotContains(response, ">Номенклатура</a>")

        self.worker.user_permissions.add(permission("view_nomenclature"))
        self.worker = User.objects.get(pk=self.worker.pk)
        self.client.force_login(self.worker)
        response = self.client.get(reverse("nomenclature:list"))
        self.assertContains(response, ">Номенклатура</a>", count=1)


class ProductCardPermissionTests(NomenclatureDataMixin, TestCase):
    def setUp(self):
        self.create_products()
        self.worker = User.objects.create_user("editor", password="StrongWorker!123")
        self.worker.user_permissions.add(permission("view_nomenclature"), permission("change_cd_name"))
        self.client.force_login(self.worker)
        self.url = reverse("nomenclature:cd_detail", args=(self.cd.pk,))

    def test_detail_shows_real_data_and_only_authorized_field_is_editable(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.cd.description)
        self.assertContains(response, self.cd.sku)
        self.assertFalse(response.context["form"].fields["name"].disabled)
        self.assertTrue(response.context["form"].fields["sku"].disabled)
        self.assertContains(response, "Средняя себестоимость")
        html = response.content.decode()
        self.assertLess(html.index("Системная информация"), html.index("Сохранить изменения"))

    def test_tech_detail_opens_and_shows_actual_product_data(self):
        response = self.client.get(reverse("nomenclature:tech_detail", args=(self.tech.pk,)))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.tech.name)
        self.assertContains(response, self.tech.description)
        self.assertContains(response, self.tech.brand.name)
        self.assertContains(response, self.tech.product_type.name)

    def test_manual_post_of_protected_field_rejects_entire_operation(self):
        response = self.client.post(self.url, {
            "version": product_version(self.cd),
            "name": "Разрешённое новое имя",
            "sku": "FORBIDDEN-SKU",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Нет права изменять поля: Артикул")
        self.cd.refresh_from_db()
        self.assertEqual(self.cd.name, "Игра без остатка")
        self.assertEqual(self.cd.sku, "CD-ZERO")
        self.assertFalse(ProductChangeEvent.objects.exists())

    def test_multiple_allowed_fields_are_rolled_back_on_forbidden_barcode(self):
        self.worker.user_permissions.add(
            permission("change_cd_description"),
            permission("change_cd_comment"),
        )
        self.worker = User.objects.get(pk=self.worker.pk)
        self.client.force_login(self.worker)
        response = self.client.post(self.url, {
            "version": product_version(self.cd),
            "name": "Новое имя",
            "description": "Новое описание",
            "comment": "Новый комментарий",
            "barcode": "FORBIDDEN-BARCODE",
        })
        self.assertEqual(response.status_code, 200)
        self.cd.refresh_from_db()
        self.assertEqual(self.cd.name, "Игра без остатка")
        self.assertEqual(self.cd.description, "Описание диска")
        self.assertEqual(self.cd.comment, "Комментарий CD")
        self.assertEqual(self.cd.barcode, "460000000001")

    def test_system_controlled_fields_are_rejected(self):
        response = self.client.post(self.url, {
            "version": product_version(self.cd),
            "name": "Новое имя",
            "cost": "1.00",
            "quantity_on_consignment": "999",
        })
        self.assertEqual(response.status_code, 200)
        self.cd.refresh_from_db()
        self.assertEqual(self.cd.name, "Игра без остатка")
        self.assertEqual(str(self.cd.cost), "0.00")
        self.assertEqual(self.cd.quantity_on_consignment, 0)

    def test_legacy_blank_barcode_does_not_block_another_allowed_change(self):
        self.cd.barcode = ""
        self.cd.save(update_fields=("barcode",))
        response = self.client.post(self.url, {
            "version": product_version(self.cd),
            "name": "Новое имя старой карточки",
        })
        self.assertEqual(response.status_code, 302)
        self.cd.refresh_from_db()
        self.assertEqual(self.cd.name, "Новое имя старой карточки")
        self.assertEqual(self.cd.barcode, "")

    def test_existing_pricing_permission_controls_retail_price(self):
        retail_permission = permission("change_retail_price", app_label="pricing")
        response = self.client.post(self.url, {
            "version": product_version(self.cd),
            "name": self.cd.name,
            "retail_price": "999.00",
        })
        self.assertEqual(response.status_code, 200)
        self.cd.refresh_from_db()
        self.assertIsNone(self.cd.retail_price)

        self.worker.user_permissions.add(retail_permission)
        self.worker = User.objects.get(pk=self.worker.pk)
        self.client.force_login(self.worker)
        response = self.client.post(self.url, {
            "version": product_version(self.cd),
            "name": self.cd.name,
            "retail_price": "999.00",
        })
        self.assertEqual(response.status_code, 302)
        self.cd.refresh_from_db()
        self.assertEqual(str(self.cd.retail_price), "999.00")
        self.assertEqual(ProductChangeEvent.objects.count(), 1)

    def test_permissions_from_group_enable_the_field(self):
        group = Group.objects.create(name="Редакторы названий")
        group.permissions.add(permission("view_nomenclature"), permission("change_tech_name"))
        grouped_user = User.objects.create_user("grouped-editor", password="StrongWorker!123")
        grouped_user.groups.add(group)
        self.client.force_login(grouped_user)
        url = reverse("nomenclature:tech_detail", args=(self.tech.pk,))

        response = self.client.get(url)
        self.assertFalse(response.context["form"].fields["name"].disabled)
        response = self.client.post(url, {
            "version": product_version(self.tech),
            "name": "Новое имя техники",
        })
        self.assertEqual(response.status_code, 302)
        self.tech.refresh_from_db()
        self.assertEqual(self.tech.name, "Новое имя техники")


class WarehouseStockEditingTests(NomenclatureDataMixin, TestCase):
    def setUp(self):
        self.create_products()
        self.worker = User.objects.create_user("stock-editor", password="StrongWorker!123")
        self.worker.user_permissions.add(permission("view_nomenclature"))
        self.client.force_login(self.worker)
        self.primary_warehouse = Warehouse.objects.order_by("pk").first()
        self.second_warehouse = Warehouse.objects.create(name="Второй склад")
        CDWarehouseStock.objects.create(warehouse=self.primary_warehouse, cd=self.cd, quantity=2)
        CDWarehouseStock.objects.create(warehouse=self.second_warehouse, cd=self.cd, quantity=5)
        TechWarehouseStock.objects.create(warehouse=self.primary_warehouse, tech=self.tech, quantity=1)

    def _stock_post_data(self, product, **overrides):
        values = {
            stock.warehouse_id: stock.quantity
            for stock in product.warehouse_stocks.all()
        }
        data = {"version": product_version(product)}
        for warehouse in Warehouse.objects.all():
            data[f"stock_{warehouse.pk}"] = values.get(warehouse.pk, 0)
        data.update(overrides)
        return data

    def test_cd_stock_can_be_changed_for_one_specific_warehouse(self):
        self.worker.user_permissions.add(permission("change_cdwarehousestock", app_label="warehouse"))
        self.worker = User.objects.get(pk=self.worker.pk)
        self.client.force_login(self.worker)
        url = reverse("nomenclature:cd_detail", args=(self.cd.pk,))
        response = self.client.get(url)
        self.assertFalse(
            response.context["form"].fields[f"stock_{self.primary_warehouse.pk}"].disabled
        )

        response = self.client.post(
            url,
            self._stock_post_data(self.cd, **{f"stock_{self.primary_warehouse.pk}": 7}),
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            CDWarehouseStock.objects.get(warehouse=self.primary_warehouse, cd=self.cd).quantity,
            7,
        )
        self.assertEqual(
            CDWarehouseStock.objects.get(warehouse=self.second_warehouse, cd=self.cd).quantity,
            5,
        )
        event = ProductChangeEvent.objects.get()
        self.assertEqual(event.executor_display, "stock-editor")
        self.assertEqual(event.action_label, "")
        change = event.field_changes.get()
        self.assertEqual(change.field_label, f"Остаток: {self.primary_warehouse.name}")
        self.assertEqual(change.old_value, "2")
        self.assertEqual(change.new_value, "7")

        detail = self.client.get(url)
        self.assertContains(detail, "Кто изменил")
        self.assertContains(detail, "Документ / действие")
        self.assertContains(detail, "stock-editor")
        self.assertNotContains(detail, "stock-editor (CRM)")

    def test_tech_stock_uses_its_own_standard_permission(self):
        self.worker.user_permissions.add(permission("change_techwarehousestock", app_label="warehouse"))
        self.worker = User.objects.get(pk=self.worker.pk)
        self.client.force_login(self.worker)
        url = reverse("nomenclature:tech_detail", args=(self.tech.pk,))

        response = self.client.post(
            url,
            self._stock_post_data(self.tech, **{f"stock_{self.second_warehouse.pk}": 4}),
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            TechWarehouseStock.objects.get(warehouse=self.second_warehouse, tech=self.tech).quantity,
            4,
        )

    def test_manual_stock_post_without_permission_is_rejected(self):
        url = reverse("nomenclature:cd_detail", args=(self.cd.pk,))
        response = self.client.post(url, {
            "version": product_version(self.cd),
            f"stock_{self.primary_warehouse.pk}": 99,
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Нет права изменять поля")
        self.assertEqual(
            CDWarehouseStock.objects.get(warehouse=self.primary_warehouse, cd=self.cd).quantity,
            2,
        )


class NomenclatureStorageLocationEditingTests(NomenclatureDataMixin, TestCase):
    def setUp(self):
        self.create_products()
        self.actor = User.objects.create_superuser("location-admin", password="StrongAdmin!123")
        self.worker = User.objects.create_user("location-editor", password="StrongWorker!123")
        self.worker.user_permissions.add(permission("view_nomenclature"))
        self.primary_warehouse = Warehouse.objects.create(name="Основной склад")
        self.second_warehouse = Warehouse.objects.create(name="Второй склад")
        self.cd_primary_stock = CDWarehouseStock.objects.create(
            warehouse=self.primary_warehouse, cd=self.cd, quantity=2,
        )
        CDWarehouseStock.objects.create(
            warehouse=self.second_warehouse, cd=self.cd, quantity=0,
        )
        TechWarehouseStock.objects.create(
            warehouse=self.primary_warehouse, tech=self.tech, quantity=2,
        )
        self.client.force_login(self.worker)

    def _post_data(self, product, *, include_stocks=False, **overrides):
        data = {"version": product_version(product)}
        stocks = {stock.warehouse_id: stock for stock in product.warehouse_stocks.all()}
        for warehouse in Warehouse.objects.all():
            stock = stocks.get(warehouse.pk)
            data[f"storage_location_{warehouse.pk}"] = ", ".join(
                assignment.location.canonical_value
                for assignment in stock.storage_assignments.select_related("location").all()
            ) if stock is not None else ""
            if include_stocks:
                data[f"stock_{warehouse.pk}"] = stock.quantity if stock is not None else 0
        data.update(overrides)
        return data

    def _grant_location_permission(self):
        self.worker.user_permissions.add(
            permission("change_storage_location", app_label="warehouse")
        )
        self.worker = User.objects.get(pk=self.worker.pk)
        self.client.force_login(self.worker)

    def test_card_shows_each_warehouse_location_without_examples(self):
        update_storage_locations(
            actor=self.actor,
            warehouse_id=self.primary_warehouse.pk,
            product_type="cd",
            product_id=self.cd.pk,
            raw_value=r"A1-2-1\2, A6-3",
        )
        response = self.client.get(reverse("nomenclature:cd_detail", args=(self.cd.pk,)))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Место хранения")
        self.assertContains(response, r"A1-2-1\2, A6-3")
        self.assertTrue(
            response.context["form"].fields[
                f"storage_location_{self.primary_warehouse.pk}"
            ].disabled
        )
        self.assertNotContains(response, 'placeholder="A1-2')
        autocomplete = self.client.get(
            reverse(
                "warehouse:storage_location_autocomplete",
                args=(self.primary_warehouse.pk,),
            ),
            {"q": "A1"},
        )
        self.assertEqual(autocomplete.status_code, 200)
        self.assertEqual(
            [item["value"] for item in autocomplete.json()["results"]],
            [r"A1-2-1\2"],
        )

    def test_permission_controls_location_editing_and_manual_post(self):
        url = reverse("nomenclature:cd_detail", args=(self.cd.pk,))
        forbidden = self.client.post(url, {
            "version": product_version(self.cd),
            f"storage_location_{self.primary_warehouse.pk}": "A1-2",
        })
        self.assertEqual(forbidden.status_code, 200)
        self.assertContains(forbidden, "Нет права изменять поля")
        self.assertFalse(self.cd_primary_stock.storage_assignments.exists())

        self._grant_location_permission()
        response = self.client.post(url, self._post_data(
            self.cd,
            **{f"storage_location_{self.primary_warehouse.pk}": r"a1 - 2 - 2 \ 1"},
        ))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            self.cd_primary_stock.storage_assignments.get().location.canonical_value,
            r"A1-2-1\2",
        )
        event = self.cd.change_events.order_by("-pk").first()
        self.assertEqual(event.source, ProductChangeEvent.Source.NOMENCLATURE)

    def test_invalid_location_keeps_previous_value(self):
        update_storage_locations(
            actor=self.actor,
            warehouse_id=self.primary_warehouse.pk,
            product_type="cd",
            product_id=self.cd.pk,
            raw_value="A1-2",
        )
        self._grant_location_permission()
        response = self.client.post(
            reverse("nomenclature:cd_detail", args=(self.cd.pk,)),
            self._post_data(
                self.cd,
                **{f"storage_location_{self.primary_warehouse.pk}": "A1-2-1,2"},
            ),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Некорректный формат места хранения")
        self.assertEqual(
            self.cd_primary_stock.storage_assignments.get().location.canonical_value,
            "A1-2",
        )

    def test_stock_and_location_can_be_saved_together_and_zero_clears_location(self):
        self._grant_location_permission()
        self.worker.user_permissions.add(
            permission("change_cdwarehousestock", app_label="warehouse")
        )
        self.worker = User.objects.get(pk=self.worker.pk)
        self.client.force_login(self.worker)
        url = reverse("nomenclature:cd_detail", args=(self.cd.pk,))

        response = self.client.post(url, self._post_data(
            self.cd,
            include_stocks=True,
            **{
                f"stock_{self.second_warehouse.pk}": 3,
                f"storage_location_{self.second_warehouse.pk}": "B2-4",
            },
        ))
        self.assertEqual(response.status_code, 302)
        second_stock = CDWarehouseStock.objects.get(
            warehouse=self.second_warehouse, cd=self.cd,
        )
        self.assertEqual(second_stock.quantity, 3)
        self.assertEqual(
            second_stock.storage_assignments.get().location.canonical_value, "B2-4"
        )

        response = self.client.post(url, self._post_data(
            self.cd,
            include_stocks=True,
            **{f"stock_{self.second_warehouse.pk}": 0},
        ))
        self.assertEqual(response.status_code, 302)
        second_stock.refresh_from_db()
        self.assertEqual(second_stock.quantity, 0)
        self.assertFalse(second_stock.storage_assignments.exists())

    def test_tech_card_uses_the_same_location_fields(self):
        self._grant_location_permission()
        url = reverse("nomenclature:tech_detail", args=(self.tech.pk,))
        response = self.client.post(url, self._post_data(
            self.tech,
            **{f"storage_location_{self.primary_warehouse.pk}": "C3-5"},
        ))
        self.assertEqual(response.status_code, 302)
        stock = TechWarehouseStock.objects.get(
            warehouse=self.primary_warehouse, tech=self.tech,
        )
        self.assertEqual(stock.storage_assignments.get().location.canonical_value, "C3-5")


class ProductAuditTests(NomenclatureDataMixin, TestCase):
    def setUp(self):
        self.create_products()
        self.worker = User.objects.create_user("audited-editor", password="StrongWorker!123")
        self.worker.user_permissions.add(
            permission("view_nomenclature"),
            permission("change_cd_name"),
            permission("change_cd_description"),
            permission("change_cd_comment"),
            permission("change_cd_platform"),
        )
        self.client.force_login(self.worker)
        self.url = reverse("nomenclature:cd_detail", args=(self.cd.pk,))

    def test_one_save_creates_one_event_with_three_field_changes(self):
        response = self.client.post(self.url, {
            "version": product_version(self.cd),
            "name": "Новое имя",
            "description": "Новое описание",
            "comment": "Новый комментарий",
            "platform": self.cd.platform_id,
        })
        self.assertEqual(response.status_code, 302)
        event = ProductChangeEvent.objects.get()
        self.assertEqual(event.actor, self.worker)
        self.assertEqual(event.source, ProductChangeEvent.Source.NOMENCLATURE)
        self.assertEqual(event.cd, self.cd)
        self.assertEqual(event.field_changes.count(), 3)
        name_change = event.field_changes.get(field_name="name")
        self.assertEqual(name_change.old_value, "Игра без остатка")
        self.assertEqual(name_change.new_value, "Новое имя")

    def test_single_field_change_creates_one_event_and_one_snapshot(self):
        response = self.client.post(self.url, {
            "version": product_version(self.cd),
            "name": "Только новое имя",
            "description": self.cd.description,
            "comment": self.cd.comment,
            "platform": self.cd.platform_id,
        })
        self.assertEqual(response.status_code, 302)
        event = ProductChangeEvent.objects.get()
        self.assertEqual(event.field_changes.count(), 1)
        change = event.field_changes.get()
        self.assertEqual(change.field_name, "name")
        self.assertEqual(change.old_value, "Игра без остатка")
        self.assertEqual(change.new_value, "Только новое имя")

    def test_no_actual_changes_create_no_event(self):
        response = self.client.post(self.url, {
            "version": product_version(self.cd),
            "name": self.cd.name,
            "description": self.cd.description,
            "comment": self.cd.comment,
            "platform": self.cd.platform_id,
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(ProductChangeEvent.objects.exists())

    def test_foreign_key_history_is_a_historical_snapshot(self):
        response = self.client.post(self.url, {
            "version": product_version(self.cd),
            "name": self.cd.name,
            "description": self.cd.description,
            "comment": self.cd.comment,
            "platform": self.switch.pk,
        })
        self.assertEqual(response.status_code, 302)
        change = ProductChangeEvent.objects.get().field_changes.get(field_name="platform")
        self.assertEqual(change.old_value, "PlayStation 5")
        self.assertEqual(change.new_value, "Nintendo Switch")

        self.switch.name = "Переименованная платформа"
        self.switch.save(update_fields=("name",))
        change.refresh_from_db()
        self.assertEqual(change.new_value, "Nintendo Switch")

    def test_audit_failure_rolls_back_product_change(self):
        with patch("catalog.nomenclature_services.record_product_changes", side_effect=RuntimeError("audit failed")):
            with self.assertRaises(RuntimeError):
                update_product_card(
                    actor=self.worker,
                    product_kind="cd",
                    product_id=self.cd.pk,
                    data={
                        "version": product_version(self.cd),
                        "name": "Не должно сохраниться",
                        "description": self.cd.description,
                        "comment": self.cd.comment,
                        "platform": self.cd.platform_id,
                    },
                )
        self.cd.refresh_from_db()
        self.assertEqual(self.cd.name, "Игра без остатка")
        self.assertFalse(ProductChangeEvent.objects.exists())

    def test_stale_version_does_not_overwrite_concurrent_change(self):
        stale_version = product_version(self.cd)
        CD.objects.filter(pk=self.cd.pk).update(name="Изменено параллельно")
        response = self.client.post(self.url, {
            "version": stale_version,
            "name": "Устаревшее изменение",
            "description": self.cd.description,
            "comment": self.cd.comment,
            "platform": self.cd.platform_id,
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Карточка уже была изменена другим пользователем")
        self.cd.refresh_from_db()
        self.assertEqual(self.cd.name, "Изменено параллельно")


class ProductAdminAuditTests(NomenclatureDataMixin, TestCase):
    def setUp(self):
        self.create_products()
        self.admin = User.objects.create_superuser("audit-admin", password="StrongAdmin!123")
        self.client.force_login(self.admin)

    def test_cd_and_tech_changes_from_admin_use_the_shared_audit(self):
        cd_response = self.client.post(reverse("admin:catalog_cd_change", args=(self.cd.pk,)), {
            "platform": self.cd.platform_id,
            "name": "CD из Admin",
            "description": self.cd.description,
            "sku": self.cd.sku,
            "barcode": self.cd.barcode,
            "cusa_ppsa_code": self.cd.cusa_ppsa_code,
            "retail_price": "",
            "wholesale_price": "",
            "yandex_market_price": "",
            "comment": self.cd.comment,
            "_save": "Сохранить",
        })
        self.assertEqual(cd_response.status_code, 302)
        tech_response = self.client.post(reverse("admin:catalog_tech_change", args=(self.tech.pk,)), {
            "brand": self.tech.brand_id,
            "product_type": self.tech.product_type_id,
            "name": "Tech из Admin",
            "description": self.tech.description,
            "sku": self.tech.sku,
            "barcode": self.tech.barcode,
            "retail_price": "",
            "wholesale_price": "",
            "yandex_market_price": "",
            "comment": self.tech.comment,
            "_save": "Сохранить",
        })
        self.assertEqual(tech_response.status_code, 302)

        events = ProductChangeEvent.objects.order_by("id")
        self.assertEqual(events.count(), 2)
        self.assertEqual(events[0].source, ProductChangeEvent.Source.DJANGO_ADMIN)
        self.assertEqual(events[0].actor, self.admin)
        self.assertEqual(events[0].field_changes.get().field_name, "name")
        self.assertEqual(events[1].source, ProductChangeEvent.Source.DJANGO_ADMIN)
        self.assertEqual(events[1].tech, self.tech)

    def test_audit_models_cannot_be_added_or_deleted_in_admin(self):
        self.assertEqual(self.client.get(reverse("admin:catalog_productchangeevent_add")).status_code, 403)
        event = ProductChangeEvent.objects.create(
            actor=self.admin,
            source=ProductChangeEvent.Source.CRM,
            product_kind=ProductChangeEvent.ProductKind.CD,
            cd=self.cd,
        )
        response = self.client.post(
            reverse("admin:catalog_productchangeevent_delete", args=(event.pk,)),
            {"post": "yes"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(ProductChangeEvent.objects.filter(pk=event.pk).exists())
