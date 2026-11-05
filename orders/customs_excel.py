"""Экспорт только загрузкой очищенного оригинала GameBAT; никаких новых листов."""
from copy import copy
from datetime import datetime
from hashlib import sha256
from io import BytesIO
import math
from pathlib import Path
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from openpyxl import load_workbook
from .customs_models import CUSTOMS_FIELDS,CustomsManifestExport,CustomsEvent

TEMPLATE=Path(__file__).parent/'resources/customs_manifest_template.xlsx'
EXCEL_FIELDS=('number','hs_code','marking','ru_description','en_description','material','country','manufacturer','quantity','unit')


def build_workbook(rows):
    if any(type(r['quantity']) is not int or r['quantity']<0 for r in rows):
        raise ValidationError('Количество Excel должно быть целым неотрицательным числом.')
    rows=[r for r in rows if r['quantity']>0]
    if not rows:raise ValidationError('В описи нет строк с положительным количеством.')
    book=load_workbook(TEMPLATE,keep_links=False);sheet=book['ОПИСАНИЕ']
    styles=[[copy(sheet.cell(r,c)._style) for c in range(1,11)] for r in range(6,31)]
    heights={r:sheet.row_dimensions[r].height for r in range(6,31)}
    for merge in list(sheet.merged_cells.ranges):
        if merge.min_row>=6:sheet.unmerge_cells(str(merge))
    sheet.delete_rows(6,max(sheet.max_row-5,0))
    for index in list(sheet.row_dimensions):
        if index>=6:del sheet.row_dimensions[index]
    for index,row in enumerate(rows):
        line=index+6;style=styles[index] if index<25 else styles[2]
        height=heights.get(line) or sheet.sheet_format.defaultRowHeight or 15
        for column,field in enumerate(EXCEL_FIELDS,1):
            cell=sheet.cell(line,column);cell._style=copy(style[column-1])
            if field=='quantity':
                if type(row[field]) is not int or row[field]<0:raise ValidationError('Количество Excel должно быть целым неотрицательным числом.')
                cell.value=row[field]
            else:
                cell.value=str(row.get(field,'') or '');cell.data_type='s'
            if field in ('ru_description','en_description'):
                alignment=copy(cell.alignment);alignment.wrap_text=True;cell.alignment=alignment
                width=sheet.column_dimensions[cell.column_letter].width or 50
                lines=sum(max(1,math.ceil(len(part)/max(1,int(width)-3))) for part in str(cell.value).split('\n'))
                height=max(height,lines*((cell.font.sz or 11)+3))
        # Excel ограничивает высоту строки; полный текст остаётся в ячейке.
        sheet.row_dimensions[line].height=min(409.5,height)
    book.properties.modified=timezone.now().replace(tzinfo=None)
    return book


@transaction.atomic
def export_manifest(*,actor,manifest,acknowledged=False):
    from .customs_service import require,source_snapshot,manifest_rows,row_warnings,STALE
    require(actor,'download')
    current=source_snapshot(manifest.trip_id,lock=True)
    if current.signature!=manifest.source_signature:raise ValidationError(STALE)
    rows=manifest_rows(manifest);warnings=row_warnings(rows)
    if warnings and acknowledged is not True:raise ValidationError('Подтвердите проверку предупреждений перед экспортом.')
    if any(r['quantity']!=r['expected_quantity'] and not (r['quantity_confirmed'] and r['quantity_reason'] and r['quantity_approved_by_id']) for r in rows):
        raise ValidationError('Отличие количества не подтверждено.')
    output=BytesIO();build_workbook(rows).save(output);content=output.getvalue()
    date=timezone.localdate().isoformat()
    item=CustomsManifestExport(manifest=manifest,actor=actor,
        filename=f'GameBAT_Таможенная_опись_Рейс_{manifest.trip_id}_{date}_ред{manifest.revision}.xlsx',
        size=len(content),sha256=sha256(content).hexdigest(),template_sha256=sha256(TEMPLATE.read_bytes()).hexdigest(),
        acknowledged_warnings=warnings if acknowledged else [])
    # UUID задаётся сервером; пользователь не управляет именем/путём хранилища.
    item.file.save(str(item.pk)+'.xlsx',ContentFile(content),save=False)
    try:
        item.save()
        CustomsEvent.objects.create(manifest=manifest,actor=actor,action='exported',details={'export_id':str(item.pk),'sha256':item.sha256})
    except Exception:
        item.file.delete(save=False);raise
    return item
