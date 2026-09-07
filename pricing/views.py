from collections import defaultdict

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from catalog.models import CD, Tech
from core.decorators import permission_required_any
from partners.models import Supplier
from .models import SupplierCDPrice, SupplierTechPrice
from .services import update_product_prices, update_supplier_price


def _pricing_destination(request):
    if request.user.is_superuser or request.user.has_perm("pricing.view_pricing"):
        return redirect("pricing:list")
    return redirect("core:home")


@permission_required_any("pricing.view_pricing")
def pricing_list(request):
    can_view_supplier = request.user.is_superuser or request.user.has_perm("pricing.view_supplier_prices")
    full_supplier_access = request.user.is_superuser or request.user.has_perm("partners.view_supplier_details")
    suppliers = []
    if can_view_supplier:
        fields = ("id", "letter", "highlight_color", "name") if full_supplier_access else (
            "id", "letter", "highlight_color"
        )
        suppliers = list(Supplier.objects.order_by("letter").values(*fields))
        for supplier in suppliers:
            supplier["label"] = supplier.get("name") or f"[{supplier['letter']}]"

    cd_prices = {(item.cd_id, item.supplier_id): item.price for item in SupplierCDPrice.objects.all()} if can_view_supplier else {}
    tech_prices = {
        (item.tech_id, item.supplier_id): item.price for item in SupplierTechPrice.objects.all()
    } if can_view_supplier else {}
    cd_groups = defaultdict(list)
    for product in CD.objects.select_related("platform").order_by("platform__name", "name", "id"):
        cd_groups[product.platform].append({
            "type": "cd",
            "product": product,
            "supplier_prices": [
                {"supplier": supplier, "price": cd_prices.get((product.pk, supplier["id"]), 0)}
                for supplier in suppliers
            ],
        })
    tech_groups = defaultdict(list)
    for product in Tech.objects.select_related("brand", "product_type").order_by(
        "product_type__name", "name", "id"
    ):
        tech_groups[product.product_type].append({
            "type": "tech",
            "product": product,
            "supplier_prices": [
                {"supplier": supplier, "price": tech_prices.get((product.pk, supplier["id"]), 0)}
                for supplier in suppliers
            ],
        })
    return render(request, "pricing/list.html", {
        "cd_groups": cd_groups.items(),
        "tech_groups": tech_groups.items(),
        "suppliers": suppliers,
        "can_change_supplier": request.user.is_superuser or request.user.has_perm("pricing.change_supplier_prices"),
        "can_change_retail": request.user.is_superuser or request.user.has_perm("pricing.change_retail_price"),
        "can_change_wholesale": request.user.is_superuser or request.user.has_perm("pricing.change_wholesale_price"),
        "can_change_yandex": request.user.is_superuser or request.user.has_perm("pricing.change_yandex_market_price"),
    })


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
