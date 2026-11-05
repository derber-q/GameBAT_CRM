"""Очищает исходный XLSX отправки, сохраняя оформление таможенной таблицы."""
import argparse
from datetime import datetime
from pathlib import Path
from openpyxl import load_workbook
from openpyxl.cell.cell import Cell
from copy import copy
from openpyxl.xml.functions import tostring


def layout_snapshot(book):
    """Только оформление/заголовки, без коммерческих строк и личных свойств."""
    sheet=book['ОПИСАНИЕ']
    styles=[]
    for row in (4,5):
        styles.append([{
            'font':tostring(copy(sheet.cell(row,c).font).to_tree()).decode(),
            'fill':tostring(copy(sheet.cell(row,c).fill).to_tree()).decode(),
            'border':tostring(copy(sheet.cell(row,c).border).to_tree()).decode(),
            'alignment':tostring(copy(sheet.cell(row,c).alignment).to_tree()).decode(),
            'number_format':sheet.cell(row,c).number_format,
        } for c in range(1,11)])
    from hashlib import sha256
    return {'sheet':'ОПИСАНИЕ','headers':[sheet.cell(4,c).value for c in range(1,11)],'grand_total':sheet['A5'].value,
        'theme_sha256':sha256(book.loaded_theme or b'').hexdigest(),
        'styles':styles,'widths':{k:v.width for k,v in sheet.column_dimensions.items()},
        'heights':{str(r):sheet.row_dimensions[r].height for r in (4,5)},
        'page_setup':tostring(sheet.page_setup.to_tree()).decode(),
        'page_margins':tostring(sheet.page_margins.to_tree()).decode()}


def prepare(source,target):
    book=load_workbook(source,keep_links=False)
    if book.sheetnames!=['ОПИСАНИЕ']:raise ValueError('Ожидается оригинальный лист ОПИСАНИЕ.')
    sheet=book.active
    if sheet['A5'].value!='GRAND TOTAL' or 'A5:J5' not in {str(m) for m in sheet.merged_cells.ranges}:
        raise ValueError('Структура оригинального шаблона не совпадает.')
    for merge in list(sheet.merged_cells.ranges):
        if merge.min_row>=6:sheet.unmerge_cells(str(merge))
    for row in sheet:
        for cell in row:
            if not isinstance(cell,Cell):continue
            if cell.row<4 or cell.row>=6:cell.value=None
            cell.comment=None;cell.hyperlink=None
    # Содержимое общих XML-строк и личные свойства не копируются в новый ZIP.
    for field in ('creator','lastModifiedBy','title','subject','description','keywords','identifier','category'):
        setattr(book.properties,field,'')
    book.properties.created=book.properties.modified=datetime(2000,1,1)
    book.custom_doc_props.props=[]
    book.defined_names.clear()
    target=Path(target)
    if target.exists():raise ValueError('Нужен новый файл, существующий шаблон не перезаписывается.')
    target.parent.mkdir(parents=True,exist_ok=True);book.save(target)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('source',type=Path);parser.add_argument('target',type=Path)
    args=parser.parse_args();prepare(args.source,args.target)
