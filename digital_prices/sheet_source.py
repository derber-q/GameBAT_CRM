"""Чтение выбранной Google-таблицы тарифов; ни записи в Sheets, ни сети в учёте."""
import re
from urllib.parse import urlsplit
from decimal import Decimal
import requests
from dataclasses import dataclass
from django.conf import settings
from core.external_policy import require_live_operation

READONLY_SCOPE = 'https://www.googleapis.com/auth/spreadsheets.readonly'
SOURCE_TAB = 'Прайс'
HEADINGS = {'игры турция':('game_tariff','tr','coefficient'),
    'игры снг':('game_tariff','sng','coefficient'), 'игры индия':('game_tariff','in','rub'),
    'игры польша':('game_tariff','pl','rub'), 'игры индонезия':('game_tariff','id','rub'),
    'игры сша':('game_tariff','us','rub'), 'пополнение steam':('steam_tariff','','percent')}


@dataclass(frozen=True)
class SheetCost:
    kind: str
    region: str
    label: str
    mode: str
    cost: Decimal | None
    reference: str


class SheetSourceError(Exception):
    def __init__(self, category):
        self.category = category
        super().__init__(category)  # Ключи, URL запросов и содержимое ответов не журналируются.


def normalized_label(label):
    value = str(label).casefold().strip().replace('–','-').replace('—','-').replace('−','-')
    value = re.sub(r'руб(?:лей|ля|ль)?\.?|₽|\s+', '', value)
    nominal = re.fullmatch(r'(\d+(?:[.,]\d+)?)([kmкм])', value)
    if nominal:
        factor = Decimal(1000 if nominal[2] in ('k','к') else 1000000)
        value = format(Decimal(nominal[1].replace(',','.'))*factor,'.0f')
    return value


def _number(raw, mode):
    text = re.sub(r'руб(?:лей|ля|ль)?\.?|₽|\s+', '', str(raw).casefold())
    if not text:
        return None
    if mode == 'percent':
        if not text.endswith('%'):
            raise SheetSourceError('sheet_price_format')
        text = text[:-1]
    precision = 4 if mode == 'coefficient' else 2
    if not re.fullmatch(r'\d+(?:[.,]\d{1,'+str(precision)+r'})?', text):
        raise SheetSourceError('sheet_price_format')
    result = Decimal(text.replace(',','.'))
    maximum = Decimal('1000000') if mode == 'percent' else Decimal('1e16') if mode == 'coefficient' else Decimal('1e18')
    if result >= maximum:
        raise SheetSourceError('sheet_price_format')
    # В рублёвом прайсе поставщика ноль означает отсутствие расчёта, не бесплатную выдачу.
    return None if result == 0 and mode != 'percent' else result


def parse_costs(values):
    from .classification import clean_caption
    if not isinstance(values,list) or len(values)>400 or any(not isinstance(row,list) or len(row)>24 for row in values):
        raise SheetSourceError('sheet_structure')
    headings = {}
    for y,row in enumerate(values):
        for x,cell in enumerate(row):
            key = clean_caption(cell).casefold()
            if key in HEADINGS:
                if key in headings or x >= 23:
                    raise SheetSourceError('sheet_structure')
                headings[key]=(y,x)
    if set(headings)!=set(HEADINGS):
        raise SheetSourceError('sheet_structure')
    costs = {}
    for name,(y,x) in headings.items():
        kind,region,mode = HEADINGS[name]
        for n in range(y+1,len(values)):
            row=values[n]
            label=str(row[x]) if len(row)>x else ''
            if not label.strip():
                break
            normal=normalized_label(label)
            if clean_caption(label).casefold() in ('тип','сумма'):
                continue
            if not re.fullmatch(r'(?:до|от)?\d+(?:[.,]\d+)?(?:-\d+|\+)?', normal):
                raise SheetSourceError('sheet_structure')
            key=(kind,region,normal)
            if key in costs:
                raise SheetSourceError('sheet_structure')
            raw=row[x+1] if len(row)>x+1 else ''
            reference=f'{SOURCE_TAB}!{chr(65+x+1)}{n+1}'
            costs[key]=SheetCost(kind,region,normal,mode,_number(raw,mode),reference)
    if not costs:
        raise SheetSourceError('sheet_empty')
    return costs


def spreadsheet_id(url):
    parsed = urlsplit(str(url or '').strip())
    match = re.fullmatch(r'/spreadsheets/d/([A-Za-z0-9_-]{10,128})(?:/[^?#]*)?', parsed.path)
    if parsed.scheme != 'https' or parsed.netloc != 'docs.google.com' or not match:
        raise SheetSourceError('sheet_url')
    return match[1]


class SheetClient:
    """Транспорт имеет только GET к фиксированному Google API и readonly scope."""
    def __init__(self, url, *, session=None):
        require_live_operation('digital_prices_google_read')
        self.identity = spreadsheet_id(url)
        if session is None:
            from google.oauth2 import service_account
            from google.auth.transport.requests import AuthorizedSession
            try:
                credentials = service_account.Credentials.from_service_account_file(
                    settings.GOOGLE_SERVICE_ACCOUNT_FILE, scopes=[READONLY_SCOPE])
                session = AuthorizedSession(credentials, refresh_timeout=15)
            except Exception:
                raise SheetSourceError('sheet_credentials') from None
        self.session = session

    def _get(self, suffix, params):
        require_live_operation('digital_prices_google_read')
        from google.auth.exceptions import GoogleAuthError
        try:
            response = self.session.get('https://sheets.googleapis.com/v4/spreadsheets/' + self.identity + suffix,
                params=params, timeout=(5, 25), allow_redirects=False)
        except (requests.RequestException, GoogleAuthError):
            raise SheetSourceError('sheet_network') from None
        try:
            if response.status_code in (401, 403):
                raise SheetSourceError('sheet_access')
            if response.status_code == 429:
                raise SheetSourceError('sheet_rate_limited')
            if response.status_code >= 500:
                raise SheetSourceError('sheet_unavailable')
            if response.status_code != 200 or len(response.content) > 4*1024*1024:
                raise SheetSourceError('sheet_response')
            try:
                result = response.json(parse_float=Decimal)
            except (TypeError, ValueError):
                raise SheetSourceError('sheet_response') from None
            if not isinstance(result, dict):
                raise SheetSourceError('sheet_response')
            return result
        finally:
            response.close()

    def metadata(self):
        data = self._get('', {'fields': 'spreadsheetId,properties(title,locale),sheets(properties(sheetId,title,hidden,gridProperties))'})
        if data.get('spreadsheetId') != self.identity or not isinstance(data.get('sheets'), list):
            raise SheetSourceError('sheet_response')
        return data

    def read_ranges(self, ranges):
        """Диапазоны передаются только после разбора проверенных метаданных листа."""
        if not ranges or len(ranges) > 20 or any(not isinstance(value, str) or len(value) > 350 for value in ranges):
            raise SheetSourceError('sheet_ranges')
        return self._get('/values:batchGet', {'ranges': ranges, 'majorDimension': 'ROWS',
                         'valueRenderOption': 'FORMATTED_VALUE'})

    def fetch_costs(self):
        metadata=self.metadata()
        tabs=[sheet.get('properties',{}) for sheet in metadata['sheets']
              if sheet.get('properties',{}).get('title')==SOURCE_TAB and not sheet.get('properties',{}).get('hidden')]
        if len(tabs)!=1:
            raise SheetSourceError('sheet_structure')
        grid=tabs[0].get('gridProperties',{})
        rows=grid.get('rowCount',0)
        if type(rows) is not int or rows<40 or grid.get('columnCount',0)<24:
            raise SheetSourceError('sheet_structure')
        data=self.read_ranges([f"'{SOURCE_TAB}'!A1:X{min(rows,400)}"])
        ranges=data.get('valueRanges')
        if not isinstance(ranges,list) or len(ranges)!=1 or not isinstance(ranges[0],dict):
            raise SheetSourceError('sheet_response')
        return parse_costs(ranges[0].get('values',[]))

    def close(self):
        self.session.close()
