import logging
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from openpyxl import Workbook, load_workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Alignment, Border, Font, PatternFill, Protection, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from catalog.models import CD, Tech
from partners.models import Supplier
from pricing.models import SupplierCDPrice, SupplierTechPrice
from warehouse.models import CDWarehouseStock, TechWarehouseStock, Warehouse

from .models import PriceDocumentSettings, ProcurementPriceList

logger = logging.getLogger("gamebat.business")
TEMPLATE_VERSION = "1"
MAIN_SHEET = "Прайс"
META_SHEET = "_resource_meta"
HEADER_ROW = 8
BLUE = "334660"
TEAL = "2C879B"
LIGHT = "EAF3F5"
WHITE = "FFFFFF"
GRAY = "DCE5E7"
MONEY_FORMAT = '#,##0.00 "₽"'
AED_FORMAT = '#,##0.000000 "AED"'


def safe_text(value):
    result = ILLEGAL_CHARACTERS_RE.sub("", str(value or ""))
    if result.startswith(("=", "+", "-", "@")):
        result = "'" + result
    return result


def _base_workbook(*, title, subtitle, columns, settings=None):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = MAIN_SHEET
    settings = settings or PriceDocumentSettings.get_solo()
    last_column = get_column_letter(columns)
    sheet.merge_cells(f"A1:{last_column}1")
    sheet["A1"] = safe_text(settings.company_name)
    sheet["A1"].font = Font(size=20, bold=True, color=WHITE)
    sheet["A1"].fill = PatternFill("solid", fgColor=BLUE)
    sheet["A1"].alignment = Alignment(vertical="center")
    if settings.logo:
        try:
            from openpyxl.drawing.image import Image as ExcelImage

            logo = ExcelImage(settings.logo.path)
            original_height = max(logo.height, 1)
            logo.height = 28
            logo.width = min(100, int(logo.width * 28 / original_height))
            sheet.add_image(logo, f"{last_column}1")
        except (FileNotFoundError, OSError, ValueError):
            pass
    sheet.row_dimensions[1].height = 34
    sheet.merge_cells(f"A2:{last_column}2")
    sheet["A2"] = safe_text(title)
    sheet["A2"].font = Font(size=15, bold=True, color=TEAL)
    sheet.merge_cells(f"A3:{last_column}3")
    sheet["A3"] = safe_text(subtitle)
    contacts = " · ".join(filter(None, [
        settings.address, settings.phone_1, settings.phone_2,
        settings.email, settings.website, settings.telegram,
    ]))
    sheet.merge_cells(f"A4:{last_column}4")
    sheet["A4"] = safe_text(contacts)
    sheet["A4"].font = Font(color="7B8999")
    sheet.merge_cells(f"A5:{last_column}5")
    sheet["A5"] = safe_text(settings.additional_text)
    sheet["A5"].alignment = Alignment(wrap_text=True)
    sheet.merge_cells(f"A6:{last_column}6")
    sheet["A6"] = f"Дата формирования: {timezone.localtime().strftime('%d.%m.%Y %H:%M')}"
    sheet["A6"].font = Font(size=10, color="7B8999")
    sheet.freeze_panes = f"A{HEADER_ROW + 1}"
    sheet.auto_filter.ref = f"A{HEADER_ROW}:{last_column}{HEADER_ROW}"
    return workbook, sheet


def _style_table(sheet, headers, *, editable_columns=(), editable_end_row=None):
    thin = Side(style="thin", color=GRAY)
    for column, header in enumerate(headers, 1):
        cell = sheet.cell(HEADER_ROW, column, header)
        cell.font = Font(bold=True, color=WHITE)
        cell.fill = PatternFill("solid", fgColor=TEAL)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = Border(bottom=thin)
    for column in range(1, len(headers) + 1):
        sheet.column_dimensions[get_column_letter(column)].width = 22
    sheet.column_dimensions["A"].width = 62
    for row in sheet.iter_rows(min_row=HEADER_ROW + 1):
        for cell in row:
            cell.border = Border(bottom=thin)
            is_editable = cell.column in editable_columns and (
                editable_end_row is None or cell.row <= editable_end_row
            )
            cell.protection = Protection(locked=not is_editable)
        if row and (row[0].row - HEADER_ROW) % 2 == 0:
            for cell in row:
                cell.fill = PatternFill("solid", fgColor="F8FAFB")
        for column in editable_columns:
            if editable_end_row is None or row[0].row <= editable_end_row:
                row[column - 1].fill = PatternFill("solid", fgColor=LIGHT)
    sheet.protection.sheet = True
    sheet.protection.autoFilter = False
    sheet.protection.sort = False


def _meta_sheet(workbook, *, document_type, values, rows=()):
    meta = workbook.create_sheet(META_SHEET)
    pairs = {"document_type": document_type, "template_version": TEMPLATE_VERSION, **values}
    for index, (key, value) in enumerate(pairs.items(), 1):
        meta.cell(index, 1, key)
        meta.cell(index, 2, str(value))
    start = len(pairs) + 2
    meta.cell(start, 1, "row_number")
    meta.cell(start, 2, "product_type")
    meta.cell(start, 3, "product_id")
    meta.cell(start, 4, "article")
    for offset, row in enumerate(rows, 1):
        for column, value in enumerate(row, 1):
            meta.cell(start + offset, column, value)
    meta.sheet_state = "veryHidden"
    meta.protection.sheet = True


def _bytes(workbook):
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def generate_retail_price_xlsx(*, warehouse_id, actor):
    try:
        warehouse = Warehouse.objects.get(pk=warehouse_id)
    except Warehouse.DoesNotExist as exc:
        raise ValidationError("Выберите существующий склад.") from exc
    stocks = list(CDWarehouseStock.objects.filter(warehouse=warehouse, quantity__gt=0).select_related("cd")) + list(
        TechWarehouseStock.objects.filter(warehouse=warehouse, quantity__gt=0).select_related("tech")
    )
    available = []
    skipped = 0
    for stock in stocks:
        product = getattr(stock, "cd", None) or stock.tech
        if product.retail_price is None:
            skipped += 1
        else:
            available.append((product.name, product.retail_price))
    available.sort(key=lambda row: row[0].casefold())
    workbook, sheet = _base_workbook(
        title="Розничный прайс", subtitle=f"Склад: {warehouse.name}", columns=2
    )
    if skipped:
        sheet["A7"] = f"Не включено товаров без розничной цены: {skipped}"
        sheet["A7"].font = Font(color="C94F55", italic=True)
    for index, (name, price) in enumerate(available, HEADER_ROW + 1):
        sheet.cell(index, 1, safe_text(name))
        sheet.cell(index, 2, price).number_format = MONEY_FORMAT
    _style_table(sheet, ("Товар", "Цена"))
    logger.info(
        "Розничный прайс сформирован: user_id=%s warehouse_id=%s rows=%s skipped=%s",
        actor.pk, warehouse.pk, len(available), skipped,
    )
    return _bytes(workbook), skipped


def generate_wholesale_price_xlsx(*, warehouse_id, actor):
    try:
        warehouse = Warehouse.objects.get(pk=warehouse_id)
    except Warehouse.DoesNotExist as exc:
        raise ValidationError("Выберите существующий склад.") from exc
    rows = []
    for kind, model, field in (
        ("cd", CDWarehouseStock, "cd"), ("tech", TechWarehouseStock, "tech")
    ):
        for stock in model.objects.filter(warehouse=warehouse, quantity__gt=0).select_related(field):
            product = getattr(stock, field)
            if product.wholesale_price is not None:
                rows.append((kind, product, stock.quantity))
    rows.sort(key=lambda row: row[1].name.casefold())
    workbook, sheet = _base_workbook(
        title="Оптовый прайс", subtitle=f"Склад: {warehouse.name}", columns=4
    )
    metadata = []
    for excel_row, (kind, product, quantity) in enumerate(rows, HEADER_ROW + 1):
        sheet.cell(excel_row, 1, safe_text(product.name))
        sheet.cell(excel_row, 2, product.wholesale_price).number_format = MONEY_FORMAT
        sheet.cell(excel_row, 3, quantity)
        sheet.cell(excel_row, 4, 0)
        metadata.append((excel_row, kind, product.pk, safe_text(product.sku)))
    end = max(HEADER_ROW + 1, HEADER_ROW + len(rows))
    totals = end + 2
    sheet.cell(totals, 3, "Выбрано позиций")
    sheet.cell(totals, 4, f'=COUNTIF(D{HEADER_ROW + 1}:D{end},">0")')
    sheet.cell(totals + 1, 3, "Заказано единиц")
    sheet.cell(totals + 1, 4, f"=SUM(D{HEADER_ROW + 1}:D{end})")
    sheet.cell(totals + 2, 3, "Итоговая стоимость")
    sheet.cell(totals + 2, 4, f"=SUMPRODUCT(B{HEADER_ROW + 1}:B{end},D{HEADER_ROW + 1}:D{end})")
    sheet.cell(totals + 2, 4).number_format = MONEY_FORMAT
    validation = DataValidation(type="whole", operator="greaterThanOrEqual", formula1="0", allow_blank=True)
    sheet.add_data_validation(validation)
    validation.add(f"D{HEADER_ROW + 1}:D{end}")
    _style_table(
        sheet,
        ("Товар", "Оптовая цена", "Доступно для заказа", "Количество к заказу"),
        editable_columns=(4,),
        editable_end_row=end,
    )
    _meta_sheet(workbook, document_type="resource_wholesale", values={
        "warehouse_id": warehouse.pk, "generated_at": timezone.now().isoformat(), "main_sheet": MAIN_SHEET,
    }, rows=metadata)
    logger.info(
        "Оптовый прайс сформирован: user_id=%s warehouse_id=%s rows=%s",
        actor.pk, warehouse.pk, len(rows),
    )
    return _bytes(workbook)


def generate_supplier_template(*, actor):
    workbook, sheet = _base_workbook(
        title="Шаблон цен поставщика", subtitle="Заполните только колонку «Цена AED»", columns=5
    )
    rows = [("cd", item) for item in CD.objects.all()] + [("tech", item) for item in Tech.objects.all()]
    rows.sort(key=lambda row: (row[0], row[1].name.casefold(), row[1].pk))
    metadata = []
    for excel_row, (kind, product) in enumerate(rows, HEADER_ROW + 1):
        values = (kind.upper(), product.pk, safe_text(product.sku), safe_text(product.name), None)
        for column, value in enumerate(values, 1):
            sheet.cell(excel_row, column, value)
        sheet.cell(excel_row, 5).number_format = AED_FORMAT
        metadata.append((excel_row, kind, product.pk, safe_text(product.sku)))
    _style_table(sheet, ("Тип", "ID", "Артикул", "Название", "Цена AED"), editable_columns=(5,))
    _meta_sheet(workbook, document_type="resource_supplier", values={
        "generated_at": timezone.now().isoformat(), "main_sheet": MAIN_SHEET,
    }, rows=metadata)
    logger.info("Шаблон поставщика сформирован: user_id=%s rows=%s", actor.pk, len(rows))
    return _bytes(workbook)


def generate_procurement_customer_xlsx(*, price_list_id, actor):
    try:
        price_list = ProcurementPriceList.objects.prefetch_related("items").get(pk=price_list_id)
    except ProcurementPriceList.DoesNotExist as exc:
        raise ValidationError("Закупочный прайс не найден.") from exc
    workbook, sheet = _base_workbook(
        title="Закупочный прайс", subtitle="Укажите количество по предоплате или постоплате", columns=5
    )
    metadata = []
    rows = list(price_list.items.all())
    for excel_row, item in enumerate(rows, HEADER_ROW + 1):
        values = (
            safe_text(item.product_name_snapshot), item.prepayment_price_rub, 0,
            item.postpayment_price_rub, 0,
        )
        for column, value in enumerate(values, 1):
            sheet.cell(excel_row, column, value)
        sheet.cell(excel_row, 2).number_format = MONEY_FORMAT
        sheet.cell(excel_row, 4).number_format = MONEY_FORMAT
        metadata.append((excel_row, item.product_kind, item.product_id, safe_text(item.article_snapshot)))
    end = max(HEADER_ROW + 1, HEADER_ROW + len(rows))
    totals = end + 2
    formulas = (
        ("Количество позиций", f'=SUMPRODUCT(--((C{HEADER_ROW + 1}:C{end}+E{HEADER_ROW + 1}:E{end})>0))'),
        ("Единиц предоплата", f"=SUM(C{HEADER_ROW + 1}:C{end})"),
        ("Единиц постоплата", f"=SUM(E{HEADER_ROW + 1}:E{end})"),
        ("Всего единиц", f"=SUM(C{HEADER_ROW + 1}:C{end})+SUM(E{HEADER_ROW + 1}:E{end})"),
        ("Сумма предоплаты", f"=SUMPRODUCT(B{HEADER_ROW + 1}:B{end},C{HEADER_ROW + 1}:C{end})"),
        ("Сумма постоплаты", f"=SUMPRODUCT(D{HEADER_ROW + 1}:D{end},E{HEADER_ROW + 1}:E{end})"),
        ("Итого", f"=SUMPRODUCT(B{HEADER_ROW + 1}:B{end},C{HEADER_ROW + 1}:C{end})+SUMPRODUCT(D{HEADER_ROW + 1}:D{end},E{HEADER_ROW + 1}:E{end})"),
    )
    for offset, (label, formula) in enumerate(formulas):
        sheet.cell(totals + offset, 4, label)
        sheet.cell(totals + offset, 5, formula)
        if offset >= 4:
            sheet.cell(totals + offset, 5).number_format = MONEY_FORMAT
    validation = DataValidation(type="whole", operator="greaterThanOrEqual", formula1="0", allow_blank=True)
    sheet.add_data_validation(validation)
    validation.add(f"C{HEADER_ROW + 1}:C{end}")
    validation.add(f"E{HEADER_ROW + 1}:E{end}")
    _style_table(
        sheet,
        ("Товар", "Цена предоплата", "Количество предоплата", "Цена постоплата", "Количество постоплата"),
        editable_columns=(3, 5),
        editable_end_row=end,
    )
    _meta_sheet(workbook, document_type="resource_procurement", values={
        "price_list_token": price_list.public_token, "generated_at": timezone.now().isoformat(),
        "main_sheet": MAIN_SHEET,
    }, rows=metadata)
    logger.info(
        "Клиентский закупочный прайс сформирован: user_id=%s price_list_id=%s rows=%s",
        actor.pk, price_list.pk, len(rows),
    )
    return _bytes(workbook)


def _load_uploaded_workbook(upload, expected_type):
    filename = Path(getattr(upload, "name", "")).name
    if Path(filename).suffix.lower() != ".xlsx":
        raise ValidationError("Разрешены только файлы .xlsx.")
    try:
        workbook = load_workbook(
            upload, data_only=False, read_only=False, keep_vba=False, keep_links=False
        )
    except Exception as exc:
        raise ValidationError("Не удалось прочитать XLSX-файл.") from exc
    if META_SHEET not in workbook.sheetnames or MAIN_SHEET not in workbook.sheetnames:
        workbook.close()
        raise ValidationError("Файл не является документом ReSOURCE: отсутствует технический лист.")
    meta = workbook[META_SHEET]
    values = {}
    row = 1
    while meta.cell(row, 1).value not in (None, ""):
        values[str(meta.cell(row, 1).value)] = str(meta.cell(row, 2).value or "")
        row += 1
    if values.get("document_type") != expected_type:
        workbook.close()
        raise ValidationError("Загружен документ другого типа.")
    if values.get("template_version") != TEMPLATE_VERSION:
        workbook.close()
        raise ValidationError("Версия шаблона не поддерживается.")
    header_row = row + 1
    technical_rows = []
    row = header_row + 1
    while meta.cell(row, 1).value not in (None, ""):
        technical_rows.append((
            meta.cell(row, 1).value, meta.cell(row, 2).value,
            meta.cell(row, 3).value, meta.cell(row, 4).value,
        ))
        row += 1
    return workbook, workbook[MAIN_SHEET], values, technical_rows


def _require_headers(sheet, expected):
    actual = tuple(sheet.cell(HEADER_ROW, column).value for column in range(1, len(expected) + 1))
    if actual != tuple(expected):
        raise ValidationError("Структура видимого листа изменена: заголовки не соответствуют шаблону.")


def _quantity(value, *, excel_row):
    if value in (None, ""):
        return 0
    if isinstance(value, bool) or isinstance(value, str):
        raise ValidationError(f"Строка {excel_row}: количество должно быть целым числом, не формулой или текстом.")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError(f"Строка {excel_row}: некорректное количество.") from exc
    if number < 0 or number != number.to_integral_value():
        raise ValidationError(f"Строка {excel_row}: количество должно быть целым числом не меньше нуля.")
    return int(number)


def import_wholesale_price_to_sale(upload):
    workbook, sheet, values, technical_rows = _load_uploaded_workbook(upload, "resource_wholesale")
    try:
        _require_headers(sheet, ("Товар", "Оптовая цена", "Доступно для заказа", "Количество к заказу"))
        warehouse = Warehouse.objects.get(pk=int(values.get("warehouse_id", "")))
        lines = []
        seen = set()
        for excel_row, kind, product_id, _article in technical_rows:
            try:
                excel_row, product_id = int(excel_row), int(product_id)
            except (TypeError, ValueError) as exc:
                raise ValidationError("Технические идентификаторы файла повреждены.") from exc
            key = (str(kind), product_id)
            if key in seen:
                raise ValidationError("В техническом листе обнаружен повтор товара.")
            seen.add(key)
            quantity = _quantity(sheet.cell(excel_row, 4).value, excel_row=excel_row)
            if not quantity:
                continue
            if kind == "cd":
                product = CD.objects.filter(pk=product_id).first()
                stock = CDWarehouseStock.objects.filter(warehouse=warehouse, cd_id=product_id).first()
            elif kind == "tech":
                product = Tech.objects.filter(pk=product_id).first()
                stock = TechWarehouseStock.objects.filter(warehouse=warehouse, tech_id=product_id).first()
            else:
                raise ValidationError(f"Строка {excel_row}: неизвестный тип товара.")
            if product is None:
                raise ValidationError(f"Строка {excel_row}: товар больше не существует.")
            available = stock.quantity if stock else 0
            if quantity > available:
                raise ValidationError(
                    f"{product.name}: запрошено {quantity} шт., доступно {available} шт."
                )
            if product.wholesale_price is None:
                raise ValidationError(f"Для товара «{product.name}» больше не задана оптовая цена.")
            lines.append({
                "product_type": kind, "product_id": product_id, "quantity": quantity,
                "label": f"{kind.upper()} — {product.name}",
            })
        if not lines:
            raise ValidationError("В файле не выбрано ни одной товарной позиции.")
        return warehouse, lines
    except (Warehouse.DoesNotExist, TypeError, ValueError) as exc:
        raise ValidationError("Склад из документа не найден.") from exc
    finally:
        workbook.close()


@transaction.atomic
def import_supplier_price(*, supplier_id, upload, actor):
    workbook, sheet, _values, technical_rows = _load_uploaded_workbook(upload, "resource_supplier")
    try:
        _require_headers(sheet, ("Тип", "ID", "Артикул", "Название", "Цена AED"))
        supplier = Supplier.objects.select_for_update().get(pk=supplier_id)
        prepared = {"cd": [], "tech": []}
        seen = set()
        for excel_row, kind, product_id, _article in technical_rows:
            try:
                excel_row, product_id = int(excel_row), int(product_id)
            except (TypeError, ValueError) as exc:
                raise ValidationError("Технические идентификаторы файла повреждены.") from exc
            key = (str(kind), product_id)
            if key in seen:
                raise ValidationError("В техническом листе обнаружен повтор товара.")
            seen.add(key)
            raw_price = sheet.cell(excel_row, 5).value
            if raw_price in (None, ""):
                continue
            if isinstance(raw_price, bool) or isinstance(raw_price, str):
                raise ValidationError(f"Строка {excel_row}: цена AED должна быть числом, не формулой или текстом.")
            try:
                price = Decimal(str(raw_price)).quantize(Decimal("0.000001"))
            except (InvalidOperation, TypeError, ValueError) as exc:
                raise ValidationError(f"Строка {excel_row}: некорректная цена AED.") from exc
            if price <= 0:
                raise ValidationError(f"Строка {excel_row}: цена AED должна быть больше нуля.")
            model = CD if kind == "cd" else Tech if kind == "tech" else None
            if model is None or not model.objects.filter(pk=product_id).exists():
                raise ValidationError(f"Строка {excel_row}: товар не найден.")
            prepared[kind].append((product_id, price))
        expected = (
            {("cd", product_id) for product_id in CD.objects.values_list("id", flat=True)}
            | {("tech", product_id) for product_id in Tech.objects.values_list("id", flat=True)}
        )
        if seen != expected:
            raise ValidationError(
                "Структура шаблона поставщика неполна или содержит посторонние товары. "
                "Скачайте новый шаблон и заполните только колонку «Цена AED»."
            )
        SupplierCDPrice.objects.filter(supplier=supplier).delete()
        SupplierTechPrice.objects.filter(supplier=supplier).delete()
        SupplierCDPrice.objects.bulk_create([
            SupplierCDPrice(supplier=supplier, cd_id=product_id, price=price)
            for product_id, price in prepared["cd"]
        ])
        SupplierTechPrice.objects.bulk_create([
            SupplierTechPrice(supplier=supplier, tech_id=product_id, price=price)
            for product_id, price in prepared["tech"]
        ])
        count = len(prepared["cd"]) + len(prepared["tech"])
        logger.info(
            "Прайс поставщика полностью заменён: user_id=%s supplier_id=%s prices=%s",
            actor.pk, supplier.pk, count,
        )
        return count
    except Supplier.DoesNotExist as exc:
        raise ValidationError("Поставщик не найден.") from exc
    finally:
        workbook.close()

def import_procurement_order_xlsx(upload):
    workbook, sheet, values, technical_rows = _load_uploaded_workbook(upload, "resource_procurement")
    try:
        _require_headers(sheet, (
            "Товар", "Цена предоплата", "Количество предоплата",
            "Цена постоплата", "Количество постоплата",
        ))
        try:
            price_list = ProcurementPriceList.objects.prefetch_related("items").get(
                public_token=values.get("price_list_token")
            )
        except (ProcurementPriceList.DoesNotExist, ValueError, ValidationError) as exc:
            raise ValidationError("Версия закупочного прайса не найдена.") from exc
        items = {(item.product_kind, item.product_id): item for item in price_list.items.all()}
        lines = []
        seen = set()
        for excel_row, kind, product_id, _article in technical_rows:
            try:
                excel_row, product_id = int(excel_row), int(product_id)
            except (TypeError, ValueError) as exc:
                raise ValidationError("Технические идентификаторы файла повреждены.") from exc
            key = (str(kind), product_id)
            if key in seen:
                raise ValidationError("В техническом листе обнаружен повтор товара.")
            seen.add(key)
            item = items.get(key)
            if item is None:
                raise ValidationError(f"Строка {excel_row}: товар отсутствует в сохранённом прайсе.")
            prepayment_quantity = _quantity(sheet.cell(excel_row, 3).value, excel_row=excel_row)
            postpayment_quantity = _quantity(sheet.cell(excel_row, 5).value, excel_row=excel_row)
            if prepayment_quantity or postpayment_quantity:
                lines.append({
                    "price_list_item_id": item.pk,
                    "prepayment_quantity": prepayment_quantity,
                    "postpayment_quantity": postpayment_quantity,
                })
        if not lines:
            raise ValidationError("В файле не выбрано ни одной товарной позиции.")
        return price_list, lines
    finally:
        workbook.close()
