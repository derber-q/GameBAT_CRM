"""Страницы прибытия, сверки и общей финализации рейса."""
from decimal import Decimal
from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction, OperationalError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST, require_http_methods
from core.decorators import permission_required_any
from catalog.product_identifiers import set_product_weight
from .models import SupplierOrderBatch, CustomerProcurementOrder
from .arrival_models import TripArrival
from .arrival import (ArrivalForm, arrival_preview, confirm_arrival, unconfirm_arrival,
    require_arrival_permissions, reduce_received)
from .arrival_documents import build_draft, form_rows, create_arrival_sale, create_arrival_supply
from .arrival_finalization import readiness, finalization_rows, finalize_arrival, distribute_arrival
from .operation_changes import ChangesConfirmationRequired


def missing_weights(batch):
    products={}
    for line in batch.lines.select_related('cd','tech').filter(quantity__gt=0):
        product=line.product
        if not product.weight_grams or product.weight_grams<=0:
            products[(line.product_kind,product.pk)]=product
    return [{'kind':kind,'product':product,'field_name':f'weight_{kind}_{pk}'}
            for (kind,pk),product in products.items()]


def panel_context(request, batch):
    arrival=TripArrival.objects.filter(trip=batch).first()
    initial=request.session.get(f'arrival_parameters_{batch.pk}',{})
    return {'arrival':arrival,'arrival_form':ArrivalForm(initial=initial),
        'arrival_weights':missing_weights(batch) if not arrival or not arrival.arrived else [],
        'arrival_preview':request.session.get(f'arrival_preview_{batch.pk}'),
        'arrival_readiness':readiness(arrival) if arrival and arrival.arrived else None,
        'arrival_can_manage':all(request.user.has_perm(p) for p in
            ('orders.view_order_detail','orders.generate_supplier_orders','price.view_supplier_prices')),
        'arrival_can_finalize':request.user.has_perm('supplies.finalize_supply'),
        'arrival_can_unset':bool(arrival and arrival.arrived and not batch.trip_orders.filter(operations__calculation__arrival_id=arrival.pk).exists())}


@require_POST
@permission_required_any('orders.generate_supplier_orders')
def update_arrival(request, pk):
    batch=get_object_or_404(SupplierOrderBatch,pk=pk,price_list__isnull=False)
    require_arrival_permissions(request.user)
    action=request.POST.get('action')
    try:
        if action=='unset':
            arrival=get_object_or_404(TripArrival,trip=batch)
            unconfirm_arrival(actor=request.user,arrival_id=arrival.pk,expected_revision=request.POST.get('revision'))
            messages.success(request,'Отметка прибытия снята. Курсы и доставка доступны для нового расчёта.')
        else:
            parameters={name:request.POST.get(name,'') for name in ArrivalForm.base_fields}
            request.session[f'arrival_parameters_{batch.pk}']=parameters
            with transaction.atomic():
                for row in missing_weights(batch):
                    weight=forms.IntegerField(min_value=1).clean(request.POST.get(row['field_name']))
                    set_product_weight(actor=request.user,product_kind=row['kind'],product_id=row['product'].pk,weight_grams=weight)
                if action=='preview':
                    result=arrival_preview(actor=request.user,batch_id=pk,**parameters)
                    request.session[f'arrival_preview_{pk}']={key:str(result[key]) for key in ('purchase_total','control_total','actual_delivery')}
                elif action=='confirm':
                    confirm_arrival(actor=request.user,batch_id=pk,expected_revision=request.POST.get('revision'),**parameters)
                    request.session.pop(f'arrival_preview_{pk}',None)
                    messages.success(request,'Рейс приехал. Курсы, фактическая доставка и исходные закупочные позиции зафиксированы.')
                else:
                    raise ValidationError('Неизвестное действие с прибытием рейса.')
    except (ValidationError,OperationalError) as exc:
        messages.error(request,' '.join(exc.messages) if isinstance(exc,ValidationError) else 'База занята. Повторите действие.')
    return redirect('orders:trip_detail',pk=pk)


@require_http_methods(['GET','POST'])
@permission_required_any('orders.view_order_detail')
def prepare_document(request, pk):
    from .fulfillment_views import DRAFTS, _metadata_forms, _save_metadata
    order=get_object_or_404(CustomerProcurementOrder,pk=pk)
    try:
        draft=build_draft(actor=request.user,order=order)
    except ValidationError as exc:
        messages.error(request,' '.join(exc.messages))
        return redirect('orders:trip_detail',pk=order.trip_id) if order.trip_id else redirect('orders:detail',pk=pk)
    metadata=_metadata_forms(order,request.POST if request.method=='POST' else None)
    if metadata and (request.method!='POST' or not all([row['form'].is_valid() for row in metadata])):
        return render(request,'orders/arrival_prepare.html',{'order':order,'metadata':metadata})
    if metadata:
        try:
            with transaction.atomic(): _save_metadata(request.user,metadata)
        except ValidationError as exc:
            messages.error(request,' '.join(exc.messages))
            return render(request,'orders/arrival_prepare.html',{'order':order,'metadata':metadata})
    drafts=request.session.get(DRAFTS,{})
    drafts[draft['key']]=draft
    request.session[DRAFTS]=dict(list(drafts.items())[-20:])
    from django.urls import reverse
    destination='supplies:create' if order.is_stock_order else 'sales:create'
    return redirect(f'{reverse(destination)}?trip_draft={draft["key"]}')


@require_http_methods(['GET','POST'])
@permission_required_any('orders.view_order_detail')
def receipt(request, pk):
    from .fulfillment import require_permissions
    order=get_object_or_404(CustomerProcurementOrder,pk=pk)
    require_permissions(request.user,order)
    arrival=get_object_or_404(TripArrival,trip_id=order.trip_id,arrived_at__isnull=False)
    if request.method=='POST':
        try:
            ids=request.POST.getlist('cost_row')
            quantities=request.POST.getlist('actual_quantity')
            if len(ids)!=len(quantities) or len(set(ids))!=len(ids): raise ValidationError('Состав формы повреждён.')
            reduce_received(actor=request.user,arrival_id=arrival.pk,order_id=order.pk,
                quantities=dict(zip(ids,quantities)),expected_revision=request.POST.get('revision'))
        except (ValidationError,OperationalError) as exc:
            messages.error(request,' '.join(exc.messages) if isinstance(exc,ValidationError) else 'База занята. Повторите сверку.')
        else: messages.success(request,'Состав сверен. Вся фактическая доставка рейса перераспределена.')
        return redirect('orders:arrival_receipt',pk=pk)
    return render(request,'orders/arrival_receipt.html',{'order':order,'arrival':arrival,
        'rows':arrival.rows.filter(order=order).select_related('cd','tech','supplier'),
        'operation':order.operations.filter(active=True).select_related('sale','supply').first()})


def _posted_rows(request, arrival, order, *, supply=False):
    from sales.views import _parse_lines
    from supplies.views import _parse_supply_post
    if supply:
        lines,expenses,transport=_parse_supply_post(request.POST)
        amount=forms.DecimalField(max_digits=20,decimal_places=2,min_value=0)
        if any(expense.get('name') or amount.clean(expense.get('amount') or 0) for expense in expenses) or amount.clean(transport or 0):
            raise ValidationError('Фактическая доставка учитывается общей финализацией рейса.')
    else: lines=_parse_lines(request.POST)
    references=request.POST.getlist('trip_row')
    if len(lines)!=len(references): raise ValidationError('Строки формы повреждены. Обновите страницу.')
    for row,reference in zip(lines,references): row['trip_row']=reference
    return lines


def sale_form(request, order, draft):
    from sales.forms import SaleCreateForm
    from sales.views import _sale_destination
    from warehouse.form_defaults import single_warehouse_id
    arrival=get_object_or_404(TripArrival,pk=draft['arrival_id'])
    draft=_refresh_draft(request,order,draft,arrival)
    initial={'warehouse':order.payment_warehouse_id or single_warehouse_id(), 'sale_type':'wholesale',
        'price_type':'wholesale','payment_method':'cash_postpay','customer':str(order.partner_id) if order.partner_id else 'custom',
        'custom_partner_name':'' if order.partner_id else order.partner_name_snapshot or order.recipient,'note':order.comment}
    form=SaleCreateForm(request.POST or None,initial=initial)
    for name in ('sale_type','price_type','customer','custom_partner_name','cash_received_amount'): form.fields[name].disabled=True
    form.fields['cash_received_amount'].help_text='Оплату подтвердите в созданной продаже после общей финализации рейса.'
    form.fields['payment_method'].choices=[choice for choice in form.fields['payment_method'].choices if choice[0] in ('cash_postpay','bank_transfer_postpay')]
    rows,confirmation=form_rows(arrival,order.pk),None
    if request.method=='POST' and form.is_valid():
        try:
            lines=_posted_rows(request,arrival,order)
            sale=create_arrival_sale(actor=request.user,arrival_id=arrival.pk,order_id=order.pk,
                expected_revision=draft['arrival_revision'],warehouse_id=form.cleaned_data['warehouse'].pk,
                lines=lines,draft_key=draft['key'],payment_method=form.cleaned_data['payment_method'],
                note=form.cleaned_data['note'],changes_confirmation=request.POST.get('operation_confirmation',''))
        except ChangesConfirmationRequired as exc:
            rows=exc.rows; confirmation={'changes':exc.changes,'token':exc.token}
        except (ValidationError,OperationalError) as exc:
            form.add_error(None,exc if isinstance(exc,ValidationError) else 'База занята. Повторите сохранение.')
        else:
            if sale:return _sale_destination(request,sale)
            messages.success(request,'Все товары заказа отмечены как непоступившие. Пустая продажа не создана.')
            return redirect('orders:trip_detail',pk=order.trip_id)
    return render(request,'sales/create.html',{'form':form,'creation_key':draft['key'],'trip_draft':draft,
        'trip_order':order,'trip_arrival':arrival,'initial_items':rows,'operation_confirmation':confirmation,
        'consignment_options':[],'can_view_sales':request.user.has_perm('sales.view_sales')})


def supply_form(request, order, draft):
    from supplies.views import _supplier_options
    from warehouse.models import Warehouse
    from warehouse.form_defaults import single_warehouse_id
    arrival=get_object_or_404(TripArrival,pk=draft['arrival_id'])
    draft=_refresh_draft(request,order,draft,arrival)
    rows=[{**row,'purchase_unit_cost':row['unit_cost']} for row in form_rows(arrival,order.pk)]
    confirmation=None
    if request.method=='POST':
        try:
            lines=_posted_rows(request,arrival,order,supply=True)
            supply=create_arrival_supply(actor=request.user,arrival_id=arrival.pk,order_id=order.pk,
                expected_revision=draft['arrival_revision'],warehouse_id=request.POST.get('warehouse_id'),
                lines=lines,draft_key=draft['key'],changes_confirmation=request.POST.get('operation_confirmation',''))
        except ChangesConfirmationRequired as exc:
            rows=[{**row,'purchase_unit_cost':row['unit_cost']} for row in exc.rows]
            confirmation={'changes':exc.changes,'token':exc.token}
        except (ValidationError,OperationalError) as exc:
            messages.error(request,' '.join(exc.messages) if isinstance(exc,ValidationError) else 'База занята. Повторите сохранение.')
        else:
            if supply:return redirect('supplies:detail',pk=supply.pk)
            messages.success(request,'Заказ отмечен как непоступивший. Пустой приход не создан.')
            return redirect('orders:trip_detail',pk=order.trip_id)
    return render(request,'supplies/create.html',{'warehouses':Warehouse.objects.all(),'suppliers':_supplier_options(request.user),
        'selected_warehouse':str(request.POST.get('warehouse_id') or single_warehouse_id() or ''),
        'initial_supply_lines':rows,'initial_expenses':[],'weight_transport_cost':'0','trip_draft':draft,
        'trip_order':order,'trip_arrival':arrival,'operation_confirmation':confirmation})


def _prices(post, arrival):
    if any(name.startswith('price_') for name in post):
        raise ValidationError('Оптовая цена и цена Авито подтверждаются при приёмке прихода. Обновите финализацию рейса.')
    return {}


@require_http_methods(['GET','POST'])
@permission_required_any('supplies.finalize_supply')
def finalization(request, pk):
    from supplies.views import _parse_finalization_post
    require_arrival_permissions(request.user,finalization=True)
    arrival=get_object_or_404(TripArrival,trip_id=pk,arrived_at__isnull=False)
    if request.method=='POST':
        try:
            finalize_arrival(actor=request.user,arrival_id=arrival.pk,expected_revision=request.POST.get('revision_number'),
                raw_rows=_parse_finalization_post(request.POST),proposed_prices=_prices(request.POST,arrival))
        except (ValidationError,OperationalError) as exc:
            messages.error(request,' '.join(exc.messages) if isinstance(exc,ValidationError) else 'База занята. Обновите финализацию.')
            return redirect('orders:arrival_finalization',pk=pk)
        messages.success(request,'Итоговая себестоимость рейса зафиксирована. Продажи и приходы завершите отдельно.')
        return redirect('orders:trip_detail',pk=pk)
    state=readiness(arrival)
    if arrival.finalized or not state['ready']:
        for error in state['errors'] if not arrival.finalized else ['Рейс уже финализирован.']:
            messages.error(request,error)
        return redirect('orders:trip_detail',pk=pk)
    return render(request,'orders/arrival_finalization.html',{'arrival':arrival,'batch':arrival.trip,
        'rows':finalization_rows(arrival),'initial_penalty':Decimal('0'),
        'distribution_help':'Ручное изменение фиксирует строку. Автораспределение переносит текущий остаток между выбранными единицами этого рейса. Складские дополнения продаж не участвуют.'})


@require_POST
@permission_required_any('supplies.finalize_supply')
def finalization_auto(request, pk):
    from supplies.views import _parse_finalization_post
    arrival=get_object_or_404(TripArrival,trip_id=pk)
    try:
        selected=set()
        for raw in request.POST.getlist('selected_product'):
            kind,separator,pk_value=raw.partition(':')
            if separator:selected.add((kind,int(pk_value)))
        result=distribute_arrival(actor=request.user,arrival_id=arrival.pk,
            expected_revision=request.POST.get('revision_number'),raw_rows=_parse_finalization_post(request.POST),selected_keys=selected)
    except (ValidationError,ValueError) as exc:
        return JsonResponse({'ok':False,'error':' '.join(exc.messages) if isinstance(exc,ValidationError) else 'Некорректные строки для распределения.'},status=400)
    return JsonResponse({'ok':True,'penalty':'0.00','rows':[
        {'key':f'{row.product_type}:{row.product_id}','corrected_cost':f'{row.corrected_cost:.2f}',
         'change_source':row.change_source,'row_penalty':f'{row.row_penalty:.2f}'} for row in result]})


@require_POST
@permission_required_any('supplies.add_supply')
def post_supply(request, pk):
    from supplies.models import Supply
    from .arrival_finalization import prepare_supply_price_review
    get_object_or_404(Supply,pk=pk,trip_operation__calculation__has_key='arrival_id')
    try:
        revision=forms.IntegerField(min_value=1).clean(request.POST.get('revision_number'))
        names,amounts=request.POST.getlist('expense_name'),request.POST.getlist('expense_amount')
        if len(names)!=len(amounts):raise ValidationError('Состав дополнительных расходов повреждён.')
        supply=prepare_supply_price_review(actor=request.user,supply_id=pk,
            expected_revision_number=revision,independent_expenses=[{'name':name,'amount':amount} for name,amount in zip(names,amounts)])
    except (ValidationError,OperationalError) as exc:
        messages.error(request,' '.join(exc.messages) if isinstance(exc,ValidationError) else 'База занята. Повторите проведение.')
    else:
        return redirect('supplies:price_review',pk=pk)
    return redirect('supplies:detail',pk=pk)


def _refresh_draft(request, order, draft, arrival):
    if request.method=='GET' and draft['arrival_revision']!=arrival.revision:
        from .fulfillment_views import DRAFTS
        current=build_draft(actor=request.user,order=order)
        current['key']=draft['key']
        drafts=request.session.get(DRAFTS,{})
        drafts[current['key']]=current
        request.session[DRAFTS]=drafts
        return current
    return draft
