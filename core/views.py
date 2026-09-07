from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from cash.models import CashRegister
from warehouse.models import Warehouse


@login_required
def home(request):
    destinations = (
        (("sales.view_sales",), "sales:list"),
        (("catalog.view_nomenclature",), "nomenclature:list"),
        (("warehouse.view_global_stock", "catalog.view_cd", "catalog.view_tech"), "catalog:warehouse"),
        (("warehouse.view_transfers",), "warehouse:transfer_list"),
        (("pricing.view_pricing",), "pricing:list"),
        (("supplies.view_supply",), "supplies:list"),
        (("consignment.view_cdconsignmentstock", "consignment.view_techconsignmentstock"), "consignment:list"),
        (("partners.view_supplier",), "partners:list"),
    )
    for permissions, url_name in destinations:
        if request.user.is_superuser or any(request.user.has_perm(p) for p in permissions):
            return redirect(url_name)
    if request.user.has_perm("warehouse.view_warehouse_stock"):
        warehouse = Warehouse.objects.first()
        if warehouse:
            return redirect("warehouse:detail", pk=warehouse.pk)
    if request.user.has_perm("cash.view_cash_register") or request.user.has_perm("cash.view_cash_history"):
        register = CashRegister.objects.select_related("warehouse").first()
        if register:
            return redirect("cash:register", warehouse_pk=register.warehouse_id)
    return render(request, "core/no_access.html")


def permission_denied(request, exception=None):
    return render(request, "403.html", status=403)
