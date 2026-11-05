"""Шаблоны поставщиков проверяются на искусственных товарах без настоящего Telegram."""
from io import BytesIO
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from openpyxl import load_workbook

from accounts.models import User
from catalog.models import CD, Tech, Platform, Brand, ProductType
from partners.models import Supplier
from pricing.models import SupplierCDPrice, SupplierTechPrice
from .access import issue_link
from .handlers import accept_update
from .models import StaffBot, StaffBotAccess, StaffBotJob
from .tests import update, FakeClient
from .jobs import claim_job, run_job, recover_interrupted
from .client import TelegramError


TEMPLATES = 'supplier_price_templates'
TITLE = 'Скачать шаблоны поставщиков с ценами'


@override_settings(GAMEBAT_ENV='local_live')
class SupplierTemplateBotTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('supplier-bot-employee')
        self.grant('telegram_bots.use_staff_bot', 'price.download_supplier_template', 'price.view_supplier_prices')
        self.bot = StaffBot.objects.create(username='SupplierTestBot', enabled=True, cooldown_seconds=0)
        self.access = StaffBotAccess.objects.create(bot=self.bot, user=self.user, allowed=True,
            telegram_user_id=101, linked_at=timezone.now())
        self.supplier = Supplier.objects.create(name='Закрытое название A', letter='A')
        self.other = Supplier.objects.create(name='Другой поставщик F', letter='F')
        self.cd = CD.objects.create(name='Игра шаблона', platform=Platform.objects.create(name='Test PS5'))
        self.tech = Tech.objects.create(name='Техника шаблона', brand=Brand.objects.create(name='Test Brand'),
            product_type=ProductType.objects.create(name='Test Type'))
        SupplierCDPrice.objects.create(supplier=self.supplier, cd=self.cd, price=101)
        SupplierTechPrice.objects.create(supplier=self.supplier, tech=self.tech, price=202)
        SupplierCDPrice.objects.create(supplier=self.other, cd=self.cd, price=999)

    def grant(self, *permissions):
        for value in permissions:
            app, code = value.split('.')
            self.user.user_permissions.add(Permission.objects.get(content_type__app_label=app, codename=code))

    def request(self, number=1, supplier=None):
        return accept_update(self.bot.pk, update(number,
            data=f'{TEMPLATES}:{(supplier or self.supplier).pk}'))

    def test_template_only_employee_can_link_and_sees_only_own_function(self):
        reply = accept_update(self.bot.pk, update(1, text='/menu'))
        self.assertEqual(reply['reply_markup']['keyboard'], [[{'text': TITLE}]])
        self.assertTrue(reply['reply_markup']['is_persistent'])
        self.assertIn('разрешения', accept_update(self.bot.pk, update(2, data='wholesale_stock_price'))['text'])
        self.access.telegram_user_id = None
        self.access.save()
        self.assertIn('start=', issue_link(self.user, self.bot))

    def test_dynamic_supplier_menu_hides_details_and_has_back(self):
        reply = accept_update(self.bot.pk, update(1, text=TITLE))
        buttons = reply['reply_markup']['inline_keyboard']
        self.assertEqual([row[0]['text'] for row in buttons], ['[A]', '[F]', 'Назад'])
        self.assertNotIn(self.supplier.name, str(reply))
        self.grant('partners.view_supplier_details')
        reply = accept_update(self.bot.pk, update(2, text=TITLE))
        self.assertIn(self.supplier.name, str(reply))
        self.assertIn(TITLE, str(accept_update(self.bot.pk, update(3, data='menu'))))

    def test_callback_queues_pair_without_warehouse_and_deduplicates(self):
        reply = self.request()
        self.assertIn('Формирую шаблоны', reply['text'])
        self.assertNotIn(self.supplier.name, reply['text'])
        job = StaffBotJob.objects.get()
        self.assertEqual(job.function, TEMPLATES)
        self.assertEqual(job.supplier_id, self.supplier.pk)
        self.assertIsNone(job.warehouse_id)
        self.assertEqual(list(job.documents.values_list('product_kind', flat=True)), ['cd', 'tech'])
        self.assertIsNone(self.request())
        self.assertIn('уже', self.request(2)['text'])
        self.assertEqual(StaffBotJob.objects.count(), 1)

    def test_forged_callback_requires_both_supplier_permissions(self):
        self.user.user_permissions.remove(Permission.objects.get(
            content_type__app_label='price', codename='view_supplier_prices'))
        reply = self.request()
        self.assertIn('нет разрешения', reply['text'])
        self.assertEqual(StaffBotJob.objects.count(), 0)
        reply = accept_update(self.bot.pk, update(2, text='/menu'))
        self.assertEqual(reply['reply_markup'], {'remove_keyboard': True})

    def test_documents_match_web_exports_and_only_selected_supplier_prices(self):
        from .documents import supplier_documents
        documents = supplier_documents(self.access, self.supplier.pk)
        self.client.force_login(self.user)
        for kind, filename, content in documents:
            self.assertEqual(filename, f'resource-supplier-A-{kind}-template.xlsx')
            response = self.client.get(reverse('price:supplier_template_prefilled', args=[self.supplier.pk, kind]))
            self.assertEqual(response.status_code, 200)
            actual, web = load_workbook(BytesIO(content)), load_workbook(BytesIO(response.content))
            self.assertEqual(list(actual.worksheets[0].values), list(web.worksheets[0].values))
            prices = [row[5].value for row in actual.worksheets[0].iter_rows() if row[0].value in ['CD', 'TECH']]
            self.assertEqual(prices, [101 if kind == 'cd' else 202])
            self.assertNotIn(999, prices)
            self.assertEqual(actual.worksheets[1].sheet_state, web.worksheets[1].sheet_state)
            self.assertIn(actual.worksheets[1].sheet_state, ['hidden', 'veryHidden'])

    def test_sends_both_files_in_order_and_records_separate_message_ids(self):
        from sales.models import Sale
        from supplies.models import Supply
        from cash.models import CashTransaction
        from warehouse.models import CDWarehouseStock, TechWarehouseStock
        business_models = [SupplierCDPrice, SupplierTechPrice, Sale, Supply, CashTransaction,
            CDWarehouseStock, TechWarehouseStock]
        snapshots = [list(model.objects.order_by('pk').values()) for model in business_models]
        self.request()
        job = claim_job(self.bot.pk)
        client = FakeClient()
        client.document = lambda chat, name, data: (client.documents.append((chat, name, data)) or
            {'message_id': 100 + len(client.documents)})
        run_job(job, client)
        job.refresh_from_db()
        self.assertEqual(job.state, 'done')
        self.assertEqual([d[1] for d in client.documents], ['resource-supplier-A-cd-template.xlsx',
            'resource-supplier-A-tech-template.xlsx'])
        self.assertEqual(list(job.documents.values_list('state', 'telegram_message_id')),
            [('done', 101), ('done', 102)])
        self.assertEqual([list(model.objects.order_by('pk').values()) for model in business_models], snapshots)

    def test_first_success_second_failure_is_partial_and_never_retried(self):
        self.request()
        job, client = claim_job(self.bot.pk), FakeClient()
        def send(chat, filename, content):
            client.documents.append((chat, filename, content))
            if len(client.documents) == 2:
                raise TelegramError('forbidden')
            return {'message_id': 501}
        client.document = send
        run_job(job, client)
        job.refresh_from_db()
        self.assertEqual(job.state, 'partial')
        self.assertEqual(list(job.documents.values_list('state', 'telegram_message_id')),
            [('done', 501), ('error', None)])
        run_job(job, client)
        recover_interrupted(self.bot.pk)
        self.assertEqual(len(client.documents), 2)
        self.request(2)
        self.assertEqual(StaffBotJob.objects.count(), 2)

    def test_first_unknown_stops_second_and_requires_chat_check(self):
        self.request()
        job, client = claim_job(self.bot.pk), FakeClient()
        client.error = TelegramError('timeout', uncertain=True)
        run_job(job, client)
        job.refresh_from_db()
        self.assertEqual(job.state, 'uncertain')
        self.assertEqual(list(job.documents.values_list('state', flat=True)), ['uncertain', 'pending'])
        self.assertEqual(len(client.documents), 1)

    def test_revocation_between_files_stops_tech_and_preserves_cd_confirmation(self):
        self.request()
        job, client = claim_job(self.bot.pk), FakeClient()
        def send(chat, filename, content):
            client.documents.append((chat, filename, content))
            self.user.user_permissions.remove(Permission.objects.get(
                content_type__app_label='price', codename='view_supplier_prices'))
            return {'message_id': 601}
        client.document = send
        run_job(job, client)
        job.refresh_from_db()
        self.assertEqual(job.state, 'partial')
        self.assertEqual(len(client.documents), 1)
        self.assertEqual(list(job.documents.values_list('state', 'telegram_message_id')),
            [('done', 601), ('pending', None)])

    def test_intent_is_saved_before_each_api_call_and_restart_does_not_resend(self):
        self.request()
        job, client = claim_job(self.bot.pk), FakeClient()
        def send(chat, filename, content):
            kind = 'cd' if '-cd-' in filename else 'tech'
            self.assertEqual(job.documents.get(product_kind=kind).state, 'sending')
            client.documents.append((chat, filename, content))
            return {'message_id': 700 + len(client.documents)}
        client.document = send
        run_job(job, client)
        job.state = 'sending'
        job.save(update_fields=['state'])
        tech = job.documents.get(product_kind='tech')
        tech.state, tech.telegram_message_id = 'sending', None
        tech.save()
        recover_interrupted(self.bot.pk)
        job.refresh_from_db()
        self.assertEqual(job.state, 'uncertain')
        self.assertEqual(job.documents.get(product_kind='cd').telegram_message_id, 701)
        self.assertEqual(job.documents.get(product_kind='tech').state, 'uncertain')
        self.assertIsNone(claim_job(self.bot.pk))

    def test_missing_prices_new_products_exclusions_and_fresh_values(self):
        from .documents import supplier_documents
        new_cd = CD.objects.create(name='Новая игра без цены', platform=self.cd.platform)
        hidden = CD.objects.create(name='Исключённая игра', platform=self.cd.platform,
            exclude_from_supplier_template=True)
        archived = Tech.objects.create(name='Архив', brand=self.tech.brand, product_type=self.tech.product_type,
            is_archived=True)
        SupplierCDPrice.objects.create(supplier=self.supplier, cd=hidden, price=333)
        SupplierTechPrice.objects.create(supplier=self.supplier, tech=archived, price=444)
        SupplierTechPrice.objects.get(supplier=self.supplier, tech=self.tech).delete()
        contents = supplier_documents(self.access, self.supplier.pk)
        books = {kind: load_workbook(BytesIO(data)) for kind, _, data in contents}
        def cells(book):
            return {(row[0].value.lower(), row[1].value): row[5]
                for row in book.worksheets[0].iter_rows() if row[0].value in ['CD', 'TECH']}
        cd, tech = cells(books['cd']), cells(books['tech'])
        self.assertIsNone(cd['cd', new_cd.pk].value)
        self.assertIsNone(tech['tech', self.tech.pk].value)
        self.assertNotIn(('cd', hidden.pk), cd)
        self.assertNotIn(('tech', archived.pk), tech)
        self.assertIn('AED', str(list(books['cd'].worksheets[0].values)))
        price = SupplierCDPrice.objects.get(supplier=self.supplier, cd=self.cd)
        price.price = 123
        price.save()
        latest = supplier_documents(self.access, self.supplier.pk)
        self.assertEqual(cells(load_workbook(BytesIO(latest[0][2])))['cd', self.cd.pk].value, 123)
        price.delete()
        latest = supplier_documents(self.access, self.supplier.pk)
        self.assertIsNone(cells(load_workbook(BytesIO(latest[0][2])))['cd', self.cd.pk].value)

    def test_returned_documents_import_through_existing_service(self):
        from .documents import supplier_documents
        from price.excel import import_supplier_price
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.grant('price.upload_supplier_price')
        for kind, filename, data in supplier_documents(self.access, self.supplier.pk):
            book = load_workbook(BytesIO(data))
            sheet = book.worksheets[0]
            row = next(row for row in sheet.iter_rows() if row[0].value == kind.upper())
            row[5].value = 321
            stream = BytesIO()
            book.save(stream)
            import_supplier_price(supplier_id=self.supplier.pk, actor=self.user, product_kind=kind,
                upload=SimpleUploadedFile(filename, stream.getvalue()))
        self.assertEqual(SupplierCDPrice.objects.get(supplier=self.supplier, cd=self.cd).price, Decimal('321'))
        self.assertEqual(SupplierTechPrice.objects.get(supplier=self.supplier, tech=self.tech).price, Decimal('321'))
        self.assertEqual(SupplierCDPrice.objects.get(supplier=self.other, cd=self.cd).price, Decimal('999'))

    def test_deleted_supplier_invalid_callbacks_and_private_chat(self):
        empty = Supplier.objects.create(name='Без цен', letter='B')
        self.request(supplier=empty)
        empty.delete()
        job, client = claim_job(self.bot.pk), FakeClient()
        run_job(job, client)
        job.refresh_from_db()
        self.assertEqual(job.state, 'error')
        self.assertIsNone(job.supplier_id)
        self.assertEqual(client.documents, [])
        for i, suffix in enumerate(['0', '-1', '1;DROP', '9223372036854775808', str(empty.pk or 999999)], 2):
            accept_update(self.bot.pk, update(i, data=f'{TEMPLATES}:{suffix}'))
        accept_update(self.bot.pk, update(20, data=f'{TEMPLATES}:{self.supplier.pk}', chat_type='group'))
        self.assertEqual(StaffBotJob.objects.count(), 1)

    def test_generation_failure_sends_no_documents_or_sensitive_exception(self):
        self.request()
        job, client = claim_job(self.bot.pk), FakeClient()
        with patch('telegram_bots.documents.generate_supplier_template', side_effect=ValueError('private key detail')):
            run_job(job, client)
        job.refresh_from_db()
        self.assertEqual(job.state, 'error')
        self.assertEqual(client.documents, [])
        self.assertNotIn('private key', str(client.messages))
        self.assertIn('Не удалось сформировать шаблоны', str(client.messages))

    def test_database_ack_failure_keeps_unknown_document_result(self):
        from .jobs import finish_document
        self.request()
        job, client = claim_job(self.bot.pk), FakeClient()
        def fail_ack(document, state, *args, **kwargs):
            if state == 'done':
                raise RuntimeError('Database ack failed')
            return finish_document(document, state, *args, **kwargs)
        with patch('telegram_bots.jobs.finish_document', side_effect=fail_ack):
            run_job(job, client)
        job.refresh_from_db()
        self.assertEqual(job.state, 'uncertain')
        self.assertEqual(job.documents.get(product_kind='cd').state, 'uncertain')
        self.assertEqual(len(client.documents), 1)

    def test_both_functions_share_active_job_limit_and_cooldown(self):
        from warehouse.models import Warehouse
        self.grant('price.generate_wholesale_price')
        reply = accept_update(self.bot.pk, update(1, text='/menu'))
        self.assertEqual(len(reply['reply_markup']['keyboard']), 2)
        self.request(2)
        warehouse = Warehouse.objects.create(name='Склад другой функции')
        reply = accept_update(self.bot.pk, update(3, data=f'wholesale_stock_price:{warehouse.pk}'))
        self.assertIn('уже', reply['text'])
        self.assertEqual(StaffBotJob.objects.count(), 1)
        run_job(claim_job(self.bot.pk), FakeClient())
        self.bot.cooldown_seconds = 30
        self.bot.save()
        self.assertIn('частые', self.request(4)['text'])
        self.assertEqual(StaffBotJob.objects.count(), 1)

    def test_rebinding_or_revocation_during_generation_blocks_all_delivery(self):
        from .documents import supplier_documents
        for action in ['rebind', 'revoke']:
            with self.subTest(action=action):
                self.access.telegram_user_id = 101
                self.access.save()
                self.grant('price.view_supplier_prices')
                self.request(10 if action == 'rebind' else 11)
                job, client = claim_job(self.bot.pk), FakeClient()
                def generate(*args):
                    result = supplier_documents(*args)
                    if action == 'rebind':
                        self.access.telegram_user_id = 202
                        self.access.save()
                    else:
                        self.user.user_permissions.remove(Permission.objects.get(
                            content_type__app_label='price', codename='view_supplier_prices'))
                    return result
                with patch('telegram_bots.jobs.supplier_documents', side_effect=generate):
                    run_job(job, client)
                job.refresh_from_db()
                self.assertEqual(job.state, 'error')
                self.assertEqual(client.documents, [])

    def test_first_known_failure_and_second_unknown_have_distinct_results(self):
        for position, uncertain, expected in [(1, False, 'error'), (2, True, 'uncertain')]:
            with self.subTest(position=position):
                self.request(position)
                job, client = claim_job(self.bot.pk), FakeClient()
                def send(chat, filename, content):
                    client.documents.append((chat, filename, content))
                    if len(client.documents) == position:
                        raise TelegramError('timeout' if uncertain else 'forbidden', uncertain=uncertain)
                    return {'message_id': 900}
                client.document = send
                run_job(job, client)
                job.refresh_from_db()
                self.assertEqual(job.state, expected)
                self.assertEqual(len(client.documents), position)
                if uncertain:
                    self.assertIn('Проверьте чат', str(client.messages))

    def test_missing_suppliers_and_recovery_before_any_send(self):
        with patch('telegram_bots.handlers.Supplier.objects.order_by', return_value=[]):
            self.assertIn('нет доступных поставщиков', accept_update(self.bot.pk, update(1, text=TITLE))['text'])
        self.request(2)
        job = claim_job(self.bot.pk)
        recover_interrupted(self.bot.pk)
        job.refresh_from_db()
        self.assertEqual(job.state, 'error')
        self.assertIsNone(claim_job(self.bot.pk))
        self.request(3)
        self.assertEqual(StaffBotJob.objects.count(), 2)

    def test_document_size_limit_blocks_whole_pair_before_first_delivery(self):
        self.request()
        job, client = claim_job(self.bot.pk), FakeClient()
        with override_settings(TELEGRAM_STAFF_MAX_DOCUMENT_BYTES=1):
            run_job(job, client)
        job.refresh_from_db()
        self.assertEqual(job.state, 'error')
        self.assertEqual(client.documents, [])

    def test_recovery_preserves_confirmed_documents_and_never_resumes_pending_file(self):
        for number, second_state, expected in [(1, 'pending', 'partial'), (2, 'done', 'done')]:
            self.request(number)
            job = claim_job(self.bot.pk)
            cd = job.documents.get(product_kind='cd')
            cd.state, cd.telegram_message_id = 'done', 1100 + number
            cd.save()
            tech = job.documents.get(product_kind='tech')
            tech.state = second_state
            tech.telegram_message_id = 1200 + number if second_state == 'done' else None
            tech.save()
            recover_interrupted(self.bot.pk)
            job.refresh_from_db()
            self.assertEqual(job.state, expected)
            self.assertEqual(job.documents.get(product_kind='cd').telegram_message_id, 1100 + number)
            self.assertIsNone(claim_job(self.bot.pk))

    def test_deleted_access_is_closed_without_technical_exception(self):
        from .access import BotDenied, check_access
        self.access.delete()
        with self.assertRaises(BotDenied):
            check_access(self.access)
