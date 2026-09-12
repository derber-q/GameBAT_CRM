from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from catalog.models import CD, Tech
from core.decorators import permission_required_any
from partners.models import SalesPlatform
from .forms import ConsignmentSaleForm, ReturnForm, TransferForm
from .models import CDConsignmentStock, ConsignmentMovement, TechConsignmentStock
from .services import (
    record_consignment_sale,
    return_from_consignment,
    transfer_many_to_consignment,
    update_consignment_reward,
)


def _can_record_sale(user):
    return user.is_superuser or user.has_perm("sales.create_sale")


def _parse_transfer_lines(post):
    product_types = post.getlist("product_type")
    product_ids = post.getlist("product_id")
    quantities = post.getlist("quantity")
    amounts = post.getlist("receivable_per_unit")
    if not all(len(values) == len(product_types) for values in (product_ids, quantities, amounts)):
        raise ValidationError("Заполните все поля товарных позиций.")
    return [
        {
            "product_type": product_types[index],
            "product_id": product_ids[index],
            "quantity": quantities[index],
            "receivable_per_unit": amounts[index],
        }
        for index in range(len(product_types))
    ]


def _submitted_transfer_lines(post):
    product_types = post.getlist("product_type")
    product_ids = post.getlist("product_id")
    labels = post.getlist("product_search")
    quantities = post.getlist("quantity")
    amounts = post.getlist("receivable_per_unit")
    rows = []
    for index, product_type in enumerate(product_types):
        def value(values):
            return values[index] if index < len(values) else ""

        product_id = value(product_ids)
        label = value(labels)
        product = None
        if product_id:
            model = CD if product_type == "cd" else Tech if product_type == "tech" else None
            try:
                product = model.objects.select_related(
                    "platform" if product_type == "cd" else "product_type"
                ).get(pk=product_id) if model else None
            except (CD.DoesNotExist, Tech.DoesNotExist, ValueError):
                product = None
            if product and not label:
                group = product.platform.name if product_type == "cd" else product.product_type.name
                label = f"{'CD' if product_type == 'cd' else 'Tech'} — {product.name} — {group}"
        rows.append({
            "product_type": product_type,
            "product_id": product_id,
            "label": label,
            "quantity": value(quantities),
            "receivable_per_unit": value(amounts),
            "cost": f"{product.cost:.2f}" if product else "",
        })
    return rows


@permission_required_any("consignment.view_cdconsignmentstock", "consignment.view_techconsignmentstock")
def consignment_list(request):
    platforms = []
    can_record_sale = _can_record_sale(request.user)
    can_change_reward = request.user.is_superuser or request.user.has_perm(
        "consignment.change_consignment_reward"
    )
    for platform in SalesPlatform.objects.all():
        rows = []
        if request.user.is_superuser or request.user.has_perm("consignment.view_cdconsignmentstock"):
            rows.extend({
                "product_kind": "cd", "stock_id": stock.pk, "type": "CD",
                "name": stock.cd.name, "sku": stock.cd.sku, "warehouse": stock.warehouse,
                "cost": stock.cd.cost, "quantity": stock.quantity,
                "receivable": stock.receivable_per_unit, "potential": stock.potential_receivable,
            } for stock in CDConsignmentStock.objects.filter(
                platform=platform, quantity__gt=0
            ).select_related("cd", "warehouse"))
        if request.user.is_superuser or request.user.has_perm("consignment.view_techconsignmentstock"):
            rows.extend({
                "product_kind": "tech", "stock_id": stock.pk, "type": "Tech",
                "name": stock.tech.name, "sku": stock.tech.sku, "warehouse": stock.warehouse,
                "cost": stock.tech.cost, "quantity": stock.quantity,
                "receivable": stock.receivable_per_unit, "potential": stock.potential_receivable,
            } for stock in TechConsignmentStock.objects.filter(
                platform=platform, quantity__gt=0
            ).select_related("tech", "warehouse"))
        platforms.append((platform, sorted(
            rows, key=lambda row: (row["type"], row["name"], row["warehouse"].name)
        )))
    return render(request, "consignment/list.html", {
        "platforms": platforms, "can_record_sale": can_record_sale,
        "can_change_reward": can_change_reward,
    })


@require_POST
@permission_required_any("consignment.change_consignment_reward")
def reward_update(request, product_kind, pk):
    try:
        update_consignment_reward(
            actor=request.user,
            product_type=product_kind,
            stock_id=pk,
            value=request.POST.get("receivable_per_unit"),
        )
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        messages.success(request, "Вознаграждение сохранено.")
    return redirect("consignment:list")


@permission_required_any("consignment.transfer_stock")
def transfer(request):
    form = TransferForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            movement = transfer_many_to_consignment(
                actor=request.user,
                warehouse_id=form.cleaned_data["warehouse"].pk,
                platform_id=form.cleaned_data["platform"].pk,
                lines=_parse_transfer_lines(request.POST),
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(
                request,
                f"Передача №{movement.number} создана: {movement.position_count} поз., {movement.total_units} шт.",
            )
            return redirect("consignment:movement_detail", pk=movement.pk)
    return render(request, "consignment/transfer.html", {
        "form": form,
        "initial_lines": _submitted_transfer_lines(request.POST) if request.method == "POST" else [],
    })


@permission_required_any("consignment.return_stock")
def return_stock(request):
    form = ReturnForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            return_from_consignment(
                actor=request.user,
                warehouse_id=form.cleaned_data["warehouse"].pk,
                platform_id=form.cleaned_data["platform"].pk,
                product_type=form.cleaned_data["product_type"],
                product_id=form.cleaned_data["product_id"],
                quantity=form.cleaned_data["quantity"],
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Товар возвращён на склад-источник.")
            return redirect("consignment:list")
    return render(request, "consignment/form.html", {"form": form, "title": "Снять товар с реализации"})


@permission_required_any("sales.create_sale")
def consignment_sale(request, product_kind, pk):
    if product_kind == "cd":
        stock = get_object_or_404(
            CDConsignmentStock.objects.select_related("cd", "platform", "warehouse"),
            pk=pk, quantity__gt=0,
        )
        product = stock.cd
    elif product_kind == "tech":
        stock = get_object_or_404(
            TechConsignmentStock.objects.select_related("tech", "platform", "warehouse"),
            pk=pk, quantity__gt=0,
        )
        product = stock.tech
    else:
        raise Http404
    form = ConsignmentSaleForm(request.POST or None, stock=stock)
    if request.method == "POST" and form.is_valid():
        try:
            sale = record_consignment_sale(
                actor=request.user,
                product_type=product_kind,
                stock_id=stock.pk,
                quantity=form.cleaned_data["quantity"],
                payment_method=form.cleaned_data["payment_method"],
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, f"Продажа {sale.visible_id} создана и оплачена.")
            if request.user.is_superuser or request.user.has_perm("sales.view_sale_detail"):
                return redirect("sales:detail", pk=sale.pk)
            if request.user.has_perm("sales.view_sales"):
                return redirect("sales:list")
            return redirect("consignment:list")
    return render(request, "consignment/sale.html", {
        "form": form, "stock": stock, "product": product, "product_kind": product_kind,
    })


@permission_required_any(
    "catalog.view_nomenclature",
    "consignment.view_cdconsignmentstock",
    "consignment.view_techconsignmentstock",
)
def movement_detail(request, pk):
    movement = get_object_or_404(
        ConsignmentMovement.objects.select_related(
            "created_by", "warehouse", "platform"
        ).prefetch_related("items__cd", "items__tech"),
        pk=pk,
    )
    return render(request, "consignment/movement_detail.html", {"movement": movement})
