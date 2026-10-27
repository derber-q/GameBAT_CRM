"""Создание складского импортного заказа без Excel и совместимость загрузки."""
from decimal import Decimal
from uuid import uuid4

from django.contrib.auth.models import Permission
from django.test import TestCase
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from accounts.models import User
from cash.models import CashTransaction
from catalog.models import Brand, CD, Platform, ProductType, Tech
from consignment.models import CDConsignmentStock
from partners.models import SalesPlatform, Supplier
from price.services import create_procurement_price_list
from pricing.models import SupplierCDPrice, SupplierTechPrice
from sales.models import Sale
from supplies.models import Supply
from warehouse.models import CDWarehouseStock, TechWarehouseStock, Warehouse
from .models import CustomerProcurementOrder, SupplierOrderBatch
from .services import create_customer_procurement_order
from .trips import change_trip_line, create_trip


def create_stock_form_fixture(target):
    target.user = User.objects.create_superuser("form-admin", password="StrongAdmin!123")
    target.supplier = Supplier.objects.create(name="Поставщик A", letter="A", priority=1,
        highlight_color="#37A7BA", legal_entity="A", phone_1="1")
    target.cd = CD.objects.create(name="Игра для формы", platform=Platform.objects.create(name="PS5"),
        sku="000-CD-FORM", weight_grams=100, cost=Decimal("111.25"))
    target.tech = Tech.objects.create(name="Консоль для формы", brand=Brand.objects.create(name="Sony"),
        product_type=ProductType.objects.create(name="Консоли"), sku="000-TECH-FORM", weight_grams=1000)
    SupplierCDPrice.objects.create(supplier=target.supplier, cd=target.cd, price=100)
    SupplierTechPrice.objects.create(supplier=target.supplier, tech=target.tech, price=150)
    target.price = create_procurement_price_list(actor=target.user,
        exchange_rate_usdt_aed=4, exchange_rate_usdt_rub=80, delivery_general_usdt_per_kg=2,
        delivery_devices_usdt_per_kg=2, delivery_storage_usdt_per_kg=2, delivery_cd_rub=Decimal("50.25"))
    target.cd_source = target.price.items.get(cd=target.cd)
    target.tech_source = target.price.items.get(tech=target.tech)
    target.warehouse = Warehouse.objects.create(name="Склад формы")


class StockOrderFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        create_stock_form_fixture(cls)

    def setUp(self):
        self.client.force_login(self.user)
        self.url = reverse("orders:stock_create")

    def data(self, **overrides):
        return {"price_list": self.price.pk, "recipient": "", "comment": "Тестовая закупка",
                f"quantity_{self.cd_source.pk}": "3", f"quantity_{self.tech_source.pk}": "2", **overrides}

    def employee(self, *permissions):
        employee = User.objects.create_user("form-worker")
        for permission in permissions:
            app, code = permission.split(".")
            employee.user_permissions.add(Permission.objects.get(content_type__app_label=app, codename=code))
        return employee

    def order(self, purpose, cd_quantity, tech_quantity=0):
        return create_customer_procurement_order(actor=self.user, price_list_id=self.price.pk,
            recipient="На склад", comment="", purpose=purpose, lines=[{
                "price_list_item_id": source.pk, "prepayment_quantity": quantity, "postpayment_quantity": 0,
            } for source, quantity in ((self.cd_source, cd_quantity), (self.tech_source, tech_quantity)) if quantity])

    def test_form_has_physical_stock_current_cost_and_saved_landed_cost(self):
        CDWarehouseStock.objects.create(cd=self.cd, warehouse=self.warehouse, quantity=2)
        other = Warehouse.objects.create(name="Другой склад")
        CDWarehouseStock.objects.create(cd=self.cd, warehouse=other, quantity=3)
        CDConsignmentStock.objects.create(cd=self.cd, warehouse=self.warehouse,
            platform=SalesPlatform.objects.create(name="Реализация"), quantity=99)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        rows = [row for group in response.context["groups"] for row in group["rows"]]
        self.assertEqual([row["item"].pk for row in rows], [self.tech_source.pk, self.cd_source.pk])
        self.assertEqual(rows[1]["stock"], 5)
        self.assertEqual(rows[1]["current_cost"], Decimal("111.25"))
        self.assertEqual(rows[1]["item"].stock_unit_cost, Decimal("2050.25"))
        self.assertIsNone(response.context['previous_trip'])
        self.assertEqual([row['previous_trip_quantity'] for row in rows], [0, 0])
        self.assertContains(response, 'На склад в предыдущем рейсе')
        self.assertContains(response, 'css/stock-order-form.css?v=2')
        self.assertContains(response, 'data-unit-kopecks="205025"')
        self.assertContains(response, reverse("orders:upload"))

    def test_previous_trip_counts_only_stock_orders_across_versions_and_supplier_transfers(self):
        old = self.order('stock', 50, 40)
        create_trip(actor=self.user, order_ids=[old.pk], creation_key=uuid4())
        customer = self.order('customer', 100, 90)
        first, second = self.order('stock', 2, 3), self.order('stock', 3)
        trip = create_trip(actor=self.user, order_ids=[customer.pk, first.pk, second.pk], creation_key=uuid4())
        self.order('stock', 88, 77)
        SupplierOrderBatch.objects.create(created_by=self.user)
        supplier = Supplier.objects.create(name='Второй поставщик', letter='B', priority=2,
            legal_entity='B', phone_1='1', highlight_color='#37A7BA')
        self.cd_source.supplier_offers.create(supplier=supplier, price_aed=110)
        line = trip.lines.get(cd=self.cd)
        change_trip_line(actor=self.user, batch_id=trip.pk, line_id=line.pk, revision=trip.revision,
            quantity=line.quantity - 2, action='transfer', target_supplier_id=supplier.pk,
            price_supplier_id=self.supplier.pk)
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(self.url, {'price_list': self.price.pk})
        self.assertEqual(response.context['previous_trip'].pk, trip.pk)
        rows = {row['item'].product_kind: row for group in response.context['groups'] for row in group['rows']}
        self.assertEqual(rows['cd']['previous_trip_quantity'], 5)
        self.assertEqual(rows['tech']['previous_trip_quantity'], 3)
        self.assertEqual(sum('FROM "orders_customerprocurementorderitem"' in query['sql'] for query in queries), 1)
        self.assertFalse(any(query['sql'].lstrip().upper().startswith(('INSERT ', 'UPDATE ', 'DELETE '))
            for query in queries))
        newer = create_procurement_price_list(actor=self.user, exchange_rate_usdt_aed=4,
            exchange_rate_usdt_rub=100, delivery_general_usdt_per_kg=0,
            delivery_devices_usdt_per_kg=0, delivery_storage_usdt_per_kg=0, delivery_cd_rub=0)
        response = self.client.get(self.url, {'price_list': newer.pk})
        self.assertEqual(response.context['previous_trip'].pk, trip.pk)
        rows = {row['item'].product_kind: row for group in response.context['groups'] for row in group['rows']}
        self.assertEqual((rows['cd']['previous_trip_quantity'], rows['tech']['previous_trip_quantity']), (5, 3))
        for supplier_line in trip.lines.filter(cd=self.cd).order_by('pk'):
            trip.refresh_from_db()
            change_trip_line(actor=self.user, batch_id=trip.pk, line_id=supplier_line.pk,
                revision=trip.revision, quantity=0, action='adjust')
        response = self.client.get(self.url)
        rows = {row['item'].product_kind: row for group in response.context['groups'] for row in group['rows']}
        self.assertEqual((rows['cd']['previous_trip_quantity'], rows['tech']['previous_trip_quantity']), (0, 3))

    def test_latest_customer_only_trip_does_not_fall_back_to_older_stock_trip(self):
        stock = self.order('stock', 20)
        create_trip(actor=self.user, order_ids=[stock.pk], creation_key=uuid4())
        customer = self.order('customer', 99)
        latest = create_trip(actor=self.user, order_ids=[customer.pk], creation_key=uuid4())
        response = self.client.get(self.url)
        self.assertEqual(response.context['previous_trip'].pk, latest.pk)
        self.assertTrue(all(row['previous_trip_quantity'] == 0
            for group in response.context['groups'] for row in group['rows']))

    def test_preview_back_and_creation_share_existing_stock_order_service(self):
        response = self.client.post(self.url, self.data())
        self.assertRedirects(response, reverse("orders:preview"))
        self.assertFalse(CustomerProcurementOrder.objects.exists())
        preview = self.client.get(reverse("orders:preview"))
        self.assertContains(preview, "Изменить состав")
        back = self.client.get(preview.context["back_url"])
        self.assertEqual(back.context["form"][f"quantity_{self.cd_source.pk}"].value(), 3)
        self.assertEqual(back.context["form"]["comment"].value(), "Тестовая закупка")
        response = self.client.post(reverse("orders:preview"))
        order = CustomerProcurementOrder.objects.get()
        self.assertRedirects(response, reverse("orders:detail", args=[order.pk]))
        self.assertEqual((order.purpose, order.status, order.recipient), ("stock", "created", "На склад"))
        self.assertEqual(order.grand_total, self.cd_source.stock_unit_cost * 3 + self.tech_source.stock_unit_cost * 2)
        self.assertEqual(order.postpayment_total, 0)
        self.assertEqual(order.items.get(cd=self.cd).selected_supplier_id, self.supplier.pk)
        self.assertFalse(Sale.objects.exists())
        self.assertFalse(Supply.objects.exists())
        self.assertFalse(CashTransaction.objects.exists())
        self.assertFalse(CDWarehouseStock.objects.exists())
        self.assertFalse(TechWarehouseStock.objects.exists())
        self.client.post(reverse("orders:preview"))
        self.assertEqual(CustomerProcurementOrder.objects.count(), 1)

    def test_post_cannot_replace_supplier_cost_or_purpose(self):
        self.cd_source.markup_rub = Decimal("500")
        self.cd_source.prepayment_price_rub = self.cd_source.stock_unit_cost + 500
        self.cd_source.save()
        self.client.post(self.url, self.data(purpose="customer", unit_cost="0", selected_supplier="999"))
        self.client.post(reverse("orders:preview"))
        order = CustomerProcurementOrder.objects.get()
        item = order.items.get(cd=self.cd)
        self.assertEqual(order.purpose, "stock")
        self.assertEqual(item.prepayment_unit_price, self.cd_source.stock_unit_cost)
        self.assertEqual(item.selected_supplier_id, self.supplier.pk)

    def test_empty_negative_fractional_and_too_large_quantities_are_rejected(self):
        for value in ("0", "", "-1", "1.5", "abc", "2147483648"):
            with self.subTest(value=value):
                response = self.client.post(self.url, self.data(**{
                    f"quantity_{self.cd_source.pk}": value, f"quantity_{self.tech_source.pk}": "0"}))
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)
                self.assertFalse(CustomerProcurementOrder.objects.exists())
                self.assertNotIn("procurement_order_import_draft", self.client.session)

    def test_archived_product_is_hidden_and_cannot_be_submitted(self):
        self.cd.is_archived = True
        self.cd.save(update_fields=["is_archived"])
        response = self.client.get(self.url)
        self.assertNotContains(response, f'name="quantity_{self.cd_source.pk}"')
        response = self.client.post(self.url, self.data())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Одна из выбранных позиций недоступна")

    def test_archive_between_preview_and_creation_does_not_create_order(self):
        self.client.post(self.url, self.data())
        self.cd.is_archived = True
        self.cd.save(update_fields=["is_archived"])
        response = self.client.post(reverse("orders:preview"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(self.url))
        self.assertFalse(CustomerProcurementOrder.objects.exists())

    def test_missing_or_foreign_price_list_item_is_rejected(self):
        for data in (self.data(price_list="bad"), self.data(price_list="999999"), self.data(quantity_999999="2")):
            with self.subTest(data=data):
                response = self.client.post(self.url, data)
                self.assertEqual(response.status_code, 200)
                self.assertNotIn("procurement_order_import_draft", self.client.session)
                self.assertFalse(CustomerProcurementOrder.objects.exists())

    def test_both_permissions_are_required_for_get_and_post(self):
        for permissions in ((), ("orders.create_order",), ("price.view_supplier_prices",)):
            with self.subTest(permissions=permissions):
                employee = self.employee(*permissions)
                self.client.force_login(employee)
                self.assertEqual(self.client.get(self.url).status_code, 403)
                self.assertEqual(self.client.post(self.url, self.data()).status_code, 403)
                employee.delete()
        self.client.force_login(self.employee("orders.create_order", "price.view_supplier_prices"))
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertRedirects(self.client.post(self.url, self.data()), reverse("orders:preview"))
        self.assertEqual(self.client.post(reverse("orders:preview")).status_code, 302)
        self.assertEqual(CustomerProcurementOrder.objects.get().created_by.username, "form-worker")

    def test_permission_removed_after_preview_blocks_creation(self):
        employee = self.employee("orders.create_order", "price.view_supplier_prices")
        self.client.force_login(employee)
        self.client.post(self.url, self.data())
        employee.user_permissions.remove(Permission.objects.get(content_type__app_label="price", codename="view_supplier_prices"))
        self.assertEqual(self.client.post(reverse("orders:preview")).status_code, 403)
        self.assertFalse(CustomerProcurementOrder.objects.exists())

    def test_import_page_buttons_point_to_specific_price_and_excel_stays(self):
        response = self.client.get(reverse("price:imports"))
        self.assertContains(response, f'{self.url}?price_list={self.price.pk}')
        self.assertContains(response, "Заказ на склад через форму")
        self.assertContains(response, reverse("price:procurement_stock_export", args=[self.price.pk]))
        detail = self.client.get(reverse("price:procurement_detail", args=[self.price.pk]))
        self.assertContains(detail, f'{self.url}?price_list={self.price.pk}')
        employee = self.employee("orders.create_order", "price.view_price_page")
        self.client.force_login(employee)
        self.assertNotContains(self.client.get(reverse("price:imports")), self.url)

    def test_invalid_post_keeps_other_quantities_and_header(self):
        response = self.client.post(self.url, self.data(**{f"quantity_{self.cd_source.pk}": "-1", "recipient": "Моя закупка"}))
        self.assertEqual(response.context["form"]["recipient"].value(), "Моя закупка")
        self.assertEqual(response.context["form"][f"quantity_{self.tech_source.pk}"].value(), "2")

    def test_version_selection_and_foreign_version_quantity(self):
        newer = create_procurement_price_list(actor=self.user, exchange_rate_usdt_aed=4,
            exchange_rate_usdt_rub=100, delivery_general_usdt_per_kg=0,
            delivery_devices_usdt_per_kg=0, delivery_storage_usdt_per_kg=0, delivery_cd_rub=0)
        self.assertEqual(self.client.get(self.url).context["price_list"].pk, newer.pk)
        self.assertEqual(self.client.get(self.url, {"price_list": self.price.pk}).context["price_list"].pk, self.price.pk)
        new_item = newer.items.get(cd=self.cd)
        response = self.client.post(self.url, self.data(**{f"quantity_{new_item.pk}": "1"}))
        self.assertContains(response, "Одна из выбранных позиций недоступна")
        self.assertNotIn("procurement_order_import_draft", self.client.session)


class EmptyStockOrderFormTests(TestCase):
    def test_no_price_lists_shows_empty_state(self):
        self.client.force_login(User.objects.create_superuser("empty-form-admin"))
        response = self.client.get(reverse("orders:stock_create"))
        self.assertContains(response, "Сохранённых импортных прайсов пока нет")
        self.assertNotContains(response, "data-stock-order-form")
