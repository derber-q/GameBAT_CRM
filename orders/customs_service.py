"""Фактические источники и изолированные редакции таможенной описи.

Ни один сервис этого модуля не сохраняет рейс, прибытие, товар, Sale/Supply,
остаток или денежную запись. Блокировки рейса используются только для согласованности.
"""
from dataclasses import dataclass
from hashlib import sha256
import json
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from core.db_retry import retry_database_lock
from .models import SupplierOrderBatch,TripArrival
from .customs_models import (CUSTOMS_FIELDS,CONFIRMABLE_FIELDS,CustomsGroup,CustomsProductDefaults,
    CustomsManifest,CustomsManifestLine,CustomsManifestSource,CustomsEvent)

STALE='Фактический состав рейса изменился после подготовки таможенной описи. Необходимо обновить документ.'
LABELS=dict(number='N',hs_code='Код ТН ВЭД',marking='Маркировка',ru_description='Русское описание',
    en_description='Английское описание',material='Материал',country='Страна',manufacturer='Производитель',unit='Единица')


def require(actor,action='view'):
    if not actor.is_active or not actor.has_perm('orders.view_customs_manifest'):
        raise PermissionDenied('Нет права просмотра таможенной описи.')
    names={'change':'change_customs_manifest','download':'download_customs_manifest','rules':'manage_customs_rules',
        'quantity':'approve_customs_quantity'}
    if action!='view' and not actor.has_perm('orders.'+names[action]):
        raise PermissionDenied('Недостаточно прав для этого действия с таможенной описью.')


def digest(value):return sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()


@dataclass
class SourceSnapshot:
    trip:object
    arrival:object
    rows:list
    signature:str
    total:int
    orders:list
    source_kind:str='actual'


def snapshot_name(row):
    if row._meta.model_name=='supplierorderbatchline':
        return row.product_name_snapshot or row.product.name
    return row.order_item.product_name_snapshot or row.allocation.line.product_name_snapshot or row.product.name


def source_snapshot(trip_id,*,lock=False):
    trips=SupplierOrderBatch.objects.select_for_update() if lock else SupplierOrderBatch.objects
    trip=trips.get(pk=trip_id)
    if not trip.is_trip:raise ValidationError('Таможенная опись доступна только для рейса.')
    arrivals=TripArrival.objects.select_for_update() if lock else TripArrival.objects
    arrival=arrivals.filter(trip=trip).first()
    orders=list(trip.trip_orders.order_by('pk').values_list('pk',flat=True))
    if not arrival or not arrival.arrived_at:
        from .trips import _assert_balances
        _assert_balances(trip)
        query=trip.lines.select_related('cd__platform','tech__brand','tech__product_type').order_by('pk')
        if lock:query=query.select_for_update()
        all_rows=list(query)
        for row in all_rows:row.actual_quantity=row.quantity
        positive=[r for r in all_rows if r.quantity>0]
        total=sum(r.quantity for r in positive)
        if not total:raise ValidationError('В составе рейса нет товаров для описи.')
        facts=[(r.pk,r.product_kind,r.product_id,r.quantity,snapshot_name(r),
            r.cd.platform_id if r.cd_id else None,r.tech.brand_id if r.tech_id else None,
            r.tech.product_type_id if r.tech_id else None) for r in all_rows]
        return SourceSnapshot(trip,None,positive,digest(['planned',trip.pk,trip.revision,orders,facts]),total,orders,'planned')
    if not isinstance(arrival.reviewed_orders,list) or set(orders)-set(arrival.reviewed_orders):
        raise ValidationError('Не сверены фактические количества всех заказов рейса.')
    query=arrival.rows.select_related('order_item','allocation__line','cd__platform','tech__brand','tech__product_type')
    if lock:query=query.select_for_update()
    all_rows=list(query.order_by('pk'))
    if any(row.order_id not in orders for row in all_rows):raise ValidationError('Источники прибытия не соответствуют заказам рейса.')
    positive=[row for row in all_rows if row.actual_quantity>0]
    total=sum(row.actual_quantity for row in positive)
    if not total:raise ValidationError('В рейсе нет фактически поступивших товаров.')
    facts=[(r.pk,r.order_id,r.product_kind,r.product_id,r.original_quantity,r.actual_quantity,snapshot_name(r),
        r.cd.platform_id if r.cd_id else None,r.tech.brand_id if r.tech_id else None,
        r.tech.product_type_id if r.tech_id else None) for r in all_rows]
    signature=digest([trip.pk,trip.revision,arrival.pk,arrival.revision,arrival.arrived_at,
        sorted(arrival.reviewed_orders),orders,facts])
    return SourceSnapshot(trip,arrival,positive,signature,total,orders)


def source_data(row):
    planned=row._meta.model_name=='supplierorderbatchline'
    return dict(source_row_id=row.pk,arrival_row_id=None if planned else row.pk,
        trip_line_id=row.pk if planned else None,source_kind='planned' if planned else 'actual',product_kind=row.product_kind,
        product_id_snapshot=row.product_id,product_name_snapshot=snapshot_name(row),
        cd_id=row.cd_id,tech_id=row.tech_id,actual_quantity=row.actual_quantity)


def prepare_rows(snapshot):
    groups=list(CustomsGroup.objects.filter(active=True))
    by_platform={g.platform_id:g for g in groups if g.platform_id}
    by_type={g.product_type_id:g for g in groups if g.product_type_id}
    defaults=CustomsProductDefaults.objects.filter(Q(cd_id__in=[r.cd_id for r in snapshot.rows if r.cd_id])|
        Q(tech_id__in=[r.tech_id for r in snapshot.rows if r.tech_id]))
    profiles={('cd',p.cd_id) if p.cd_id else ('tech',p.tech_id):p for p in defaults}
    result={}
    for source in snapshot.rows:
        product=source.product
        group=by_platform.get(source.cd.platform_id) if source.cd_id else by_type.get(source.tech.product_type_id)
        profile=profiles.get((source.product_kind,source.product_id))
        values={f:'' for f in CUSTOMS_FIELDS};values['unit']='ШТ'
        values['ru_description']=snapshot_name(source)
        confirmed={'unit'}
        if source.tech_id:
            values.update(country='CHINA',material='МЕТАЛЛ / ПЛАСТИК',manufacturer=source.tech.brand.name if source.tech.brand_id else '')
        elif group:
            if group.medium in ('disc','cartridge'):
                values.update(country='AUSTRIA' if group.medium=='disc' else 'CHINA',material='ПЛАСТИК')
            values['ru_description']=group.ru_description or group.name
        # В справочник попадают только явно подтверждённые непустые значения.
        for owner in (group,profile):
            if owner:
                for field in CONFIRMABLE_FIELDS:
                    if field in owner.confirmed_fields and getattr(owner,field):
                        values[field]=getattr(owner,field);confirmed.add(field)
        if not values['en_description']:values['en_description']=values['ru_description']
        mode=('group',group.pk) if source.cd_id and group else (source.product_kind,source.product_id)
        key=digest([mode,values])
        if key not in result:
            result[key]={**values,'stable_key':key,'group_id':group.pk if group else None,
                'quantity':0,'expected_quantity':0,'sources':[],'confirmed_fields':sorted(confirmed),'edited_fields':[],
                'quantity_reason':'','quantity_confirmed':False,'quantity_approved_by_id':None,'quantity_approved_at':None,
                'review_notes':'Для платформы не настроена таможенная группа. Проверьте характеристики.' if source.cd_id and not group else ''}
        row=result[key];row['quantity']+=source.actual_quantity;row['expected_quantity']+=source.actual_quantity
        row['sources'].append(source_data(source));row['confirmed_fields']=sorted(set(row['confirmed_fields'])&confirmed)
    rows=sorted(result.values(),key=lambda r:(0 if r['sources'][0]['product_kind']=='tech' else 1,r['ru_description'].casefold(),r['stable_key']))
    if sum(r['quantity'] for r in rows)!=snapshot.total:raise ValidationError('Не совпадает сумма фактических источников.')
    return rows


def latest_manifest(trip_id):
    return CustomsManifest.objects.filter(trip_id=trip_id).order_by('-revision').first()


def manifest_rows(manifest):
    rows=[]
    for line in manifest.lines.prefetch_related('sources').all():
        fields=(*CUSTOMS_FIELDS,'stable_key','group_id','quantity','expected_quantity','confirmed_fields','edited_fields',
            'quantity_reason','quantity_confirmed','quantity_approved_by_id','quantity_approved_at','review_notes')
        row={f:getattr(line,f) for f in fields}
        row['sources']=[{f:getattr(s,f) for f in ('source_row_id','arrival_row_id','trip_line_id','source_kind','product_kind','product_id_snapshot',
            'product_name_snapshot','cd_id','tech_id','actual_quantity')} for s in line.sources.all()]
        rows.append(row)
    return rows


def row_warnings(rows):
    warnings=[]
    for index,row in enumerate(rows,1):
        issues=[]
        if 'en_description' not in row['confirmed_fields']:issues.append('Английское описание не подтверждено')
        if not row['hs_code']:issues.append('Не указан код ТН ВЭД')
        for field in ('country','material','manufacturer'):
            if not row[field]:issues.append('Не заполнено: '+LABELS[field])
            elif field not in row['confirmed_fields']:issues.append(LABELS[field]+' не подтверждено')
        if row['review_notes']:issues.append(row['review_notes'])
        if row['quantity']!=row['expected_quantity']:issues.append('Количество отличается от состава рейса')
        if issues:warnings.append(f'Строка {index}: '+'. '.join(issues))
    return warnings


def integer(value,label):
    text=str(value)
    if len(text)>19 or not text.isascii() or not text.isdecimal() or int(text)>9223372036854775807:
        raise ValidationError(label+': укажите целое неотрицательное количество.')
    return int(text)


def apply_edits(rows,posted,actor):
    if not isinstance(posted,list) or len(posted)!=len(rows):raise ValidationError('Передан неполный состав описи.')
    by_key={r.get('stable_key'):r for r in posted if isinstance(r,dict)}
    if len(by_key)!=len(rows) or set(by_key)!={r['stable_key'] for r in rows}:
        raise ValidationError('Состав или редакция описи изменились. Обновите страницу.')
    result=[]
    for index,original in enumerate(rows,1):
        row=dict(original);data=by_key[row['stable_key']];edited=set(row['edited_fields'])
        for field in CUSTOMS_FIELDS:
            value=data.get(field,row[field])
            if not isinstance(value,str):raise ValidationError(f'Строка {index}: {LABELS[field]} должно быть текстом.')
            value=value.strip()
            if value!=row[field]:edited.add(field)
            row[field]=value
        confirmed=data.get('confirmed_fields',row['confirmed_fields'])
        if not isinstance(confirmed,list) or any(f not in CONFIRMABLE_FIELDS or not row.get(f) for f in confirmed):
            raise ValidationError(f'Строка {index}: подтвердить можно только непустые характеристики.')
        edited.update(set(confirmed)-set(row['confirmed_fields']))
        row['confirmed_fields']=sorted(set(confirmed));row['edited_fields']=sorted(edited)
        row['quantity']=integer(data.get('quantity',row['quantity']),f'Строка {index}')
        reason=data.get('quantity_reason',row['quantity_reason'])
        if not isinstance(reason,str) or len(reason)>500:raise ValidationError('Причина корректировки: не более 500 символов.')
        row['quantity_reason']=reason.strip()
        if row['quantity']!=row['expected_quantity']:
            retained=(row['quantity']==original['quantity'] and original['quantity_confirmed'] and
                data.get('quantity_confirmed') is True and row['quantity_reason']==original['quantity_reason'] and original['quantity_approved_by_id'])
            if not retained:
                require(actor,'quantity')
                if data.get('quantity_confirmed') is not True or not row['quantity_reason']:
                    raise ValidationError(f'Строка {index}: отличие количества требует подтверждения и причины.')
                row['quantity_approved_by_id']=actor.pk;row['quantity_approved_at']=timezone.now()
            row['quantity_confirmed']=True
        else:
            row.update(quantity_confirmed=False,quantity_reason='',quantity_approved_by_id=None,quantity_approved_at=None)
        line=CustomsManifestLine(**{f:row[f] for f in CUSTOMS_FIELDS},confirmed_fields=row['confirmed_fields'])
        line.clean_fields(exclude=[f.name for f in line._meta.fields if f.name not in (*CUSTOMS_FIELDS,'confirmed_fields')]);line.clean()
        if not row['ru_description'] or not row['unit']:raise ValidationError(f'Строка {index}: заполните русское описание и единицу.')
        result.append(row)
    return result


def refresh_rows(old_rows,new_rows):
    # Перенос только взаимно однозначных сопоставлений. История спорных строк
    # остаётся в прежней редакции; новая явно требует ручной проверки.
    identities=lambda r:{(s['product_kind'],s['product_id_snapshot']) for s in r['sources']}
    matches=[]
    for row in new_rows:
        matches.append([i for i,old in enumerate(old_rows) if old['group_id']==row['group_id'] and identities(old)&identities(row)])
    for row,candidates in zip(new_rows,matches):
        if len(candidates)==1 and sum(candidates[0] in other for other in matches)==1:
            old=old_rows[candidates[0]]
            for field in old['edited_fields']:
                if field in CUSTOMS_FIELDS:row[field]=old[field]
            row['edited_fields']=list(old['edited_fields'])
            row['confirmed_fields']=sorted((set(row['confirmed_fields'])-set(old['edited_fields']))|
                (set(old['confirmed_fields'])&set(old['edited_fields'])))
            if identities(row)-identities(old):
                row['confirmed_fields']=sorted(set(row['confirmed_fields'])-set(old['edited_fields']))
                row['review_notes']+=' В группу добавлены новые товары: перепроверьте перенесённые характеристики.'
            if old['quantity']!=old['expected_quantity']:
                row['review_notes']+=' Предыдущая корректировка количества не перенесена: подтвердите новую при необходимости.'
        elif candidates:
            row['review_notes']+=' Неоднозначное объединение или разделение прежних строк. Проверьте описания и характеристики по истории.'
        elif any(identities(old)&identities(row) for old in old_rows):
            row['review_notes']+=' Изменена таможенная группа товаров. Проверьте ручные описания прежней редакции.'
    return new_rows


def persist(snapshot,rows,actor,action):
    require(actor,'change')
    # Проверяем покрытие каждого положительного источника ровно один раз.
    sources=[s for r in rows for s in r['sources']]
    ids=[s['source_row_id'] for s in sources]
    if len(ids)!=len(set(ids)) or set(ids)!={r.pk for r in snapshot.rows}:
        raise ValidationError('Не все фактические источники учтены ровно один раз.')
    if sum(s['actual_quantity'] for s in sources)!=snapshot.total:
        raise ValidationError('Не совпадает сумма количеств источников описи.')
    edited_total=integer(sum(r['quantity'] for r in rows),'Общее количество описи')
    previous=latest_manifest(snapshot.trip.pk)
    manifest=CustomsManifest.objects.create(trip=snapshot.trip,arrival=snapshot.arrival,source_kind=snapshot.source_kind,
        revision=previous.revision+1 if previous else 1,arrival_revision=snapshot.arrival.revision if snapshot.arrival else 0,
        trip_revision=snapshot.trip.revision,source_signature=snapshot.signature,arrived_at=snapshot.arrival.arrived_at if snapshot.arrival else None,
        source_total=snapshot.total,edited_total=edited_total,reviewed_order_ids=snapshot.orders,
        status='review' if row_warnings(rows) else 'prepared',created_by=actor)
    for index,row in enumerate(rows,1):
        fields=(*CUSTOMS_FIELDS,'group_id','stable_key','quantity','expected_quantity','confirmed_fields','edited_fields',
            'quantity_reason','quantity_confirmed','quantity_approved_by_id','quantity_approved_at','review_notes')
        line=CustomsManifestLine.objects.create(manifest=manifest,position=index,**{f:row[f] for f in fields})
        for source in row['sources']:CustomsManifestSource.objects.create(manifest=manifest,line=line,**source)
    CustomsEvent.objects.create(manifest=manifest,actor=actor,action=action,details={
        'source_total':snapshot.total,'edited_total':manifest.edited_total,'source_signature':snapshot.signature,
        'quantity_changes':[{'key':r['stable_key'],'actual':r['expected_quantity'],'declared':r['quantity'],
            'reason':r['quantity_reason'],'approved_by':r['quantity_approved_by_id']} for r in rows if r['quantity']!=r['expected_quantity']]})
    return manifest


@retry_database_lock
@transaction.atomic
def save_document(*,actor,trip_id,expected_revision,source_signature,rows,refresh=False,export=False,acknowledged=False):
    require(actor,'change')
    if export:require(actor,'download')
    snapshot=source_snapshot(trip_id,lock=True)
    previous=latest_manifest(trip_id)
    expected=integer(expected_revision,'Редакция')
    if expected!=(previous.revision if previous else 0):raise ValidationError('Опись уже изменена другим сотрудником. Обновите страницу.')
    baseline=previous.source_signature if previous else snapshot.signature
    if source_signature!=baseline:raise ValidationError('Исходная версия формы не совпадает. Обновите страницу.')
    old_rows=manifest_rows(previous) if previous else prepare_rows(snapshot)
    edited=apply_edits(old_rows,rows,actor)
    if refresh:
        edited=refresh_rows(edited,prepare_rows(snapshot))
    elif baseline!=snapshot.signature:
        raise ValidationError(STALE)
    if export and row_warnings(edited) and acknowledged is not True:
        raise ValidationError('Проверьте предупреждения и подтвердите их перед скачиванием Excel.')
    manifest=persist(snapshot,edited,actor,'refreshed' if refresh else 'saved')
    if export:
        from .customs_excel import export_manifest
        return manifest,export_manifest(actor=actor,manifest=manifest,acknowledged=acknowledged)
    return manifest,None


@retry_database_lock
@transaction.atomic
def save_defaults(*,actor,trip_id,expected_revision,source_signature,key,data,target,product_kind=None,product_id=None):
    require(actor,'rules')
    snapshot=source_snapshot(trip_id,lock=True);manifest=latest_manifest(trip_id)
    if not manifest or manifest.revision!=integer(expected_revision,'Редакция') or manifest.source_signature!=snapshot.signature or source_signature!=snapshot.signature:
        raise ValidationError('Опись изменилась или устарела. Сначала сохраните актуальную редакцию.')
    rows=manifest_rows(manifest);original=next((r for r in rows if r['stable_key']==key),None)
    if not original:raise ValidationError('Строка описи не найдена.')
    edited=apply_edits([original],[data],actor)[0]
    confirmed=edited['confirmed_fields']
    if not confirmed:raise ValidationError('Сначала подтвердите проверенные непустые характеристики.')
    if target=='group':
        if not original['group_id']:raise ValidationError('Для строки не задана таможенная группа.')
        owner=CustomsGroup.objects.select_for_update().get(pk=original['group_id'])
    elif target=='product':
        reference=(product_kind,integer(product_id,'Товар'))
        if reference not in {(s['product_kind'],s['product_id_snapshot']) for s in original['sources']}:
            raise ValidationError('Товар не относится к источникам этой строки.')
        lookup={reference[0]+'_id':reference[1]}
        owner=CustomsProductDefaults.objects.select_for_update().filter(**lookup).first() or CustomsProductDefaults(**lookup)
    else:raise ValidationError('Выберите товар или группу для сохранения характеристик.')
    before={f:getattr(owner,f) for f in CUSTOMS_FIELDS}
    for field in confirmed:setattr(owner,field,edited[field])
    owner.confirmed_fields=sorted(set(owner.confirmed_fields)|set(confirmed));owner.updated_by=actor
    owner.full_clean();owner.save()
    CustomsEvent.objects.create(actor=actor,manifest=manifest,action='defaults_saved',details={
        'target':target,'id':owner.pk,'before':before,'after':{f:getattr(owner,f) for f in CUSTOMS_FIELDS}})
    return owner


@retry_database_lock
@transaction.atomic
def download_existing(*,actor,trip_id,expected_revision,source_signature,acknowledged=False):
    """Право скачивания не даёт права незаметно сохранять переданные правки."""
    require(actor,'download');snapshot=source_snapshot(trip_id,lock=True);manifest=latest_manifest(trip_id)
    if not manifest or manifest.revision!=integer(expected_revision,'Редакция'):
        raise ValidationError('Сначала сохраните актуальную редакцию описи.')
    if manifest.source_signature!=snapshot.signature or source_signature!=manifest.source_signature:
        raise ValidationError(STALE)
    from .customs_excel import export_manifest
    return manifest,export_manifest(actor=actor,manifest=manifest,acknowledged=acknowledged)
