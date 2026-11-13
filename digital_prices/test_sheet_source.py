"""Будущие проверки Sheets используют фиктивный транспорт, не рабочую таблицу."""
from decimal import Decimal
from unittest.mock import Mock, patch
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, override_settings
from .sheet_source import SheetClient, SheetSourceError, spreadsheet_id, parse_costs, normalized_label, HEADINGS

IDENTITY = 'synthetic_sheet_123456789'
URL = 'https://docs.google.com/spreadsheets/d/' + IDENTITY


class SheetTransportTests(SimpleTestCase):
    def test_manual_blocks_parse_decimal_comma_percentage_and_zero_without_touching_api_cards(self):
        rows=[[] for _ in range(5)]
        for column,(heading,(_,region,mode)) in enumerate(HEADINGS.items()):
            x=column*3
            for row in rows:
                row.extend(['']*max(0,x+2-len(row)))
            rows[0][x]=heading
            rows[1][x]='СУММА' if mode=='percent' else 'ТИП'
            rows[2][x]='До 99 руб' if mode=='percent' else '1-99' if mode=='coefficient' else '100000'
            rows[2][x+1]='7%' if mode=='percent' else '2,960' if mode=='coefficient' else '1460 руб'
        data=parse_costs(rows)
        self.assertEqual(data[('game_tariff','tr','1-99')].cost,Decimal('2.960'))
        self.assertEqual(data[('steam_tariff','','до99')].cost,Decimal(7))
        self.assertEqual(normalized_label('1.5M'),'1500000')
        self.assertEqual(normalized_label('100–499 ₽'),'100-499')
        # Ноль не становится бесплатной игрой.
        index=list(HEADINGS).index('игры индонезия')*3
        rows[2][index+1]='0 руб'
        self.assertIsNone(parse_costs(rows)[('game_tariff','id','100000')].cost)
        rows[2][index+1]='#REF!'
        with self.assertRaises(SheetSourceError):
            parse_costs(rows)

    def test_spreadsheet_url_cannot_change_transport_host(self):
        self.assertEqual(spreadsheet_id(URL+'/edit#gid=123'), IDENTITY)
        for url in ('http://docs.google.com/spreadsheets/d/'+IDENTITY,
                    'https://evil.invalid/spreadsheets/d/'+IDENTITY,
                    'https://docs.google.com@evil.invalid/spreadsheets/d/'+IDENTITY,
                    'https://docs.google.com:443/spreadsheets/d/'+IDENTITY,
                    'https://docs.google.com/document/d/'+IDENTITY):
            with self.assertRaises(SheetSourceError):
                spreadsheet_id(url)

    def test_metadata_and_ranges_use_only_get_and_bounded_timeout(self):
        session = Mock()
        response = Mock(status_code=200, content=b'{}')
        response.json.return_value = {'spreadsheetId':IDENTITY,'sheets':[{'properties':{'title':'Тарифы'}}]}
        session.get.return_value = response
        with patch('digital_prices.sheet_source.require_live_operation'):
            client = SheetClient(URL, session=session)
            self.assertEqual(client.metadata()['spreadsheetId'], IDENTITY)
            client.read_ranges(["'Тарифы'!A1:D30"])
        self.assertEqual(session.get.call_count, 2)
        self.assertFalse(session.get.call_args.kwargs['allow_redirects'])
        self.assertEqual(session.get.call_args.kwargs['params']['valueRenderOption'], 'FORMATTED_VALUE')
        self.assertEqual(session.get.call_args.kwargs['timeout'], (5,25))
        response.json.assert_called_with(parse_float=Decimal)
        session.post.assert_not_called()

    def test_access_error_is_sanitized_and_previous_snapshot_is_not_touched(self):
        response = Mock(status_code=403,content=b'not-public')
        session = Mock();session.get.return_value=response
        with patch('digital_prices.sheet_source.require_live_operation'):
            client=SheetClient(URL,session=session)
            with self.assertRaises(SheetSourceError) as caught:
                client.metadata()
        self.assertEqual(caught.exception.category,'sheet_access')
        self.assertNotIn('not-public',str(caught.exception))
        response.close.assert_called_once()

    @override_settings(GAMEBAT_ENV='local_test')
    def test_real_google_transport_is_blocked_in_local_test(self):
        session=Mock()
        with self.assertRaises(ValidationError):
            SheetClient(URL,session=session)
        session.get.assert_not_called()
