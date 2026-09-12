from collections import defaultdict

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from catalog.models import CD, Tech
from catalog.product_filters import (
    filter_product_querysets,
    product_filter_context,
    product_filter_query_string,
)
from core.decorators import permission_required_any
from .services import update_product_prices, update_supplier_price


def _pricing_destination(request):
    if request.user.is_superuser or request.user.has_perm("pricing.view_pricing"):
        destination = reverse("pricing:list")
        query_string = product_filter_query_string(request.GET)
        return redirect(f"{destination}?{query_string}" if query_string else destination)
    return redirect("core:home")


@permission_required_any("pricing.view_pricing")
def pricing_list(request):
    filters, filter_context = product_filter_context(request.GET)
    cds = CD.objects.select_related("platform").order_by("platform__name", "name", "id")
    tech_items = Tech.objects.select_related("brand", "product_type").order_by(
        "product_type__name", "name", "id"
    )
    cds, tech_items = filter_product_querysets(cds, tech_items, filters)
    cd_groups = defaultdict(list)
    for product in cds:
        cd_groups[product.platform].append({
            "type": "cd",
            "product": product,
        })
    tech_groups = defaultdict(list)
    for product in tech_items:
        tech_groups[product.product_type].append({
            "type": "tech",
            "product": product,
        })
    context = {
        "query": filters.search,
        "cd_groups": list(cd_groups.items()),
        "tech_groups": list(tech_groups.items()),
        "filter_query": product_filter_query_string(request.GET),
        "can_change_retail": request.user.is_superuser or request.user.has_perm("pricing.change_retail_price"),
        "can_change_wholesale": request.user.is_superuser or request.user.has_perm("pricing.change_wholesale_price"),
        "can_change_yandex": request.user.is_superuser or request.user.has_perm("pricing.change_yandex_market_price"),
    }
    context.update(filter_context)
    return render(request, "pricing/list.html", context)


@require_POST
@permission_required_any(
    "pricing.change_retail_price", "pricing.change_wholesale_price", "pricing.change_yandex_market_price"
)
def product_prices_update(request):
    field_permissions = {
        "retail_price": "pricing.change_retail_price",
        "wholesale_price": "pricing.change_wholesale_price",
        "yandex_market_price": "pricing.change_yandex_market_price",
    }
    changes = {}
    for field, permission in field_permissions.items():
        if field in request.POST:
            if not (request.user.is_superuser or request.user.has_perm(permission)):
                raise PermissionDenied("У вас нет доступа к изменению этой цены.")
            changes[field] = request.POST[field]
    try:
        update_product_prices(
            actor=request.user,
            product_type=request.POST.get("product_type", ""),
            product_id=request.POST.get("product_id", ""),
            changes=changes,
        )
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        messages.success(request, "Продажные цены сохранены.")
    return _pricing_destination(request)


@require_POST
@permission_required_any("pricing.change_supplier_prices")
def supplier_price_update(request):
    try:
        update_supplier_price(
            actor=request.user,
            product_type=request.POST.get("product_type", ""),
            product_id=request.POST.get("product_id", ""),
            supplier_id=request.POST.get("supplier_id", ""),
            value=request.POST.get("price", ""),
        )
    except (ValidationError, ValueError) as exc:
        messages.error(request, " ".join(exc.messages) if isinstance(exc, ValidationError) else "Некорректные данные.")
    else:
        messages.success(request, "Цена поставщика сохранена.")
    return _pricing_destination(request)
