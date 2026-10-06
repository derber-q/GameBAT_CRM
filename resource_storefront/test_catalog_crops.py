import tempfile
from io import BytesIO
from pathlib import Path

from cryptography.fernet import Fernet
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from . import test_refinement
from .models import CatalogImageCrop, WholesaleAccessLink


@override_settings(RESOURCE_TOKEN_ENCRYPTION_KEY=Fernet.generate_key().decode())
class CatalogCropTests(TestCase):
    setUpTestData = classmethod(test_refinement.RefinementTests.setUpTestData.__func__)
    setUp = test_refinement.RefinementTests.setUp

    def test_focal_crop_original_and_replacement(self):
        with tempfile.TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            original = Image.new("RGB", (1200, 600), "red")
            original.paste("blue", (600, 0, 1200, 600))
            source = BytesIO()
            original.save(source, "PNG")
            self.cd.title_image.save("wide.png", ContentFile(source.getvalue()))
            path = Path(self.cd.title_image.path)
            framing = CatalogImageCrop.objects.create(cd=self.cd, position_x=100, zoom="1.20")
            url = reverse("resource_storefront:product_photo", args=["cd", self.cd.pk, 0])
            response = self.client.get(url, {"w": "320", "crop": "card"})
            self.assertEqual(response.status_code, 200)
            self.assertIn("no-store", response["Cache-Control"])
            with Image.open(BytesIO(response.content)) as image:
                self.assertEqual(image.width, 320)
                self.assertAlmostEqual(image.width / image.height, .75, delta=.005)
                self.assertGreater(image.getpixel((10, 10))[2], 240)
            self.assertEqual(path.read_bytes(), source.getvalue())
            self.assertEqual(self.client.get(url).content, source.getvalue())
            self.cd.title_image.save("replacement.png", ContentFile(source.getvalue()))
            response = self.client.get(url, {"w": "320", "crop": "card"})
            with Image.open(BytesIO(response.content)) as image:
                self.assertGreater(image.getpixel((10, 10))[0], 240)
            framing.refresh_from_db()
            self.assertNotEqual(framing.source_image, self.cd.title_image.name)
            link = WholesaleAccessLink.objects.get(pk=self.client.session["resource_link_id"])
            link.is_active = False
            link.save(update_fields=("is_active",))
            self.assertEqual(self.client.get(url, {"w": "320", "crop": "card"}, follow=True).status_code, 403)

    def test_crop_validation(self):
        for values in ({"position_x":101}, {"zoom":"0.5"}, {"zoom":"3.1"}):
            framing = CatalogImageCrop(cd=self.cd, source_image="photo.jpg", **values)
            with self.assertRaises(ValidationError):
                framing.full_clean()

    def test_card_order_and_original_link(self):
        response = self.client.get(reverse("resource_storefront:catalogue"))
        html = response.content.decode()
        self.assertLess(html.index('class="rs-price"'), html.index('class="rs-card-name"'))
        self.assertNotIn('class="rs-card-kind"', html)
