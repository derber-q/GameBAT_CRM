from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from .models import Supplier


class SupplierPrivacyTests(TestCase):
    def setUp(self):
        self.supplier = Supplier.objects.create(
            name="Секретный поставщик", letter="A", highlight_color="#37A7BA",
            legal_entity="ООО Секрет", email="hidden@example.com", phone_1="+79990000000",
            telegram="hidden_contact",
        )
        self.worker = User.objects.create_user("worker", password="StrongWorker!123")
        self.worker.user_permissions.add(Permission.objects.get(content_type__app_label="partners", codename="view_supplier"))
        self.client.force_login(self.worker)

    def test_user_without_detail_permission_receives_only_safe_supplier_marker(self):
        response = self.client.get(reverse("partners:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, ">A</span>", html=False)
        self.assertNotContains(response, self.supplier.name)
        self.assertNotContains(response, self.supplier.legal_entity)
        self.assertNotContains(response, self.supplier.email)
        self.assertNotContains(response, self.supplier.phone_1)
        self.assertNotContains(response, self.supplier.telegram)

    def test_detail_permission_reveals_full_data(self):
        self.worker.user_permissions.add(Permission.objects.get(content_type__app_label="partners", codename="view_supplier_details"))
        response = self.client.get(reverse("partners:list"))
        self.assertContains(response, self.supplier.name)
        self.assertContains(response, self.supplier.email)
