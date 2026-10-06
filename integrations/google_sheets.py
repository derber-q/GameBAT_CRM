import calendar
import re
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from catalog.models import CD, Tech

from .models import GoogleSheetsIntegration


SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
SPREADSHEET_ID_RE = re.compile(r"/spreadsheets/d/([a-zA-Z0-9_-]+)")
CENT = Decimal("0.01")


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


def _included_products(model, related):
    now = timezone.now()
    cutoff = _calendar_month_before(now)
    products = list(
        model.objects.active().select_related(*related).annotate(
            global_quantity=Coalesce(Sum("warehouse_stocks__quantity"), 0),
        ).order_by(*(f"{field}__name" for field in related), "name", "id")
    )
    missing_markers = [product.pk for product in products if product.global_quantity == 0 and not product.zero_stock_since]
    if missing_markers:
        model.objects.filter(pk__in=missing_markers, zero_stock_since__isnull=True).update(zero_stock_since=now)
        for product in products:
            if product.pk in missing_markers:
                product.zero_stock_since = now
    return [
        product for product in products
        if product.global_quantity > 0 or (product.zero_stock_since and product.zero_stock_since >= cutoff)
    ]


def build_price_rows():
    """Строит полное содержимое управляемого листа и номера строк недавнего нуля."""
    rows = [["Наименование", "Себестоимость", "Количество", "Оптовая цена"]]
    heading_rows = {1}
    zero_rows = []

    rows.append(["Техника", "", "", ""])
    heading_rows.add(len(rows))
    tech = _included_products(Tech, ("brand", "product_type"))
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

    rows.append(["Диски", "", "", ""])
    heading_rows.add(len(rows))
    cds = _included_products(CD, ("platform",))
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


def sync_price_sheet(integration=None):
    integration = integration or get_google_sheets_integration()
    integration.status = GoogleSheetsIntegration.Status.SYNCING
    integration.last_attempt_at = timezone.now()
    integration.last_error = ""
    integration.save(update_fields=("status", "last_attempt_at", "last_error", "updated_at"))
    try:
        service = _google_service()
        spreadsheet = service.spreadsheets().get(
            spreadsheetId=integration.spreadsheet_id, fields="sheets.properties",
        ).execute()
        sheet = next(
            (item for item in spreadsheet.get("sheets", [])
             if item["properties"]["title"] == integration.sheet_name), None,
        )
        if sheet is None:
            result = service.spreadsheets().batchUpdate(
                spreadsheetId=integration.spreadsheet_id,
                body={"requests": [{"addSheet": {"properties": {"title": integration.sheet_name}}}]},
            ).execute()
            sheet_id = result["replies"][0]["addSheet"]["properties"]["sheetId"]
        else:
            sheet_id = sheet["properties"]["sheetId"]
        rows, heading_rows, zero_rows = build_price_rows()
        escaped_name = integration.sheet_name.replace("'", "''")
        managed_range = f"'{escaped_name}'!A:D"
        service.spreadsheets().values().clear(
            spreadsheetId=integration.spreadsheet_id, range=managed_range, body={},
        ).execute()
        service.spreadsheets().values().update(
            spreadsheetId=integration.spreadsheet_id, range=f"'{escaped_name}'!A1",
            valueInputOption="USER_ENTERED", body={"values": rows},
        ).execute()
        requests = [
            {"repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": len(rows),
                          "startColumnIndex": 0, "endColumnIndex": 4},
                "cell": {"userEnteredFormat": {"backgroundColor": {"red": 1, "green": 1, "blue": 1},
                                                 "textFormat": {"bold": False},
                                                 "horizontalAlignment": "LEFT"}},
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
        for row_number in sorted(heading_rows):
            requests.append({"repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": row_number - 1, "endRowIndex": row_number,
                          "startColumnIndex": 0, "endColumnIndex": 4},
                "cell": {"userEnteredFormat": {"textFormat": {"bold": True},
                                                 "backgroundColor": {"red": .86, "green": .92, "blue": .98}}},
                "fields": "userEnteredFormat(textFormat,backgroundColor)",
            }})
        for row_number in zero_rows:
            requests.append({"repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": row_number - 1, "endRowIndex": row_number,
                          "startColumnIndex": 0, "endColumnIndex": 4},
                "cell": {"userEnteredFormat": {"backgroundColor": {"red": 1, "green": .88, "blue": .88},
                                                 "textFormat": {"foregroundColor": {"red": .55, "green": .2, "blue": .2}}}},
                "fields": "userEnteredFormat(backgroundColor,textFormat.foregroundColor)",
            }})
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
    return len(rows)
