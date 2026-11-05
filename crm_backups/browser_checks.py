"""Новые административные страницы, отдельная SQLite и запрещённая внешняя сеть."""
from pathlib import Path
from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from playwright.sync_api import sync_playwright,expect
from accounts.models import User


class BackupPagesBrowserChecks(StaticLiveServerTestCase):
    def test_admin_pages_and_mobile_width(self):
        self.client.force_login(User.objects.create_superuser('backup-browser-owner'))
        output=Path(settings.BASE_DIR)/'outputs/local_agent_20261103/browser';output.mkdir(parents=True,exist_ok=True)
        with sync_playwright() as pw:
            browser=pw.chromium.launch()
            context=browser.new_context(viewport={'width':1440,'height':1000})
            context.route('**/*',lambda route:route.continue_() if route.request.url.startswith(self.live_server_url+'/') else route.abort())
            context.route('**/crm/api/exchange-rates/',lambda route:route.fulfill(json={'rates':{},'available':False}))
            context.add_cookies([{'name':settings.SESSION_COOKIE_NAME,'value':self.client.cookies[settings.SESSION_COOKIE_NAME].value,'url':self.live_server_url}])
            page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            for name,title in [('dashboard','Резервное копирование'),('devices','Локальные приложения'),('applications','Приложения и расширения')]:
                page.goto(self.live_server_url+reverse('crm_backups:'+name))
                expect(page.get_by_role('heading',name=title,exact=True)).to_be_visible()
                for width in (1440,390):
                    page.set_viewport_size({'width':width,'height':1000})
                    page.screenshot(path=str(output/f'{name}-{width}.png'),full_page=True)
                    if page.evaluate('document.documentElement.scrollWidth')>width:
                        import json
                        (output/'overflow.json').write_text(json.dumps(page.evaluate('''() => [...document.querySelectorAll('body *')].filter(n=>n.getBoundingClientRect().right>innerWidth+1).map(n=>({tag:n.tagName,cls:n.className,width:n.getBoundingClientRect().width,min:getComputedStyle(n).minWidth})).slice(0,25)''')),encoding='utf-8')
                    self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'),width)
            self.assertEqual(errors,[])
            browser.close()
