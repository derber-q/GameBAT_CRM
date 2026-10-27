"""Создание площадки отдельно и в одной транзакции с партнёром."""
import uuid
from unittest.mock import patch
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from accounts.models import User
from creditors.models import Creditor
from .models import Partner, SalesPlatform


class PlatformCreationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('platform-admin')
        self.client.force_login(self.admin)
        self.details = {'name': 'Игромир', 'address': 'Адрес', 'legal_entity': 'ИП', 'phone_1': '00123',
            'phone_2': '00456', 'phone_3': '', 'email': 'shop@example.com', 'telegram': '@shop'}

    def partner_payload(self):
        return {'request_key': str(uuid.uuid4()), 'name': 'Партнёр', 'create_platform': 'on',
            **{f'new_platform-{key}': value for key, value in self.details.items()}}

    def grant(self, user, *permissions):
        for app_label, codename in (value.split('.') for value in permissions):
            user.user_permissions.add(Permission.objects.get(content_type__app_label=app_label, codename=codename))

    def test_standalone_creation_and_button(self):
        response = self.client.get(reverse('consignment:list'))
        self.assertContains(response, reverse('consignment:platform_create'))
        response = self.client.post(reverse('consignment:platform_create'), self.details)
        platform = SalesPlatform.objects.get()
        self.assertRedirects(response, reverse('consignment:platform', args=[platform.pk]))
        self.assertEqual(platform.email, 'shop@example.com')
        self.assertFalse(Partner.objects.exists())
        self.assertFalse(Creditor.objects.exists())

    def test_standalone_permission_checked_on_backend(self):
        user = User.objects.create_user('platform-viewer')
        self.grant(user, 'consignment.view_cdconsignmentstock')
        self.client.force_login(user)
        self.assertNotContains(self.client.get(reverse('consignment:list')), reverse('consignment:platform_create'))
        self.assertEqual(self.client.get(reverse('consignment:platform_create')).status_code, 403)
        self.assertEqual(self.client.post(reverse('consignment:platform_create'), self.details).status_code, 403)
        self.assertFalse(SalesPlatform.objects.exists())

    def test_creation_requires_model_fields(self):
        response = self.client.post(reverse('consignment:platform_create'), {'name': 'Без реквизитов'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('legal_entity', response.context['form'].errors)
        self.assertFalse(SalesPlatform.objects.exists())

    def test_inline_creates_partner_platform_account_once(self):
        payload = self.partner_payload()
        first = self.client.post(reverse('partners:partner_create'), payload)
        partner = Partner.objects.select_related('platform', 'creditor').get()
        self.assertRedirects(first, reverse('partners:partner_detail', args=[partner.pk]))
        self.assertEqual(partner.platform.name, self.details['name'])
        self.assertEqual(partner.creditor.current_debt, 0)
        second = self.client.post(reverse('partners:partner_create'), payload)
        self.assertRedirects(second, first['Location'])
        self.assertEqual((Partner.objects.count(), SalesPlatform.objects.count(), Creditor.objects.count()), (1, 1, 1))

    def test_inline_invalid_fields_create_nothing(self):
        for field in ('name', 'new_platform-name', 'new_platform-legal_entity'):
            with self.subTest(field=field):
                payload = self.partner_payload()
                payload[field] = ''
                response = self.client.post(reverse('partners:partner_create'), payload)
                self.assertEqual(response.status_code, 200)
                self.assertEqual((Partner.objects.count(), SalesPlatform.objects.count(), Creditor.objects.count()), (0, 0, 0))

    def test_cannot_select_existing_and_create_another(self):
        platform = SalesPlatform.objects.create(**self.details)
        response = self.client.post(reverse('partners:partner_create'), {**self.partner_payload(), 'platform': platform.pk})
        self.assertContains(response, 'Выберите существующую площадку или создайте новую.')
        self.assertEqual(SalesPlatform.objects.count(), 1)
        self.assertFalse(Partner.objects.exists())

    def test_account_failure_rolls_back_new_platform(self):
        with patch('creditors.models.Creditor.objects.create', side_effect=RuntimeError('account failed')):
            with self.assertRaisesMessage(RuntimeError, 'account failed'):
                self.client.post(reverse('partners:partner_create'), self.partner_payload())
        self.assertEqual((Partner.objects.count(), SalesPlatform.objects.count(), Creditor.objects.count()), (0, 0, 0))

    def test_partner_permission_does_not_grant_platform_creation(self):
        user = User.objects.create_user('partner-creator')
        self.grant(user, 'partners.add_partner', 'partners.view_partner_contacts')
        self.client.force_login(user)
        response = self.client.get(reverse('partners:partner_create'))
        self.assertNotContains(response, 'name="create_platform"')
        self.assertEqual(self.client.post(reverse('partners:partner_create'), self.partner_payload()).status_code, 403)
        self.assertEqual((Partner.objects.count(), SalesPlatform.objects.count(), Creditor.objects.count()), (0, 0, 0))
