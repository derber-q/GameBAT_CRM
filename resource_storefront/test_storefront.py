from decimal import Decimal

from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse

from catalog.models import CD, Platform, ProductChangeEvent
from cash.models import CashTransaction
from sales.models import Sale
from warehouse.models import CDWarehouseStock, Warehouse

from .models import StorefrontNews, StorefrontSettings, StorefrontSubmission, WholesaleAccessLink, WholesaleContact
from .security import issue_link


@override_settings(RESOURCE_TOKEN_ENCRYPTION_KEY=Fernet.generate_key().decode("ascii"))
class StorefrontAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_superuser("storefront-admin", password="StrongAdmin!234")
        cls.contact = WholesaleContact.objects.create(name="Тестовый клиент", phone="+7 (999) 123-45-67", address="Улица, 1")
        cls.warehouse = Warehouse.objects.order_by("pk").first()
        StorefrontSettings.objects.update_or_create(pk=1, defaults={"warehouse": cls.warehouse})
        cls.platform = Platform.objects.create(name="PS5")
        cls.product = CD.objects.create(name="Игра длинного названия", platform=cls.platform, wholesale_price=Decimal("1250.00"), avito_price=Decimal("1500.00"), cost=Decimal("800.00"))
        CDWarehouseStock.objects.create(warehouse=cls.warehouse, cd=cls.product, quantity=2)
        cls.link, cls.token = issue_link(cls.contact, cls.staff)

    def test_link_grants_storefront_without_employee_login_and_pages_are_private(self):
        response = self.client.get(reverse("resource_storefront:catalogue"))
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("1250", response.content.decode())
        response = self.client.get(reverse("resource_storefront:access", kwargs={"token": self.token}))
        self.assertRedirects(response, reverse("resource_storefront:home"))
        self.assertIn("private, no-store, max-age=0", response["Cache-Control"])
        self.assertEqual(self.client.get(reverse("resource_storefront:catalogue")).status_code, 200)
        self.assertContains(self.client.get(reverse("resource_storefront:catalogue")), "1\u00a0250 ₽")
        self.assertNotIn("/opt/", self.client.get(reverse("core:home")).url)

    def test_revocation_invalidates_existing_buyer_session(self):
        self.client.get(reverse("resource_storefront:access", kwargs={"token": self.token}))
        self.link.is_active = False
        self.link.save(update_fields=("is_active",))
        response = self.client.get(reverse("resource_storefront:catalogue"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("resource_storefront:denied"))

    def test_checkout_uses_current_stock_contact_snapshot_and_does_not_post_cash(self):
        self.client.get(reverse("resource_storefront:access", kwargs={"token": self.token}))
        self.client.post(reverse("resource_storefront:cart_add"), {"kind": "cd", "product_id": self.product.pk, "quantity": 1, "next": reverse("resource_storefront:catalogue")})
        cart = self.client.get(reverse("resource_storefront:cart"))
        version = cart.context["version"]
        checkout_key = self.client.session["resource_checkout_key"]
        before_checkout_cookie = self.client.cookies[settings.SESSION_COOKIE_NAME].value
        response = self.client.post(reverse("resource_storefront:checkout"), {
            "cart_version": version, "extra_phone": "+7 999 000 00 00", "comment": "Позвонить перед доставкой",
        })
        sale = Sale.objects.get(storefront_source="resource_storefront")
        self.assertRedirects(response, reverse("resource_storefront:success", kwargs={"sale_id": sale.pk}))
        self.assertEqual(sale.created_by, None)
        self.assertEqual(sale.wholesale_contact_id, self.contact.pk)
        self.assertEqual(sale.buyer_name_snapshot, self.contact.name)
        self.assertEqual(sale.buyer_phone_snapshot, self.contact.phone)
        self.assertEqual(sale.buyer_address_snapshot, self.contact.address)
        self.assertEqual(sale.buyer_extra_phone, "+7 999 000 00 00")
        self.assertEqual(sale.buyer_comment, "Позвонить перед доставкой")
        self.assertEqual(sale.sale_type, Sale.SaleType.WHOLESALE)
        self.assertEqual(sale.price_type, Sale.PriceType.WHOLESALE)
        self.assertEqual(sale.payment_method, Sale.PaymentMethod.CASH_POSTPAY)
        self.assertEqual(sale.payment_status, Sale.PaymentStatus.UNPAID)
        self.assertEqual(sale.order_status, Sale.OrderStatus.CREATED)
        self.assertEqual(CDWarehouseStock.objects.get(warehouse=self.warehouse, cd=self.product).quantity, 1)
        self.assertFalse(CashTransaction.objects.filter(sale=sale).exists())
        submission = StorefrontSubmission.objects.get(sale=sale)
        self.assertEqual(submission.contact_id, self.contact.pk)
        self.assertEqual(submission.idempotency_key, checkout_key)
        # Simulate a client retry with the pre-success cookie after the success response was lost.
        self.client.cookies[settings.SESSION_COOKIE_NAME] = before_checkout_cookie
        self.assertEqual(self.client.session["resource_checkout_key"], checkout_key)
        retry = self.client.post(reverse("resource_storefront:checkout"), {"cart_version": version})
        self.assertRedirects(retry, reverse("resource_storefront:success", kwargs={"sale_id": sale.pk}))
        self.assertEqual(Sale.objects.filter(storefront_source="resource_storefront").count(), 1)
        self.assertEqual(CDWarehouseStock.objects.get(warehouse=self.warehouse, cd=self.product).quantity, 1)

    def test_price_change_requires_explicit_cart_refresh(self):
        self.client.get(reverse("resource_storefront:access", kwargs={"token": self.token}))
        self.client.post(reverse("resource_storefront:cart_add"), {"kind": "cd", "product_id": self.product.pk, "quantity": 1})
        self.product.wholesale_price = Decimal("1300.00")
        self.product.save(update_fields=("wholesale_price",))
        cart = self.client.get(reverse("resource_storefront:cart"))
        self.assertTrue(cart.context["changes"])
        self.assertFalse(cart.context["checkout_allowed"])

    def test_staff_can_toggle_catalogue_publication_with_audit(self):
        self.client.force_login(self.staff)
        hide_url = reverse("resource_storefront:product_publication", kwargs={"kind": "cd", "pk": self.product.pk})
        response = self.client.post(hide_url, {"enabled": "0"})
        self.assertRedirects(response, reverse("resource_storefront:manage"))
        self.product.refresh_from_db()
        self.assertFalse(self.product.wholesale_site_enabled)
        event = ProductChangeEvent.objects.filter(action_kind="storefront_publication", cd=self.product).get()
        change = event.field_changes.get(field_name="wholesale_site_enabled")
        self.assertEqual((change.old_value, change.new_value), ("True", "False"))
        self.client.get(reverse("resource_storefront:access", kwargs={"token": self.token}))
        self.assertEqual(self.client.get(reverse("resource_storefront:product", kwargs={"kind": "cd", "pk": self.product.pk})).status_code, 404)
        response = self.client.post(hide_url, {"enabled": "1"})
        self.assertRedirects(response, reverse("resource_storefront:manage"))
        self.product.refresh_from_db()
        self.assertTrue(self.product.wholesale_site_enabled)
        self.assertEqual(ProductChangeEvent.objects.filter(action_kind="storefront_publication", cd=self.product).count(), 2)

    def test_contact_management_requires_permission_and_access_link_does_not_log_in_staff(self):
        url = reverse("resource_storefront:contacts")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.get(reverse("resource_storefront:manage")).status_code, 200)
        self.assertFalse(self.staff.is_authenticated is False)
        new_link, new_token = issue_link(self.contact, self.staff)
        self.assertNotEqual(new_token, self.token)
        self.assertFalse(WholesaleAccessLink.objects.get(pk=self.link.pk).is_active)

    def test_new_contact_receives_a_link_automatically(self):
        self.client.force_login(self.staff)
        response = self.client.post(reverse("resource_storefront:contact_new"), {
            "name": "Новый оптовый покупатель", "phone": "+7 999 111-22-33", "address": "Новый адрес",
        })
        self.assertRedirects(response, reverse("resource_storefront:contacts"))
        contact = WholesaleContact.objects.get(phone="+7 999 111-22-33")
        link = WholesaleAccessLink.objects.get(contact=contact, is_active=True)
        from .security import recover_token
        token = recover_token(link)
        self.assertTrue(token)
        self.assertEqual(self.client.get(reverse("resource_storefront:access", kwargs={"token": token})).status_code, 302)

    def test_price_page_lists_contacts_and_their_recoverable_links(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("price:index"))
        self.assertContains(response, "Пользователи оптового сайта")
        self.assertContains(response, self.contact.name)
        self.assertContains(response, f"/opt/{self.token}/")
        self.assertContains(response, "Перегенерировать")

    def test_draft_news_only_appears_in_staff_preview(self):
        StorefrontNews.objects.create(title="Черновик", slug="draft-only", body="Внутренний текст")
        public = self.client.get(reverse("resource_storefront:access", kwargs={"token": self.token}))
        self.assertEqual(public.status_code, 302)
        response = self.client.get(reverse("resource_storefront:news_detail", kwargs={"slug": "draft-only"}))
        self.assertEqual(response.status_code, 404)
        self.client.logout()
        self.client.force_login(self.staff)
        preview = self.client.get(reverse("resource_storefront:preview_start"))
        self.assertEqual(preview.status_code, 302)
        response = self.client.get(preview.url)
        self.assertContains(response, "Черновик")
