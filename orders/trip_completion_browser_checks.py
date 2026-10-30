"""Серый завершённый рейс и возврат в работу после отмены прихода, отдельная БД."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import re

from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from playwright.sync_api import expect, sync_playwright

from sales.payment_browser_checks import database_call
from supplies.services import cancel_supply
from .test_fulfillment import FulfillmentFixture
from .test_trip_completion import complete_trip


class TripCompletionBrowserChecks(FulfillmentFixture, StaticLiveServerTestCase):
    def test_completed_trip_is_grey_until_a_document_is_cancelled(self):
        _, supply = complete_trip(self)
        output = Path(settings.BASE_DIR) / 'outputs/trip-completion-20261027'
        output.mkdir(parents=True, exist_ok=True)
        with ThreadPoolExecutor(max_workers=1) as database, sync_playwright() as pw:
            browser = pw.chromium.launch()
            context = browser.new_context(viewport={'width': 1440, 'height': 1000})
            context.add_cookies([{'name': settings.SESSION_COOKIE_NAME,
                'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value, 'url': self.live_server_url}])
            context.route('**/crm/api/exchange-rates/', lambda route: route.fulfill(json={'available': False, 'rates': {}}))
            page = context.new_page()
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(self.live_server_url + reverse('orders:list'))
            row = page.locator(f'[data-trip-id="{self.trip.pk}"]')
            expect(row.locator('[data-trip-status]')).to_have_text('Завершён')
            expect(row).to_have_class(re.compile(r'\btrip-completed\b'))
            for cell in row.locator('td').all():
                expect(cell).to_have_css('background-color', 'rgb(229, 231, 235)')
            row.hover()
            expect(row.locator('td').first).to_have_css('background-color', 'rgb(229, 231, 235)')
            page.screenshot(path=str(output / 'completed.png'), full_page=True)
            database.submit(database_call, lambda: cancel_supply(actor=self.user, supply_id=supply.pk, comment='Возврат')).result()
            page.reload()
            expect(row.locator('[data-trip-status]')).to_have_text('В работе')
            expect(row).not_to_have_class(re.compile(r'\btrip-completed\b'))
            page.screenshot(path=str(output / 'reopened.png'), full_page=True)
            self.assertEqual(errors, [])
            browser.close()
