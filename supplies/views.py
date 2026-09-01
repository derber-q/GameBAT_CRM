from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from catalog.models import CD, Tech
from core.decorators import permission_required_any
from partners.models import Supplier
from .models import Supply
from .services import accept_supply


@permission_required("supplies.view_supply", raise_exception=True)
def supply_list(request):
    supplies = list(Supply.objects.select_related("accepted_by").annotate(
        cd_count=Count("cd_items", distinct=True), tech_count=Count("tech_items", distinct=True)
    ))
    for supply in supplies:
        supply.position_count = supply.cd_count + supply.tech_count
    return render(request, "supplies/list.html", {"supplies": supplies})


def _parse_supply_post(post):
    product_types = post.getlist("product_type")
    product_ids = post.getlist("product_id")
    supplier_ids = post.getlist("supplier_id")
    quantities = post.getlist("quantity")
    costs = post.getlist("purchase_unit_cost")
    if not all(len(values) == len(product_types) for values in (product_ids, supplier_ids, quantities, costs)):
        raise ValidationError("Заполните все поля товарных позиций.")
    lines = [
        {
            "product_type": product_types[index], "product_id": product_ids[index],
            "supplier_id": supplier_ids[index], "quantity": quantities[index],
            "purchase_unit_cost": costs[index],
        }
        for index in range(len(product_types))
    ]
    expense_names = post.getlist("expense_name")
    expense_amounts = post.getlist("expense_amount")
    if len(expense_names) != len(expense_amounts):
        raise ValidationError("Заполните все поля дополнительных расходов.")
    expenses = [{"name": name, "amount": amount} for name, amount in zip(expense_names, expense_amounts)]
    return lines, expenses


@permission_required("supplies.add_supply", raise_exception=True)
def supply_create(request):
    full_supplier_access = request.user.is_superuser or request.user.has_perm("partners.view_supplier_details")
    supplier_values = Supplier.objects.order_by("letter").values("id", "letter", "highlight_color", "name")
    suppliers = [
        {
            "id": row["id"], "label": row["name"] if full_supplier_access else f"[{row['letter']}]",
            "color": row["highlight_color"],
        }
        for row in supplier_values
    ]
    if request.method == "POST":
        try:
            lines, expenses = _parse_supply_post(request.POST)
            supply = accept_supply(accepted_by=request.user, lines=lines, expenses=expenses)
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        else:
            messages.success(request, f"Поставка №{supply.pk} принята.")
            return redirect("supplies:detail", pk=supply.pk)
    return render(request, "supplies/create.html", {"suppliers": suppliers})


@permission_required("supplies.view_supply", raise_exception=True)
def supply_detail(request, pk):
    supply = get_object_or_404(Supply.objects.select_related("accepted_by"), pk=pk)
    full_supplier_access = request.user.is_superuser or request.user.has_perm("partners.view_supplier_details")
    rows = []
    for item in supply.cd_items.all():
        rows.append({
            "type": "CD", "name": item.product_name_snapshot, "sku": item.product_sku_snapshot,
            "supplier": item.supplier_name_snapshot if full_supplier_access else f"[{item.supplier_letter_snapshot}]",
            "supplier_color": item.supplier_color_snapshot, "quantity": item.quantity,
            "purchase": item.purchase_unit_cost, "allocated": item.allocated_expense_per_unit,
            "effective": item.effective_unit_cost, "base_total": item.base_line_total,
            "final_total": item.final_line_total,
        })
    for item in supply.tech_items.all():
        rows.append({
            "type": "Tech", "name": item.product_name_snapshot, "sku": item.product_sku_snapshot,
            "supplier": item.supplier_name_snapshot if full_supplier_access else f"[{item.supplier_letter_snapshot}]",
            "supplier_color": item.supplier_color_snapshot, "quantity": item.quantity,
            "purchase": item.purchase_unit_cost, "allocated": item.allocated_expense_per_unit,
            "effective": item.effective_unit_cost, "base_total": item.base_line_total,
            "final_total": item.final_line_total,
        })
    return render(request, "supplies/detail.html", {
        "supply": supply, "rows": rows, "expenses": supply.expenses.all(), "position_count": len(rows),
    })


@permission_required_any("supplies.add_supply", "consignment.transfer_stock", "consignment.return_stock")
def product_autocomplete(request):
    query = request.GET.get("q", "").strip()
    results = []
    if len(query) >= 2:
        cds = CD.objects.filter(Q(name__icontains=query) | Q(sku__icontains=query)).select_related("platform")[:10]
        tech = Tech.objects.filter(Q(name__icontains=query) | Q(sku__icontains=query)).select_related("product_type")[:10]
        results.extend({
            "type": "cd", "id": item.pk,
            "label": f"CD — {item.name} — {item.platform.name}", "available": item.quantity,
        } for item in cds)
        results.extend({
            "type": "tech", "id": item.pk,
            "label": f"Tech — {item.name} — {item.product_type.name}", "available": item.quantity,
        } for item in tech)
    return JsonResponse({"results": results[:20]})
