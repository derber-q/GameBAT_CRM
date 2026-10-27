"""Справочник партнёров: контакты и финансовые сведения проверяются отдельно."""
import logging
from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django import forms
from django.core.exceptions import PermissionDenied
from django.db import transaction, IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from .forms import PartnerForm, SalesPlatformForm
from .models import Partner

logger = logging.getLogger('gamebat.business')


@permission_required('partners.view_partner', raise_exception=True)
def partner_list(request):
    return render(request, 'partners/partner_list.html', {'partners': Partner.objects.select_related('platform'),
        'show_contacts': request.user.has_perm('partners.view_partner_contacts')})


@permission_required('partners.view_partner', raise_exception=True)
def partner_detail(request, pk):
    partner = get_object_or_404(Partner.objects.select_related('platform'), pk=pk)
    return render(request, 'partners/partner_detail.html', {'partner': partner,
        'show_contacts': request.user.has_perm('partners.view_partner_contacts')})


@permission_required('partners.add_partner', raise_exception=True)
@permission_required('partners.view_partner_contacts', raise_exception=True)
def partner_create(request):
    return _edit(request)


@permission_required('partners.change_partner', raise_exception=True)
@permission_required('partners.view_partner_contacts', raise_exception=True)
def partner_edit(request, pk):
    return _edit(request, pk)


def _edit(request, pk=None):
    instance = get_object_or_404(Partner, pk=pk) if pk else None
    can_create_platform = request.user.has_perm('partners.add_salesplatform')
    creating_platform = request.method == 'POST' and forms.BooleanField(required=False).clean(request.POST.get('create_platform'))
    if creating_platform and not can_create_platform:
        raise PermissionDenied('Нет права создания площадок реализации.')
    form = PartnerForm(request.POST or None, instance=instance, can_create_platform=can_create_platform)
    platform_form = SalesPlatformForm(request.POST if creating_platform else None, prefix='new_platform')
    partner_valid = form.is_valid() if request.method == 'POST' else False
    platform_valid = platform_form.is_valid() if creating_platform else True
    if request.method == 'POST' and partner_valid and platform_valid:
        key = form.cleaned_data.get('request_key')
        existing = Partner.objects.filter(creation_key=key).first() if key and not pk else None
        if not pk and not key:
            form.add_error(None, 'Откройте новую форму создания партнёра.')
        elif existing:
            fields = ('name', 'contact_person', 'phone_1', 'phone_2', 'telegram', 'address', 'platform', 'is_archived')
            same_partner = all(getattr(existing, field) == form.cleaned_data[field]
                for field in fields if not (creating_platform and field == 'platform'))
            same_platform = not creating_platform or (existing.platform_id is not None and all(
                getattr(existing.platform, field) == platform_form.cleaned_data[field] for field in SalesPlatformForm.Meta.fields))
            if same_partner and same_platform:
                return redirect('partners:partner_detail', pk=existing.pk)
            form.add_error(None, 'Эта форма уже использована. Откройте новую форму.')
        else:
            try:
                with transaction.atomic():
                    if not pk: form.instance.creation_key = key
                    if creating_platform:
                        platform = platform_form.save()
                        form.instance.platform = platform
                        logger.info('Площадка создана вместе с партнёром: user_id=%s platform_id=%s', request.user.pk, platform.pk)
                    partner = form.save()
                    logger.info('Партнёр сохранён: user_id=%s partner_id=%s fields=%s', request.user.pk, partner.pk, form.changed_data)
            except IntegrityError:
                form.add_error(None, 'Данные уже сохранены или площадка занята. Проверьте список партнёров.')
            else:
                messages.success(request, 'Партнёр сохранён.')
                return redirect('partners:partner_detail', pk=partner.pk)
    return render(request, 'partners/partner_form.html', {'form': form, 'partner': instance,
        'platform_form': platform_form, 'can_create_platform': can_create_platform, 'creating_platform': creating_platform})
