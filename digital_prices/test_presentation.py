"""Оформление пересылаемого прайса без Telegram и рабочей БД."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

from django.test import SimpleTestCase

from telegram_bots.client import TelegramClient
from .presentation import page_caption, page_title


class PresentationTests(SimpleTestCase):
    def bundle(self, **changes):
        values = dict(buyer_name_snapshot='Магазин покупателя', source_at=datetime(2026, 11, 13, 9, 15, tzinfo=timezone.utc),
                      public_snapshot={'page_titles': ['Главная', 'PlayStation — Коды пополнения'],
                                       'rows': [{'section': 'services', 'family': 'PlayStation'},
                                                {'section': 'codes', 'family': 'PlayStation'}]})
        return SimpleNamespace(**(values | changes))

    def page(self, index=1, filename='GameBAT_services_20261113_01.png'):
        return SimpleNamespace(index=index, filename=filename)

    def test_first_caption_has_buyer_types_real_source_time_and_contact(self):
        text = page_caption(self.bundle(), self.page(), 2)
        for value in ('Магазин покупателя', '1/2 · Главная', 'Подписки PlayStation',
                      'PlayStation — коды пополнения', '13.11.2026 в 12:15 (МСК)', '@GameBAT_Store'):
            self.assertIn(value, text)
        self.assertNotIn('себестоимость', text.casefold())

    def test_every_later_page_has_own_title_buyer_date_and_contact(self):
        text = page_caption(self.bundle(), self.page(2), 2)
        self.assertIn('2/2 · PlayStation — Коды пополнения', text)
        self.assertIn('Для: Магазин покупателя', text)
        self.assertIn('@GameBAT_Store', text)
        self.assertNotIn('В прайсе:', text)

    def test_new_bundle_iso_source_time_matches_loaded_bundle(self):
        self.assertEqual(page_caption(self.bundle(source_at='2026-11-13T09:15:00+00:00'), self.page(), 2),
                         page_caption(self.bundle(), self.page(), 2))

    def test_new_account_note_is_specific_to_buyer_and_on_every_page(self):
        for name, fee in (('Подписки GNS', 150), ('GNS', 150), ('Подписки Играть', 100), ('Играть', 100)):
            for index in (1, 2):
                self.assertIn(f'🆕 Оформление на новый аккаунт: +{fee} ₽',
                              page_caption(self.bundle(buyer_name_snapshot=name), self.page(index), 2))
        self.assertNotIn('новый аккаунт', page_caption(self.bundle(), self.page(), 2))

    def test_old_bundle_uses_filename_without_repricing(self):
        bundle = self.bundle(public_snapshot={})
        self.assertEqual(page_title(bundle, self.page(3, 'GameBAT_codes_steam_topup_20261112_02.png')),
                         'Steam — коды пополнения')

    def test_unknown_and_stale_source_is_not_replaced_with_current_date(self):
        text = page_caption(self.bundle(source_at=None, public_snapshot={'stale': True}), self.page(), 1)
        self.assertIn('дата обновления не подтверждена', text)
        self.assertIn('Актуальность цен', text)

    def test_maximum_caption_fits_telegram_even_with_long_categories(self):
        bundle = self.bundle(buyer_name_snapshot='😀' * 160,
            public_snapshot={'stale': True, 'page_titles': ['😀' * 200],
                'rows': [{'section': 'codes', 'family': '😀' * 300}]})
        self.assertLessEqual(len(page_caption(bundle, self.page(), 100).encode('utf-16-le')) // 2, 1024)

    def test_photo_and_document_transport_accept_optional_caption(self):
        client = object.__new__(TelegramClient)
        client.call = Mock(return_value={'message_id': 1})
        for sender, method in ((client.photo, 'sendPhoto'), (client.image_document, 'sendDocument')):
            sender(77, 'price.png', b'\x89PNG\r\n\x1a\n', caption='Прайс покупателя')
            self.assertEqual(client.call.call_args.args, (method, {'chat_id': 77, 'caption': 'Прайс покупателя'}))
        client.photo(77, 'price.png', b'\x89PNG\r\n\x1a\n')
        self.assertEqual(client.call.call_args.args[1], {'chat_id': 77})
