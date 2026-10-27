"""Отчёт площадки и создание партнёра при первой частичной оплате."""
from decimal import Decimal
from django.contrib import messages
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError, OperationalError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from core.decorators import permission_required_all
from partners.models import Partner, SalesPlatform
from partners.forms import PartnerForm
from sales.models import Sale
from sales.forms import WholesalePriceImportForm
from sales.partner_payments import money, quote, SALT
from .reports import import_report, current_report_rows, DRAFT_KEY


@permission_required_all('sales.create_sale')
def report_import(request, pk):
    platform = get_object_or_404(SalesPlatform, pk=pk)
    key = f'consignment_import_{pk}'
    pending = request.session.get(key)
    partner = Partner.objects.filter(platform=platform, is_archived=False).first()
    initial = {'customer': str(partner.pk) if partner else 'custom', 'custom_partner_name': platform.name}
    form = WholesalePriceImportForm(request.POST or None, request.FILES or None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        try:
            if form.cleaned_data.get('file'):
                pending = import_report(upload=form.cleaned_data['file'], platform_id=pk, actor=request.user)
                request.session[key] = pending
            elif request.POST.get('confirm_report') == '1' and pending:
                if not partner and not form.cleaned_data.get('customer'):
                    raise ValidationError('Укажите заказчика продажи.')
                pending.update(partner_id=partner.pk if partner else form.cleaned_data['partner_id'],
                               partner_name='' if partner else form.cleaned_data['partner_name'])
                request.session[DRAFT_KEY] = pending
                request.session.pop(key, None)
                return redirect(reverse('sales:create') + '?consignment_report=1')
            else:
                raise ValidationError('Загрузите заполненный отчёт площадки.')
        except (ValidationError, OperationalError) as exc:
            form.add_error(None, exc if isinstance(exc, ValidationError) else 'База занята. Повторите проверку отчёта.')
    return render(request, 'consignment/report_import.html', {'platform': platform, 'form': form, 'report': pending})


def needs_report_partner(sale, received):
    if not sale.consignment_report_id or sale.partner_id or sale.is_cancelled or sale.payment_status != Sale.PaymentStatus.UNPAID:
        return False
    try:
        return received not in (None, '') and money(received) < sale.total_amount
    except ValidationError:
        return False


@permission_required_all('sales.mark_sale_paid', 'partners.add_partner', 'partners.view_partner_contacts', 'creditors.change_debt')
def report_partner_payment(request, pk):
    sale = get_object_or_404(Sale.objects.select_related('consignment_platform'), pk=pk)
    pending = request.session.get(f'report_payment_{pk}')
    if not pending or not needs_report_partner(sale, pending['received']):
        return redirect('sales:detail', pk=pk)
    platform = sale.consignment_platform
    form = PartnerForm(request.POST or None, initial={'name': sale.partner_name_snapshot,
                       'platform': platform, 'is_archived': False})
    form.fields['platform'].disabled = True
    form.fields['is_archived'].disabled = True
    debt = sale.total_amount - money(pending['received'])
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                locked = Sale.objects.select_for_update().get(pk=pk)
                SalesPlatform.objects.select_for_update().get(pk=platform.pk)
                if not needs_report_partner(locked, pending['received']):
                    raise ValidationError('Оплата или партнёр уже изменены. Обновите продажу.')
                if Partner.objects.filter(platform=platform).exists():
                    raise ValidationError('У площадки уже появился партнёр. Обновите продажу и выберите его.')
                partner = form.save(commit=False)
                partner.creation_key = form.cleaned_data.get('request_key')
                if not partner.creation_key:
                    raise ValidationError('Обновите форму создания партнёра.')
                partner.platform = platform
                partner.save()
                locked.partner, locked.partner_name_snapshot = partner, partner.name
                locked.save(update_fields=('partner', 'partner_name_snapshot'))
                from sales.services import mark_sale_paid
                note = str(request.POST.get('payment_note') or '').strip()
                if not note:
                    raise ValidationError('Укажите примечание для начисления задолженности.')
                values = quote(total=locked.total_amount, received=pending['received'], debt=partner.creditor.current_debt,
                               partner_id=partner.pk, sale_id=locked.pk)
                mark_sale_paid(actor=request.user, sale_id=pk, cash_received_amount=pending['received'], note=note,
                               settlement_confirmation=signing.dumps(values, salt=SALT))
        except (ValidationError, IntegrityError, OperationalError) as exc:
            form.add_error(None, exc if isinstance(exc, ValidationError) else 'Данные изменены другим пользователем. Обновите форму.')
        else:
            request.session.pop(f'report_payment_{pk}', None)
            messages.success(request, 'Партнёр создан, оплата принята, остаток начислен в задолженность.')
            return redirect('sales:detail', pk=pk)
    return render(request, 'consignment/report_partner_payment.html', {'sale': sale, 'form': form,
                  'received': pending['received'], 'debt': debt})
