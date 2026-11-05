"""HTML/JSON редактор и защищённые исторические файлы таможенной описи."""
import json
from hashlib import sha256
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction,OperationalError
from django.http import JsonResponse,FileResponse,Http404
from django.shortcuts import render,get_object_or_404,redirect
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods,require_GET
from core.decorators import permission_required_all
from .models import SupplierOrderBatch
from .customs_models import CustomsGroup,CustomsEvent,CustomsManifest,CustomsManifestExport,CUSTOMS_FIELDS,CONFIRMABLE_FIELDS
from .customs_service import (source_snapshot,prepare_rows,manifest_rows,latest_manifest,row_warnings,save_document,
    save_defaults,download_existing,require,STALE,LABELS)
from .customs_forms import CustomsGroupForm


def ui_rows(rows):
    for row in rows:
        row['confirmed_json']=json.dumps(row['confirmed_fields'])
        row['verified']=all(f in row['confirmed_fields'] for f in CONFIRMABLE_FIELDS if row[f])
        row['cells']=[{'field':f,'label':LABELS[f],'value':row[f]} for f in CUSTOMS_FIELDS if f not in ('number','unit')]
        products={}
        for source in row['sources']:
            key=(source['product_kind'],source['product_id_snapshot'])
            products[key]={'key':f'{key[0]}:{key[1]}','name':source['product_name_snapshot']}
        row['products']=list(products.values())
    return rows


@never_cache
@require_http_methods(['GET','POST'])
@permission_required_all('orders.view_customs_manifest')
def editor(request,pk):
    trip=get_object_or_404(SupplierOrderBatch.objects.trips(),pk=pk)
    if request.method=='POST':
        try:
            raw=request.POST.get('payload','')
            if len(raw)>2000000:raise ValidationError('Данные описи слишком большие; сократите описания.')
            data=json.loads(raw)
            if not isinstance(data,dict):raise ValidationError('Не удалось прочитать опись.')
            action=data.get('action','save')
            common=dict(actor=request.user,trip_id=pk,expected_revision=data.get('revision'),source_signature=data.get('source_signature'))
            if action=='defaults':
                product=data.get('product','').split(':')
                owner=save_defaults(**common,key=data.get('key'),data=data.get('row'),target=data.get('target'),
                    product_kind=product[0] if len(product)==2 else None,product_id=product[1] if len(product)==2 else None)
                return JsonResponse({'ok':True,'message':'Проверенные значения сохранены для будущих рейсов. Текущая опись не изменена.'})
            if action not in ('save','refresh','download'):raise ValidationError('Неизвестное действие описи.')
            if action=='download' and not request.user.has_perm('orders.change_customs_manifest'):
                manifest,export=download_existing(**common,acknowledged=data.get('acknowledged') is True)
            else:
                require(request.user,'change')
                manifest,export=save_document(**common,rows=data.get('rows'),refresh=action=='refresh',
                    export=action=='download',acknowledged=data.get('acknowledged') is True)
            return JsonResponse({'ok':True,'revision':manifest.revision,'source_signature':manifest.source_signature,
                'message':f'Сохранена редакция {manifest.revision}.',
                'warnings':row_warnings(manifest_rows(manifest)),
                'refresh_url':reverse('orders:customs',args=[pk]) if action=='refresh' else '',
                'download_url':reverse('orders:customs_download',args=[export.pk]) if export else ''})
        except (ValueError,TypeError,AttributeError,ValidationError,OperationalError) as exc:
            text=' '.join(exc.messages) if isinstance(exc,ValidationError) else (
                'База занята. Повторите сохранение.' if isinstance(exc,OperationalError) else 'Проверьте формат данных описи.')
            return JsonResponse({'ok':False,'error':text},status=400)
    manifest=latest_manifest(pk);historical=False
    if request.GET.get('revision'):
        try:revision=int(request.GET['revision'])
        except (ValueError,TypeError):raise Http404
        if revision<1 or revision>2147483647:raise Http404
        manifest=get_object_or_404(CustomsManifest,trip=trip,revision=revision);historical=True
    snapshot=None;error='';stale=False
    try:snapshot=source_snapshot(pk)
    except ValidationError as exc:error=' '.join(exc.messages)
    if manifest:
        rows=manifest_rows(manifest)
        stale=bool(error or snapshot.signature!=manifest.source_signature)
    else:rows=prepare_rows(snapshot) if snapshot else []
    history=trip.customs_manifests.select_related('created_by').prefetch_related('exports').order_by('-revision')[:30]
    return render(request,'orders/customs.html',{'trip':trip,'manifest':manifest,'snapshot':snapshot,'rows':ui_rows(rows),
        'source_error':error,'stale':stale,'stale_message':STALE,'warnings':row_warnings(rows),
        'revision':manifest.revision if manifest else 0,'source_signature':manifest.source_signature if manifest else (snapshot.signature if snapshot else ''),
        'historical':historical,
        'display_arrived_at':manifest.arrived_at if historical else (snapshot.arrival.arrived_at if snapshot and snapshot.arrival else None),
        'display_arrival_revision':manifest.arrival_revision if historical else (snapshot.arrival.revision if snapshot and snapshot.arrival else None),
        'quantity_label':'Количество по составу рейса' if (manifest.source_kind if historical else (snapshot.source_kind if snapshot else (manifest.source_kind if manifest else 'actual'))) == 'planned' else 'Фактически поступило',
        'total':sum(r['quantity'] for r in rows),'expected_total':manifest.source_total if historical else (snapshot.total if snapshot else (manifest.source_total if manifest else 0)),
        'can_edit':not historical and request.user.has_perm('orders.change_customs_manifest'),
        'can_download':request.user.has_perm('orders.download_customs_manifest'),
        'can_rules':not historical and request.user.has_perm('orders.manage_customs_rules'),
        'can_quantity':request.user.has_perm('orders.approve_customs_quantity'),'history':history})


@never_cache
@require_GET
@permission_required_all('orders.view_customs_manifest','orders.download_customs_manifest')
def download(request,pk):
    item=get_object_or_404(CustomsManifestExport.objects.select_related('manifest'),pk=pk)
    if not item.file or not item.file.storage.exists(item.file.name):raise Http404('Сохранённый файл описи отсутствует.')
    source=item.file.open('rb');digest=sha256();size=0
    try:
        for part in iter(lambda:source.read(1024*1024),b''):digest.update(part);size+=len(part)
        if digest.hexdigest()!=item.sha256 or size!=item.size:raise Http404('Проверка целостности файла описи не пройдена.')
        source.seek(0)
        return FileResponse(source,as_attachment=True,filename=item.filename,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    except Exception:source.close();raise


@never_cache
@require_http_methods(['GET','POST'])
@permission_required_all('orders.view_customs_manifest','orders.manage_customs_rules')
def rules(request,pk=None):
    owner=get_object_or_404(CustomsGroup,pk=pk) if pk else None
    form=CustomsGroupForm(request.POST if request.method=='POST' else None,instance=owner)
    if request.method=='POST' and form.is_valid():
        try:
            with transaction.atomic():
                current=CustomsGroup.objects.select_for_update().get(pk=pk) if pk else None
                if current and current.updated_at.isoformat()!=form.cleaned_data['expected_updated']:
                    raise ValidationError('Правило изменено другим сотрудником. Обновите страницу.')
                rule=form.save(commit=False);rule.updated_by=request.user;rule.full_clean();rule.save()
                CustomsEvent.objects.create(actor=request.user,action='group_saved',details={'group_id':rule.pk,
                    'platform_id':rule.platform_id,'product_type_id':rule.product_type_id,'confirmed_fields':rule.confirmed_fields})
        except (ValidationError,OperationalError) as exc:
            form.add_error(None,exc if isinstance(exc,ValidationError) else 'База занята. Повторите сохранение.')
        else:
            messages.success(request,'Таможенное правило сохранено. Изменения действуют при новой подготовке или обновлении описи.')
            return redirect('orders:customs_rules')
    return render(request,'orders/customs_rules.html',{'form':form,'groups':CustomsGroup.objects.select_related('platform','product_type'),
        'editing':owner})
