import shutil
import tempfile
from pathlib import Path

from django.contrib.auth.models import Group, Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import User


def permission(app_label, codename):
    return Permission.objects.get(content_type__app_label=app_label, codename=codename)


class AuthenticationAndPermissionTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("admin", password="StrongAdmin!123")
        self.worker = User.objects.create_user("worker", password="StrongWorker!123", full_name="Иван Работник")

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse("catalog:warehouse"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_superuser_has_full_access(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("accounts:user_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Пользователи")

    def test_administrative_forms_render_for_superuser(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("accounts:user_create")).status_code, 200)
        self.assertEqual(self.client.get(reverse("accounts:user_update", args=(self.worker.pk,))).status_code, 200)
        self.assertEqual(self.client.get(reverse("accounts:permission_set_create")).status_code, 200)

    def test_worker_with_admin_panel_permission_still_cannot_open_user_admin(self):
        self.worker.user_permissions.add(
            permission("core", "access_admin_panel"), permission("accounts", "view_user")
        )
        response = self.client.post(reverse("admin:login"), {
            "username": "worker", "password": "StrongWorker!123", "next": reverse("admin:index")
        })
        self.assertRedirects(response, reverse("admin:index"))
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 200)
        self.assertEqual(self.client.get(reverse("admin:accounts_user_changelist")).status_code, 403)

    def test_worker_without_permissions_is_denied_direct_url(self):
        self.client.force_login(self.worker)
        self.assertEqual(self.client.get(reverse("catalog:warehouse")).status_code, 403)

    def test_worker_cannot_create_users_or_edit_own_profile(self):
        self.client.force_login(self.worker)
        self.assertEqual(self.client.get(reverse("accounts:user_create")).status_code, 403)
        self.assertEqual(self.client.get(reverse("accounts:user_update", args=(self.worker.pk,))).status_code, 403)

    def test_worker_can_change_own_password_and_keeps_session(self):
        self.client.force_login(self.worker)
        response = self.client.post(reverse("accounts:password_change"), {
            "old_password": "StrongWorker!123",
            "new_password1": "AnotherStrong!456",
            "new_password2": "AnotherStrong!456",
        })
        self.assertRedirects(response, reverse("core:home"))
        self.worker.refresh_from_db()
        self.assertTrue(self.worker.check_password("AnotherStrong!456"))
        self.assertIn("_auth_user_id", self.client.session)

    def test_admin_resets_password_and_old_password_stops_working(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("accounts:password_reset", args=(self.worker.pk,)), {
            "new_password1": "ResetStrong!789",
            "new_password2": "ResetStrong!789",
        })
        self.assertRedirects(response, reverse("accounts:user_detail", args=(self.worker.pk,)))
        self.worker.refresh_from_db()
        self.assertFalse(self.worker.check_password("StrongWorker!123"))
        self.assertTrue(self.worker.check_password("ResetStrong!789"))

    def test_permissions_from_multiple_groups_and_individual_are_united(self):
        group_one = Group.objects.create(name="Склад")
        group_two = Group.objects.create(name="Поставщики")
        view_cd = permission("catalog", "view_cd")
        view_supplier = permission("partners", "view_supplier")
        view_supply = permission("supplies", "view_supply")
        group_one.permissions.add(view_cd)
        group_two.permissions.add(view_supplier)
        self.worker.groups.add(group_one, group_two)
        self.worker.user_permissions.add(view_supply)
        self.assertTrue(self.worker.has_perm("catalog.view_cd"))
        self.assertTrue(self.worker.has_perm("partners.view_supplier"))
        self.assertTrue(self.worker.has_perm("supplies.view_supply"))


class ProtectedDocumentTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()
        self.owner = User.objects.create_user("owner", password="OwnerStrong!123")
        self.other = User.objects.create_user("other", password="OtherStrong!123")
        self.owner.verification_document.save(
            "proof.png", SimpleUploadedFile("proof.png", b"private-image", content_type="image/png")
        )

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)

    def test_owner_can_open_own_document_but_other_worker_cannot(self):
        url = reverse("accounts:verification_document", args=(self.owner.pk,))
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 403)
