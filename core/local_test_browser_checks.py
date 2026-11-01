"""Браузерная приёмка отдельно запущенного local_test; live URL не открываются."""
import json
from pathlib import Path
import unittest
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parent.parent


class LocalTestBrowserChecks(unittest.TestCase):
    def test_orange_navigation_login_cookies_and_blocked_actions(self):
        credentials=json.loads((ROOT/'outputs/local_test/acceptance/secrets/test-admin.json').read_text('utf-8'))
        output=ROOT/'outputs/hosting_stage_a/browser'; output.mkdir(parents=True,exist_ok=True)
        origin='http://127.0.0.1:8001'
        with sync_playwright() as pw:
            browser=pw.chromium.launch()
            context=browser.new_context(viewport={'width':1440,'height':1000})
            page=context.new_page(); errors=[]; outside=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.on('request',lambda request:outside.append(request.url) if not request.url.startswith(origin+'/') else None)
            response=page.goto(origin+'/crm/accounts/login/')
            self.assertEqual(response.headers.get('x-gamebat-environment'),'local_test')
            expect(page.locator('[data-test-environment]')).to_be_visible()
            page.get_by_label('Логин',exact=True).fill(credentials['username'])
            page.get_by_label('Пароль',exact=True).fill(credentials['password'])
            page.get_by_role('button',name='Войти',exact=True).click()
            page.goto(origin+'/crm/integrations/workers/')
            expect(page.locator('[data-worker-row]')).to_have_count(4)
            expect(page.locator('.crm-topbar')).to_have_css('background-color','rgb(184, 92, 18)')
            expect(page.locator('[data-worker-summary]')).to_contain_text('Только сайт')
            expect(page.locator('[data-notification-sound-enable]')).to_be_visible()
            trigger=page.locator('.main-nav .nav-dropdown-trigger').filter(has_text='Интеграции')
            trigger.hover()
            expect(page.locator('.main-nav .nav-dropdown-menu').filter(has=page.get_by_role('link',name='API ключи',exact=True))).to_be_visible()
            page.screenshot(path=str(output/'desktop.png'))
            cookies=context.cookies()
            self.assertTrue(any(row['name'].startswith('resource_test_session_') for row in cookies))
            self.assertFalse(any(row['name']=='sessionid' for row in cookies))
            page.goto(origin+'/crm/integrations/workers/?GAMEBAT_ENV=local_live')
            expect(page.locator('[data-test-environment]')).to_be_visible()
            page.set_viewport_size({'width':390,'height':844})
            expect(page.locator('[data-test-environment]')).to_be_visible()
            expect(page.locator('.crm-topbar')).to_have_css('background-color','rgb(184, 92, 18)')
            self.assertLessEqual(page.locator('.crm-topbar').bounding_box()['width'],390)
            snapshot=context.request.get(origin+'/crm/integrations/workers/status/').json()
            snapshot['alarm']=True
            snapshot['incidents']=[{'id':'synthetic-orange-alert','started_at':snapshot['server_time']}]
            page.route('**/crm/integrations/workers/status/',lambda route:route.fulfill(json=snapshot))
            page.get_by_role('button',name='Обновить',exact=True).click()
            expect(page.locator('[data-worker-alert]')).to_be_visible()
            page.screenshot(path=str(output/'mobile-alert.png'))
            page.get_by_role('button',name='Открыть навигацию',exact=True).click()
            expect(page.get_by_role('dialog',name='Навигация',exact=True)).to_be_visible()
            expect(page.locator('.navigation-drawer')).to_have_css('background-color','rgb(184, 92, 18)')
            expect(page.locator('.test-menu-environment')).to_be_visible()
            page.screenshot(path=str(output/'mobile.png'))
            page.keyboard.press('Escape')
            page.goto(origin+'/crm/integrations/')
            expect(page.locator('[data-test-environment]')).to_be_visible()
            page.screenshot(path=str(output/'keys.png'))
            # Тестовая ручная кнопка не доходит до настоящего транспорта.
            page.get_by_label('API key',exact=True).fill('synthetic-not-a-real-key')
            page.get_by_role('button',name='Сохранить ключ',exact=True).click()
            expect(page.locator('.messages')).to_contain_text('реальное внешнее действие заблокировано')
            expect(page.locator('[data-test-environment]')).to_be_visible()
            page.goto(origin+'/crm/admin/')
            expect(page.locator('[data-test-environment]')).to_be_visible()
            self.assertEqual(errors,[])
            self.assertEqual(outside,[])
            browser.close()
