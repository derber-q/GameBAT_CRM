from decimal import Decimal
from django.urls import reverse
from . import test_refinement
from django.test import TestCase, override_settings
from cryptography.fernet import Fernet
from sales.models import Sale


@override_settings(RESOURCE_TOKEN_ENCRYPTION_KEY=Fernet.generate_key().decode())
class MobileFlowTests(TestCase):
    setUpTestData = classmethod(test_refinement.RefinementTests.setUpTestData.__func__)
    setUp = test_refinement.RefinementTests.setUp
    def add(self, operation="mobile-op"):
        return self.client.post(reverse("resource_storefront:cart_add"),
            {"kind":"cd", "product_id":self.cd.pk, "quantity":1, "operation":operation}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")

    def test_add_retry_has_same_result(self):
        self.assertEqual(self.add().status_code,200)
        self.assertEqual(self.add().json()["cart_count"],1)
        self.assertEqual(self.client.session["resource_cart"][f"cd:{self.cd.pk}"],1)

    def test_edit_does_not_accept_changed_prices(self):
        self.add()
        self.cd.wholesale_price = Decimal("2000")
        self.cd.save(update_fields=("wholesale_price",))
        response = self.client.post(reverse("resource_storefront:cart_update", args=[f"cd:{self.cd.pk}"]), {"quantity":2}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code,200)
        self.assertIn("Цена или наличие изменились",response.json()["html"])
        cart = self.client.get(reverse("resource_storefront:cart"))
        self.assertFalse(cart.context["checkout_allowed"])
        self.assertEqual(self.client.session["resource_cart_seen"][f"cd:{self.cd.pk}"]["price"],"1000.25")

    def test_checkout_fields_and_recovery(self):
        self.add()
        cart = self.client.get(reverse("resource_storefront:cart"))
        version = cart.context["version"]
        response = self.client.post(reverse("resource_storefront:checkout"), {"cart_version":version,"extra_phone":"abc","comment":"Не потерять"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code,400)
        self.assertIn("extra_phone",response.json()["fields"])
        self.assertEqual(self.client.get(reverse("resource_storefront:cart")).context["checkout_form"]["comment"].value(),"Не потерять")
        response = self.client.post(reverse("resource_storefront:checkout"), {"cart_version":version,"comment":"Не потерять"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.client.get(reverse("resource_storefront:checkout_status")).json()["url"],response.json()["url"])
        retry = self.client.post(reverse("resource_storefront:checkout"), {"cart_version":version}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(retry.json()["url"],response.json()["url"])
        self.assertEqual(Sale.objects.filter(storefront_source="resource_storefront").count(),1)

    def test_revoked_session_cannot_read_status_or_mutate_cart(self):
        from .models import WholesaleAccessLink
        link=WholesaleAccessLink.objects.get(pk=self.client.session["resource_link_id"])
        link.is_active=False
        link.save(update_fields=("is_active",))
        self.assertEqual(self.add().status_code,403)
        self.assertEqual(self.client.get(reverse("resource_storefront:checkout_status"),HTTP_X_REQUESTED_WITH="XMLHttpRequest").status_code,403)

    def test_contact_switch_clears_cart_and_draft(self):
        from .models import WholesaleContact
        from .security import issue_link
        self.add()
        session = self.client.session
        session["resource_checkout_draft"] = {"comment":"Первый контакт"}
        session.save()
        contact = WholesaleContact.objects.create(name="Второй контакт", phone="+79991111111")
        _, token = issue_link(contact, None)
        self.client.get(reverse("resource_storefront:access", args=[token]))
        for key in ("resource_cart", "resource_checkout_draft", "resource_cart_operations"):
            self.assertNotIn(key, self.client.session)

    def test_thumbnail_is_private_and_preserves_aspect_ratio(self):
        import tempfile
        from io import BytesIO
        from PIL import Image
        from django.core.files.base import ContentFile
        with tempfile.TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            source = BytesIO()
            Image.new("RGB",(1200,600),(35,85,60)).save(source,"PNG")
            self.cd.title_image.save("mobile-thumbnail.png",ContentFile(source.getvalue()))
            response = self.client.get(reverse("resource_storefront:product_photo", args=["cd",self.cd.pk,0]),{"w":"320"})
            self.assertEqual(response.status_code,200)
            self.assertEqual(response["Content-Type"],"image/webp")
            self.assertIn("no-store",response["Cache-Control"])
            with Image.open(BytesIO(response.content)) as image:
                self.assertEqual(image.size,(320,160))
