"""Обновление доступно только администратору production и только по явному POST."""
from unittest.mock import patch
import uuid

from django.test import TestCase, Client, override_settings
from django.urls import reverse

from accounts.models import User


class UpdatesPageTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('updates-admin')
        self.client.force_login(self.admin)

    def test_local_modes_only_show_message_without_io_or_installation(self):
        for mode in ('local_live', 'local_test'):
            with override_settings(GAMEBAT_ENV=mode), \
                    patch('subprocess.run', side_effect=AssertionError('shell forbidden')), \
                    patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('network forbidden')), \
                    patch('core.update_views.update_state', side_effect=AssertionError('state forbidden')), \
                    patch('core.update_views.submit', side_effect=AssertionError('socket forbidden')):
                page = self.client.get(reverse('integrations:updates'))
                self.assertContains(page, 'Обновить до последней версии')
                response = self.client.post(reverse('integrations:updates'), {'action': 'install', 'environment': 'production'}, follow=True)
                self.assertContains(response, 'Обновления доступны только для production-версии.')

    def test_only_superuser_can_open_or_submit(self):
        self.client.force_login(User.objects.create_user('updates-staff'))
        for method in (self.client.get, self.client.post):
            self.assertEqual(method(reverse('integrations:updates')).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(reverse('integrations:updates')).status_code, 302)

    def test_csrf_and_method_are_enforced(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        self.assertEqual(client.post(reverse('integrations:updates'), {'action': 'install'}).status_code, 403)
        self.assertEqual(self.client.put(reverse('integrations:updates')).status_code, 405)

    @override_settings(GAMEBAT_ENV='production', UPDATE_STATUS_FILE='')
    def test_unconfigured_production_cannot_install(self):
        page = self.client.post(reverse('integrations:updates'), {'action': 'install', 'confirm': 'yes'}, follow=True)
        self.assertContains(page, 'Менеджер обновлений не настроен')

    def test_menu_is_only_visible_to_superuser(self):
        self.assertContains(self.client.get(reverse('integrations:workers')), reverse('integrations:updates'))
        self.client.force_login(User.objects.create_user('updates-menu-staff'))
        self.assertNotContains(self.client.get(reverse('integrations:workers')), reverse('integrations:updates'))

    @override_settings(GAMEBAT_ENV='production', UPDATE_SOCKET='/run/resource-update.sock')
    def test_production_get_never_enqueues_and_install_requires_exact_approved_sha(self):
        from deployment.store import now
        state={'heartbeat':{'at':now(),'protocol':1},'current':{'sha':'a'*40},
               'latest':{'sha':'b'*40,'approved':True},'history':[]}
        request_id=str(uuid.uuid4())
        with patch('core.update_views.update_state',return_value=state), patch('core.update_views.submit',return_value=request_id) as submit:
            self.client.get(reverse('integrations:updates'))
            submit.assert_not_called()
            for data in ({'action':'install'}, {'action':'install','confirm':'yes','target':'c'*40}):
                self.client.post(reverse('integrations:updates'),data)
            submit.assert_not_called()
            self.client.post(reverse('integrations:updates'),{'action':'install','confirm':'yes','target':'b'*40,'request_id':request_id})
            self.assertEqual(submit.call_args.args[1],{'action':'install','target':'b'*40,'request_id':request_id,'actor':self.admin.pk})

    @override_settings(GAMEBAT_ENV='production')
    def test_health_requires_exact_version_database_and_stable_workers(self):
        with patch('core.update_health.current_version',return_value={'sha':'a'*40}), \
                patch('core.update_health.connection') as connection, \
                patch('integrations.worker_monitoring.monitoring_snapshot') as snapshot:
            connection.vendor='postgresql'
            connection.is_usable.return_value=True
            snapshot.return_value={'mode':'managed','controller_ok':True,'services':[{'expected':'required','status':'recovering'}]}
            self.assertEqual(self.client.get(reverse('core:update_health')).status_code,503)
            snapshot.return_value['services'][0]['status']='running'
            response=self.client.get(reverse('core:update_health'))
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json()['sha'],'a'*40)
