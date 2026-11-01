"""Подменённые транспорты доказывают запрет до сетевого/физического эффекта."""
from unittest.mock import Mock, patch
from django.test import TestCase, override_settings
from django.core.exceptions import ValidationError
from django.urls import reverse
from accounts.models import User


@override_settings(GAMEBAT_ENV='local_test')
class ExternalIsolationTests(TestCase):
    def test_clients_refuse_even_explicit_keys_and_injected_transport(self):
        from integrations.client import AvitoClient
        from integrations.reef_api import ReefApiClient
        from yandex_market.client import YandexMarketClient, api_key
        transport = Mock()
        for factory in (lambda:AvitoClient(credential=Mock()), lambda:ReefApiClient(key='fake',transport=transport),
                        lambda:YandexMarketClient(key='fake',transport=transport), api_key):
            with self.assertRaisesMessage(ValidationError, 'ТЕСТОВЫЙ РЕЖИМ'):
                factory()
        transport.assert_not_called()

    def test_existing_clients_cannot_bypass_policy_at_request_boundary(self):
        from integrations.client import AvitoClient
        from integrations.reef_api import ReefApiClient
        from yandex_market.client import YandexMarketClient
        with override_settings(GAMEBAT_ENV='local_live'):
            avito = AvitoClient(credential=Mock())
            reef = ReefApiClient(key='fake',transport=Mock())
            yandex = YandexMarketClient(key='fake',transport=Mock())
        for action in (lambda:avito.get_self(), lambda:reef.search('test',1),lambda:yandex.call('getCampaigns')):
            with self.assertRaises(ValidationError):
                action()
        reef._transport.assert_not_called()
        yandex.transport.assert_not_called()

    def test_google_document_rates_and_printer_are_blocked_before_transport(self):
        from integrations.google_sheets import _google_service, sync_price_sheet
        from yandex_market.documents import download_public
        from core.services.coinbase import fetch_usdt_aed_rate, get_cached_usdt_aed_rate
        from core.services.rapira import fetch_market_rates, get_cached_market_rates
        from sales.label_printing import print_pdf, printer_configuration, _control_job, _printer_job_info
        with patch('core.services.coinbase.urlopen') as coinbase, patch('core.services.rapira.urlopen') as rapira:
            for action in (_google_service, sync_price_sheet,
                           lambda:download_public('https://yandex.ru/test.pdf',pdf=True),
                           fetch_usdt_aed_rate, fetch_market_rates, printer_configuration,
                           lambda:print_pdf(b'%PDF-',printer_name='unused',title='test'),
                           lambda:_control_job('fake',1,8), lambda:_printer_job_info('fake',1)):
                with self.assertRaises(ValidationError):
                    action()
            self.assertFalse(get_cached_usdt_aed_rate()['available'])
            self.assertFalse(get_cached_market_rates()['available'])
            coinbase.assert_not_called()
            rapira.assert_not_called()

    def test_webhook_and_extension_are_disabled_without_creating_business_data(self):
        self.client.force_login(User.objects.create_superuser('test-isolation'))
        from yandex_market.webhooks import notification
        from django.test import RequestFactory
        from yandex_market.models import WebhookEvent
        request=RequestFactory().post('/notification/',data='{"notificationType":"PING"}',content_type='application/json')
        with patch('yandex_market.webhooks.allowed_source',return_value=True) as allowed:
            self.assertEqual(notification(request).status_code,403)
            allowed.assert_not_called()
        self.assertEqual(WebhookEvent.objects.count(),0)
        self.assertEqual(self.client.get(reverse('pricing:avito_check_manual_context')).status_code,403)
        self.assertEqual(self.client.post(reverse('pricing:avito_check_found_price'),
            {'manual_queue':'1'}).status_code,403)

    def test_no_real_credentials_can_be_saved(self):
        from integrations.services import save_avito_credentials
        from integrations.reef_settings import save_key
        from yandex_market.services import store_api_key
        from integrations.models import IntegrationCredential, ReefApiCredential
        for action in (lambda:save_avito_credentials(client_id='fake',client_secret='fake'),
                       lambda:save_key('fake'),lambda:store_api_key('fake')):
            with self.assertRaises(ValidationError): action()
        self.assertEqual(IntegrationCredential.objects.count(),0)
        self.assertEqual(ReefApiCredential.objects.count(),0)

    def test_monitoring_intentionally_disables_live_services(self):
        from integrations.worker_policy import expected_services
        self.assertEqual(set(expected_services().values()), {'disabled'})

    def test_fixture_can_exercise_recovery_without_real_processes(self):
        from datetime import timedelta
        from django.utils import timezone
        from integrations.worker_models import WorkerController, WorkerProcess, WorkerService
        from integrations.worker_monitoring import supervise_once
        from integrations.test_worker_monitoring import FakeProcesses
        WorkerController.objects.create(mode='managed')
        now=timezone.now(); adapter=FakeProcesses()
        policy={code:'required' if code=='avito' else 'disabled' for code in ('avito','yandex','google','print')}
        with patch('integrations.worker_monitoring.expected_services',return_value=policy):
            supervise_once(adapter,now=now)
            code,instance=adapter.launches[0]
            row=adapter.rows[0]
            process=WorkerProcess.objects.create(instance=instance,pid=row['pid'],birth=row['birth'],
                services=[code],ready=True,heartbeat_at=now+timedelta(seconds=1))
            supervise_once(adapter,now=now+timedelta(seconds=1))
            process.heartbeat_at=now+timedelta(seconds=62); process.save()
            supervise_once(adapter,now=now+timedelta(seconds=62))
        self.assertEqual(WorkerService.objects.get(pk='avito').status,'running')
