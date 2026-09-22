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


def _stock_row(stock, product_kind):
    product = stock.cd if product_kind == "cd" else stock.tech
    return {
        "product_kind": product_kind,
        "stock_id": stock.pk,
        "name": product.name,
        "sku": product.sku,
        "warehouse": stock.warehouse,
        "cost": product.cost,
        "quantity": stock.quantity,
        "receivable": stock.receivable_per_unit,
        "potential": stock.potential_receivable,
    }


def _group_stocks(stocks, *, product_kind):
    grouped = {}
    for stock in stocks:
        product = stock.cd if product_kind == "cd" else stock.tech
        group = product.platform if product_kind == "cd" else product.product_type
        grouped.setdefault(group, []).append(_stock_row(stock, product_kind))
    return [
        (group, sorted(rows, key=lambda row: (row["name"].casefold(), row["warehouse"].name.casefold())))
        for group, rows in sorted(grouped.items(), key=lambda item: item[0].name.casefold())
    ]


def _platform_presentations(user, platform_queryset):
    platforms = list(platform_queryset)
    platform_ids = [platform.pk for platform in platforms]
    cd_by_platform = {platform_id: [] for platform_id in platform_ids}
    tech_by_platform = {platform_id: [] for platform_id in platform_ids}
    if platform_ids and (user.is_superuser or user.has_perm("consignment.view_cdconsignmentstock")):
        for stock in CDConsignmentStock.objects.filter(
            platform_id__in=platform_ids, quantity__gt=0, cd__is_archived=False,
        ).select_related("cd__platform", "warehouse"):
            cd_by_platform[stock.platform_id].append(stock)
    if platform_ids and (user.is_superuser or user.has_perm("consignment.view_techconsignmentstock")):
        for stock in TechConsignmentStock.objects.filter(
            platform_id__in=platform_ids, quantity__gt=0, tech__is_archived=False,
        ).select_related("tech__product_type", "warehouse"):
            tech_by_platform[stock.platform_id].append(stock)
    result = []
    for platform in platforms:
        cd_groups = _group_stocks(cd_by_platform[platform.pk], product_kind="cd")
        tech_groups = _group_stocks(tech_by_platform[platform.pk], product_kind="tech")
        result.append({
            "platform": platform,
            "cd_groups": cd_groups,
            "tech_groups": tech_groups,
            "count": sum(len(rows) for _, rows in cd_groups + tech_groups),
        })
    return result


def _consignment_context(request, platform_queryset, *, selected_platform=None):
    return {
        "platforms": _platform_presentations(request.user, platform_queryset),
        "selected_platform": selected_platform,
        "can_record_sale": _can_record_sale(request.user),
        "can_change_reward": request.user.is_superuser or request.user.has_perm(
            "consignment.change_consignment_reward"
        ),
    }


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
                product = model.objects.active().select_related(
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
    return render(
        request, "consignment/list.html",
        _consignment_context(request, SalesPlatform.objects.all()),
    )


@permission_required_any("consignment.view_cdconsignmentstock", "consignment.view_techconsignmentstock")
def consignment_platform(request, pk):
    platform = get_object_or_404(SalesPlatform, pk=pk)
    return render(
        request, "consignment/list.html",
        _consignment_context(
            request, SalesPlatform.objects.filter(pk=platform.pk), selected_platform=platform,
        ),
    )


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
            pk=pk, quantity__gt=0, cd__is_archived=False,
        )
        product = stock.cd
    elif product_kind == "tech":
        stock = get_object_or_404(
            TechConsignmentStock.objects.select_related("tech", "platform", "warehouse"),
            pk=pk, quantity__gt=0, tech__is_archived=False,
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
