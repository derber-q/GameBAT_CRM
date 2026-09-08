from collections import defaultdict

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from catalog.models import CD, Tech
from consignment.models import CDConsignmentStock, TechConsignmentStock
from core.decorators import permission_required_any
from .forms import WarehouseTransferForm, WarehouseTransferSourceForm
from .models import (
    CDWarehouseStock,
    CDWarehouseTransferItem,
    TechWarehouseStock,
    TechWarehouseTransferItem,
    Warehouse,
    WarehouseTransfer,
)
from .services import advance_transfer_status, create_transfer


def _totals(model, product_field):
    return dict(
        model.objects.values_list(f"{product_field}_id").annotate(total=Sum("quantity"))
    )


def _filter_products(products, query, *, include_cusa=False):
    """Фильтрует товары с Unicode-регистронезависимостью, которой не даёт SQLite LIKE."""
    if not query:
        return products
    needle = query.casefold()
    numeric_id = int(query) if query.isdecimal() and len(query) <= 19 else None
    matching_ids = []
    for product in products:
        values = [product.name, product.sku, product.barcode]
        if include_cusa:
            values.append(product.cusa_ppsa_code)
        if product.pk == numeric_id or any(needle in (value or "").casefold() for value in values):
            matching_ids.append(product.pk)
    return products.filter(pk__in=matching_ids)


def _warehouse_stock_groups(
    warehouse, *, include_cd=True, include_tech=True, only_available=False, requested_quantities=None,
    query="",
):
    """Группирует номенклатуру склада одинаково для остатков и перемещения."""
    requested_quantities = requested_quantities or {}
    cd_quantities = dict(
        CDWarehouseStock.objects.filter(warehouse=warehouse).values_list("cd_id", "quantity")
    )
    tech_quantities = dict(
        TechWarehouseStock.objects.filter(warehouse=warehouse).values_list("tech_id", "quantity")
    )
    cd_consignment = _totals(CDConsignmentStock, "cd")
    tech_consignment = _totals(TechConsignmentStock, "tech")
    cd_groups = defaultdict(list)
    tech_groups = defaultdict(list)

    if include_cd:
        products = CD.objects.select_related("platform").order_by("platform__name", "name", "id")
        products = _filter_products(products, query, include_cusa=True)
        if only_available:
            products = products.filter(pk__in=[pk for pk, quantity in cd_quantities.items() if quantity > 0])
        for product in products:
            cd_groups[product.platform].append({
                "product": product,
                "quantity": cd_quantities.get(product.pk, 0),
                "consignment": cd_consignment.get(product.pk, 0),
                "requested_quantity": requested_quantities.get(("cd", product.pk), ""),
            })

    if include_tech:
        products = Tech.objects.select_related("brand", "product_type").order_by(
            "product_type__name", "name", "id"
        )
        products = _filter_products(products, query)
        if only_available:
            products = products.filter(pk__in=[pk for pk, quantity in tech_quantities.items() if quantity > 0])
        for product in products:
            tech_groups[product.product_type].append({
                "product": product,
                "quantity": tech_quantities.get(product.pk, 0),
                "consignment": tech_consignment.get(product.pk, 0),
                "requested_quantity": requested_quantities.get(("tech", product.pk), ""),
            })

    return list(cd_groups.items()), list(tech_groups.items())


def global_stock_context(*, include_cd=True, include_tech=True, query=""):
    warehouses = list(Warehouse.objects.all())
    cd_stocks = {
        (row.warehouse_id, row.cd_id): row.quantity
        for row in CDWarehouseStock.objects.all()
    }
    tech_stocks = {
        (row.warehouse_id, row.tech_id): row.quantity
        for row in TechWarehouseStock.objects.all()
    }
    active_statuses = (
        WarehouseTransfer.Status.CREATED,
        WarehouseTransfer.Status.ASSEMBLED,
        WarehouseTransfer.Status.SHIPPED,
    )
    cd_transit = dict(
        CDWarehouseTransferItem.objects.filter(transfer__status__in=active_statuses)
        .values_list("cd_id").annotate(total=Sum("quantity"))
    )
    tech_transit = dict(
        TechWarehouseTransferItem.objects.filter(transfer__status__in=active_statuses)
        .values_list("tech_id").annotate(total=Sum("quantity"))
    )
    cd_consignment = _totals(CDConsignmentStock, "cd")
    tech_consignment = _totals(TechConsignmentStock, "tech")

    rows = []
    cd_groups = defaultdict(list)
    tech_groups = defaultdict(list)
    if include_cd:
        products = CD.objects.select_related("platform").order_by("platform__name", "name", "id")
        products = _filter_products(products, query, include_cusa=True)
        for product in products:
            quantities = [cd_stocks.get((warehouse.pk, product.pk), 0) for warehouse in warehouses]
            row = {
                "type": "CD",
                "id": product.pk,
                "name": product.name,
                "sku": product.sku,
                "group": product.platform.name,
                "quantities": quantities,
                "warehouse_total": sum(quantities),
                "consignment": cd_consignment.get(product.pk, 0),
                "transit": cd_transit.get(product.pk, 0),
            }
            rows.append(row)
            cd_groups[product.platform].append(row)
    if include_tech:
        products = Tech.objects.select_related("brand", "product_type").order_by(
            "product_type__name", "name", "id"
        )
        products = _filter_products(products, query)
        for product in products:
            quantities = [tech_stocks.get((warehouse.pk, product.pk), 0) for warehouse in warehouses]
            row = {
                "type": "Tech",
                "id": product.pk,
                "name": product.name,
                "sku": product.sku,
                "group": product.product_type.name,
                "quantities": quantities,
                "warehouse_total": sum(quantities),
                "consignment": tech_consignment.get(product.pk, 0),
                "transit": tech_transit.get(product.pk, 0),
            }
            rows.append(row)
            tech_groups[product.product_type].append(row)
    return {
        "warehouses": warehouses,
        "rows": rows,
        "cd_groups": list(cd_groups.items()),
        "tech_groups": list(tech_groups.items()),
        "query": query,
    }


@permission_required_any("warehouse.view_global_stock", "catalog.view_cd", "catalog.view_tech")
def global_stock(request):
    full_access = request.user.is_superuser or request.user.has_perm("warehouse.view_global_stock")
    query = request.GET.get("search", "").strip()
    context = global_stock_context(
        include_cd=full_access or request.user.has_perm("catalog.view_cd"),
        include_tech=full_access or request.user.has_perm("catalog.view_tech"),
        query=query,
    )
    context["can_view_warehouse_details"] = (
        request.user.is_superuser
        or request.user.has_perm("warehouse.view_warehouse_stock")
        or request.user.has_perm("catalog.view_cd")
        or request.user.has_perm("catalog.view_tech")
    )
    return render(request, "warehouse/global_stock.html", context)


@permission_required_any("warehouse.view_warehouse_stock", "catalog.view_cd", "catalog.view_tech")
def warehouse_detail(request, pk):
    warehouse = get_object_or_404(Warehouse, pk=pk)
    query = request.GET.get("search", "").strip()
    can_view_cd = request.user.is_superuser or request.user.has_perm("catalog.view_cd") or request.user.has_perm(
        "warehouse.view_warehouse_stock"
    )
    can_view_tech = request.user.is_superuser or request.user.has_perm("catalog.view_tech") or request.user.has_perm(
        "warehouse.view_warehouse_stock"
    )
    cd_groups, tech_groups = _warehouse_stock_groups(
        warehouse, include_cd=can_view_cd, include_tech=can_view_tech,
        only_available=True, query=query,
    )
    return render(request, "warehouse/detail.html", {
        "warehouse": warehouse,
        "cd_groups": cd_groups,
        "tech_groups": tech_groups,
        "query": query,
        "can_view_global": (
            request.user.is_superuser
            or request.user.has_perm("warehouse.view_global_stock")
            or request.user.has_perm("catalog.view_cd")
            or request.user.has_perm("catalog.view_tech")
        ),
    })


def _parse_lines(post):
    table_lines = []
    table_fields_found = False
    for field_name, quantity in post.items():
        if not field_name.startswith("line_"):
            continue
        table_fields_found = True
        try:
            _, product_type, product_id = field_name.split("_", 2)
            product_id = int(product_id)
        except (TypeError, ValueError) as exc:
            raise ValidationError("Некорректная товарная позиция.") from exc
        if product_type not in {"cd", "tech"}:
            raise ValidationError("Некорректная товарная позиция.")
        if str(quantity).strip() not in {"", "0"}:
            table_lines.append({
                "product_type": product_type,
                "product_id": product_id,
                "quantity": quantity,
            })
    if table_fields_found:
        return table_lines

    # Поддержка прежнего формата нужна для обратной совместимости запросов.
    types = post.getlist("product_type")
    ids = post.getlist("product_id")
    quantities = post.getlist("quantity")
    if not (len(types) == len(ids) == len(quantities)):
        raise ValidationError("Заполните все поля товарных позиций.")
    return [
        {"product_type": types[index], "product_id": ids[index], "quantity": quantities[index]}
        for index in range(len(types))
        if str(quantities[index]).strip() not in {"", "0"}
    ]


def _requested_quantities(post):
    """Возвращает введённые количества для повторного показа формы с ошибкой."""
    requested = {}
    for field_name, quantity in post.items():
        if not field_name.startswith("line_"):
            continue
        try:
            _, product_type, product_id = field_name.split("_", 2)
            requested[(product_type, int(product_id))] = quantity
        except (TypeError, ValueError):
            continue
    types = post.getlist("product_type")
    ids = post.getlist("product_id")
    quantities = post.getlist("quantity")
    for product_type, product_id, quantity in zip(types, ids, quantities):
        try:
            requested[(product_type, int(product_id))] = quantity
        except (TypeError, ValueError):
            continue
    return requested


@permission_required_any("warehouse.view_transfers")
def transfer_list(request):
    transfers = list(WarehouseTransfer.objects.select_related(
        "source_warehouse", "destination_warehouse", "created_by"
    ).prefetch_related("cd_items", "tech_items"))
    return render(request, "warehouse/transfer_list.html", {
        "transfers": transfers,
        "can_create_transfer": (
            request.user.is_superuser or request.user.has_perm("warehouse.create_transfer")
        ),
        "can_view_global": (
            request.user.is_superuser
            or request.user.has_perm("warehouse.view_global_stock")
            or request.user.has_perm("catalog.view_cd")
            or request.user.has_perm("catalog.view_tech")
        ),
    })


@permission_required_any("warehouse.create_transfer")
def transfer_start(request):
    """Выбирает склад-отправитель перед открытием таблицы перемещения."""
    form = WarehouseTransferSourceForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        return redirect("warehouse:transfer_create", source_pk=form.cleaned_data["source_warehouse"].pk)
    return render(request, "warehouse/transfer_start.html", {"form": form})


def _transfer_destination(request, transfer):
    if request.user.is_superuser or request.user.has_perm("warehouse.view_transfers"):
        return redirect("warehouse:transfer_detail", pk=transfer.pk)
    if (
        request.user.has_perm("warehouse.view_warehouse_stock")
        or request.user.has_perm("catalog.view_cd")
        or request.user.has_perm("catalog.view_tech")
    ):
        return redirect("warehouse:detail", pk=transfer.source_warehouse_id)
    return redirect("core:home")


@permission_required_any("warehouse.view_transfers")
def transfer_detail(request, pk):
    transfer = get_object_or_404(
        WarehouseTransfer.objects.select_related("source_warehouse", "destination_warehouse", "created_by")
        .prefetch_related(
            "cd_items__cd__platform",
            "tech_items__tech__brand",
            "tech_items__tech__product_type",
        ),
        pk=pk,
    )
    cd_groups = defaultdict(list)
    tech_groups = defaultdict(list)
    for item in sorted(transfer.cd_items.all(), key=lambda row: (row.cd.platform.name, row.cd.name, row.cd_id)):
        cd_groups[item.cd.platform].append({"product": item.cd, "quantity": item.quantity})
    for item in sorted(
        transfer.tech_items.all(), key=lambda row: (row.tech.product_type.name, row.tech.name, row.tech_id)
    ):
        tech_groups[item.tech.product_type].append({"product": item.tech, "quantity": item.quantity})
    next_actions = {
        WarehouseTransfer.Status.CREATED: (
            WarehouseTransfer.Status.ASSEMBLED, "Отметить как собранное", "warehouse.mark_transfer_assembled"
        ),
        WarehouseTransfer.Status.ASSEMBLED: (
            WarehouseTransfer.Status.SHIPPED, "Отметить как отправленное", "warehouse.mark_transfer_shipped"
        ),
        WarehouseTransfer.Status.SHIPPED: (
            WarehouseTransfer.Status.ACCEPTED, "Принять перемещение", "warehouse.mark_transfer_accepted"
        ),
    }
    action = next_actions.get(transfer.status)
    if action and not (request.user.is_superuser or request.user.has_perm(action[2])):
        action = None
    return render(request, "warehouse/transfer_detail.html", {
        "transfer": transfer,
        "cd_groups": list(cd_groups.items()),
        "tech_groups": list(tech_groups.items()),
        "next_action": action,
    })


@permission_required_any("warehouse.create_transfer")
def transfer_create(request, source_pk):
    source = get_object_or_404(Warehouse, pk=source_pk)
    form = WarehouseTransferForm(request.POST or None, source_warehouse=source)
    if request.method == "POST" and form.is_valid():
        try:
            transfer = create_transfer(
                actor=request.user,
                source_warehouse_id=source.pk,
                destination_warehouse_id=form.cleaned_data["destination_warehouse"].pk,
                lines=_parse_lines(request.POST),
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, f"Перемещение №{transfer.pk} создано.")
            return _transfer_destination(request, transfer)
    cd_groups, tech_groups = _warehouse_stock_groups(
        source,
        only_available=True,
        requested_quantities=_requested_quantities(request.POST) if request.method == "POST" else None,
    )
    return render(request, "warehouse/transfer_create.html", {
        "form": form,
        "source": source,
        "cd_groups": cd_groups,
        "tech_groups": tech_groups,
        "can_view_source": (
            request.user.is_superuser
            or request.user.has_perm("warehouse.view_warehouse_stock")
            or request.user.has_perm("catalog.view_cd")
            or request.user.has_perm("catalog.view_tech")
        ),
        "can_view_transfers": request.user.is_superuser or request.user.has_perm("warehouse.view_transfers"),
    })


@require_POST
@permission_required_any(
    "warehouse.mark_transfer_assembled", "warehouse.mark_transfer_shipped", "warehouse.mark_transfer_accepted"
)
def transfer_advance(request, pk):
    next_status = request.POST.get("next_status", "")
    permission_by_status = {
        WarehouseTransfer.Status.ASSEMBLED: "warehouse.mark_transfer_assembled",
        WarehouseTransfer.Status.SHIPPED: "warehouse.mark_transfer_shipped",
        WarehouseTransfer.Status.ACCEPTED: "warehouse.mark_transfer_accepted",
    }
    required = permission_by_status.get(next_status)
    if required is None or not (request.user.is_superuser or request.user.has_perm(required)):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("У вас нет доступа к этому действию.")
    try:
        advance_transfer_status(actor=request.user, transfer_id=pk, next_status=next_status)
    except (ValidationError, WarehouseTransfer.DoesNotExist) as exc:
        messages.error(request, " ".join(exc.messages) if isinstance(exc, ValidationError) else "Перемещение не найдено.")
    else:
        messages.success(request, "Статус перемещения изменён.")
    transfer = WarehouseTransfer.objects.filter(pk=pk).first()
    return _transfer_destination(request, transfer) if transfer else redirect("core:home")
