"""Кнопка локальной CRM и меню обновлений на отдельной тестовой БД."""
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse
from playwright.sync_api import expect, sync_playwright

from accounts.models import User


class UpdatesBrowserChecks(StaticLiveServerTestCase):
    def test_menu_hover_local_button_message_and_responsive_page(self):
        admin=User.objects.create_superuser('updates-browser')
        self.client.force_login(admin)
        output=Path(settings.BASE_DIR)/'outputs/updates_20261101/browser'
        output.mkdir(parents=True,exist_ok=True)
        with override_settings(GAMEBAT_ENV='local_live'), \
                patch('core.update_views.submit',side_effect=AssertionError('No manager in local mode')), \
                patch('core.update_views.update_state',side_effect=AssertionError('No production state in local mode')), \
                sync_playwright() as pw:
            browser=pw.chromium.launch()
            context=browser.new_context(viewport={'width':1440,'height':1000})
            context.add_cookies([{'name':settings.SESSION_COOKIE_NAME,
                'value':self.client.cookies[settings.SESSION_COOKIE_NAME].value,'url':self.live_server_url}])
            context.route('**/crm/api/exchange-rates/',lambda route:route.fulfill(json={'rates':{},'available':False}))
            page=context.new_page()
            errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(self.live_server_url+reverse('integrations:workers'))
            page.locator('.nav-dropdown-trigger').filter(has_text='Интеграции').hover()
            link=page.locator('.nav-dropdown-menu a').filter(has_text='Обновления')
            expect(link).to_be_visible()
            page.screenshot(path=str(output/'updates-menu.png'),full_page=True)
            link.click()
            expect(page.get_by_role('heading',name='Обновления',exact=True)).to_be_visible()
            page.get_by_role('button',name='Обновить до последней версии',exact=True).click()
            expect(page.locator('.messages')).to_contain_text('Обновления доступны только для production-версии.')
            for width in (1440,390,320):
                page.set_viewport_size({'width':width,'height':1000})
                page.screenshot(path=str(output/f'updates-{width}.png'),full_page=True)
                overflow=page.evaluate("Array.from(document.querySelectorAll('body *')).filter(e=>e.getBoundingClientRect().right>innerWidth+1).slice(0,8).map(e=>({tag:e.tagName,cls:e.className,text:e.textContent.slice(0,80)}))")
                self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'),width,str(overflow))
            self.assertEqual(errors,[])
            context.close();browser.close()
