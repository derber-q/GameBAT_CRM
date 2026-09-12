from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from catalog.models import CD, Tech
from core.decorators import permission_required_any
from partners.models import Supplier
from warehouse.models import CDWarehouseStock, TechWarehouseStock, Warehouse
from .models import Supply
from .services import accept_supply, cancel_supply


@permission_required("supplies.view_supply", raise_exception=True)
def supply_list(request):
    supplies = list(Supply.objects.select_related("accepted_by", "warehouse", "cancelled_by").annotate(
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


def _submitted_supply_lines(post):
    product_types = post.getlist("product_type")
    product_ids = post.getlist("product_id")
    labels = post.getlist("product_search")
    supplier_ids = post.getlist("supplier_id")
    quantities = post.getlist("quantity")
    costs = post.getlist("purchase_unit_cost")
    rows = []
    for index, product_type in enumerate(product_types):
        value = lambda values: values[index] if index < len(values) else ""
        product_id = value(product_ids)
        label = value(labels)
        if not label and product_id:
            model = CD if product_type == "cd" else Tech if product_type == "tech" else None
            try:
                product = model.objects.select_related(
                    "platform" if product_type == "cd" else "product_type"
                ).get(pk=product_id) if model else None
            except (CD.DoesNotExist, Tech.DoesNotExist, ValueError):
                product = None
            if product:
                group = product.platform.name if product_type == "cd" else product.product_type.name
                label = f"{'CD' if product_type == 'cd' else 'Tech'} — {product.name} — {group}"
        rows.append({
            "product_type": product_type,
            "product_id": product_id,
            "label": label,
            "supplier_id": value(supplier_ids),
            "quantity": value(quantities),
            "purchase_unit_cost": value(costs),
        })
    return rows


def _submitted_expenses(post):
    names = post.getlist("expense_name")
    amounts = post.getlist("expense_amount")
    length = max(len(names), len(amounts), 0)
    return [
        {
            "name": names[index] if index < len(names) else "",
            "amount": amounts[index] if index < len(amounts) else "",
        }
        for index in range(length)
    ]


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
            supply = accept_supply(
                accepted_by=request.user, warehouse_id=request.POST.get("warehouse_id"),
                lines=lines, expenses=expenses,
            )
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        else:
            messages.success(request, f"Поставка №{supply.pk} принята.")
            return redirect("supplies:detail", pk=supply.pk)
    return render(request, "supplies/create.html", {
        "suppliers": suppliers, "warehouses": Warehouse.objects.all(),
        "selected_warehouse": request.POST.get("warehouse_id", ""),
        "initial_supply_lines": _submitted_supply_lines(request.POST) if request.method == "POST" else [],
        "initial_expenses": _submitted_expenses(request.POST) if request.method == "POST" else [],
    })


@permission_required("supplies.view_supply", raise_exception=True)
def supply_detail(request, pk):
    supply = get_object_or_404(
        Supply.objects.select_related("accepted_by", "warehouse", "cancelled_by"), pk=pk
    )
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
        "supply": supply,
        "rows": rows,
        "expenses": supply.expenses.all(),
        "position_count": len(rows),
        "cost_calculations": supply.cost_calculations.select_related("cd", "tech"),
        "can_cancel": not supply.is_cancelled and (
            request.user.is_superuser or request.user.has_perm("supplies.cancel_supply")
        ),
    })


@require_POST
@permission_required("supplies.cancel_supply", raise_exception=True)
def supply_cancel(request, pk):
    try:
        result = cancel_supply(
            actor=request.user, supply_id=pk, comment=request.POST.get("cancellation_comment"),
        )
    except (ValidationError, Supply.DoesNotExist) as exc:
        messages.error(
            request,
            " ".join(exc.messages) if isinstance(exc, ValidationError) else "Приход не найден.",
        )
    else:
        if result.cancelled:
            messages.success(request, f"Приход №{result.supply.pk} отменён.")
        else:
            messages.info(request, "Приход уже был отменён ранее.")
    return redirect("supplies:detail", pk=pk)


@permission_required_any(
    "supplies.add_supply", "consignment.transfer_stock", "consignment.return_stock",
    "warehouse.create_transfer", "sales.create_sale",
)
def product_autocomplete(request):
    query = request.GET.get("q", "").strip()
    include_cost = request.user.is_superuser or request.user.has_perm("consignment.transfer_stock")
    try:
        warehouse_id = int(request.GET.get("warehouse")) if request.GET.get("warehouse") else None
    except (TypeError, ValueError):
        warehouse_id = None
    results = []
    if len(query) >= 2:
        cds = CD.objects.filter(
            Q(name__icontains=query) | Q(sku__icontains=query) | Q(barcode__icontains=query)
        ).select_related("platform")[:10]
        tech = Tech.objects.filter(
            Q(name__icontains=query) | Q(sku__icontains=query) | Q(barcode__icontains=query)
        ).select_related("product_type")[:10]
        cd_available = dict(CDWarehouseStock.objects.filter(
            warehouse_id=warehouse_id
        ).values_list("cd_id", "quantity")) if warehouse_id else dict(
            CDWarehouseStock.objects.values_list("cd_id").annotate(total=Sum("quantity"))
        )
        tech_available = dict(TechWarehouseStock.objects.filter(
            warehouse_id=warehouse_id
        ).values_list("tech_id", "quantity")) if warehouse_id else dict(
            TechWarehouseStock.objects.values_list("tech_id").annotate(total=Sum("quantity"))
        )
        results.extend({
            "type": "cd", "id": item.pk,
            "label": f"CD — {item.name} — {item.platform.name}", "available": cd_available.get(item.pk, 0),
            "barcode": item.barcode,
            "cost": f"{item.cost:.2f}" if include_cost else None,
        } for item in cds)
        results.extend({
            "type": "tech", "id": item.pk,
            "label": f"Tech — {item.name} — {item.product_type.name}", "available": tech_available.get(item.pk, 0),
            "barcode": item.barcode,
            "cost": f"{item.cost:.2f}" if include_cost else None,
        } for item in tech)
    return JsonResponse({"results": results[:20]})
