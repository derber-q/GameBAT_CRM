"""Живая страница агента и ручная проверка результата, только отдельная БД."""
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from playwright.sync_api import sync_playwright,expect
from concurrent.futures import ThreadPoolExecutor
from accounts.models import User
from sales.models import PrintAgent,MarketPrintJob,Sale
from warehouse.models import Warehouse
from yandex_market.models import Integration,OrderMetadata


@override_settings(LABEL_PRINT_BACKEND='agent')
class PrintAgentBrowserChecks(StaticLiveServerTestCase):
    def test_connection_changes_and_employee_resolves_uncertain_without_printing(self):
        actor=User.objects.create_superuser('print-agent-browser')
        self.client.force_login(actor)
        agent=PrintAgent.objects.create(name='Browser agent',printer_name='Fake printer',token_hash='a'*64)
        warehouse=Warehouse.objects.create(name='Browser warehouse')
        integration=Integration.objects.create(business_id=1,campaign_id=2,enabled=True,fulfillment_warehouse=warehouse,operator=actor)
        sale=Sale.objects.create(warehouse=warehouse,created_by=actor)
        order=OrderMetadata.objects.create(integration=integration,sale=sale,order_id=123)
        job=MarketPrintJob.objects.create(order=order,actor=actor,agent=agent,printer_name='Fake printer',print_backend='agent',state='uncertain')
        with sync_playwright() as p:
            browser=p.chromium.launch()
            context=browser.new_context()
            context.add_cookies([{'name':settings.SESSION_COOKIE_NAME,'value':self.client.cookies[settings.SESSION_COOKIE_NAME].value,'url':self.live_server_url}])
            context.route('**/crm/api/exchange-rates/',lambda route:route.fulfill(json={'available':False,'rates':{}}))
            page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(self.live_server_url+reverse('integrations:workers'))
            node=page.locator('[data-print-agent]')
            expect(node.locator('[data-agent-field="connected"]')).to_have_text('Нет связи')
            def connect_agent():
                from django.db import connections
                try:
                    current=PrintAgent.objects.get(pk=agent.pk)
                    current.last_seen_at=timezone.now();current.printer_available=True;current.version='1.0.0';current.save()
                finally:
                    connections.close_all()
            with ThreadPoolExecutor(max_workers=1) as executor:
                executor.submit(connect_agent).result(timeout=10)
            page.get_by_role('button',name='Обновить',exact=True).click()
            expect(node.locator('[data-agent-field="connected"]')).to_have_text('Подключён')
            page.get_by_label('Результат проверки заказа 123',exact=True).select_option('not_printed')
            page.get_by_label('Я проверил этикетку и очередь принтера').check()
            page.get_by_role('button',name='Сохранить решение',exact=True).click()
            expect(page.get_by_text('Решение о результате печати сохранено в журнале.')).to_be_visible()
            self.assertEqual(errors,[])
            browser.close()
        job.refresh_from_db();self.assertEqual(job.state,'pending');self.assertIsNone(job.printed_at)
