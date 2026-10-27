"""Сохранение Telegram, повтор формы и защита контакта правами справочника."""
import uuid

from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from creditors.models import Creditor
from .models import Partner
from .telegram import normalize_telegram, telegram_chat_url


class PartnerTelegramTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_superuser('telegram-admin')
        self.client.force_login(self.actor)

    def test_supported_formats_and_invalid_values(self):
        for value in ('@Some_User', 'Some_User', ' https://t.me/Some_User/ ', 't.me/Some_User', 'https://telegram.me/Some_User'):
            with self.subTest(value=value):
                self.assertEqual(normalize_telegram(value), '@Some_User')
                self.assertEqual(telegram_chat_url(value), 'https://web.telegram.org/k/#@Some_User')
        self.assertEqual(telegram_chat_url(''), '')
        for value in ('javascript:alert(1)', 'https://example.com/user', '@invalid name', '@@name', 'https://t.me/name/123'):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                normalize_telegram(value)
            self.assertEqual(telegram_chat_url(value), '')

    def test_create_replay_edit_clear_and_safe_links(self):
        payload = {'request_key': str(uuid.uuid4()), 'name': 'Игромир', 'telegram': 'https://t.me/Partner_Contact'}
        first = self.client.post(reverse('partners:partner_create'), payload)
        partner = Partner.objects.get()
        self.assertEqual(partner.telegram, '@Partner_Contact')
        self.assertEqual(self.client.post(reverse('partners:partner_create'), payload)['Location'], first['Location'])
        self.assertEqual(Creditor.objects.count(), 1)
        for name, args in (('partners:partner_list', []), ('partners:partner_detail', [partner.pk])):
            response = self.client.get(reverse(name, args=args))
            self.assertContains(response, 'href="https://web.telegram.org/k/#@Partner_Contact"')
            self.assertContains(response, 'target="_blank" rel="noopener noreferrer"')
        payload.update(telegram='@Updated_Contact')
        self.assertEqual(self.client.post(reverse('partners:partner_edit', args=[partner.pk]), payload).status_code, 302)
        partner.refresh_from_db()
        self.assertEqual(partner.telegram, '@Updated_Contact')
        payload['telegram'] = ''
        self.client.post(reverse('partners:partner_edit', args=[partner.pk]), payload)
        partner.refresh_from_db()
        self.assertEqual(partner.telegram, '')
        self.assertNotContains(self.client.get(reverse('partners:partner_list')), 'web.telegram.org/k/#')

    def test_contact_permission_applies_to_link_and_edit(self):
        partner = Partner.objects.create(name='Игромир', telegram='@Private_Contact')
        viewer = User.objects.create_user('telegram-viewer')
        viewer.user_permissions.add(Permission.objects.get(content_type__app_label='partners', codename='view_partner'))
        self.client.force_login(viewer)
        for name, args in (('partners:partner_list', []), ('partners:partner_detail', [partner.pk])):
            response = self.client.get(reverse(name, args=args))
            self.assertNotContains(response, 'Private_Contact')
            self.assertNotContains(response, 'web.telegram.org/k/#')
        self.assertEqual(self.client.post(reverse('partners:partner_edit', args=[partner.pk]),
            {'name': 'Игромир', 'telegram': '@Other_Contact'}).status_code, 403)
        partner.refresh_from_db()
        self.assertEqual(partner.telegram, '@Private_Contact')

    def test_invalid_contact_does_not_create_partner_or_account(self):
        response = self.client.post(reverse('partners:partner_create'),
            {'request_key': str(uuid.uuid4()), 'name': 'Игромир', 'telegram': 'https://example.com/'})
        self.assertIn('telegram', response.context['form'].errors)
        with self.assertRaises(ValidationError):
            Partner.objects.create(name='Некорректный контакт', telegram='bad contact')
        self.assertFalse(Partner.objects.exists())
        self.assertFalse(Creditor.objects.exists())
