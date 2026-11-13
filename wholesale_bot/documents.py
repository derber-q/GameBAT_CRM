"""Именной Excel и строгая граница загрузки над существующим price.excel."""
from datetime import timedelta, date, datetime
from decimal import Decimal
from io import BytesIO
from pathlib import PurePosixPath
from zipfile import ZipFile, BadZipFile
import uuid
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from openpyxl import load_workbook
from price.excel import (generate_wholesale_price_xlsx, import_wholesale_price_to_sale,
                         MAIN_SHEET, safe_text, _load_uploaded_workbook, _quantity)
from .models import PriceIssue

MAX_FILE = 5 * 1024 * 1024
MAX_ROWS = 16000
MAX_QUANTITY = 1000000
ISSUE_SHEET = '_resource_opt'
INVALID = 'Не удалось прочитать прайс. Скачайте файл из этого бота и изменяйте только количество товаров.'


def open_safe(content):
    """До openpyxl ограничиваем архив/XML; макросы, ссылки и произвольные части не исполняются."""
    if not 0 < len(content) <= MAX_FILE:
        raise ValidationError('Размер XLSX должен быть не больше 5 МБ.')
    try:
        with ZipFile(BytesIO(content)) as archive:
            entries = archive.infolist()
            if (len(entries) > 100 or len({e.filename for e in entries}) != len(entries)
                    or sum(e.file_size for e in entries) > 32 * 1024 * 1024):
                raise ValidationError(INVALID)
            for entry in entries:
                path = PurePosixPath(entry.filename)
                if (entry.flag_bits & 1 or path.is_absolute() or '..' in path.parts
                        or entry.file_size > 12 * 1024 * 1024
                        or entry.filename.endswith('.bin') or 'externalLinks/' in entry.filename
                        or 'embeddings/' in entry.filename):
                    raise ValidationError(INVALID)
                if entry.filename.endswith(('.xml', '.rels')):
                    data = archive.read(entry).replace(b'\x00', b'').upper()
                    if b'<!DOCTYPE' in data or b'<!ENTITY' in data or b'TARGETMODE="EXTERNAL"' in data:
                        raise ValidationError(INVALID)
                    # Не позволяем sparse-координатам превратить небольшой XML в гигантскую таблицу.
                    if entry.filename.startswith('xl/worksheets/'):
                        import re
                        for column, row in re.findall(rb'\bR="([A-Z]+)(\d+)"', data):
                            if len(column) > 1 or column > b'P' or int(row) > MAX_ROWS:
                                raise ValidationError(INVALID)
        wb = load_workbook(BytesIO(content), data_only=False, keep_vba=False, keep_links=False)
        if len(wb.sheetnames) > 3 or any(s.max_row > MAX_ROWS or s.max_column > 16 for s in wb):
            wb.close()
            raise ValidationError(INVALID)
        return wb
    except ValidationError:
        raise
    except Exception:
        raise ValidationError(INVALID) from None


def _value(cell):
    value = cell.value
    if value is None:
        return None
    if isinstance(value, bool):
        return ['bool', value]
    if isinstance(value, (int, float, Decimal)):
        return ['number', str(Decimal(str(value)).normalize())]
    if isinstance(value, (date, datetime)):
        return ['date', value.isoformat()]
    return [cell.data_type, str(value)]


def manifest(wb, products):
    editable = {(p['row'], 4) for p in products}
    sheets = {}
    for sheet in wb:
        sheets[sheet.title] = {'rows': sheet.max_row, 'columns': sheet.max_column,
            'merges': sorted(str(value) for value in sheet.merged_cells.ranges),
            'cells': {cell.coordinate: _value(cell) for row in sheet for cell in row
                if cell.value is not None and not (sheet.title == MAIN_SHEET and (cell.row, cell.column) in editable)}}
    return {'sheets': sheets, 'products': products}


@transaction.atomic
def issue_price(customer_id):
    from .services import active_customer, operator
    customer = active_customer(customer_id)
    config, actor = operator()
    content = generate_wholesale_price_xlsx(warehouse_id=config.warehouse_id, actor=actor,
                                           partner_id=customer.partner_id)
    raw = BytesIO(content)
    raw.name = 'price.xlsx'
    original, _sheet, _values, rows = _load_uploaded_workbook(raw, 'resource_wholesale')
    original.close()
    products = [{'row': int(row), 'kind': str(kind), 'id': int(pk)} for row, kind, pk, _sku in rows]
    wb = open_safe(content)
    wb[MAIN_SHEET]['A3'] = safe_text(f'Склад: {config.warehouse.name} · Заказчик: {customer.partner.display_name}')
    from copy import copy
    alignment = copy(wb[MAIN_SHEET]['A3'].alignment)
    alignment.wrap_text = True
    wb[MAIN_SHEET]['A3'].alignment = alignment
    wb[MAIN_SHEET].row_dimensions[3].height = 32
    issue_id = uuid.uuid4()
    wb.create_sheet(ISSUE_SHEET).cell(1, 1, str(issue_id))
    wb[ISSUE_SHEET].sheet_state = 'veryHidden'
    stream = BytesIO()
    wb.save(stream)
    wb.close()
    content = stream.getvalue()
    wb = open_safe(content)
    snapshot = manifest(wb, products)
    wb.close()
    return PriceIssue.objects.create(id=issue_id, customer=customer, partner=customer.partner,
        customer_revision=customer.revision, warehouse=config.warehouse, content=content,
        manifest=snapshot, expires_at=timezone.now() + timedelta(days=30))


def read_order(content, customer):
    wb = open_safe(content)
    try:
        try:
            issue_id = uuid.UUID(str(wb[ISSUE_SHEET].cell(1, 1).value))
        except (KeyError, ValueError, TypeError):
            raise ValidationError(INVALID) from None
        issue = PriceIssue.objects.filter(pk=issue_id, customer=customer, partner_id=customer.partner_id,
            customer_revision=customer.revision, expires_at__gt=timezone.now()).first()
        if issue is None:
            raise ValidationError('Этот прайс не соответствует вашему аккаунту или устарел. Скачайте новый именной прайс.')
        products = issue.manifest['products']
        if manifest(wb, products) != issue.manifest:
            raise ValidationError(INVALID)
        selected = []
        for row in products:
            value = wb[MAIN_SHEET].cell(row['row'], 4).value
            if isinstance(value, (int, float, Decimal)) and not Decimal(str(value)).is_finite():
                raise ValidationError('Количество должно быть конечным целым числом.')
            quantity = _quantity(value, excel_row=row['row'])
            if quantity > MAX_QUANTITY:
                raise ValidationError('Количество товара не должно превышать 1 000 000.')
            if quantity:
                selected.append({'product_type': row['kind'], 'product_id': row['id'], 'quantity': quantity,
                    'original_price': str(wb[MAIN_SHEET].cell(row['row'], 2).value)})
        if not selected:
            raise ValidationError('В файле не выбрано ни одной товарной позиции.')
        return issue, selected
    finally:
        wb.close()


def current_lines(intent):
    """Штатный импорт проверяет актуальные товары, склад, количества и цены; формат веба не меняется."""
    from sales.services import sale_stock_shortages
    shortages = sale_stock_shortages(warehouse_id=intent.issue.warehouse_id, lines=intent.lines)
    if shortages:
        raise ValidationError([f"{row['name']}: запрошено {row['requested']} шт., доступно {row['available']} шт."
                               for row in shortages])
    source = BytesIO(bytes(intent.content))
    source.name = 'order.xlsx'
    warehouse, lines, customer = import_wholesale_price_to_sale(source, with_customer=True)
    if warehouse.pk != intent.issue.warehouse_id or customer['partner_id'] != intent.partner_id:
        raise ValidationError(INVALID)
    return lines


def invoice(intent):
    from sales.invoice_excel import sale_invoice_document
    return sale_invoice_document(intent.sale)
