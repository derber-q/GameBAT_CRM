"""Синтетические пользователи/Excel; Telegram и рабочие ключи не используются."""
import uuid
from io import BytesIO
from decimal import Decimal
from unittest.mock import patch, Mock
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError, PermissionDenied
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from openpyxl import load_workbook
from catalog.models import CD, Platform
from partners.models import Partner
from warehouse.models import Warehouse, CDWarehouseStock
from sales.models import Sale
from sales.services import cancel_sale
from .models import BotConfig, Customer, PriceIssue, OrderIntent, Delivery, Event, Audit
from . import services, documents
from .handlers import ingest, process_event, deliver_one


class WholesaleTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_superuser(username='opt-test')
        self.partner = Partner.objects.create(name='Тестовый опт')
        self.other_partner = Partner.objects.create(name='Другой опт')
        self.warehouse = Warehouse.objects.create(name='Тестовый склад')
        self.config = BotConfig.objects.create(operator=self.actor, warehouse=self.warehouse)
        self.customer = Customer.objects.create(telegram_id=123, first_name='Покупатель', status='pending')
        self.cd = CD.objects.create(name='Тестовая игра', sku='OPT-1', platform=Platform.objects.create(name='PS5'),
                                    cost=100, wholesale_price=150)
        self.stock = CDWarehouseStock.objects.create(cd=self.cd, warehouse=self.warehouse, quantity=5)
        services.authorize(actor=self.actor, customer_id=self.customer.pk, revision=1, action='approve', partner_id=self.partner.pk)
        self.customer.refresh_from_db()

    def issue(self):
        return documents.issue_price(self.customer.pk)

    def set_accepting(self, value):
        self.config.enabled = True
        self.config.save(update_fields=['enabled'])
        self.config.refresh_from_db()
        return services.set_service_state(actor=self.actor, accepting=value, revision=self.config.service_revision)

    def test_service_pause_and_resume_notify_only_authorized_once(self):
        Customer.objects.create(telegram_id=999, status='pending')
        config = self.set_accepting(False)
        self.assertTrue(config.enabled)
        notice = Delivery.objects.get(key__startswith='service:')
        self.assertEqual(notice.customer_id, self.customer.pk)
        self.assertIn('@GameBAT_Store', notice.text)
        self.assertIn('временно', notice.text)
        self.assertTrue(notice.requires_authorization)
        services.set_service_state(actor=self.actor, accepting=False, revision=config.service_revision)
        self.assertEqual(Delivery.objects.filter(key__startswith='service:').count(), 1)
        config = self.set_accepting(True)
        self.assertEqual(Delivery.objects.filter(key__startswith='service:').count(), 2)
        self.assertEqual(Audit.objects.filter(kind__in=['service_paused', 'service_resumed']).count(), 2)
        with self.assertRaises(ValidationError):
            services.set_service_state(actor=self.actor, accepting=False, revision=1)

    def test_paused_messages_callbacks_and_files_do_not_process_orders(self):
        self.set_accepting(False)
        client = Mock()
        for index, payload in enumerate([{'text': 'Скачать оптовый прайс'},
                {'callback': 'w:old:1:confirm'}, {'document': {'file_id': 'no-download'}}], 1):
            event = Event.objects.create(update_id=index, customer=self.customer, payload=payload)
            process_event(event, client)
            event.refresh_from_db()
            self.assertEqual(event.state, 'done')
            self.assertIn('@GameBAT_Store', Delivery.objects.get(key=f'event:{event.pk}').text)
        client.download.assert_not_called()
        self.assertFalse(PriceIssue.objects.exists())
        self.assertFalse(OrderIntent.objects.exists())
        self.assertFalse(Sale.objects.exists())
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 5)

    def test_paused_service_blocks_direct_business_entries_and_holds_price_delivery(self):
        from .handlers import claim_delivery
        issue = self.issue()
        content = self.order_file(issue)
        self.cd.wholesale_price = 200
        self.cd.save(update_fields=['wholesale_price'])
        intent = self.submit(content)
        document = services.enqueue(self.customer, 'held-price', issue=issue, document=bytes(issue.content))
        self.set_accepting(False)
        with self.assertRaises(ValidationError):
            self.issue()
        with self.assertRaises(ValidationError):
            self.submit(content, 55)
        with self.assertRaises(ValidationError):
            services.confirm(customer_id=self.customer.pk, intent_id=intent.pk, revision=intent.revision)
        for _ in range(Delivery.objects.count()):
            row = claim_delivery()
            if row:
                self.assertNotEqual(row.pk, document.pk)
        document.refresh_from_db()
        self.assertEqual(document.state, 'pending')
        self.assertFalse(Sale.objects.exists())

    def test_request_received_during_pause_is_not_replayed_after_resume(self):
        self.set_accepting(False)
        ingest({'update_id': 77, 'message': {'message_id': 1, 'chat': {'id': 123, 'type': 'private'},
                'from': {'id': 123}, 'text': 'Скачать оптовый прайс'}})
        event = Event.objects.get(update_id=77)
        self.assertTrue(event.payload['paused'])
        self.set_accepting(True)
        process_event(event, Mock())
        self.assertFalse(PriceIssue.objects.exists())
        self.assertIn('Повторите', Delivery.objects.get(key=f'event:{event.pk}').text)

    def test_pause_switch_web_permission_csrf_and_staff_menu(self):
        from django.test import Client
        from telegram_bots.models import StaffBot, StaffBotAccess
        from telegram_bots.menu import WHOLESALE_CONTROL, main_menu
        from .staff import handle
        self.config.enabled = True
        self.config.save(update_fields=['enabled'])
        self.client.force_login(self.actor)
        self.assertContains(self.client.get(reverse('price:index')), 'role="switch"')
        url = reverse('wholesale_bot:service_state')
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.actor)
        self.assertEqual(csrf.post(url, {'accepting': 'off', 'revision': 1}).status_code, 403)
        bot = StaffBot.objects.create(enabled=True)
        access = StaffBotAccess.objects.create(bot=bot, user=self.actor, allowed=True, telegram_user_id=555)
        self.assertIn(WHOLESALE_CONTROL.title, str(main_menu(self.actor)))
        reply = handle(access, {'text': WHOLESALE_CONTROL.title}, {})
        self.assertIn('принимает', reply['text'])
        handle(access, {}, {'data': 'optservice:1:pause'})
        self.config.refresh_from_db()
        self.assertFalse(self.config.accepting_orders)
        denied = get_user_model().objects.create_user(username='no-opt-control')
        self.client.force_login(denied)
        self.assertEqual(self.client.post(url, {'accepting': 'on', 'revision': 2}).status_code, 403)
        with self.assertRaises(PermissionDenied):
            services.set_service_state(actor=denied, accepting=True, revision=2)

    def order_file(self, issue, quantity=2, change=None):
        wb = load_workbook(BytesIO(bytes(issue.content)))
        row = issue.manifest['products'][0]['row']
        wb['Прайс'].cell(row, 4, quantity)
        if change:
            change(wb, row)
        stream = BytesIO()
        wb.save(stream)
        wb.close()
        return stream.getvalue()

    def submit(self, content, number=1):
        return services.receive_order(customer_id=self.customer.pk, message_id=number, content=content)

    def test_regular_sale_and_invoice_use_existing_services(self):
        from cash.models import CashTransaction
        before = CashTransaction.objects.count()
        issue = self.issue()
        intent = self.submit(self.order_file(issue))
        self.assertEqual(intent.state, 'created')
        sale = intent.sale
        self.assertEqual(sale.partner_id, self.partner.pk)
        self.assertEqual(sale.sale_type, Sale.SaleType.WHOLESALE)
        self.assertEqual(sale.payment_method, Sale.PaymentMethod.CASH_POSTPAY)
        self.assertFalse(sale.is_completed)
        self.assertEqual(sale.total_amount, Decimal('300'))
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 3)
        self.assertEqual(CashTransaction.objects.count(), before)
        from sales.invoice_excel import sale_invoice_document
        def cells(document):
            wb = load_workbook(BytesIO(document))
            result = list(wb.active.values)
            wb.close()
            return result
        filename, content = documents.invoice(intent)
        other_filename, other_content = sale_invoice_document(sale)
        self.assertEqual(filename, other_filename)
        self.assertEqual(cells(content), cells(other_content))
        self.client.force_login(self.actor)
        response = self.client.get(reverse('sales:invoice', args=[sale.pk]))
        self.assertEqual(cells(response.content), cells(content))

    def test_price_change_again_requires_new_confirmation(self):
        issue = self.issue()
        self.cd.wholesale_price = 170
        self.cd.save(update_fields=['wholesale_price'])
        intent = self.submit(self.order_file(issue))
        self.assertEqual(intent.state, 'prices')
        self.assertFalse(Sale.objects.exists())
        old_revision = intent.revision
        self.cd.wholesale_price = 140
        self.cd.save(update_fields=['wholesale_price'])
        intent = services.confirm(customer_id=self.customer.pk, intent_id=intent.pk, revision=old_revision)
        self.assertEqual(intent.state, 'prices')
        self.assertGreater(intent.revision, old_revision)
        with self.assertRaises(ValidationError):
            services.confirm(customer_id=self.customer.pk, intent_id=intent.pk, revision=old_revision)
        intent = services.confirm(customer_id=self.customer.pk, intent_id=intent.pk, revision=intent.revision)
        self.assertEqual(intent.sale.total_amount, 280)
        services.confirm(customer_id=self.customer.pk, intent_id=intent.pk, revision=intent.revision)
        self.assertEqual(Sale.objects.count(), 1)

    def test_shortage_never_creates_partial_sale(self):
        issue = self.issue()
        intent = self.submit(self.order_file(issue, quantity=6))
        self.assertEqual(intent.state, 'shortage')
        self.assertIn('6', intent.error)
        self.assertFalse(Sale.objects.exists())
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 5)

    def test_all_shortages_are_reported_without_partial_reservation(self):
        extra = CD.objects.create(name='Вторая игра', sku='OPT-2', platform=self.cd.platform,
                                  cost=100, wholesale_price=200)
        CDWarehouseStock.objects.create(cd=extra, warehouse=self.warehouse, quantity=1)
        issue = self.issue()
        wb = load_workbook(BytesIO(bytes(issue.content)))
        for product in issue.manifest['products']:
            wb['Прайс'].cell(product['row'], 4, 10)
        stream = BytesIO()
        wb.save(stream)
        wb.close()
        intent = self.submit(stream.getvalue())
        self.assertEqual(intent.state, 'shortage')
        self.assertIn(self.cd.name, intent.error)
        self.assertIn(extra.name, intent.error)
        self.assertFalse(Sale.objects.exists())

    def test_price_returning_to_original_still_requires_new_confirmation(self):
        issue = self.issue()
        self.cd.wholesale_price = 170
        self.cd.save(update_fields=['wholesale_price'])
        intent = self.submit(self.order_file(issue))
        self.cd.wholesale_price = 150
        self.cd.save(update_fields=['wholesale_price'])
        intent = services.confirm(customer_id=self.customer.pk, intent_id=intent.pk, revision=intent.revision)
        self.assertEqual(intent.state, 'prices')
        self.assertFalse(Sale.objects.exists())
        self.assertEqual(services.confirm(customer_id=self.customer.pk, intent_id=intent.pk,
                                          revision=intent.revision).sale.total_amount, 300)

    def test_invalid_quantities_and_modified_prices_or_identifiers(self):
        issue = self.issue()
        changes = [lambda w, r: w['Прайс'].cell(r, 2, 1),
                   lambda w, r: w['_resource_meta'].cell(1, 2, 'fake')]
        for number, quantity in enumerate([-1, 1.5, '=1+1', '2', 1000001, 0], 1):
            self.assertEqual(self.submit(self.order_file(issue, quantity), number).state, 'invalid')
        for number, change in enumerate(changes, 20):
            self.assertEqual(self.submit(self.order_file(issue, change=change), number).state, 'invalid')
        self.assertFalse(Sale.objects.exists())

    def test_other_owner_rebinding_revocation_and_archived_partner(self):
        issue = self.issue()
        other = Customer.objects.create(telegram_id=124, status='authorized', partner=self.partner)
        intent = services.receive_order(customer_id=other.pk, message_id=1, content=self.order_file(issue))
        self.assertEqual(intent.state, 'invalid')
        services.authorize(actor=self.actor, customer_id=self.customer.pk, revision=self.customer.revision,
                           action='approve', partner_id=self.other_partner.pk)
        self.assertEqual(self.submit(self.order_file(issue), 2).state, 'invalid')
        self.customer.refresh_from_db()
        services.authorize(actor=self.actor, customer_id=self.customer.pk, revision=self.customer.revision, action='revoke')
        with self.assertRaises(ValidationError):
            self.issue()

    def test_repeated_file_requires_explicit_new_intent_and_cancellation_returns_stock(self):
        issue = self.issue()
        content = self.order_file(issue, 1)
        first = self.submit(content)
        self.assertEqual(self.submit(content).pk, first.pk)
        second = self.submit(content, 2)
        self.assertEqual(second.state, 'duplicate')
        self.assertEqual(Sale.objects.count(), 1)
        second = services.confirm(customer_id=self.customer.pk, intent_id=second.pk, revision=second.revision, repeat=True)
        self.assertEqual(Sale.objects.count(), 2)
        self.assertNotEqual(first.sale_id, second.sale_id)
        cancel_sale(actor=self.actor, sale_id=first.sale_id, comment='Тестовая отмена')
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 4)

    def test_no_staff_permissions_no_authorization(self):
        user = get_user_model().objects.create_user(username='forbidden')
        with self.assertRaises(PermissionDenied):
            services.authorize(actor=user, customer_id=self.customer.pk, revision=self.customer.revision, action='revoke')
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse('wholesale_bot:dashboard')).status_code, 403)

    def test_pending_user_cannot_get_price_or_order(self):
        customer = Customer.objects.create(telegram_id=999)
        with self.assertRaises(ValidationError):
            documents.issue_price(customer.pk)
        with self.assertRaises(ValidationError):
            services.receive_order(customer_id=customer.pk, message_id=1, content=b'bad')

    def test_broken_zip_is_safe_and_operator_rights_are_fresh(self):
        self.assertEqual(self.submit(b'not an xlsx').state, 'invalid')
        self.actor.is_active = False
        self.actor.save(update_fields=['is_active'])
        with self.assertRaises(ValidationError):
            self.issue()

    def test_long_change_report_is_delivered_in_full_with_one_confirmation_keyboard(self):
        text = ('Товар со старой и новой ценой ' + 'x' * 100 + '\n') * 100
        markup = {'inline_keyboard': [[{'text': 'Подтвердить', 'callback_data': 'synthetic'}]]}
        services.enqueue(self.customer, 'long-report', text=text, markup=markup)
        rows = list(Delivery.objects.filter(key__startswith='long-report').order_by('pk'))
        self.assertGreater(len(rows), 1)
        self.assertEqual(''.join(row.text for row in rows), text)
        self.assertTrue(all(len(row.text) <= 3800 for row in rows))
        self.assertEqual(sum(bool(row.markup) for row in rows), 1)
        self.assertEqual(rows[-1].markup, markup)

    def test_start_authorization_request_is_single_and_username_change_preserves_link(self):
        def update(number, identity=987, text='Авторизоваться', username='before'):
            return {'update_id': number, 'message': {'message_id': number,
                'chat': {'id': identity, 'type': 'private'},
                'from': {'id': identity, 'username': username, 'first_name': 'Test'}, 'text': text}}
        ingest(update(1, text='/start'))
        client = Mock()
        process_event(Event.objects.get(update_id=1), client)
        pending = Customer.objects.get(telegram_id=987)
        self.assertEqual(pending.status, 'new')
        for number in [2, 2, 3]:
            ingest(update(number))
        for event in Event.objects.filter(state='pending'):
            process_event(event, client)
        self.assertEqual(Customer.objects.filter(telegram_id=987).count(), 1)
        self.assertEqual(Audit.objects.filter(customer=pending, kind='access_requested').count(), 1)
        services.authorize(actor=self.actor, customer_id=pending.pk, revision=pending.revision,
                           action='approve', partner_id=self.partner.pk)
        ingest(update(4, username='after'))
        pending.refresh_from_db()
        self.assertEqual(pending.partner_id, self.partner.pk)
        self.assertEqual(pending.username, 'after')
        self.config.refresh_from_db()
        self.assertEqual(self.config.next_update_id, 5)

    def test_groups_and_foreign_callback_owner_are_rejected(self):
        ingest({'update_id': 1, 'message': {'message_id': 1, 'chat': {'id': -1, 'type': 'group'},
                'from': {'id': 123}, 'text': '/start'}})
        self.assertFalse(Event.objects.exists())
        issue = self.issue()
        self.cd.wholesale_price = 200
        self.cd.save(update_fields=['wholesale_price'])
        intent = self.submit(self.order_file(issue))
        other = Customer.objects.create(telegram_id=444, status='authorized', partner=self.partner)
        with self.assertRaises(ValidationError):
            services.confirm(customer_id=other.pk, intent_id=intent.pk, revision=intent.revision)
        self.assertFalse(Sale.objects.exists())

    def test_revocation_blocks_pending_confirmation_and_document_delivery(self):
        issue = self.issue()
        self.cd.wholesale_price = 200
        self.cd.save(update_fields=['wholesale_price'])
        intent = self.submit(self.order_file(issue))
        services.authorize(actor=self.actor, customer_id=self.customer.pk, revision=self.customer.revision, action='revoke')
        with self.assertRaises(ValidationError):
            services.confirm(customer_id=self.customer.pk, intent_id=intent.pk, revision=intent.revision)
        client = Mock()
        for _ in range(Delivery.objects.count()):
            deliver_one(client)
        # Только уведомление об отзыве; никаких частных прайсов/расчётов старой ревизии.
        client.call.assert_not_called()
        self.assertFalse(Sale.objects.exists())

    def test_delivery_failure_keeps_sale_and_retry_does_not_reserve_again(self):
        from telegram_bots.client import TelegramError
        issue = self.issue()
        intent = self.submit(self.order_file(issue))
        Delivery.objects.exclude(key=f'invoice:{intent.pk}').delete()
        client = Mock()
        client.call.side_effect = TelegramError('network', uncertain=True)
        deliver_one(client)
        delivery = Delivery.objects.get()
        self.assertEqual(delivery.state, 'uncertain')
        self.assertTrue(delivery.document)
        client.call.reset_mock()
        deliver_one(client)
        client.call.assert_not_called()
        self.client.force_login(self.actor)
        self.client.post(reverse('wholesale_bot:retry', args=['delivery', delivery.pk]))
        client.call.side_effect = None
        deliver_one(client)
        self.assertEqual(Sale.objects.count(), 1)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 3)

    def test_cancel_quote_and_expired_file_or_quote_do_not_create_sale(self):
        from datetime import timedelta
        from django.utils import timezone
        issue = self.issue()
        self.cd.wholesale_price = 200
        self.cd.save(update_fields=['wholesale_price'])
        intent = self.submit(self.order_file(issue))
        services.confirm(customer_id=self.customer.pk, intent_id=intent.pk, revision=intent.revision, cancel=True)
        self.assertFalse(Sale.objects.exists())
        issue.expires_at = timezone.now() - timedelta(seconds=1)
        issue.save(update_fields=['expires_at'])
        self.assertEqual(self.submit(self.order_file(issue), 2).state, 'invalid')

    def test_zip_and_sparse_cell_limits(self):
        from zipfile import ZipFile, ZIP_DEFLATED
        for name, payload in [('xl/a.xml', b'<!DOCTYPE foo><foo/>'), ('xl/vbaProject.bin', b'bad'),
                              ('xl/worksheets/sheet1.xml', b'<c r="A99999999"/>')]:
            stream = BytesIO()
            with ZipFile(stream, 'w', ZIP_DEFLATED) as archive:
                archive.writestr(name, payload)
            with self.subTest(name=name), self.assertRaises(ValidationError):
                documents.open_safe(stream.getvalue())

    def test_dashboard_and_configuration_are_read_only_and_csrf_protected(self):
        self.client.force_login(self.actor)
        with patch('wholesale_bot.client.WholesaleClient.call', side_effect=AssertionError('No network')):
            self.assertEqual(self.client.get(reverse('wholesale_bot:dashboard')).status_code, 200)
            self.assertEqual(self.client.get(reverse('wholesale_bot:configuration')).status_code, 200)
        from django.test import Client
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.actor)
        self.assertEqual(client.post(reverse('wholesale_bot:customer_action', args=[self.customer.pk]),
                                     {'action': 'revoke', 'revision': self.customer.revision}).status_code, 403)

    def test_worker_restart_processes_persisted_event_without_duplicate_sale(self):
        from threading import Event as Stop
        from .worker import run_polling
        # TestCase держит фикстуру в транзакции. Штатный цикл очистки соединений
        # проверяется отдельным процессом/TransactionTestCase, а не закрытием этой фикстуры.
        self.enterContext(patch('wholesale_bot.worker.close_old_connections'))
        self.enterContext(patch('wholesale_bot.worker.connections.close_all'))
        issue = self.issue()
        content = self.order_file(issue)
        update = {'update_id': 777, 'message': {'message_id': 99, 'chat': {'type': 'private', 'id': 123},
            'from': {'id': 123}, 'document': {'file_id': 'synthetic-file', 'file_name': 'order.xlsx', 'file_size': len(content)}}}
        client = Mock()
        replies = [[update], [], []]
        def call(method, *args, **kwargs):
            if method == 'getMe':
                return {'username': self.config.username}
            if method == 'getWebhookInfo':
                return {'url': ''}
            if method == 'getUpdates':
                return replies.pop(0)
            return {'message_id': 123}
        client.call.side_effect = call
        client.download.return_value = content
        with patch('wholesale_bot.worker.expected_status', return_value='required'),\
                patch('wholesale_bot.worker.read_token', return_value='not-a-real-token'):
            run_polling(Stop(), client_factory=lambda _: client, once=True)
            self.assertEqual(Event.objects.get().state, 'pending')
            self.assertFalse(Sale.objects.exists())
            run_polling(Stop(), client_factory=lambda _: client, once=True)
            self.assertEqual(Sale.objects.count(), 1)
            self.assertEqual(Event.objects.get().state, 'done')
            run_polling(Stop(), client_factory=lambda _: client, once=True)
            self.assertEqual(Sale.objects.count(), 1)
        self.config.refresh_from_db()
        self.assertEqual(self.config.next_update_id, 778)


class ConcurrentOrdersTests(TransactionTestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_superuser(username='parallel-opt')
        self.partner = Partner.objects.create(name='Parallel Partner')
        self.warehouse = Warehouse.objects.create(name='Parallel Warehouse')
        BotConfig.objects.create(operator=self.actor, warehouse=self.warehouse)
        self.cd = CD.objects.create(name='Last Game', sku='OPT-LAST', wholesale_price=150, cost=100,
                                    platform=Platform.objects.create(name='PS5'))
        self.stock = CDWarehouseStock.objects.create(cd=self.cd, warehouse=self.warehouse, quantity=1)
        self.customers = [Customer.objects.create(telegram_id=identity, status='authorized', partner=self.partner)
                          for identity in [123, 124]]
        self.contents = []
        for customer in self.customers:
            issue = documents.issue_price(customer.pk)
            wb = load_workbook(BytesIO(bytes(issue.content)))
            wb['Прайс'].cell(issue.manifest['products'][0]['row'], 4, 1)
            stream = BytesIO()
            wb.save(stream)
            wb.close()
            self.contents.append(stream.getvalue())

    def race(self, operation):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import connections
        barrier = Barrier(2)
        def run(index):
            try:
                barrier.wait(timeout=10)
                return operation(index)
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(run, [0, 1]))

    def test_last_item_is_used_by_only_one_sale(self):
        result = self.race(lambda index: services.receive_order(customer_id=self.customers[index].pk,
            message_id=1, content=self.contents[index]).state)
        self.assertCountEqual(result, ['created', 'shortage'])
        self.assertEqual(Sale.objects.count(), 1)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 0)

    def test_repeated_same_document_message_creates_one_sale(self):
        result = self.race(lambda _: services.receive_order(customer_id=self.customers[0].pk,
            message_id=1, content=self.contents[0]).pk)
        self.assertEqual(result[0], result[1])
        self.assertEqual(Sale.objects.count(), 1)
