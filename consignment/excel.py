"""Экспорт актуальных партий реализации без себестоимости и финансовых снимков."""
from decimal import Decimal
from io import BytesIO
from itertools import groupby
from textwrap import wrap

from django.db import transaction
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from price.excel import BLUE, GRAY, GROUP_FILL, LIGHT, MONEY_FORMAT, TEAL, WHITE, safe_text
from .models import CDConsignmentStock, TechConsignmentStock


def _stock_rows(platform, user):
    """Явный список разрешённых полей: ни стоимость, ни история не загружаются."""
    sections = []
    # Обе выборки читают один снимок БД; создание XLSX происходит после транзакции.
    with transaction.atomic():
        for kind, model, product, category, label in (
            ("cd", CDConsignmentStock, "cd", "platform", "CD · Диски"),
            ("tech", TechConsignmentStock, "tech", "product_type", "Tech · Техника"),
        ):
            if not (user.is_superuser or user.has_perm(f"consignment.view_{kind}consignmentstock")):
                continue
            fields = (
                "pk", f"{product}__name", f"{product}__sku", f"{product}__{category}_id",
                f"{product}__{category}__name", "quantity", "receivable_per_unit",
            )
            rows = list(model.objects.filter(platform=platform, quantity__gt=0).values(*fields))
            rows.sort(key=lambda row: (
                row[f"{product}__{category}__name"].casefold(),
                row[f"{product}__{category}_id"], row[f"{product}__name"].casefold(),
                row[f"{product}__sku"], row["receivable_per_unit"], row["pk"],
            ))
            sections.append((label, product, category, rows))
    return sections


def generate_consignment_xlsx(*, platform, user):
    sections = _stock_rows(platform, user)
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
    headers = ("Наименование", "Артикул", "Количество", "Вознаграждение за единицу, ₽", "Общая сумма, ₽")
    for column, header in enumerate(headers, 1):
        cell = sheet.cell(4, column, header)
        cell.font = Font(bold=True, color=WHITE)
        cell.fill = PatternFill("solid", fgColor=TEAL)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    sheet.row_dimensions[4].height = 44
    for column, width in zip("ABCDE", (62, 24, 14, 25, 24)):
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

    total_quantity = 0
    total_amount = Decimal("0.00")
    border = Border(bottom=Side(style="thin", color=GRAY))
    for label, product, category, rows in sections:
        if not rows:
            continue
        group_heading(label, main=True)
        for _, grouped in groupby(rows, key=lambda row: row[f"{product}__{category}_id"]):
            grouped = list(grouped)
            group_heading(grouped[0][f"{product}__{category}__name"])
            for stock in grouped:
                quantity, reward = stock["quantity"], stock["receivable_per_unit"]
                amount = quantity * reward
                # Каждая реальная партия остаётся самостоятельной строкой, как в интерфейсе.
                sheet.append((safe_text(stock[f"{product}__name"]), safe_text(stock[f"{product}__sku"]),
                              quantity, reward, amount))
                row_number = sheet.max_row
                for cell in sheet[row_number]:
                    cell.border = border
                    cell.alignment = Alignment(vertical="center", wrap_text=cell.column < 3,
                                               horizontal="right" if cell.column > 2 else "left")
                sheet.cell(row_number, 2).number_format = "@"
                sheet.cell(row_number, 3).number_format = "0"
                for column in (4, 5):
                    sheet.cell(row_number, column).number_format = MONEY_FORMAT
                lines = max(len(wrap(str(sheet.cell(row_number, 1).value), 53)),
                            len(wrap(str(sheet.cell(row_number, 2).value), 20)), 1)
                sheet.row_dimensions[row_number].height = max(22, 16 * lines)
                total_quantity += quantity
                total_amount += amount
    if not total_quantity:
        group_heading("Нет товаров на реализации")
    sheet.append(("Итого", None, total_quantity, None, total_amount))
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
