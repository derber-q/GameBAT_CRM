from html.parser import HTMLParser
from types import SimpleNamespace

from django import forms
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase
from django.urls import reverse

from accounts.models import User
from cash.models import CashRegister, Safe
from consignment.forms import TransferForm
from creditors.forms import DebtAdjustmentForm
from orders.forms import PaymentWarehouseForm
from price.forms import WarehousePriceForm
from resource_storefront.models import RetailSettings, StorefrontSettings
from sales.forms import SaleCreateForm
from sales.statistics_forms import SaleStatisticsFilterForm
from warehouse.form_defaults import SingleWarehouseInitialMixin, single_warehouse_id
from warehouse.forms import WarehouseTransferForm, WarehouseTransferSourceForm
from warehouse.models import Warehouse
from yandex_market.forms import IntegrationForm


class WarehouseSelectParser(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.selected = {}
        self.name = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "select":
            self.name = attrs.get("name")
            self.selected.setdefault(self.name, [])
        elif tag == "option" and self.name and "selected" in attrs:
            self.selected[self.name].append(attrs.get("value"))

    def handle_endtag(self, tag):
        if tag == "select":
            self.name = None


class WarehouseDefaultTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser("warehouse-defaults", password="Test-password-123")
        cls.warehouse = Warehouse.objects.get(name="Варфоломеева 265")

    def setUp(self):
        self.client.force_login(self.user)

    def warehouse_forms(self):
        return (
            (SaleCreateForm(), "warehouse"),
            (TransferForm(), "warehouse"),
            (DebtAdjustmentForm(), "warehouse"),
            (WarehousePriceForm(), "warehouse"),
            (PaymentWarehouseForm(), "warehouse"),
            (WarehouseTransferSourceForm(), "source_warehouse"),
            (IntegrationForm(), "fulfillment_warehouse"),
        )

    def assert_page_defaults(self, expected):
        for route, field_name in (
            ("sales:create", "warehouse"),
            ("supplies:create", "warehouse_id"),
            ("consignment:transfer", "warehouse"),
            ("consignment:list", "warehouse"),
            ("warehouse:transfer_start", "source_warehouse"),
            ("price:index", "warehouse"),
        ):
            with self.subTest(route=route):
                response = self.client.get(reverse(route))
                self.assertEqual(response.status_code, 200)
                selected = WarehouseSelectParser(response.content.decode()).selected[field_name]
                self.assertEqual([value for value in selected if value], expected * (2 if route == "price:index" else 1))

    def test_only_warehouse_is_selected_in_forms_and_pages(self):
        self.assertEqual(single_warehouse_id(), self.warehouse.pk)
        for form, field_name in self.warehouse_forms():
            with self.subTest(form=type(form).__name__):
                self.assertEqual(form[field_name].value(), self.warehouse.pk)
        self.assert_page_defaults([str(self.warehouse.pk)])
        self.assertIsNone(SaleStatisticsFilterForm()["warehouse"].value())

    def test_second_warehouse_disables_automatic_selection(self):
        Warehouse.objects.create(name="Второй склад")
        self.assertIsNone(single_warehouse_id())
        for form, field_name in self.warehouse_forms():
            with self.subTest(form=type(form).__name__):
                self.assertIsNone(form[field_name].value())
        self.assert_page_defaults([])
        form = WarehouseTransferForm(source_warehouse=self.warehouse)
        self.assertEqual(form.fields["destination_warehouse"].queryset.count(), 1)
        self.assertIsNone(form["destination_warehouse"].value())

    def test_empty_database_and_warehouse_with_arbitrary_id(self):
        # Удаление касается только изолированной тестовой базы.
        StorefrontSettings.objects.all().delete()
        RetailSettings.objects.all().delete()
        CashRegister.objects.all().delete()
        Safe.objects.all().delete()
        Warehouse.objects.all().delete()
        self.assertIsNone(single_warehouse_id())
        self.assertIsNone(SaleCreateForm()["warehouse"].value())
        warehouse = Warehouse.objects.create(name="Единственный новый склад")
        self.assertNotEqual(warehouse.pk, self.warehouse.pk)
        self.assertEqual(SaleCreateForm()["warehouse"].value(), warehouse.pk)

    def test_bound_values_and_wholesale_initial_are_preserved(self):
        for value in ("", str(self.warehouse.pk), "999999"):
            with self.subTest(value=value):
                form = SaleCreateForm({"warehouse": value})
                self.assertEqual(form["warehouse"].value(), value)
        blank = WarehousePriceForm({"warehouse": ""})
        self.assertFalse(blank.is_valid())
        self.assertIn("warehouse", blank.errors)
        other = Warehouse.objects.create(name="Склад импортированного прайса")
        form = SaleCreateForm(initial={"warehouse": other.pk}, imported_wholesale=True)
        self.assertEqual(form["warehouse"].value(), other.pk)
        self.assertTrue(form.fields["warehouse"].disabled)

    def test_filtered_choices_do_not_override_global_warehouse_count(self):
        class RestrictedForm(SingleWarehouseInitialMixin, forms.Form):
            warehouse = forms.ModelChoiceField(queryset=Warehouse.objects.filter(pk=self.warehouse.pk))

        class ExcludedForm(SingleWarehouseInitialMixin, forms.Form):
            warehouse = forms.ModelChoiceField(queryset=Warehouse.objects.exclude(pk=self.warehouse.pk))

        self.assertIsNone(ExcludedForm()["warehouse"].value())
        Warehouse.objects.create(name="Другой склад")
        self.assertIsNone(RestrictedForm()["warehouse"].value())

    def test_supply_blank_submission_is_not_replaced_with_default(self):
        response = self.client.post(reverse("supplies:create"), {"warehouse_id": ""})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_warehouse"], "")
        self.assertEqual(WarehouseSelectParser(response.content.decode()).selected["warehouse_id"], [])

    def test_order_payment_and_stock_receipt_defaults(self):
        request = RequestFactory().get("/")
        request.user = self.user
        request.session = {}
        for count in (1, 2):
            if count == 2:
                Warehouse.objects.create(name="Второй склад")
            for stock_order in (False, True):
                with self.subTest(count=count, stock_order=stock_order):
                    order = SimpleNamespace(
                        pk=3, price_list_id=1, is_stock_order=stock_order,
                        prepayment_total=1, payment_warehouse_id=None, created_by=self.user,
                    )
                    html = render_to_string("orders/detail.html", {
                        "order": order, "can_confirm": True, "can_complete": True,
                    }, request=request)
                    selected = WarehouseSelectParser(html).selected["warehouse"]
                    expected = [str(self.warehouse.pk)] * (1 if stock_order else 2) if count == 1 else []
                    self.assertEqual(selected, expected)
