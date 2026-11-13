"""Экспорт актуальных партий реализации без себестоимости и финансовых снимков."""
from uuid import uuid4
from openpyxl.worksheet.datavalidation import DataValidation
from .reports import sign_report
from decimal import Decimal
from io import BytesIO
from itertools import groupby
from textwrap import wrap
from types import SimpleNamespace

from django.db import transaction
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from price.excel import BLUE, GRAY, GROUP_FILL, LIGHT, MONEY_FORMAT, TEAL, WHITE, safe_text
from catalog.product_ordering import cd_order_key, tech_price_order
from .models import CDConsignmentStock, TechConsignmentStock


def _stock_rows(platform, user):
    """Явный список разрешённых полей: ни стоимость, ни история не загружаются."""
    sections = []
    # Обе выборки читают один снимок БД; создание XLSX происходит после транзакции.
    with transaction.atomic():
        for kind, model, product, category, label in (
            ("tech", TechConsignmentStock, "tech", "product_type", "Tech · Техника"),
            ("cd", CDConsignmentStock, "cd", "platform", "CD · Диски"),
        ):
            if not (user.is_superuser or user.has_perm(f"consignment.view_{kind}consignmentstock")):
                continue
            fields = (
                "pk", f"{product}_id", f"{product}__name", f"{product}__sku", f"{product}__{category}_id",
                f"{product}__{category}__name", "quantity", "receivable_per_unit",
            )
            if kind == 'tech':
                fields += ('tech__brand_id', 'tech__brand__name')
            rows = list(model.objects.filter(platform=platform, quantity__gt=0).values(*fields))
            ordered = []
            for row in rows:
                # Общий ключ прайса получает только разрешённые реквизиты, без cost.
                item = SimpleNamespace(pk=row[f'{product}_id'], name=row[f'{product}__name'])
                category_id = row[f'{product}__{category}_id']
                category_name = row[f'{product}__{category}__name']
                setattr(item, f'{category}_id', category_id)
                setattr(item, category, SimpleNamespace(name=category_name))
                if kind == 'tech':
                    item.brand_id = row['tech__brand_id']
                    item.brand = SimpleNamespace(name=row['tech__brand__name'])
                    key, title = tech_price_order(item, for_excel=True)
                else:
                    key = cd_order_key(item)
                    title = f'CD · Платформа: {category_name}'
                ordered.append((key, title, row))
            # Партии одного товара не объединяются: подпись хранит исходный stock_id.
            ordered.sort(key=lambda entry: (entry[0], entry[2]['receivable_per_unit'], entry[2]['pk']))
            groups = [(title, [entry[2] for entry in entries])
                      for title, entries in groupby(ordered, key=lambda entry: entry[1])]
            sections.append((label, product, groups))
    return sections


def generate_consignment_xlsx(*, platform, user):
    sections = _stock_rows(platform, user)
    report_id = str(uuid4())
    identities = []
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Реализация"
    sheet.sheet_view.showGridLines = False
    sheet.merge_cells("A1:E1")
    sheet["A1"] = safe_text(f"Реализация · {platform.name}")
    sheet["A1"].font = Font(size=18, bold=True, color=WHITE)
    sheet["A1"].fill = PatternFill("solid", fgColor=BLUE)
    sheet["A1"].alignment = Alignment(vertical="center", wrap_text=True)
    sheet.row_dimensions[1].height = max(34, 24 * len(wrap(str(sheet["A1"].value), 85)))
    sheet.merge_cells("A2:E2")
    sheet["A2"] = f"Дата формирования: {timezone.localtime():%d.%m.%Y %H:%M:%S}"
    sheet["A2"].font = Font(size=10, color="7B8999")
    headers = ("Наименование", "Остаток на реализации", "Цена за единицу, ₽", "Количество реализованного", "Сумма реализованного, ₽")
    for column, header in enumerate(headers, 1):
        cell = sheet.cell(4, column, header)
        cell.font = Font(bold=True, color=WHITE)
        cell.fill = PatternFill("solid", fgColor=TEAL)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    sheet.row_dimensions[4].height = 44
    for column, width in zip("ABCDE", (62, 18, 21, 23, 25)):
        sheet.column_dimensions[column].width = width
    sheet.freeze_panes = "A5"

    def group_heading(text, *, main=False):
        row = sheet.max_row + 1
        sheet.merge_cells(start_row=row, start_column=1, end_row=row, end_column=5)
        cell = sheet.cell(row, 1, safe_text(text))
        cell.font = Font(bold=True, color=WHITE if main else BLUE, size=12 if main else 11)
        cell.fill = PatternFill("solid", fgColor=BLUE if main else GROUP_FILL)
        cell.alignment = Alignment(wrap_text=True, vertical="center")
        sheet.row_dimensions[row].height = max(24, 16 * len(wrap(str(cell.value), 100)))

    sheet.column_dimensions["F"].hidden = True
    validation = DataValidation(type="whole", operator="greaterThanOrEqual", formula1=0, allow_blank=True)
    validation.errorTitle = "Количество реализованного"
    validation.error = "Введите целое неотрицательное число."
    validation.showErrorMessage = True
    sheet.add_data_validation(validation)
    total_quantity = 0
    total_amount = Decimal("0.00")
    border = Border(bottom=Side(style="thin", color=GRAY))
    for label, product, groups in sections:
        if not groups:
            continue
        group_heading(label, main=True)
        for title, grouped in groups:
            group_heading(title)
            for stock in grouped:
                quantity, reward = stock["quantity"], stock["receivable_per_unit"]
                amount = quantity * reward
                # Каждая реальная партия остаётся самостоятельной строкой, как в интерфейсе.
                identity = f"{product}:{stock['pk']}"
                identities.append(identity)
                token = sign_report({'report_id': report_id, 'platform_id': platform.pk, 'kind': product,
                                     'stock_id': stock['pk'], 'quantity': quantity, 'price': str(reward)})
                row_number = sheet.max_row + 1
                sheet.append((safe_text(stock[f"{product}__name"]), quantity, reward, 0,
                              f'=IF(D{row_number}="",0,C{row_number}*D{row_number})', token))
                validation.add(sheet.cell(row_number, 4))
                for cell in sheet[row_number]:
                    cell.border = border
                    cell.alignment = Alignment(vertical="center", wrap_text=cell.column < 3,
                                               horizontal="right" if cell.column > 2 else "left")
                sheet.cell(row_number, 2).number_format = "0"
                sheet.cell(row_number, 4).number_format = "0"
                for column in (3, 5):
                    sheet.cell(row_number, column).number_format = MONEY_FORMAT
                lines = max(len(wrap(str(sheet.cell(row_number, 1).value), 53)),
                            len(wrap(str(sheet.cell(row_number, 2).value), 20)), 1)
                sheet.row_dimensions[row_number].height = max(22, 16 * lines)
                total_quantity += quantity
                total_amount += amount
    if not total_quantity:
        group_heading("Нет товаров на реализации")
    last = sheet.max_row
    sheet.append(("Итого площадка должна за реализованные товары", None, None, None, f"=SUM(E5:E{last})"))
    metadata = workbook.create_sheet("_resource_report")
    metadata.sheet_state = "veryHidden"
    token = sign_report({'version': 1, 'report_id': report_id, 'platform_id': platform.pk, 'identities': identities})
    for offset in range(0, len(token), 30000):
        metadata.append((token[offset:offset+30000],))
    for cell in sheet[sheet.max_row]:
        cell.font = Font(bold=True, color=BLUE)
        cell.fill = PatternFill("solid", fgColor=LIGHT)
    sheet.cell(sheet.max_row, 3).number_format = "0"
    sheet.cell(sheet.max_row, 5).number_format = MONEY_FORMAT
    sheet.row_dimensions[sheet.max_row].height = 26
    sheet.print_options.horizontalCentered = True
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.page_setup.orientation = "landscape"
    sheet.page_setup.paperSize = sheet.PAPERSIZE_A4
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0
    sheet.print_title_rows = "1:4"
    sheet.print_area = f"A1:E{sheet.max_row}"
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()
