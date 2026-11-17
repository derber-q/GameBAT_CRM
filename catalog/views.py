"""HTTP-обработчики: доступ, формы, вызов сервисов и ответ пользователю номенклатуры.

Карточка описывает товар; физическое количество хранится в warehouse, штрихкоды — в BarcodeRegistry."""
from warehouse.views import global_stock
from django.http import JsonResponse
from django.db.models import Q
from django.views.decorators.http import require_GET
from django.views.decorators.cache import never_cache
from core.decorators import permission_required_any
from .models import BarcodeRegistry


@require_GET
@never_cache
@permission_required_any('warehouse.view_global_stock', 'warehouse.view_warehouse_stock',
                         'catalog.view_nomenclature', 'catalog.view_cd', 'catalog.view_tech', 'pricing.view_pricing')
def barcode_lookup(request):
    """Проверяет точное совпадение в реестре без выдачи цен и складских данных."""
    barcode = str(request.GET.get('barcode') or '').strip()
    if not barcode or len(barcode) > 100:
        return JsonResponse({'found': False}, status=400)
    both = request.user.is_superuser or any(request.user.has_perm(p) for p in (
        'warehouse.view_global_stock', 'warehouse.view_warehouse_stock',
        'catalog.view_nomenclature', 'pricing.view_pricing',
    ))
    allowed = Q(pk__in=[])
    if both or request.user.has_perm('catalog.view_cd'):
        allowed |= Q(cd__is_archived=False)
    if both or request.user.has_perm('catalog.view_tech'):
        allowed |= Q(tech__is_archived=False)
    return JsonResponse({'found': BarcodeRegistry.objects.filter(allowed, value=barcode).exists()})


def warehouse(request):
    """Сохраняет прежний URL склада, показывая новую страницу общих остатков."""
    return global_stock(request)
