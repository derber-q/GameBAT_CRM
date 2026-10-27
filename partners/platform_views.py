"""Создание площадки из раздела реализации без складских и денежных операций."""
import logging
from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.db import transaction
from django.shortcuts import redirect, render
from .forms import SalesPlatformForm

logger = logging.getLogger('gamebat.business')


@permission_required('partners.add_salesplatform', raise_exception=True)
def platform_create(request):
    form = SalesPlatformForm(request.POST or None)
    can_view_consignment = any(request.user.has_perm(permission) for permission in (
        'consignment.view_cdconsignmentstock', 'consignment.view_techconsignmentstock'))
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            platform = form.save()
            logger.info('Площадка реализации создана: user_id=%s platform_id=%s', request.user.pk, platform.pk)
        messages.success(request, 'Площадка реализации создана.')
        return redirect('consignment:platform', pk=platform.pk) if can_view_consignment else redirect('core:home')
    return render(request, 'partners/platform_form.html', {'form': form, 'can_view_consignment': can_view_consignment})
