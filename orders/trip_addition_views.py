"""Пошаговая форма дополнительных товаров текущего рейса."""
from uuid import uuid4, UUID
from decimal import Decimal
from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import OperationalError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from core.decorators import permission_required_all
from catalog.models import CD, Tech
from catalog.product_search import filter_products_by_text
from partners.models import Partner, Supplier
from partners.customers import PartnerMultipleChoiceField
from price.models import ProcurementPriceList
from .models import SupplierOrderBatch
from .trip_additions import prepare_addition, commit_addition, addition_price_list
from .trips import MANAGE_PERMISSIONS

PERMISSIONS = (*MANAGE_PERMISSIONS, 'orders.create_order')


class AdditionLineForm(forms.Form):
    label = forms.CharField(label='Товар', required=False, widget=forms.TextInput(attrs={'data-addition-search': True, 'autocomplete': 'off'}))
    product = forms.CharField(widget=forms.HiddenInput)
    supplier = forms.ModelChoiceField(label='Поставщик', queryset=Supplier.objects.all())
    aed = forms.DecimalField(label='Цена поставщика, AED', max_digits=20, decimal_places=6, min_value=Decimal('0.000001'))
    customer_price = forms.DecimalField(label='Цена для заказчика, ₽', max_digits=20, decimal_places=2, min_value=0)
    stock_qty = forms.IntegerField(label='На склад', min_value=0, max_value=2147483647, initial=0)
    customer_qty = forms.IntegerField(label='Заказчикам', min_value=0, max_value=2147483647, initial=0)


LineFormSet = forms.formset_factory(AdditionLineForm, extra=0, min_num=1, max_num=100, validate_min=True, validate_max=True, can_delete=True)


class AdditionPartnersForm(forms.Form):
    partners = PartnerMultipleChoiceField(label='Заказчики', queryset=Partner.objects.filter(is_archived=False), required=False,
                                              widget=forms.CheckboxSelectMultiple)


class AdditionCalculationForm(forms.Form):
    calculation_price_list = forms.ModelChoiceField(label='Курсы и доставка для этой партии',
        queryset=ProcurementPriceList.objects.filter(is_trip_addition=False))


def _url(pk, draft_id, step):
    return f"{reverse('orders:trip_addition', args=(pk,))}?draft={draft_id}&step={step}"


@never_cache
@require_POST
@permission_required_all(*PERMISSIONS)
def calculation(request, pk):
    batch = get_object_or_404(SupplierOrderBatch.objects.trips().select_related('price_list'), pk=pk)
    formset = LineFormSet(request.POST, prefix='lines')
    if not formset.management_form.is_valid() or formset.total_form_count() > 100:
        return JsonResponse({'error': 'Некорректный состав формы.'}, status=400)
    results = []
    for index, form in enumerate(formset):
        if not form.is_valid() or form.cleaned_data.get('DELETE'):
            continue
        source = {key: str(form.cleaned_data[key]) for key in ('product', 'aed', 'customer_price', 'stock_qty', 'customer_qty')}
        source['supplier'] = form.cleaned_data['supplier'].pk
        try:
            rows, _, _, _ = prepare_addition(batch=batch, lines=[source], require_partners=False,
                calculation_price_list_id=request.POST.get('calculation_price_list') or None)
            results.append({'index': index, **{key: str(rows[0][key]) for key in ('base', 'delivery', 'cost', 'unit_profit', 'expected_profit')}})
        except ValidationError as exc:
            results.append({'index': index, 'error': ' '.join(exc.messages)})
    return JsonResponse({'rows': results})


@never_cache
@permission_required_all(*PERMISSIONS)
def product_search(request, pk):
    get_object_or_404(SupplierOrderBatch.objects.trips(), pk=pk)
    query = str(request.GET.get('q') or '').strip()
    if len(query) < 2:
        return JsonResponse({'results': []})
    results = []
    for kind, model, group in (('cd', CD, 'platform'), ('tech', Tech, 'product_type')):
        for product in filter_products_by_text(model.objects.active(), query, product_kind=kind).select_related(group).order_by('name')[:20]:
            results.append({'value': f'{kind}:{product.pk}', 'type': kind, 'id': product.pk, 'sku': product.sku,
                            'availability_label': 'Каталог', 'available': '—',
                            'label': f'{product.name} · {getattr(product, group).name} · {product.sku}'})
    return JsonResponse({'results': results})


@never_cache
@permission_required_all(*PERMISSIONS)
def addition(request, pk):
    batch = get_object_or_404(SupplierOrderBatch.objects.trips().select_related('price_list'), pk=pk)
    try:
        draft_id = str(UUID(request.GET.get('draft', '')))
        step = max(1, min(4, int(request.GET.get('step', '1'))))
    except (ValueError, TypeError):
        return redirect(_url(pk, str(uuid4()), 1))
    session_key = f'trip_addition_{pk}_{draft_id}'
    draft = request.session.get(session_key, {})
    calculation_id = draft.get('calculation_price_list_id')
    calculation_form = None
    if not batch.price_list_id:
        calculation_form = AdditionCalculationForm(request.POST if step == 1 and request.method == 'POST' else None,
            initial={'calculation_price_list': calculation_id or ProcurementPriceList.objects.filter(
                is_trip_addition=False).values_list('pk', flat=True).first()})
    if step > 1 and not draft.get('lines'):
        return redirect(_url(pk, draft_id, 1))
    if step > 2 and 'partner_ids' not in draft:
        return redirect(_url(pk, draft_id, 2))
    if step == 4 and 'allocations' not in draft:
        return redirect(_url(pk, draft_id, 3))
    line_formset, partner_form, allocation_form, rows, partners, totals = None, None, None, [], [], {}
    error, order_preview = '', []
    try:
        if step == 1:
            line_formset = LineFormSet(request.POST if request.method == 'POST' else None,
                                       initial=draft.get('lines') or [{'stock_qty': 0, 'customer_qty': 0}], prefix='lines')
            if request.method == 'POST' and line_formset.is_valid() and (calculation_form is None or calculation_form.is_valid()):
                calculation_id = calculation_form.cleaned_data['calculation_price_list'].pk if calculation_form else None
                lines = [{**{key: str(form.cleaned_data[key]) for key in ('product', 'label', 'aed', 'customer_price', 'stock_qty', 'customer_qty')},
                          'supplier': form.cleaned_data['supplier'].pk} for form in line_formset if form.cleaned_data and not form.cleaned_data.get('DELETE')]
                prepare_addition(batch=batch, lines=lines, require_partners=False, calculation_price_list_id=calculation_id)
                request.session[session_key] = {'lines': lines, 'calculation_price_list_id': calculation_id}
                return redirect(_url(pk, draft_id, 2))
        elif step == 2:
            partner_form = AdditionPartnersForm(request.POST if request.method == 'POST' else None, initial={'partners': draft.get('partner_ids', [])})
            if request.method == 'POST' and partner_form.is_valid():
                ids = list(partner_form.cleaned_data['partners'].values_list('pk', flat=True))
                prepare_addition(batch=batch, lines=draft['lines'], partner_ids=ids, calculation_price_list_id=calculation_id)
                request.session[session_key] = {**draft, 'partner_ids': ids}
                return redirect(_url(pk, draft_id, 3))
        elif step == 3:
            rows, partners, totals, _ = prepare_addition(batch=batch, lines=draft['lines'], partner_ids=draft['partner_ids'],
                calculation_price_list_id=calculation_id)
            allocation_form = forms.Form(request.POST if request.method == 'POST' else None)
            for index, row in enumerate(rows):
                if not row['customer_qty']:
                    continue
                row['allocation_fields'] = []
                for partner in partners:
                    key = f'{index}:{partner.pk}'
                    allocation_form.fields[key] = forms.IntegerField(label=partner.display_name, min_value=0, max_value=row['customer_qty'],
                        initial=draft.get('allocations', {}).get(key, row['customer_qty'] if len(partners) == 1 else 0))
                    row['allocation_fields'].append(allocation_form[key])
            if request.method == 'POST' and allocation_form.is_valid():
                allocations = allocation_form.cleaned_data
                prepare_addition(batch=batch, lines=draft['lines'], partner_ids=draft['partner_ids'], allocations=allocations,
                    calculation_price_list_id=calculation_id)
                request.session[session_key] = {**draft, 'allocations': allocations}
                return redirect(_url(pk, draft_id, 4))
        else:
            rows, partners, totals, fingerprint = prepare_addition(batch=batch, lines=draft['lines'], partner_ids=draft['partner_ids'],
                allocations=draft['allocations'], calculation_price_list_id=calculation_id)
            order_preview = []
            for partner in [None, *partners]:
                items = [{'name': row['name'], 'quantity': row['stock_qty'] if partner is None else row['distribution'].get(partner.pk, 0)} for row in rows]
                items = [item for item in items if item['quantity']]
                if items:
                    order_preview.append({'name': partner.display_name if partner else 'На склад', 'items': items})
            if request.method == 'POST':
                if not draft.get('preview_fingerprint'):
                    raise ValidationError('Повторно откройте итоговый расчёт.')
                orders = commit_addition(actor=request.user, batch_id=pk, key=draft_id, lines=draft['lines'],
                    partner_ids=draft['partner_ids'], allocations=draft['allocations'],
                    preview_fingerprint=draft['preview_fingerprint'], revision=draft['revision'],
                    calculation_price_list_id=calculation_id)
                messages.success(request, f"Дополнительные товары добавлены. Созданы новые заказы: {', '.join('#'+str(order.pk) for order in orders)}.")
                return redirect('orders:trip_detail', pk=pk)
            request.session[session_key] = {**draft, 'preview_fingerprint': fingerprint, 'revision': batch.revision}
    except (ValidationError, OperationalError) as exc:
        error = ' '.join(exc.messages) if isinstance(exc, ValidationError) else 'База занята. Повторите сохранение.'
    try:
        calculation_price = addition_price_list(batch, calculation_id or (
            calculation_form['calculation_price_list'].value() if calculation_form else None))
    except ValidationError:
        calculation_price = None
    return render(request, 'orders/trip_addition.html', {'batch': batch, 'step': step, 'line_formset': line_formset,
        'partner_form': partner_form, 'allocation_form': allocation_form, 'rows': rows, 'partners': partners,
        'totals': totals, 'order_preview': order_preview, 'error': error, 'back_url': _url(pk, draft_id, max(1, step-1)),
        'calculation_form': calculation_form, 'calculation_price': calculation_price})
