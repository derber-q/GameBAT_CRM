"""Администрирование только суперпользователю, POST с CSRF, GET без эффектов."""
from django.test import TestCase,Client,override_settings
from django.urls import reverse
from accounts.models import User
from .models import BackupConfiguration,BackupEnrollment,BackupJob


class BackupPageTests(TestCase):
    def setUp(self):
        self.admin=User.objects.create_superuser('backup-page-owner')
        self.employee=User.objects.create_user('ordinary-employee')

    def test_pages_are_superuser_only_and_get_has_no_registration_side_effect(self):
        for name in ('dashboard','devices'):
            url=reverse('crm_backups:'+name)
            self.assertEqual(self.client.get(url).status_code,302)
            self.client.force_login(self.employee);self.assertEqual(self.client.get(url).status_code,403)
            self.client.force_login(self.admin);self.assertEqual(self.client.get(url).status_code,200)
            self.client.logout()
        self.assertFalse(BackupConfiguration.objects.exists())
        self.assertFalse(BackupEnrollment.objects.exists())

    def test_csrf_and_test_mode_block_mutation(self):
        strict=Client(enforce_csrf_checks=True);strict.force_login(self.admin)
        url=reverse('crm_backups:dashboard')
        self.assertEqual(strict.post(url,{'action':'create'}).status_code,403)
        self.client.force_login(self.admin)
        with override_settings(GAMEBAT_ENV='local_test'):
            response=self.client.post(url,{'action':'create'})
            self.assertEqual(response.status_code,200)
        self.assertFalse(BackupJob.objects.exists())
