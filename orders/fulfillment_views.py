"""Общие реквизиты и переход из заказа в форму документа прибывшего рейса."""

from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_http_methods

from core.decorators import permission_required_any
from catalog.models import BarcodeRegistry
from catalog.game_codes import requires_game_codes, normalize_game_codes, set_game_codes
from catalog.product_identifiers import add_product_barcode, set_product_weight
from .models import CustomerProcurementOrder
from .fulfillment import require_permissions


DRAFTS = 'trip_operation_drafts'


def _metadata_forms(order, data=None):
    result, seen = [], set()
    if not order.is_stock_order:
        return result
    for item in order.items.select_related('cd__platform', 'tech').order_by('pk'):
        product, kind = item.product, item.product_kind
        identity = (kind, product.pk)
        if not item.quantity or identity in seen:
            continue
        seen.add(identity)
        fields = {}
        if not product.weight_grams:
            fields['weight'] = forms.IntegerField(label='Вес, г', min_value=1, max_value=2147483647)
        if not BarcodeRegistry.objects.filter(**{kind + '_id': product.pk}).exists():
            fields['barcode'] = forms.CharField(label='Штрихкод (необязательно)', required=False, max_length=64)
        if requires_game_codes(product) and not product.cusa_ppsa_code.strip():
            fields['codes'] = forms.CharField(label='CUSA/PPSA через запятую', max_length=255)
        if fields:
            form = forms.Form(data, prefix=f'{kind}-{product.pk}')
            form.fields.update(fields)
            result.append({'product': product, 'kind': kind, 'form': form})
    return result


def _save_metadata(actor, rows):
    for row in rows:
        product, kind, values = row['product'], row['kind'], row['form'].cleaned_data
        for key, suffix in (('weight', 'weight'), ('barcode', 'barcode')):
            if values.get(key) and not actor.has_perm(f'catalog.change_{kind}_{suffix}'):
                raise PermissionDenied(f'Нет права изменения поля «{row["form"].fields[key].label}».')
        if values.get('weight'):
            set_product_weight(actor=actor, product_kind=kind, product_id=product.pk, weight_grams=values['weight'])
        if values.get('barcode'):
            add_product_barcode(actor=actor, product_kind=kind, product_id=product.pk, value=values['barcode'])
        if values.get('codes'):
            set_game_codes(actor=actor, product_id=product.pk, value=normalize_game_codes(values['codes']))


@require_http_methods(['GET', 'POST'])
@permission_required_any('orders.view_order_detail')
def prepare(request, pk):
    from .arrival_views import prepare_document
    return prepare_document(request,pk)


def _draft(request):
    from .arrival_models import TripArrival
    key=request.POST.get('trip_draft') or request.GET.get('trip_draft')
    draft=request.session.get(DRAFTS,{}).get(key)
    if not draft or not draft.get('arrival_id'):
        raise ValidationError('Откройте новую форму из заказа после подтверждения прибытия рейса.')
    order=get_object_or_404(CustomerProcurementOrder,pk=draft['order_id'])
    require_permissions(request.user,order)
    if not TripArrival.objects.filter(pk=draft['arrival_id'],trip_id=order.trip_id,arrived_at__isnull=False).exists():
        raise ValidationError('Прибытие рейса не подтверждено. Откройте страницу рейса.')
    return order,draft


def sale_create(request):
    try:
        order,draft=_draft(request)
    except ValidationError as exc:
        messages.error(request,' '.join(exc.messages))
        return redirect('orders:list')
    if order.is_stock_order:
        raise PermissionDenied('Для складского заказа оформляется приход.')
    from .arrival_views import sale_form
    return sale_form(request,order,draft)


def supply_create(request):
    try:
        order,draft=_draft(request)
    except ValidationError as exc:
        messages.error(request,' '.join(exc.messages))
        return redirect('orders:list')
    if not order.is_stock_order:
        raise PermissionDenied('Для клиентского заказа оформляется продажа.')
    from .arrival_views import supply_form
    return supply_form(request,order,draft)
