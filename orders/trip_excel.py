"""Заказ поставщику из сохранённых строк рейса, включая нулевые позиции."""
from io import BytesIO
from textwrap import wrap

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from price.excel import TEAL, WHITE, safe_text


def supplier_order_xlsx(batch, supplier, lines, *, show_prices=True):
    book = Workbook()
    sheet = book.active
    sheet.title = "Заказ поставщику"
    last = "D" if show_prices else "C"
    headers = ["Наименование", "Артикул"]
    if show_prices:
        headers.append("Цена, AED")
    headers.append("Количество")
    for column, title in enumerate(headers, 1):
        cell = sheet.cell(1, column, title)
        cell.font = Font(bold=True, color=WHITE)
        cell.fill = PatternFill("solid", fgColor=TEAL)
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    sheet.row_dimensions[1].height = 30
    quantity_column = len(headers)
    for line in lines:
        values = [safe_text(line.product_name_snapshot), safe_text(line.article_snapshot)]
        if show_prices:
            values.append(line.supplier_price_aed_snapshot)
        values.append(line.quantity)
        sheet.append(values)
        row = sheet.max_row
        sheet.cell(row, 2).number_format = "@"
        sheet.cell(row, quantity_column).number_format = "0"
        for cell in sheet[row]:
            cell.alignment = Alignment(wrap_text=True, vertical="center")
            if not line.quantity:
                cell.fill = PatternFill("solid", fgColor="FFF1D6")
        if show_prices:
            price = line.supplier_price_aed_snapshot
            sheet.cell(row, 3).number_format = (
                "#,##0" if price == price.to_integral_value() else "#,##0.######"
            )
        sheet.row_dimensions[row].height = max(24, 15 * len(wrap(line.product_name_snapshot, 52)))
    for letter, width in zip("ABCD", (60, 24, 20 if show_prices else 14, 14)):
        if ord(letter) - 64 <= len(headers):
            sheet.column_dimensions[letter].width = width
    sheet.column_dimensions["B"].hidden = True
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = f"A1:{last}{sheet.max_row}"
    sheet.print_title_rows = "1:1"
    sheet.print_area = f"A1:{last}{sheet.max_row}"
    output = BytesIO()
    book.save(output)
    book.close()
    return output.getvalue()
