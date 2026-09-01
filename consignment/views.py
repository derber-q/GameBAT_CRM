from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render

from core.decorators import permission_required_any
from partners.models import SalesPlatform
from .forms import ReturnForm, TransferForm
from .models import CDConsignmentStock, TechConsignmentStock
from .services import return_from_consignment, transfer_to_consignment


@permission_required_any("consignment.view_cdconsignmentstock", "consignment.view_techconsignmentstock")
def consignment_list(request):
    platforms = []
    for platform in SalesPlatform.objects.all():
        rows = []
        if request.user.is_superuser or request.user.has_perm("consignment.view_cdconsignmentstock"):
            rows.extend({
                "type": "CD", "name": stock.cd.name, "sku": stock.cd.sku,
                "quantity": stock.quantity, "reward": stock.reward_per_unit,
                "potential": stock.potential_reward,
            } for stock in CDConsignmentStock.objects.filter(platform=platform, quantity__gt=0).select_related("cd"))
        if request.user.is_superuser or request.user.has_perm("consignment.view_techconsignmentstock"):
            rows.extend({
                "type": "Tech", "name": stock.tech.name, "sku": stock.tech.sku,
                "quantity": stock.quantity, "reward": stock.reward_per_unit,
                "potential": stock.potential_reward,
            } for stock in TechConsignmentStock.objects.filter(platform=platform, quantity__gt=0).select_related("tech"))
        platforms.append((platform, sorted(rows, key=lambda row: (row["type"], row["name"]))))
    return render(request, "consignment/list.html", {"platforms": platforms})


@permission_required_any("consignment.transfer_stock")
def transfer(request):
    form = TransferForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            transfer_to_consignment(
                actor=request.user,
                platform_id=form.cleaned_data["platform"].pk,
                product_type=form.cleaned_data["product_type"],
                product_id=form.cleaned_data["product_id"],
                quantity=form.cleaned_data["quantity"],
                reward_per_unit=form.cleaned_data["reward_per_unit"],
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Товар передан на реализацию.")
            return redirect("consignment:list")
    return render(request, "consignment/form.html", {"form": form, "title": "Передать товар на реализацию"})


@permission_required_any("consignment.return_stock")
def return_stock(request):
    form = ReturnForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            return_from_consignment(
                actor=request.user,
                platform_id=form.cleaned_data["platform"].pk,
                product_type=form.cleaned_data["product_type"],
                product_id=form.cleaned_data["product_id"],
                quantity=form.cleaned_data["quantity"],
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Товар возвращён на склад.")
            return redirect("consignment:list")
    return render(request, "consignment/form.html", {"form": form, "title": "Снять товар с реализации"})
