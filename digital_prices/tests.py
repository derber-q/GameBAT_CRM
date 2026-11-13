"""Синтетические проверки. Рабочие ключи, сеть, склад и финансовые операции не нужны."""
from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from unittest.mock import Mock, patch
import json
import uuid
from PIL import Image
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, SimpleTestCase
from django.urls import reverse
from django.utils import timezone
from .api import Offer, APIError, CatalogClient, parse_page, parse_codes, amount
from .models import CatalogState, Integration, Product, SyncJob, PricePage, PageDelivery, ManualPriceEntry
from .public import snapshot, serialize, PublicCatalog, PublicRow
from .rendering import render
from .services import selling_price, edit_product, apply_catalog, enqueue_sync, process_one
from .bundles import generate_bundle


def api_row(**values):
    return {'product_id': 'pv2_synthetic', 'name': 'Synthetic offer', 'type': 'ps',
            'platform': 'playstation', 'region': 'turkey', 'price': '9371.29', 'currency': 'rub',
            'available': True, **values}


class ArithmeticTests(SimpleTestCase):
    def test_png_document_keeps_png_mime_and_private_recipient(self):
        from telegram_bots.client import TelegramClient
        content = b'\x89PNG\r\n\x1a\n' + b'fixture'
        with patch('telegram_bots.client.require_live_operation'):
            client = TelegramClient('synthetic-token', session=Mock())
        with patch.object(client, 'call', return_value={'message_id': 77}) as call:
            self.assertEqual(client.image_document(77, 'GameBAT.png', content), {'message_id': 77})
            self.assertEqual(call.call_args.args[0], 'sendDocument')
            self.assertEqual(call.call_args.kwargs['files']['document'], ('GameBAT.png', content, 'image/png'))
            with self.assertRaises(ValueError):
                client.image_document(-77, 'GameBAT.png', content)
            self.assertEqual(call.call_count, 1)

    def test_codes_catalog_preserves_nominal_region_and_zero_stock(self):
        rows = parse_codes({'currency': 'rub', 'items': [
            {'item_id': 71, 'name': 'Коды Турция 🇹🇷 | 500 TRY', 'category': 'PlayStation - Коды пополнения', 'price': '999.13', 'in_stock': 0},
            {'item_id': 72, 'name': 'Коды Турция 🇹🇷 | 1000 TRY', 'category': 'PlayStation - Коды пополнения', 'price': '1999.26', 'in_stock': 2}]})
        self.assertEqual([row.identity for row in rows], ['v1_code_71', 'v1_code_72'])
        self.assertEqual([row.available for row in rows], [False, True])
        self.assertEqual(rows[0].region, 'tr')
        self.assertEqual(rows[0].attributes['denomination'], '500 TRY')
        with self.assertRaises(APIError):
            parse_codes({'currency': 'rub', 'items': [{'item_id': 1, 'name': 'X', 'category': 'Steam', 'price': '10', 'in_stock': True}]})

    def test_xbox_account_mode_is_not_lost_in_public_characteristics(self):
        from .classification import characteristics
        same_name = 'Game Pass Ultimate · 1 мес.'
        old = characteristics('xbox', same_name, {'account_modes': ['existing']})
        new = characteristics('xbox', same_name, {'account_modes': ['new']})
        self.assertEqual(old[1], 'Старый аккаунт')
        self.assertEqual(new[1], 'Новый аккаунт')

    def test_required_rounding_examples_and_null_markup(self):
        for rule, raw, expected in [('ps_plus_subscription', '1134', '1150'),
            ('ps_plus_subscription', '1200', '1200'), ('xbox_subscription', '2201', '2250'),
            ('xbox_subscription', '3200.01', '3250'), ('other', '327', '330'),
            ('other', '1063', '1070'), ('other', '1750', '1750'), ('other', '1181', '1190')]:
            with self.subTest(rule=rule, raw=raw):
                self.assertEqual(selling_price(Decimal(raw), 'RUB', Decimal(0), rule), Decimal(expected))
        self.assertIsNone(selling_price(Decimal(100), 'RUB', None, 'other'))
        self.assertIsNone(selling_price(None, 'RUB', Decimal(0), 'other'))
        self.assertIsNone(selling_price(Decimal(100), 'USD', Decimal(0), 'other'))

    def test_invalid_amounts_and_schema(self):
        for value in ('NaN', '-1', 'Infinity', '0.001', True, 1.2):
            with self.subTest(value=value), self.assertRaises(APIError):
                amount(value)
        for payload in ({}, {'items': [], 'has_more': True, 'page': 1},
                        {'items': [api_row(available='yes')], 'has_more': False, 'page': 1}):
            with self.assertRaises(APIError):
                parse_page(payload, 1)

    def test_pagination_and_null_price_without_real_transport(self):
        session, sleeper = Mock(), Mock()
        responses = []
        for page, rows, more in [(1, [api_row()], True),
                                 (2, [api_row(product_id='pv2_other', type='steam_topup', price=None)], False)]:
            response = Mock(status_code=200, content=b'{}', headers={})
            response.json.return_value = {'items': rows, 'page': page, 'has_more': more}
            responses.append(response)
        session.get.side_effect = responses
        with patch('digital_prices.api.require_live_operation'):
            client = CatalogClient('synthetic-key', session=session, sleeper=sleeper)
            rows = client.fetch()
        self.assertEqual(len(rows), 2)
        self.assertIsNone(rows[1].cost)
        sleeper.assert_called_once_with(3.2)
        self.assertEqual(session.get.call_count, 2)
        self.assertFalse(session.get.call_args.kwargs['allow_redirects'])

    def test_duplicate_ids_and_http_errors_are_sanitized(self):
        for code, expected in [(401, 'authentication'), (403, 'authentication'), (429, 'rate_limited'), (503, 'upstream')]:
            response = Mock(status_code=code, content=b'not-public', headers={'Retry-After': '75'})
            session = Mock()
            session.get.return_value = response
            with patch('digital_prices.api.require_live_operation'), self.assertRaises(APIError) as caught:
                CatalogClient('synthetic-secret', session=session).fetch()
            self.assertEqual(caught.exception.category, expected)
            self.assertNotIn('synthetic-secret', str(caught.exception))
        response = Mock(status_code=200, content=b'{}', headers={})
        response.json.return_value = {'items': [api_row(), api_row()], 'page': 1, 'has_more': False}
        session = Mock()
        session.get.return_value = response
        with patch('digital_prices.api.require_live_operation'), self.assertRaises(APIError):
            CatalogClient('synthetic-secret', session=session).fetch()

    def test_local_test_blocks_real_client_before_transport(self):
        from django.test import override_settings
        session = Mock()
        with override_settings(GAMEBAT_ENV='local_test'), self.assertRaises(ValidationError):
            CatalogClient('not-a-real-key', session=session)
        session.get.assert_not_called()


class CatalogTests(TestCase):
    def setUp(self):
        # Эта группа проверяет собственный синтетический каталог, без начальных
        # пустых ручных строк из миграции. Рабочие данные здесь не используются.
        ManualPriceEntry.objects.all().delete()
        self.owner = get_user_model().objects.create_superuser(username='digital-prices-owner')
        self.viewer = get_user_model().objects.create_user(username='digital-prices-viewer')
        self.viewer.user_permissions.add(*Permission.objects.filter(content_type__app_label='digital_prices',
            codename__in=['view_catalog', 'download_prices']))
        CatalogState.objects.get_or_create(pk=1)
        config, _ = Integration.objects.get_or_create(pk=1)
        config.enabled, config.encrypted_key = True, 'synthetic-encrypted-not-a-real-key'
        config.save()
        self.import_rows([api_row()])

    def import_rows(self, rows, **extra):
        job = SyncJob.objects.create(run_after=timezone.now(), state='running', owner=uuid.uuid4(),
            lease_until=timezone.now()+timedelta(minutes=2))
        offers, _ = parse_page({'items': rows, 'page': 1, 'has_more': False}, 1)
        apply_catalog(offers, job_id=job.pk, owner=job.owner, **extra)

    def test_sheet_updates_only_manual_cost_and_preserves_markup_mode_and_zero_placeholder(self):
        from .sheet_source import SheetCost
        entry=ManualPriceEntry.objects.create(kind='game_tariff',region='india',label='1000',
            manual_cost=Decimal('100'),markup=Decimal('50'),pricing_mode='percent',cost_percent=Decimal('6'))
        config=Integration.objects.get(pk=1);config.manual_sheet_enabled=True;config.save()
        key=('game_tariff','in','1000')
        source={key:SheetCost(*key,'rub',Decimal('1460'),'Прайс!H25')}
        self.import_rows([api_row(price='500')],sheet_costs=source,manual_revisions={entry.pk:entry.revision})
        entry.refresh_from_db()
        self.assertEqual(entry.manual_cost,Decimal('1460'))
        self.assertEqual(entry.markup,Decimal('50'))
        self.assertEqual(entry.pricing_mode,'percent')
        self.assertEqual(entry.cost_percent,Decimal('6'))
        source[key]=SheetCost(*key,'rub',None,'Прайс!H25')
        self.import_rows([api_row(price='510')],sheet_costs=source)
        entry.refresh_from_db()
        self.assertEqual(entry.manual_cost,Decimal('1460'))
        self.assertEqual(entry.sheet_issue,'missing_price')
        self.assertEqual(Product.objects.get().purchase_cost,Decimal('510'))

    def test_google_failure_or_local_edit_does_not_erase_previous_cost_or_stop_api_update(self):
        from .sheet_source import SheetCost
        entry=ManualPriceEntry.objects.create(kind='game_tariff',region='tr',label='1–99',cost_coefficient=Decimal('2.960'))
        config=Integration.objects.get(pk=1);config.manual_sheet_enabled=True;config.save()
        self.import_rows([api_row(price='500')],sheet_error='sheet_access')
        entry.refresh_from_db()
        self.assertEqual(entry.cost_coefficient,Decimal('2.960'))
        key=('game_tariff','tr','1-99')
        self.import_rows([api_row(price='510')],sheet_costs={key:SheetCost(*key,'coefficient',Decimal('3'),'Прайс!B25')},
                         manual_revisions={entry.pk:entry.revision-1})
        entry.refresh_from_db()
        self.assertEqual(entry.cost_coefficient,Decimal('2.960'))
        self.assertEqual(Product.objects.get().purchase_cost,Decimal('510'))
        self.assertEqual(SyncJob.objects.latest('created_at').summary['manual_sheet']['skipped'],1)

    def test_manual_cost_and_markup_compute_price_and_cannot_replace_api_cost(self):
        from .manual import edit_amounts
        entry = ManualPriceEntry.objects.create(kind='steam_tariff', label='До 99 ₽', unit='percent', value=Decimal('7'))
        entry = edit_amounts(actor=self.owner, entry_id=entry.pk, revision=entry.revision,
                            values={'manual_cost': '123.45', 'markup': '6'})
        self.assertEqual(entry.manual_cost, Decimal('123.45'))
        self.assertEqual(next(row for row in snapshot(actor=self.owner).rows if row.family == 'Пополнение Steam').price, '130 ₽')
        self.assertEqual(entry.value, Decimal('7'))
        with self.assertRaises(ValidationError):
            edit_amounts(actor=self.owner, entry_id=entry.pk, revision=entry.revision, values={'value': '6'})
        with self.assertRaises(ValidationError):
            edit_amounts(actor=self.owner, entry_id=entry.pk, revision=entry.revision-1, values={'manual_cost': '1'})
        with self.assertRaises(PermissionDenied):
            edit_amounts(actor=self.viewer, entry_id=entry.pk, revision=entry.revision, values={'manual_cost': '1'})
        self.import_rows([api_row(available=False)])
        entry.refresh_from_db()
        self.assertEqual(entry.manual_cost, Decimal('123.45'))
        self.assertEqual(entry.markup, Decimal('6'))
        row = Product.objects.get()
        with self.assertRaises(ValidationError):
            edit_product(actor=self.owner, product_id=row.pk, revision=row.revision, values={'manual_cost': '1'})
        self.client.force_login(self.owner)
        response = self.client.get(reverse('pricing:digital_prices:catalog'))
        self.assertContains(response, 'Нет в наличии')
        self.assertNotContains(response, f'form="product-price-{row.pk}" name="manual_cost"')

    def test_manual_modes_preserve_each_basis_and_calculate_without_ruble_rounding(self):
        from .manual import edit_amounts
        from .public import manual_row
        entry=ManualPriceEntry.objects.create(kind='game_tariff',region='turkey',label='1–99')
        entry=edit_amounts(actor=self.owner,entry_id=entry.pk,revision=entry.revision,
            values={'manual_cost':'500','markup':'11','cost_coefficient':'2.960',
                    'markup_coefficient':'0.150','cost_percent':'6','markup_percent':'2','pricing_mode':'coefficient'})
        self.assertEqual(manual_row(entry).price,'3.110')
        entry=edit_amounts(actor=self.owner,entry_id=entry.pk,revision=entry.revision,values={'pricing_mode':'percent'})
        self.assertEqual(manual_row(entry).price,'+8%')
        self.assertEqual(entry.cost_coefficient,Decimal('2.960'))
        entry=edit_amounts(actor=self.owner,entry_id=entry.pk,revision=entry.revision,values={'pricing_mode':'rub'})
        self.assertEqual(manual_row(entry).price,'520 ₽')
        entry=edit_amounts(actor=self.owner,entry_id=entry.pk,revision=entry.revision,
            values={'pricing_mode':'coefficient','markup_coefficient':'0'})
        self.assertEqual(manual_row(entry).price,'2.960')
        entry=edit_amounts(actor=self.owner,entry_id=entry.pk,revision=entry.revision,values={'markup_coefficient':''})
        self.assertEqual(manual_row(entry).price,'Цена уточняется')
        for values in ({'pricing_mode':'invalid'},{'cost_percent':'-1'},{'cost_coefficient':'NaN'},
                       {'cost_coefficient':'2.12345'},{'value':'10'}):
            with self.assertRaises(ValidationError):
                edit_amounts(actor=self.owner,entry_id=entry.pk,revision=entry.revision,values=values)

    def test_catalog_has_all_rows_and_manual_filter_excludes_every_api_offer(self):
        from .catalog import catalog_slides
        from .layout import COUNTRY_COLORS
        for index in range(70):
            Product.objects.create(external_id=f'pv2_{index}', source_name=f'Offer {index}', source_type='ps',
                category='PlayStation Plus', region='turkey', currency='RUB', purchase_cost=Decimal('100'),
                last_seen_at=timezone.now(), confirmed_at=timezone.now())
        manual = ManualPriceEntry.objects.create(kind='game_tariff', region='turkey', label='1–99', unit='coefficient')
        data = catalog_slides(user=self.owner, params={})
        count = sum(len(block['rows']) for slide in data['slides'] for block in slide['blocks'])
        self.assertEqual(count, Product.objects.count()+1)
        self.assertEqual(data['slides'][0]['title'], 'Главная')
        block = next(block for block in data['slides'][0]['blocks'] if block['title'] == 'Игры Турция')
        self.assertEqual(block['color'], COUNTRY_COLORS['tr'])
        filtered = catalog_slides(user=self.owner, params={'cost_source': 'manual'})
        rows = [row for slide in filtered['slides'] for block in slide['blocks'] for row in block['rows']]
        self.assertEqual([(row['kind'], row['id']) for row in rows], [('manual', manual.pk)])
        self.assertTrue(rows[0]['edit_cost'])

    def test_png_draws_main_title_without_internal_source_labels(self):
        from PIL import ImageDraw
        from pathlib import Path
        from django.conf import settings
        entries = (PublicRow('Game', 'Игры', 'services', 'tr', '2.500', 'yes', 'Игры', label='1–99'),
                   PublicRow('Steam', 'Пополнение Steam', 'services', '', '+6%', 'yes', 'Пополнение Steam', 'Ручные тарифы', label='До 99 ₽'))
        catalog = PublicCatalog(1, timezone.now().isoformat(), timezone.now().isoformat(), True, entries)
        texts = []
        original = ImageDraw.ImageDraw.text
        def record(draw, xy, text, *args, **kwargs):
            texts.append(str(text))
            return original(draw, xy, text, *args, **kwargs)
        with patch.object(ImageDraw.ImageDraw, 'text', record):
            pages = render(catalog, font_directory=Path(settings.BASE_DIR)/'static/resource/fonts')
        self.assertEqual(sum(page.row_count for page in pages), len(entries))
        self.assertIn('Главная', texts)
        self.assertFalse(any('Ручн' in text or 'Данные API' in text for text in texts))

    def test_manual_settings_survive_rename_cost_and_availability_updates(self):
        row = Product.objects.get()
        self.assertIsNone(row.markup)
        row = edit_product(actor=self.owner, product_id=row.pk, revision=row.revision,
                           values={'markup': '81.49', 'display_name': 'GameBAT offering', 'rule': 'other',
                                   'category': 'Моя категория', 'section': 'codes'})
        self.import_rows([api_row(name='Renamed', price='9000', available=False)])
        row.refresh_from_db()
        self.assertEqual((row.markup, row.display_name, row.rule, row.category, row.section),
                         (Decimal('81.49'), 'GameBAT offering', 'other', 'Моя категория', 'codes'))
        self.assertEqual(row.availability, 'no')
        self.import_rows([api_row(price='9100', available=True)])
        row.refresh_from_db()
        self.assertEqual(row.markup, Decimal('81.49'))
        self.assertEqual(row.availability, 'yes')
        self.assertEqual(Product.objects.count(), 1)

    def test_stale_edit_and_permissions_do_not_write(self):
        row = Product.objects.get()
        edit_product(actor=self.owner, product_id=row.pk, revision=row.revision, values={'markup': '0'})
        with self.assertRaises(ValidationError):
            edit_product(actor=self.owner, product_id=row.pk, revision=row.revision, values={'markup': '500'})
        with self.assertRaises(PermissionDenied):
            edit_product(actor=self.viewer, product_id=row.pk, revision=row.revision+1, values={'markup': '500'})
        row.refresh_from_db()
        self.assertEqual(row.markup, 0)

    def test_missing_and_foreign_currency_do_not_create_false_stock_or_price(self):
        self.import_rows([api_row(product_id='pv2_foreign', currency='usd', price='100')])
        row = Product.objects.get(external_id='pv2_synthetic')
        self.assertTrue(row.requires_review)
        self.assertEqual(row.availability, 'yes')
        data = snapshot(actor=self.owner)
        self.assertEqual(len(data.rows), 2)
        self.assertTrue(all(row.price == 'Цена уточняется' for row in data.rows))
        self.assertTrue(data.stale)

    def test_lease_loss_and_empty_import_cannot_change_catalog(self):
        before = list(Product.objects.values())
        job = SyncJob.objects.create(run_after=timezone.now(), state='running', owner=uuid.uuid4(),
            lease_until=timezone.now()-timedelta(seconds=1))
        offers, _ = parse_page({'items': [api_row(price='1')], 'page': 1, 'has_more': False}, 1)
        with self.assertRaises(APIError):
            apply_catalog(offers, job_id=job.pk, owner=job.owner)
        with self.assertRaises(APIError):
            apply_catalog([], job_id=job.pk, owner=job.owner)
        self.assertEqual(before, list(Product.objects.values()))

    def test_public_snapshot_and_viewer_html_do_not_contain_cost_markup_or_external_id(self):
        row = Product.objects.get()
        edit_product(actor=self.owner, product_id=row.pk, revision=row.revision, values={'markup': '81.49'})
        public = json.dumps(serialize(snapshot(actor=self.viewer)), ensure_ascii=False)
        for secret in ('9371.29', '81.49', 'pv2_synthetic', 'purchase_cost', 'markup', 'external_id'):
            self.assertNotIn(secret, public)
        self.client.force_login(self.viewer)
        response = self.client.get(reverse('pricing:digital_prices:catalog'))
        for secret in ('9371.29', '81.49', 'pv2_synthetic'):
            self.assertNotContains(response, secret)
        self.assertEqual(self.client.post(reverse('pricing:digital_prices:markup', args=[row.pk]),
            {'revision': row.revision, 'markup': '1'}).status_code, 403)

    def test_complete_png_bundle_contains_every_row_and_no_sensitive_metadata(self):
        for index in range(45):
            Product.objects.create(external_id=f'code_{index}', source_name=('Длинное название ' * 14)+str(index),
                source_type='code', category='Цифровые коды', section='codes', purchase_cost='499.13', currency='RUB',
                markup=None, availability='no', last_seen_at=timezone.now(), confirmed_at=timezone.now())
        for row in Product.objects.filter(external_id__in=['pv2_synthetic', 'code_0']):
            edit_product(actor=self.owner, product_id=row.pk, revision=row.revision, values={'markup':'0'})
        bundle = generate_bundle(actor=self.viewer)
        self.assertEqual(bundle.pages.count(), 2)
        code_page = bundle.pages.get(filename__startswith='GameBAT_codes')
        self.assertGreater(code_page.height, 2600)
        from .telegram import requires_document
        self.assertTrue(requires_document(code_page))
        self.assertEqual(sum(bundle.pages.values_list('row_count', flat=True)), Product.objects.count())
        for page in bundle.pages.all():
            image = Image.open(BytesIO(bytes(page.png)))
            self.assertEqual(image.format, 'PNG')
            self.assertEqual(image.info, {})
            self.assertLess(len(page.png), 50*1024*1024)
            self.assertEqual(image.size, (page.width, page.height))
            if not requires_document(page):
                self.assertLessEqual(page.width+page.height, 10000)

    def test_manual_requests_are_deduplicated_and_no_network_is_needed_for_prices(self):
        row = Product.objects.get()
        edit_product(actor=self.owner, product_id=row.pk, revision=row.revision, values={'markup':'0'})
        first = enqueue_sync(actor=self.owner)
        second = enqueue_sync(actor=self.owner)
        self.assertEqual(first.pk, second.pk)
        with patch('digital_prices.api.CatalogClient.fetch', side_effect=AssertionError('Сеть запрещена')):
            bundle = generate_bundle(actor=self.viewer)
        self.assertTrue(bundle.pages.exists())

    def test_manual_tariffs_have_no_api_cost_and_survive_import(self):
        from .manual import save_rows, edit_amounts
        values = {'kind': 'game_tariff', 'region': 'tr', 'label': '1–99', 'position': 0}
        save_rows(actor=self.owner, changes=[values])
        entry = ManualPriceEntry.objects.get()
        entry = edit_amounts(actor=self.owner, entry_id=entry.pk, revision=entry.revision,
                            values={'manual_cost': '2.96', 'markup': '0'})
        self.import_rows([api_row(price='500')])
        entry.refresh_from_db()
        self.assertEqual(entry.manual_cost, Decimal('2.96'))
        public = snapshot(actor=self.viewer)
        manual = next(row for row in public.rows if row.family == 'Игры')
        self.assertEqual(manual.price, '10 ₽')
        with self.assertRaises(PermissionDenied):
            save_rows(actor=self.viewer, changes=[values])
        save_rows(actor=self.owner, changes=[{**values, 'pk': entry.pk, 'revision': entry.revision, 'label': 'Новое название'}])
        with self.assertRaises(ValidationError):
            save_rows(actor=self.owner, changes=[{**values, 'pk': entry.pk, 'revision': entry.revision, 'label': 'Другой вариант'}])
        entry.refresh_from_db()
        self.assertEqual(entry.manual_cost, Decimal('2.96'))
        self.assertEqual(entry.markup, Decimal('0'))


class TelegramBundleTests(TestCase):
    setUp = CatalogTests.setUp
    import_rows = CatalogTests.import_rows

    def prepare_job(self):
        from telegram_bots.models import StaffBot, StaffBotAccess
        from telegram_bots.handlers import accept_update
        from telegram_bots.jobs import claim_job
        bot = StaffBot.objects.create(enabled=True, lease_owner=uuid.uuid4(), lease_until=timezone.now()+timedelta(minutes=3))
        StaffBotAccess.objects.create(bot=bot, user=self.owner, telegram_user_id=77, allowed=True)
        self.import_rows([api_row(), api_row(product_id='pv2_code', type='code')])
        for row in Product.objects.all():
            edit_product(actor=self.owner, product_id=row.pk, revision=row.revision, values={'markup':'0'})
        accept_update(bot.pk, {'update_id': 555, 'message': {'chat': {'id': 77, 'type': 'private'},
            'from': {'id': 77}, 'text': 'Прайс цифровых товаров'}})
        from digital_sales.models import Buyer
        buyer = Buyer.objects.create(name='Покупатель цифрового прайса')
        accept_update(bot.pk, {'update_id': 556, 'callback_query': {'id': 'pick-buyer', 'from': {'id': 77},
            'data': f'digital_price_images:buyer:{buyer.pk}',
            'message': {'chat': {'id': 77, 'type': 'private'}, 'message_id': 10}}})
        return bot, claim_job(bot.pk)

    def test_timeout_after_first_photo_keeps_known_page_and_does_not_repeat_unknown(self):
        from telegram_bots.jobs import run_job
        from telegram_bots.client import TelegramError
        bot, job = self.prepare_job()
        client = Mock()
        client.photo.side_effect = [{'message_id': 1}, TelegramError('timeout', uncertain=True)]
        with patch('digital_prices.telegram.time.sleep'):
            run_job(job, client, owner=bot.lease_owner)
        job.refresh_from_db()
        self.assertEqual(job.state, 'uncertain')
        self.assertEqual(list(PageDelivery.objects.filter(job=job).order_by('page__index').values_list('state', flat=True)), ['done', 'uncertain'])
        run_job(job, client, owner=bot.lease_owner)
        self.assertEqual(client.photo.call_count, 2)
        self.assertIn('Подтверждённые страницы: 1', client.message.call_args.args[1])

    def test_tall_png_is_document_and_unknown_result_is_not_sent_again(self):
        from telegram_bots.jobs import run_job
        from telegram_bots.client import TelegramError
        from .models import BotBundle
        bot, job = self.prepare_job()
        bundle = generate_bundle(actor=self.owner)
        page = bundle.pages.order_by('index').last()
        buffer = BytesIO()
        Image.new('RGB', (840, 3001), '#101723').save(buffer, format='PNG')
        page.png, page.width, page.height = buffer.getvalue(), 840, 3001
        page.save(update_fields=['png', 'width', 'height'])
        BotBundle.objects.create(job=job, bundle=bundle)
        for row in bundle.pages.all():
            PageDelivery.objects.create(job=job, page=row)
        client = Mock()
        client.photo.return_value = {'message_id': 1}
        client.image_document.side_effect = TelegramError('timeout', uncertain=True)
        with patch('digital_prices.telegram.time.sleep'):
            run_job(job, client, owner=bot.lease_owner)
        job.refresh_from_db()
        self.assertEqual(job.state, 'uncertain')
        self.assertEqual(client.photo.call_count, 1)
        self.assertEqual(client.image_document.call_count, 1)
        run_job(job, client, owner=bot.lease_owner)
        self.assertEqual(client.image_document.call_count, 1)

    def test_permission_revocation_stops_remaining_pages(self):
        from telegram_bots.jobs import run_job
        bot, job = self.prepare_job()
        client = Mock()
        def revoke(*args, **kwargs):
            self.owner.is_active = False
            self.owner.save(update_fields=['is_active'])
            return {'message_id': 1}
        client.photo.side_effect = revoke
        with patch('digital_prices.telegram.time.sleep'):
            run_job(job, client, owner=bot.lease_owner)
        job.refresh_from_db()
        self.assertEqual(client.photo.call_count, 1)
        self.assertEqual(job.state, 'partial')
    # Синтетический transport; никакой реальной отправки или API-ключа.
    def test_buyer_choice_sends_all_pages_with_preview_and_tracks_each_result(self):
        row = Product.objects.get()
        edit_product(actor=self.owner, product_id=row.pk, revision=row.revision, values={'markup':'0'})
        from telegram_bots.models import StaffBot, StaffBotAccess, StaffBotUpdate, StaffBotJob
        from telegram_bots.jobs import claim_job, run_job
        from telegram_bots.handlers import accept_update
        from django.test import override_settings
        bot = StaffBot.objects.create(enabled=True, lease_owner=uuid.uuid4(), lease_until=timezone.now()+timedelta(minutes=3))
        StaffBotAccess.objects.create(bot=bot, user=self.owner, telegram_user_id=77, allowed=True)
        update = {'update_id': 123, 'message': {'chat': {'id': 77, 'type': 'private'}, 'from': {'id': 77},
                                             'text': 'Прайс цифровых товаров'}}
        reply = accept_update(bot.pk, update)
        accept_update(bot.pk, update)
        self.assertIsNotNone(reply)
        self.assertEqual(StaffBotJob.objects.count(), 0)
        from digital_sales.models import Buyer
        buyer = Buyer.objects.create(name='Покупатель комплекта')
        choice = {'update_id': 124, 'callback_query': {'id': 'pick-buyer', 'from': {'id': 77},
            'data': f'digital_price_images:buyer:{buyer.pk}',
            'message': {'chat': {'id': 77, 'type': 'private'}, 'message_id': 10}}}
        accept_update(bot.pk, choice)
        accept_update(bot.pk, choice)
        self.assertEqual(StaffBotJob.objects.count(), 1)
        job = claim_job(bot.pk)
        client = Mock()
        client.photo.return_value = {'message_id': 400}
        run_job(job, client, owner=bot.lease_owner)
        job.refresh_from_db()
        self.assertEqual(job.state, 'done')
        self.assertEqual(client.photo.call_count, PageDelivery.objects.filter(job=job).count())
        self.assertTrue(all(call.args[2].startswith(b'\x89PNG') for call in client.photo.call_args_list))
        for call in client.photo.call_args_list:
            caption = call.kwargs['caption']
            self.assertIn('@GameBAT_Store', caption)
            self.assertIn('Для:', caption)
            self.assertLessEqual(len(caption.encode('utf-16-le')) // 2, 1024)
