import calendar
import re
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import OuterRef, Subquery, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from catalog.models import CD, ProductFieldChange, Tech

from .models import GoogleSheetsIntegration


SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
SPREADSHEET_ID_RE = re.compile(r"/spreadsheets/d/([a-zA-Z0-9_-]+)")
CENT = Decimal("0.01")
NOMENCLATURE_SHEET_NAME = "Номенклатура"


def extract_spreadsheet_id(url):
    match = SPREADSHEET_ID_RE.search(str(url or "").strip())
    if not match:
        raise ValidationError("Укажите корректную ссылку на Google Sheets.")
    return match.group(1)


def get_google_sheets_integration():
    spreadsheet_url = settings.GOOGLE_SHEETS_DEFAULT_URL
    credentials_configured = bool(str(settings.GOOGLE_SERVICE_ACCOUNT_FILE or "").strip())
    integration, _ = GoogleSheetsIntegration.objects.get_or_create(
        pk=1,
        defaults={
            "spreadsheet_url": spreadsheet_url,
            "spreadsheet_id": extract_spreadsheet_id(spreadsheet_url),
            "sheet_name": settings.GOOGLE_SHEETS_DEFAULT_TAB,
            "enabled": credentials_configured,
            "status": (
                GoogleSheetsIntegration.Status.IDLE
                if credentials_configured else GoogleSheetsIntegration.Status.NOT_CONFIGURED
            ),
        },
    )
    return integration


def save_google_sheets_settings(*, spreadsheet_url, sheet_name, enabled):
    integration = get_google_sheets_integration()
    integration.spreadsheet_url = str(spreadsheet_url or "").strip()
    integration.spreadsheet_id = extract_spreadsheet_id(integration.spreadsheet_url)
    integration.sheet_name = str(sheet_name or "").strip()
    if not integration.sheet_name:
        raise ValidationError("Укажите название листа Google Sheets.")
    if integration.sheet_name.casefold() == NOMENCLATURE_SHEET_NAME.casefold():
        raise ValidationError("Лист наличия должен отличаться от листа «Номенклатура».")
    integration.enabled = bool(enabled)
    integration.status = GoogleSheetsIntegration.Status.IDLE
    integration.last_error = ""
    integration.full_clean()
    integration.save()
    return integration


def _calendar_month_before(value):
    year, month = value.year, value.month - 1
    if month == 0:
        year, month = year - 1, 12
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def _sheet_money(value):
    """Передаёт денежное значение числом через точную формулу, без преобразования Decimal во float."""
    amount = Decimal(value).quantize(CENT)
    return f"={int(amount * 100)}/100"


def _all_products(model, related):
    # Дата создания уже хранится в аудите CRM и Django Admin. Подзапрос
    # не размножает складские строки при суммировании физического остатка.
    created = ProductFieldChange.objects.filter(
        field_name="created", **{f"event__{model._meta.model_name}_id": OuterRef("pk")},
    ).order_by("event__created_at", "pk").values("event__created_at")[:1]
    return list(
        model.objects.active().select_related(*related).annotate(
            global_quantity=Coalesce(Sum("warehouse_stocks__quantity"), 0),
            catalog_created_at=Subquery(created),
        ).order_by(*(f"{field}__name" for field in related), "name", "id")
    )


def _available_product(product, cutoff):
    if product.global_quantity > 0:
        return True
    # Дата нуля могла быть проставлена миграцией даже никогда не поступавшему товару.
    # Нужен подтверждённый положительный остаток в прошлом, а не только эта дата.
    return bool(
        product.global_quantity == 0 and product.has_been_in_stock
        and product.zero_stock_since and product.zero_stock_since > cutoff
        and (product.catalog_created_at is None or product.catalog_created_at <= cutoff)
    )


def build_price_rows(*, nomenclature=False, tech=None, cds=None, now=None):
    """Строит номенклатуру или наличие; заголовки добавляются только к выбранным товарам."""
    cutoff = _calendar_month_before(now or timezone.now())
    tech = _all_products(Tech, ("brand", "product_type")) if tech is None else tech
    cds = _all_products(CD, ("platform",)) if cds is None else cds
    if not nomenclature:
        tech = [product for product in tech if _available_product(product, cutoff)]
        cds = [product for product in cds if _available_product(product, cutoff)]
    rows = [["Наименование", "Себестоимость", "Количество", "Оптовая цена"]]
    heading_rows = {1}
    zero_rows = []

    if tech:
        rows.append(["Техника", "", "", ""])
        heading_rows.add(len(rows))
    last_brand = last_type = None
    for product in tech:
        if product.brand_id != last_brand:
            rows.append([product.brand.name, "", "", ""])
            heading_rows.add(len(rows))
            last_brand, last_type = product.brand_id, None
        if product.product_type_id != last_type:
            rows.append([f"  {product.product_type.name}", "", "", ""])
            heading_rows.add(len(rows))
            last_type = product.product_type_id
        rows.append([
            f"    {product.name}", _sheet_money(product.cost), int(product.global_quantity),
            _sheet_money(product.wholesale_price) if product.wholesale_price is not None else "",
        ])
        if product.global_quantity == 0:
            zero_rows.append(len(rows))

    if cds:
        rows.append(["Диски", "", "", ""])
        heading_rows.add(len(rows))
    last_platform = None
    for product in cds:
        if product.platform_id != last_platform:
            rows.append([product.platform.name, "", "", ""])
            heading_rows.add(len(rows))
            last_platform = product.platform_id
        rows.append([
            f"  {product.name}", _sheet_money(product.cost), int(product.global_quantity),
            _sheet_money(product.wholesale_price) if product.wholesale_price is not None else "",
        ])
        if product.global_quantity == 0:
            zero_rows.append(len(rows))
    return rows, heading_rows, zero_rows


def _google_service():
    key_file = str(settings.GOOGLE_SERVICE_ACCOUNT_FILE or "").strip()
    if not key_file:
        raise RuntimeError("Не задан GOOGLE_SERVICE_ACCOUNT_FILE.")
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    credentials = service_account.Credentials.from_service_account_file(key_file, scopes=[SHEETS_SCOPE])
    return build("sheets", "v4", credentials=credentials, cache_discovery=False)


def _row_ranges(row_numbers):
    """Объединяет соседние строки, чтобы не отправлять тысячи отдельных запросов оформления."""
    start = previous = None
    for number in sorted(row_numbers):
        if previous is not None and number != previous + 1:
            yield {"startRowIndex": start - 1, "endRowIndex": previous}
            start = None
        if start is None:
            start = number
        previous = number
    if start is not None:
        yield {"startRowIndex": start - 1, "endRowIndex": previous}


def _sheet_format_requests(sheet_id, rows, heading_rows, zero_rows, basic_filter):
    requests = [
        {"repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": 0,
                      "startColumnIndex": 0, "endColumnIndex": 4},
            "cell": {"userEnteredFormat": {"backgroundColor": {"red": 1, "green": 1, "blue": 1},
                                             "textFormat": {"bold": False},
                                             "horizontalAlignment": "LEFT",
                                             "verticalAlignment": "MIDDLE",
                                             "wrapStrategy": "WRAP"}},
            "fields": "userEnteredFormat",
        }},
        {"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1},
            "properties": {"pixelSize": 420}, "fields": "pixelSize",
        }},
        {"autoResizeDimensions": {
            "dimensions": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 1, "endIndex": 4},
        }},
        {"updateSheetProperties": {
            "properties": {"sheetId": sheet_id, "gridProperties": {"frozenRowCount": 1}},
            "fields": "gridProperties.frozenRowCount",
        }},
    ]
    # Расширяем существующий фильтр, сохраняя выбранные пользователем критерии.
    # Отбор наличия выполняется в CRM и не требует фильтра, скрывающего нули.
    if basic_filter:
        filter_range = basic_filter["range"]
        if (
            filter_range.get("startRowIndex", 0) == 0
            and filter_range.get("startColumnIndex", 0) == 0
            and filter_range.get("endColumnIndex") == 4
        ):
            expanded_filter = dict(basic_filter)
            expanded_filter["range"] = dict(filter_range)
            expanded_filter["range"].pop("endRowIndex", None)
            if "filterSpecs" in expanded_filter:
                expanded_filter.pop("criteria", None)
            requests.append({"setBasicFilter": {"filter": expanded_filter}})
    for row_range in _row_ranges(heading_rows):
        requests.append({"repeatCell": {
            "range": {"sheetId": sheet_id, **row_range, "startColumnIndex": 0, "endColumnIndex": 4},
            "cell": {"userEnteredFormat": {"textFormat": {"bold": True},
                                             "backgroundColor": {"red": .86, "green": .92, "blue": .98}}},
            "fields": "userEnteredFormat(textFormat,backgroundColor)",
        }})
    for row_range in _row_ranges(zero_rows):
        requests.append({"repeatCell": {
            "range": {"sheetId": sheet_id, **row_range, "startColumnIndex": 0, "endColumnIndex": 4},
            "cell": {"userEnteredFormat": {"backgroundColor": {"red": 1, "green": .88, "blue": .88},
                                             "textFormat": {"foregroundColor": {"red": .55, "green": .2, "blue": .2}}}},
            "fields": "userEnteredFormat(backgroundColor,textFormat.foregroundColor)",
        }})
    requests.append({"autoResizeDimensions": {
        "dimensions": {"sheetId": sheet_id, "dimension": "ROWS", "startIndex": 0, "endIndex": len(rows)},
    }})
    return requests


def _sheet_range(name):
    escaped_name = name.replace("'", "''")
    return f"'{escaped_name}'!A:D"


def sync_price_sheet(integration=None):
    integration = integration or get_google_sheets_integration()
    integration.status = GoogleSheetsIntegration.Status.SYNCING
    integration.last_attempt_at = timezone.now()
    integration.last_error = ""
    integration.save(update_fields=("status", "last_attempt_at", "last_error", "updated_at"))
    try:
        if integration.sheet_name.casefold() == NOMENCLATURE_SHEET_NAME.casefold():
            raise ValidationError("Лист наличия должен отличаться от листа «Номенклатура».")
        now = timezone.now()
        tech = _all_products(Tech, ("brand", "product_type"))
        cds = _all_products(CD, ("platform",))
        exports = {
            NOMENCLATURE_SHEET_NAME: build_price_rows(nomenclature=True, tech=tech, cds=cds, now=now),
            integration.sheet_name: build_price_rows(tech=tech, cds=cds, now=now),
        }
        service = _google_service()
        spreadsheet = service.spreadsheets().get(
            spreadsheetId=integration.spreadsheet_id, fields="sheets(properties,basicFilter)",
        ).execute()
        sheets = {item["properties"]["title"]: item for item in spreadsheet.get("sheets", [])}
        prepare_requests = []
        for name, (rows, _, _) in exports.items():
            if name not in sheets:
                prepare_requests.append({"addSheet": {"properties": {
                    "title": name, "gridProperties": {"rowCount": max(1000, len(rows)), "columnCount": 4},
                }}})
            else:
                properties = sheets[name]["properties"]
                grid = properties["gridProperties"]
                if grid["rowCount"] < len(rows) or grid["columnCount"] < 4:
                    prepare_requests.append({"updateSheetProperties": {
                        "properties": {"sheetId": properties["sheetId"], "gridProperties": {
                            "rowCount": max(grid["rowCount"], len(rows)),
                            "columnCount": max(grid["columnCount"], 4),
                        }}, "fields": "gridProperties(rowCount,columnCount)",
                    }})
        if prepare_requests:
            prepared = service.spreadsheets().batchUpdate(
                spreadsheetId=integration.spreadsheet_id, body={"requests": prepare_requests},
            ).execute()
            for reply in prepared.get("replies", []):
                if "addSheet" in reply:
                    sheet = reply["addSheet"]
                    sheets[sheet["properties"]["title"]] = sheet
        ranges = {name: _sheet_range(name) for name in exports}
        service.spreadsheets().values().batchClear(
            spreadsheetId=integration.spreadsheet_id, body={"ranges": list(ranges.values())},
        ).execute()
        service.spreadsheets().values().batchUpdate(
            spreadsheetId=integration.spreadsheet_id, body={
                "valueInputOption": "USER_ENTERED",
                "data": [{"range": ranges[name], "values": data[0]} for name, data in exports.items()],
            },
        ).execute()
        # Читаем критерии после записи, чтобы сохранить последние настройки в таблице.
        filter_state = service.spreadsheets().get(
            spreadsheetId=integration.spreadsheet_id, fields="sheets(properties.sheetId,basicFilter)",
        ).execute()
        filters = {item["properties"]["sheetId"]: item.get("basicFilter")
                   for item in filter_state.get("sheets", [])}
        requests = []
        for name, (rows, heading_rows, zero_rows) in exports.items():
            sheet_id = sheets[name]["properties"]["sheetId"]
            requests.extend(_sheet_format_requests(sheet_id, rows, heading_rows, zero_rows, filters.get(sheet_id)))
        service.spreadsheets().batchUpdate(
            spreadsheetId=integration.spreadsheet_id, body={"requests": requests},
        ).execute()
    except Exception as exc:
        integration.status = GoogleSheetsIntegration.Status.ERROR
        integration.last_error = str(exc)[:2000]
        integration.save(update_fields=("status", "last_error", "updated_at"))
        raise
    integration.status = GoogleSheetsIntegration.Status.OK
    integration.last_success_at = timezone.now()
    integration.last_error = ""
    integration.save(update_fields=("status", "last_success_at", "last_error", "updated_at"))
    return len(exports[integration.sheet_name][0])
