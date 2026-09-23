from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError, OperationalError
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST, require_GET

from catalog.models import CD, Tech
from catalog.product_filters import product_filter_context, filter_product_querysets
from core.decorators import permission_required_any
from partners.models import SalesPlatform
from .forms import TransferForm
from warehouse.models import Warehouse
from sales.models import Sale
from .row_actions import action_token, perform_row_action, stock_queryset
from .models import CDConsignmentStock, ConsignmentMovement, TechConsignmentStock
from .services import (
    transfer_many_to_consignment,
    update_consignment_reward,
)


def _can_record_sale(user):
    return user.is_superuser or user.has_perm("sales.create_sale")


def _stock_row(stock, product_kind, user):
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
        "token": action_token(stock, product_kind, user),
        "platform_name": stock.platform.name,
    }


def _group_stocks(stocks, *, product_kind, user):
    grouped = {}
    for stock in stocks:
        product = stock.cd if product_kind == "cd" else stock.tech
        group = product.platform if product_kind == "cd" else product.product_type
        grouped.setdefault(group, []).append(_stock_row(stock, product_kind, user))
    return [
        (group, sorted(rows, key=lambda row: (row["name"].casefold(), row["warehouse"].name.casefold())))
        for group, rows in sorted(grouped.items(), key=lambda item: item[0].name.casefold())
    ]


def _platform_presentations(user, platform_queryset, filters):
    platforms = list(platform_queryset)
    platform_ids = [platform.pk for platform in platforms]
    cd_by_platform = {platform_id: [] for platform_id in platform_ids}
    tech_by_platform = {platform_id: [] for platform_id in platform_ids}
    cds, techs = filter_product_querysets(
        CD.objects.filter(consignment_stocks__platform_id__in=platform_ids, consignment_stocks__quantity__gt=0).distinct(),
        Tech.objects.filter(consignment_stocks__platform_id__in=platform_ids, consignment_stocks__quantity__gt=0).distinct(),
        filters,
    )
    if platform_ids and (user.is_superuser or user.has_perm("consignment.view_cdconsignmentstock")):
        for stock in CDConsignmentStock.objects.filter(
            platform_id__in=platform_ids, quantity__gt=0, cd_id__in=cds.values('pk'),
        ).select_related("cd__platform", "warehouse", "platform"):
            cd_by_platform[stock.platform_id].append(stock)
    if platform_ids and (user.is_superuser or user.has_perm("consignment.view_techconsignmentstock")):
        for stock in TechConsignmentStock.objects.filter(
            platform_id__in=platform_ids, quantity__gt=0, tech_id__in=techs.values('pk'),
        ).select_related("tech__product_type", "warehouse", "platform"):
            tech_by_platform[stock.platform_id].append(stock)
    result = []
    for platform in platforms:
        cd_groups = _group_stocks(cd_by_platform[platform.pk], product_kind="cd", user=user)
        tech_groups = _group_stocks(tech_by_platform[platform.pk], product_kind="tech", user=user)
        result.append({
            "platform": platform,
            "cd_groups": cd_groups,
            "tech_groups": tech_groups,
            "count": sum(len(rows) for _, rows in cd_groups + tech_groups),
        })
    return result


def _consignment_context(request, platform_queryset, *, selected_platform=None):
    filters, filter_context = product_filter_context(request.GET)
    presentations = _platform_presentations(request.user, platform_queryset, filters)
    return {
        **filter_context,
        "platforms": presentations,
        "has_results": any(item['count'] for item in presentations),
        "selected_platform": selected_platform,
        "can_record_sale": _can_record_sale(request.user),
        "can_return": request.user.is_superuser or request.user.has_perm('consignment.return_stock'),
        "return_warehouses": Warehouse.objects.all(),
        "payment_methods": [(Sale.PaymentMethod.CASH, Sale.PaymentMethod.CASH.label),
                            (Sale.PaymentMethod.BANK_ACCOUNT, Sale.PaymentMethod.BANK_ACCOUNT.label)],
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


@require_GET
@permission_required_any("consignment.return_stock")
def return_stock(request):
    return redirect('consignment:list')


@require_GET
@permission_required_any("sales.create_sale")
def consignment_sale(request, product_kind, pk):
    if product_kind not in ('cd', 'tech'):
        raise Http404
    stock = get_object_or_404(stock_queryset(product_kind), pk=pk)
    return redirect('consignment:platform', pk=stock.platform_id)


def _row_response(request, kind, pk, success, message, status=200):
    stock = stock_queryset(kind).filter(pk=pk).first()
    product = (stock.cd if kind == 'cd' else stock.tech) if stock else None
    visible = bool(stock and stock.quantity > 0 and not product.is_archived)
    context = {
        'row': _stock_row(stock, kind, request.user) if visible else None,
        'can_record_sale': _can_record_sale(request.user),
        'can_return': request.user.is_superuser or request.user.has_perm('consignment.return_stock'),
        'can_change_reward': request.user.is_superuser or request.user.has_perm('consignment.change_consignment_reward'),
    }
    return JsonResponse({
        'success': success, 'message': message, 'quantity': stock.quantity if stock else 0,
        'row_html': render_to_string('consignment/_stock_row.html', context, request=request) if visible else '',
    }, status=status)


@require_POST
@permission_required_any('consignment.view_cdconsignmentstock', 'consignment.view_techconsignmentstock')
def row_action(request, product_kind, pk):
    action = request.POST.get('action')
    permission = {'return': 'consignment.return_stock', 'sold': 'sales.create_sale'}.get(action)
    if product_kind not in ('cd', 'tech') or not permission:
        return JsonResponse({'success': False, 'message': 'Неизвестная операция.'}, status=400)
    if not request.user.is_superuser and not (
        request.user.has_perm(permission) and request.user.has_perm(f'consignment.view_{product_kind}consignmentstock')
    ):
        return JsonResponse({'success': False, 'message': 'Недостаточно прав для операции.'}, status=403)
    if request.POST.get('confirmed') != '1':
        return _row_response(request, product_kind, pk, False, 'Подтвердите операцию.', 400)
    try:
        perform_row_action(
            actor=request.user, kind=product_kind, stock_id=pk,
            token=request.POST.get('token', ''), action=action, quantity=request.POST.get('quantity'),
            warehouse_id=request.POST.get('warehouse'), payment_method=request.POST.get('payment_method'),
        )
    except ValidationError as exc:
        return _row_response(request, product_kind, pk, False, ' '.join(exc.messages), 400)
    except IntegrityError:
        return _row_response(request, product_kind, pk, False, 'Операция уже выполнена либо данные изменились. Показан актуальный остаток.', 409)
    except OperationalError:
        return _row_response(request, product_kind, pk, False, 'База занята другой операцией. Проверьте остаток и повторите действие.', 409)
    message = 'Товар возвращён на выбранный склад.' if action == 'return' else 'Реализация подтверждена.'
    return _row_response(request, product_kind, pk, True, message)


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
