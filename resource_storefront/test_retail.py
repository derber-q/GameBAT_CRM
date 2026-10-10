import hashlib
import logging
import secrets
from decimal import Decimal

from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from catalog.models import CD, Platform
from warehouse.models import Warehouse, CDWarehouseStock
from .forms import RetailCheckoutForm
from .models import RetailSettings, WholesaleContact
from .retail_security import retail_link
from .security import recover_token, issue_link
from .log_filters import RetailTokenFilter


@override_settings(RESOURCE_TOKEN_ENCRYPTION_KEY=Fernet.generate_key().decode())
class RetailTests(TestCase):
    def setUp(self):
        self.warehouse = Warehouse.objects.create(name="Розничный тест")
        RetailSettings.objects.update_or_create(pk=1, defaults={"warehouse":self.warehouse})
        self.config = retail_link()
        self.token = recover_token(self.config)
        platform = Platform.objects.create(name="Розничная платформа")
        self.product = CD.objects.create(name="Розничная игра", platform=platform, avito_price=Decimal("4321.00"), wholesale_price=Decimal("1234.00"),cost=Decimal("250.00"))
        self.stock = CDWarehouseStock.objects.create(cd=self.product,warehouse=self.warehouse,quantity=8)
        self.access(self.client)

    def access(self, client):
        return client.get(reverse("retailer:access", args=[self.token]))

    def add(self, client=None):
        return (client or self.client).post(reverse("retailer:cart_add"), {"kind":"cd","product_id":self.product.pk,"quantity":1},HTTP_X_REQUESTED_WITH="XMLHttpRequest")

    def test_token_strength_rotation_and_all_gates(self):
        self.assertGreaterEqual(len(self.token),43)
        self.assertEqual(hashlib.sha256(self.token.encode()).hexdigest(),self.config.token_digest)
        self.assertNotIn(self.token,self.config.encrypted_token)
        anonymous = Client()
        paths=[reverse("retailer:home"), reverse("retailer:catalogue")+"?q=игра",reverse("retailer:product",args=["cd",self.product.pk]),reverse("retailer:product_photo",args=["cd",self.product.pk,0]),reverse("retailer:cart"),reverse("retailer:checkout_status"),reverse("retailer:success",args=[1])]
        posts=[reverse("retailer:cart_add"),reverse("retailer:cart_update",args=[f"cd:{self.product.pk}"]),reverse("retailer:cart_remove",args=[f"cd:{self.product.pk}"]),reverse("retailer:cart_refresh"),reverse("retailer:checkout")]
        for path in paths: self.assertEqual(anonymous.get(path).status_code,403)
        for path in posts: self.assertEqual(anonymous.post(path).status_code,403)
        self.add()
        retail_link(regenerate=True)
        self.assertEqual(self.access(anonymous).status_code,404)
        for path in paths: self.assertEqual(self.client.get(path).status_code,403)
        for path in posts: self.assertEqual(self.client.post(path).status_code,403)
        self.token=recover_token(RetailSettings.objects.get(pk=1))
        self.assertEqual(self.access(self.client).status_code,302)
        self.assertEqual(self.client.get(reverse("retailer:cart")).context["cart_count"],1)
        self.assertNotIn('/retailer/', anonymous.get('/')["Location"])

    def test_prices_stock_isolation_and_wholesale_session(self):
        from .models import StorefrontSettings
        StorefrontSettings.objects.update_or_create(pk=1,defaults={"warehouse":self.warehouse})
        contact=WholesaleContact.objects.create(name="Оптовик",phone="+79990000000")
        _,token=issue_link(contact,None)
        self.client.get(reverse("resource_storefront:access",args=[token]))
        self.client.post(reverse("resource_storefront:cart_add"),{"kind":"cd","product_id":self.product.pk,"quantity":2})
        self.add()
        retail=self.client.get(reverse("retailer:catalogue"))
        self.assertContains(retail,"4\u00a0321")
        self.assertNotContains(retail,"1\u00a0234")
        self.assertNotContains(retail,"wholesale")
        self.assertNotContains(retail,"/opt/")
        self.assertEqual(self.client.get(reverse("retailer:cart")).context["total"],Decimal("4321"))
        self.assertEqual(self.client.get(reverse("resource_storefront:cart")).context["total"],Decimal("2468"))
        other=Client();self.access(other)
        self.assertEqual(other.get(reverse("retailer:cart")).context["cart_count"],0)
        retail_link(regenerate=True)
        self.assertEqual(self.client.get(reverse("resource_storefront:cart")).status_code,200)

    def test_no_price_fallback_or_other_warehouse_stock(self):
        self.product.avito_price=None;self.product.save(update_fields=("avito_price",))
        self.assertEqual(self.client.get(reverse("retailer:catalogue")).context["page_obj"].paginator.count,0)
        self.assertEqual(self.client.get(reverse("retailer:product",args=["cd",self.product.pk])).status_code,404)
        self.product.avito_price=5000;self.product.save(update_fields=("avito_price",))
        self.stock.quantity=0;self.stock.save()
        other=Warehouse.objects.create(name="Другой розничный склад")
        CDWarehouseStock.objects.create(cd=self.product,warehouse=other,quantity=20)
        self.assertEqual(self.add().status_code,409)

    def test_contact_combinations_and_validation(self):
        base={"name":"Покупатель","phone":"+79991234567","comment":"Позвонить вечером"}
        for methods in ([],["phone"],["telegram"],["whatsapp"],["telegram","whatsapp"]):
            form=RetailCheckoutForm({**base,"communication":methods,"telegram_use_phone":"on"})
            self.assertTrue(form.is_valid(),form.errors)
            self.assertEqual(form.cleaned_data["communication"],methods or ["phone"])
        form=RetailCheckoutForm({**base,"communication":["telegram"],"telegram":"@buyer_test"})
        self.assertTrue(form.is_valid(),form.errors)
        self.assertEqual(form.cleaned_data["telegram"],"@buyer_test")
        self.assertFalse(RetailCheckoutForm({**base,"communication":["telegram"]}).is_valid())
        self.assertFalse(RetailCheckoutForm({**base,"phone":"-----"}).is_valid())

    def test_price_page_permission_and_logging(self):
        staff=get_user_model().objects.create_superuser(username="retail-admin",password="isolated-test-password")
        self.assertNotEqual(self.client.post(reverse("resource_storefront:retail_regenerate")).status_code,200)
        self.client.force_login(staff)
        response=self.client.get(reverse("price:site_links"))
        self.assertContains(response,"Розничный сайт")
        self.assertContains(response,f"/retailer/{self.token}/")
        record=logging.LogRecord("django.server",logging.INFO,"",1,'"GET %s HTTP/1.1"',('/retailer/'+self.token+'/',),None)
        RetailTokenFilter().filter(record)
        self.assertNotIn(self.token,record.getMessage())

    def test_checkout_snapshots_retry_privacy_cancel_and_cash(self):
        from sales.models import Sale
        from cash.models import CashTransaction
        from sales.services import cancel_sale
        from .models import RetailSubmission
        self.add()
        cart=self.client.get(reverse("retailer:cart"))
        data={"cart_version":cart.context["version"],"name":"Имя покупателя","phone":"+79991234567",
              "communication":["telegram","whatsapp"],"telegram":"@buyer_test","whatsapp":"+79997654321","comment":"После 18:00",
              "price_type":"wholesale","sale_type":"avito","payment_method":"cash","price":"1"}
        response=self.client.post(reverse("retailer:checkout"),data,HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code,200,response.content)
        sale=Sale.objects.get(storefront_source="resource_retail")
        self.assertEqual(sale.sale_type,Sale.SaleType.RETAIL)
        self.assertEqual(sale.total_amount,Decimal("4321"))
        self.assertEqual(sale.payment_status,Sale.PaymentStatus.UNPAID)
        self.assertFalse(CashTransaction.objects.exists())
        self.assertIsNone(sale.wholesale_contact_id)
        self.assertEqual(sale.buyer_telegram,"@buyer_test")
        self.assertEqual(sale.buyer_whatsapp,"+79997654321")
        self.assertEqual(sale.cd_items.get().unit_cost_snapshot,Decimal("250"))
        self.assertEqual(self.client.post(reverse("retailer:checkout"),data,HTTP_X_REQUESTED_WITH="XMLHttpRequest").json(),response.json())
        self.assertEqual(self.client.get(reverse("retailer:checkout_status")).json(),response.json())
        self.assertEqual(RetailSubmission.objects.count(),1)
        other=Client();self.access(other)
        self.assertEqual(other.get(response.json()["url"]).status_code,404)
        staff=get_user_model().objects.create_superuser(username="sale-review",password="isolated-test-password")
        crm=Client();crm.force_login(staff)
        detail=crm.get(reverse("sales:detail",args=[sale.pk]))
        for text in ("Розничный сайт","Имя покупателя","@buyer_test","+79997654321","После 18:00"):
            self.assertContains(detail,text)
        cancel_sale(actor=staff,sale_id=sale.pk,comment="Проверка")
        cancel_sale(actor=staff,sale_id=sale.pk,comment="Повтор")
        self.stock.refresh_from_db();self.assertEqual(self.stock.quantity,8)
        self.assertFalse(CashTransaction.objects.exists())

    def test_changed_price_confirmation_and_rollback(self):
        from unittest.mock import patch
        from sales.models import Sale
        from .models import RetailSubmission
        self.add()
        version=self.client.get(reverse("retailer:cart")).context["version"]
        data={"cart_version":version,"name":"Покупатель","phone":"+79991234567","comment":"Сохранить"}
        self.product.avito_price=5000;self.product.save(update_fields=("avito_price",))
        response=self.client.post(reverse("retailer:checkout"),data,HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code,409)
        self.assertFalse(Sale.objects.exists())
        self.assertEqual(self.client.session["retailer_checkout_draft"]["comment"],"Сохранить")
        self.client.post(reverse("retailer:cart_refresh"))
        data["cart_version"]=self.client.get(reverse("retailer:cart")).context["version"]
        from django.core.exceptions import ValidationError
        with patch.object(RetailSubmission,"save",side_effect=[None,ValidationError("Откат")]):
            # Ошибка после создания продажи откатывает также её складское списание.
            response=self.client.post(reverse("retailer:checkout"),data,HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code,409)
        self.assertFalse(Sale.objects.exists())
        self.stock.refresh_from_db();self.assertEqual(self.stock.quantity,8)

    def test_checkout_does_not_choose_payment_implicitly(self):
        self.add()
        version=self.client.get(reverse("retailer:cart")).context["version"]
        response=self.client.post(reverse("retailer:checkout"),{"cart_version":version,"name":"Покупатель","phone":"+79991234567"},HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code,200)
        from sales.models import Sale
        self.assertEqual(Sale.objects.get().payment_method, Sale.PaymentMethod.UNDEFINED)

    def test_staff_payment_selection_and_confirmation(self):
        from sales.models import Sale
        from sales.services import set_sale_payment_method, mark_sale_paid
        from cash.models import CashTransaction
        from django.core.exceptions import ValidationError
        staff = get_user_model().objects.create_superuser(username="payment-staff", password="isolated-test-password")
        for method in (Sale.PaymentMethod.CASH_POSTPAY, Sale.PaymentMethod.BANK_ACCOUNT):
            self.add()
            version = self.client.get(reverse("retailer:cart")).context["version"]
            response = self.client.post(reverse("retailer:checkout"), {"cart_version":version,"name":"Покупатель","phone":"+79991234567"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
            self.assertEqual(response.status_code, 200)
            sale = Sale.objects.latest("pk")
            self.assertEqual(sale.payment_method, Sale.PaymentMethod.UNDEFINED)
            before = CashTransaction.objects.count()
            with self.assertRaises(ValidationError):
                mark_sale_paid(actor=staff, sale_id=sale.pk)
            with self.assertRaises(ValidationError):
                set_sale_payment_method(actor=staff, sale_id=sale.pk, payment_method="cash")
            url = reverse("sales:payment_method", args=[sale.pk])
            unauthorized = Client()
            unauthorized.force_login(get_user_model().objects.create_user(username="no-permission-"+method))
            self.assertEqual(unauthorized.post(url, {"payment_method":method}).status_code, 403)
            crm = Client(); crm.force_login(staff)
            self.assertContains(crm.get(reverse("sales:detail", args=[sale.pk])), "Сохранить способ оплаты")
            self.assertEqual(crm.post(url, {"payment_method":method}).status_code, 302)
            sale.refresh_from_db()
            self.assertEqual(sale.payment_method, method)
            self.assertEqual(sale.payment_status, Sale.PaymentStatus.UNPAID)
            self.assertEqual(CashTransaction.objects.count(), before)
            with self.assertRaises(ValidationError):
                set_sale_payment_method(actor=staff, sale_id=sale.pk, payment_method=method)
            mark_sale_paid(actor=staff, sale_id=sale.pk)
            sale.refresh_from_db()
            self.assertEqual(sale.payment_status, Sale.PaymentStatus.PAID)
            self.assertEqual(CashTransaction.objects.count(), before + (method == Sale.PaymentMethod.CASH_POSTPAY))
            with self.assertRaises(ValidationError):
                mark_sale_paid(actor=staff, sale_id=sale.pk)
