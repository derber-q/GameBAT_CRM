"""Реальные вкладки/IndexedDB, изолированные данные и подменённый проигрыватель."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
from pathlib import Path
import time

from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from django.utils import timezone
from playwright.sync_api import expect, sync_playwright

from accounts.models import User
from warehouse.models import Warehouse
from yandex_market.models import Integration, OrderMetadata
from .models import MarketOrderAttention, Sale
from .notifications import acknowledge_order
from .payment_browser_checks import database_call


FAKE_AUDIO = """
window.__NativeAudio = window.Audio;
window.__audioEvents = [];
window.__audioDenied = false;
window.Audio = class {
  constructor(src) {this.src=src; this.dataset={}; this.volume=0; this.currentTime=0;}
  play() {
    if (window.__audioDenied) return Promise.reject(new DOMException('Autoplay blocked', 'NotAllowedError'));
    const event = {id:this.dataset.marketOrderId, channel:this.dataset.notificationChannel, volume:this.volume, start:Date.now(), end:null};
    this.record=event; window.__audioEvents.push(event);
    this.timer=setTimeout(()=>{event.end=Date.now(); this.onended?.();},120);
    return Promise.resolve();
  }
  pause() {clearTimeout(this.timer); if(this.record && this.record.end===null) this.record.end=Date.now();}
};
"""


class MarketNotificationBrowserChecks(StaticLiveServerTestCase):
    def test_native_mp3_activation_promise(self):
        actor = User.objects.create_superuser('native-alert-browser')
        self.client.force_login(actor)
        output = Path(settings.BASE_DIR) / 'outputs/market_staff_alerts_20261022/browser'
        output.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as pw:
            # Проверяем реальный медиадвижок без звука на рабочем устройстве.
            browser = pw.chromium.launch(args=['--mute-audio'])
            context = browser.new_context()
            context.add_cookies([{'name': settings.SESSION_COOKIE_NAME,
                'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value, 'url': self.live_server_url}])
            context.route('**/crm/api/exchange-rates/', lambda route: route.fulfill(json={'rates': {}, 'available': False}))
            context.add_init_script('''
              const NativeAudio = window.Audio;
              window.Audio = function(src) {window.__marketClip = new NativeAudio(src); return window.__marketClip;};
            ''')
            page = context.new_page()
            page.goto(self.live_server_url + reverse('sales:market_pending'))
            counter = page.locator('[data-market-counter]')
            expect(counter).to_have_class('market-alert-counter')
            expect(counter).to_have_attribute('aria-label', 'Яндекс Маркет: непринятых заказов — 0')
            expect(counter.locator('img')).to_be_visible()
            self.assertTrue(counter.locator('img').evaluate('(node) => node.complete && node.naturalWidth > 0'))
            box = counter.bounding_box()
            self.assertEqual((box['width'], box['height']), (36, 36))
            counter.hover()
            expect(counter).to_have_css('background-color', 'rgba(255, 255, 255, 0.16)')
            page.screenshot(path=str(output / 'counter-empty.png'), clip={
                'x': max(0, box['x'] - 8), 'y': max(0, box['y'] - 8), 'width': 56, 'height': 56})
            page.locator('[data-notification-sound-enable]').click()
            expect(page.locator('[data-market-audio-status]')).to_contain_text('Звук включён')
            page.wait_for_function('window.__marketClip.ended')
            actual = page.evaluate('({volume:window.__marketClip.volume, duration:window.__marketClip.duration, ended:window.__marketClip.ended})')
            self.assertEqual(actual['volume'], 1)
            self.assertTrue(actual['ended'])
            self.assertGreater(actual['duration'], 0)
            (output / 'native-audio.json').write_text(json.dumps(actual, ensure_ascii=False, indent=2), 'utf-8')
            browser.close()

    def test_channels_global_alerts_two_workplaces_tabs_ack_and_autoplay(self):
        actor = User.objects.create_superuser('market-alert-browser')
        self.client.force_login(actor)
        warehouse = Warehouse.objects.create(name='Уведомления браузер')
        integration = Integration.objects.create(business_id=1, campaign_id=2, fulfillment_warehouse=warehouse, operator=actor)
        start = timezone.now().replace(microsecond=0)
        clock = [start]
        output = Path(settings.BASE_DIR) / 'outputs/market_staff_alerts_20261022/browser'
        output.mkdir(parents=True, exist_ok=True)
        for completed in (False, True):
            for kind in ('wholesale', 'avito', 'consignment') + (('retail',) if completed else ()):
                Sale.objects.create(warehouse=warehouse, sale_type=kind, price_type='retail',
                    payment_method='bank_transfer_postpay',
                    order_status='delivered' if completed else 'created', payment_status='paid' if completed else 'unpaid')
            if completed:
                Sale.objects.create(warehouse=warehouse, sale_type='yandex_market', price_type='yandex_market',
                    payment_method='bank_transfer_postpay',
                    order_status='delivered', payment_status='paid')

        def new_order(number, minutes):
            sale = Sale.objects.create(warehouse=warehouse, created_by=actor, sale_type='yandex_market',
                price_type='yandex_market', payment_method='bank_transfer_postpay')
            order = OrderMetadata.objects.create(integration=integration, sale=sale, order_id=number,
                status='PROCESSING', substatus='STARTED')
            return MarketOrderAttention.objects.create(order=order, notification_started_at=start + timedelta(minutes=minutes)).pk
        first = new_order(101, 0)
        with ThreadPoolExecutor(max_workers=1) as database, sync_playwright() as pw:
            run = lambda callback: database.submit(database_call, callback).result()
            browser = pw.chromium.launch()
            errors = []
            def context():
                ctx = browser.new_context(viewport={'width': 1440, 'height': 1000})
                ctx.add_init_script(FAKE_AUDIO)
                ctx.add_cookies([{'name': settings.SESSION_COOKIE_NAME,
                    'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value, 'url': self.live_server_url}])
                ctx.route('**/crm/api/exchange-rates/', lambda route: route.fulfill(json={'rates': {}, 'available': False}))
                outage = [False]
                def notifications(route):
                    if outage[0] and route.request.method == 'GET':
                        route.fulfill(status=503, json={'error': 'Тестовая потеря связи'})
                        return
                    response = route.fetch()
                    data = response.json()
                    if response.ok:
                        data['server_now'] = clock[0].isoformat()
                    route.fulfill(response=response, json=data)
                ctx.route('**/sales/market-notifications/**', notifications)
                return ctx, outage
            def page(ctx, name):
                result = ctx.new_page()
                result.on('pageerror', lambda error: errors.append(str(error)))
                result.goto(self.live_server_url + reverse(name))
                return result
            def refresh(pages):
                for current in pages:
                    current.evaluate('window.GameBAT.refreshMarketNotifications()')
            def signals(pages):
                return sorted([event for current in pages for event in current.evaluate('window.__audioEvents') if event.get('channel') == 'market' and event.get('id') != 'test'],
                    key=lambda event: event['start'])
            def wait_signals(pages, count, prefix=()):
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline:
                    result = sorted([*prefix, *signals(pages)], key=lambda event: event['start'])
                    if len(result) >= count and all(event['end'] is not None for event in result):
                        self.assertEqual(len(result), count)
                        return result
                    pages[0].wait_for_timeout(50)
                self.fail(f'Получено {len(signals(pages))} сигналов вместо {count}')
            ctx_a, _ = context()
            ctx_b, _ = context()
            a1 = page(ctx_a, 'sales:incomplete')
            a2 = page(ctx_a, 'sales:market_pending')
            b1 = page(ctx_b, 'supplies:list')
            groups = a1.locator('[data-sale-group]:visible')
            self.assertEqual(groups.evaluate_all('nodes => nodes.map(node=>node.dataset.saleGroup)'), ['wholesale', 'avito', 'yandex_market'])
            self.assertEqual(a1.locator('[data-sales-channel]').all_text_contents(), ['Все', 'Яндекс Маркет', 'Опт', 'Авито', 'Розница'])
            for kind, count in [('yandex_market', 1), ('wholesale', 1), ('avito', 1), ('retail', 0), ('all', 3)]:
                a1.locator(f'[data-sales-channel="{kind}"]').click()
                expect(groups).to_have_count(count)
            a1.reload()
            expect(a1.locator('[data-sales-channel="all"]')).to_have_attribute('aria-pressed', 'true')
            expect(groups).to_have_count(3)
            a1.locator('[data-sales-channel="wholesale"]').click()
            a1.evaluate("window.dispatchEvent(new PageTransitionEvent('pageshow', {persisted:true}))")
            expect(a1.locator('[data-sales-channel="all"]')).to_have_attribute('aria-pressed', 'true')
            expect(groups).to_have_count(3)
            expect(a1.locator('[data-sale-group="consignment"]')).to_have_count(0)
            a1.goto(self.live_server_url + reverse('sales:completed'))
            self.assertEqual(a1.locator('[data-sale-group]:visible').evaluate_all('nodes=>nodes.map(n=>n.dataset.saleGroup)'),
                ['yandex_market', 'wholesale', 'avito', 'retail', 'consignment'])
            a1.locator('[data-sales-channel="retail"]').click()
            expect(a1.locator('[data-sale-group]:visible')).to_have_count(1)
            a1.reload()
            expect(a1.locator('[data-sales-channel="all"]')).to_have_attribute('aria-pressed', 'true')
            a1.goto(self.live_server_url + reverse('sales:create'))
            expect(a1.locator('#id_sale_type option[value="yandex_market"]')).to_have_count(0)
            expect(a1.locator('#id_price_type option[value="yandex_market"]')).to_have_count(0)
            a1.goto(self.live_server_url + reverse('sales:incomplete'))
            expect(a1.locator(f'tr[data-market-attention="{first}"]')).to_have_class('market-order-unacknowledged')
            a1.set_viewport_size({'width': 390, 'height': 900})
            accept_first = a1.locator(f'tr[data-market-attention="{first}"] [data-market-ack] button')
            accept_first.scroll_into_view_if_needed()
            box = accept_first.bounding_box()
            self.assertGreaterEqual(box['x'], 0)
            self.assertLessEqual(box['x'] + box['width'], 390)
            a1.screenshot(path=str(output / 'table-ack-390.png'), full_page=True)
            a1.set_viewport_size({'width': 1440, 'height': 1000})
            for current in (a1, a2, b1):
                expect(current.locator('[data-market-pending-count]')).to_have_text('1')
                expect(current.locator('[data-market-counter]')).to_have_class('market-alert-counter has-pending')
                expect(current.locator('[data-market-counter]')).to_have_attribute(
                    'aria-label', 'Яндекс Маркет: непринятых заказов — 1')
            a1.locator('[data-notification-sound-enable]').click()
            b1.locator('[data-notification-sound-enable]').click()
            wait_signals([a1, a2], 1)
            wait_signals([b1], 1)
            second = run(lambda: new_order(102, 4))
            clock[0] = start + timedelta(minutes=4)
            refresh([a1, a2, b1])
            wait_signals([a1, a2], 2); wait_signals([b1], 2)
            third = run(lambda: new_order(103, 7))
            clock[0] = start + timedelta(minutes=7)
            refresh([a1, a2, b1])
            wait_signals([a1, a2], 3); wait_signals([b1], 3)
            expect(a2.locator('[data-market-pending-count]')).to_have_text('3')
            a2.set_viewport_size({'width': 390, 'height': 900})
            a2.screenshot(path=str(output / 'pending-390.png'), full_page=True)
            clock[0] = start + timedelta(minutes=10)
            refresh([a1, a2, b1])
            events_a = wait_signals([a1, a2], 4); wait_signals([b1], 4)
            self.assertEqual(events_a[-1]['id'], str(first))
            a2.locator(f'[data-market-attention="{second}"] [data-market-ack] button').click()
            expect(a2.locator('[data-market-pending-count]')).to_have_text('2')
            refresh([a1, b1])
            expect(a1.locator('[data-market-pending-count]')).to_have_text('2')
            expect(b1.locator('[data-market-pending-count]')).to_have_text('2')
            clock[0] = start + timedelta(minutes=14)
            refresh([a1, a2, b1]); a1.wait_for_timeout(300)
            self.assertEqual(len(signals([a1, a2])), 4)
            clock[0] = start + timedelta(minutes=17)
            refresh([a1, a2, b1])
            events_a = wait_signals([a1, a2], 5); wait_signals([b1], 5)
            self.assertEqual(events_a[-1]['id'], str(third))
            past = signals([a1]); a1.close()
            clock[0] = start + timedelta(minutes=20)
            refresh([a2, b1])
            events_a = wait_signals([a2], 6, past); wait_signals([b1], 6)
            past = events_a
            a2.reload(); refresh([a2]); a2.wait_for_timeout(1200)
            self.assertEqual(signals([a2]), [])
            for key in (first, third):
                a2.locator(f'[data-market-attention="{key}"] [data-market-ack] button').click()
                expect(a2.locator(f'[data-market-attention="{key}"]')).to_have_count(0)
            expect(b1.locator('[data-market-pending-count]')).to_have_text('0', timeout=20000)
            expect(b1.locator('[data-market-counter]')).to_have_class('market-alert-counter')
            expect(b1.locator('[data-market-counter]')).to_have_attribute(
                'aria-label', 'Яндекс Маркет: непринятых заказов — 0')
            for records in (events_a, signals([b1])):
                records.sort(key=lambda event: event['start'])
                self.assertTrue(all(event['volume'] == 1 for event in records))
                self.assertTrue(all(left['end'] <= right['start'] for left, right in zip(records, records[1:])))
            ctx_a.close(); ctx_b.close()
            fourth = run(lambda: new_order(104, 21))
            clock[0] = start + timedelta(minutes=21)
            ctx_c, outage = context()
            c1 = page(ctx_c, 'sales:market_pending')
            c1.evaluate('window.__audioDenied=true')
            c1.locator('[data-notification-sound-enable]').click()
            expect(c1.locator('[data-market-audio-status]')).to_contain_text('Браузер заблокировал звук')
            self.assertEqual(signals([c1]), [])
            expect(c1.locator('[data-market-pending-count]')).to_have_text('1')
            c1.screenshot(path=str(output / 'autoplay-blocked.png'), full_page=True)
            c1.evaluate('window.__audioDenied=false')
            c1.locator('[data-notification-sound-enable]').click()
            wait_signals([c1], 1)
            outage[0] = True
            clock[0] = start + timedelta(minutes=31)
            refresh([c1])
            expect(c1.locator('[data-market-feed-status]')).to_contain_text('звук приостановлен')
            run(lambda: acknowledge_order(actor=actor, attention_id=fourth))
            fifth = run(lambda: new_order(105, 31))
            outage[0] = False
            refresh([c1]); recovered = wait_signals([c1], 2)
            self.assertEqual([event['id'] for event in recovered], [str(fourth), str(fifth)])
            duration = c1.evaluate("""async () => {
              const clip = new window.__NativeAudio(document.getElementById('market-order-alerts').dataset.soundUrl);
              return await new Promise((resolve,reject)=>{clip.onloadedmetadata=()=>resolve(clip.duration);clip.onerror=reject;clip.load();});
            }""")
            self.assertGreater(duration, 0)
            c1.screenshot(path=str(output / 'recovered.png'), full_page=True)
            c1.goto(self.live_server_url + reverse('admin:index'))
            expect(c1.locator('#market-order-alerts')).to_have_count(1)
            expect(c1.locator('[data-market-pending-count]')).to_have_text('1')
            expect(c1.locator('[data-market-counter]')).to_have_css('color', 'rgb(103, 75, 0)')
            counter = c1.locator('[data-market-counter]')
            expect(counter).to_have_css('background-color', 'rgb(255, 241, 201)')
            counter.hover()
            expect(counter).to_have_css('background-color', 'rgb(255, 231, 166)')
            box = counter.bounding_box()
            self.assertEqual(box['width'], 40)
            c1.screenshot(path=str(output / 'counter-pending-admin.png'), clip={
                'x': max(0, box['x'] - 8), 'y': max(0, box['y'] - 8), 'width': 56, 'height': 56})
            c1.screenshot(path=str(output / 'admin-global.png'), full_page=True)
            self.assertEqual(errors, [])
            result = {'profiles': 3, 'tabs_in_first_profile': 2, 'signals_in_a': 6, 'signals_in_b': 6,
                'independent_intervals': True, 'acknowledgement_shared': True, 'reload_deduplicated': True,
                'leader_close_recovered': True, 'autoplay_error_visible': True, 'offline_recovered': True,
                'volume': 1, 'mp3_duration': duration, 'page_errors': errors}
            (output / 'results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), 'utf-8')
            ctx_c.close(); browser.close()
