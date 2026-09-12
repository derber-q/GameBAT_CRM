from collections import defaultdict

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Prefetch, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from catalog.models import CD, Tech
from catalog.product_filters import (
    ProductFilterState,
    filter_product_querysets,
    product_filter_context,
)
from consignment.models import CDConsignmentStock, TechConsignmentStock
from core.decorators import permission_required_any
from .forms import WarehouseTransferForm, WarehouseTransferSourceForm
from .models import (
    CDWarehouseStock,
    CDWarehouseStorageAssignment,
    CDWarehouseTransferItem,
    TechWarehouseStock,
    TechWarehouseStorageAssignment,
    TechWarehouseTransferItem,
    Warehouse,
    WarehouseTransfer,
)
from .services import advance_transfer_status, create_transfer
from .storage_services import (
    autocomplete_storage_locations,
    storage_location_product_ids,
    storage_locations_for_stock,
    update_storage_locations,
)


def _totals(model, product_field):
    return dict(
        model.objects.values_list(f"{product_field}_id").annotate(total=Sum("quantity"))
    )


def _warehouse_stock_groups(
    warehouse, *, include_cd=True, include_tech=True, only_available=False, requested_quantities=None,
    filters=None, location_query="",
):
    """Группирует номенклатуру склада одинаково для остатков и перемещения."""
    requested_quantities = requested_quantities or {}
    cd_assignment_queryset = CDWarehouseStorageAssignment.objects.select_related("location").order_by(
        "position", "id"
    )
    tech_assignment_queryset = TechWarehouseStorageAssignment.objects.select_related("location").order_by(
        "position", "id"
    )
    cd_stock_rows = list(
        CDWarehouseStock.objects.filter(warehouse=warehouse).prefetch_related(
            Prefetch("storage_assignments", queryset=cd_assignment_queryset)
        )
    ) if include_cd else []
    tech_stock_rows = list(
        TechWarehouseStock.objects.filter(warehouse=warehouse).prefetch_related(
            Prefetch("storage_assignments", queryset=tech_assignment_queryset)
        )
    ) if include_tech else []
    cd_quantities = {stock.cd_id: stock.quantity for stock in cd_stock_rows}
    tech_quantities = {stock.tech_id: stock.quantity for stock in tech_stock_rows}
    cd_locations = {stock.cd_id: storage_locations_for_stock(stock) for stock in cd_stock_rows}
    tech_locations = {stock.tech_id: storage_locations_for_stock(stock) for stock in tech_stock_rows}
    cd_consignment = _totals(CDConsignmentStock, "cd")
    tech_consignment = _totals(TechConsignmentStock, "tech")
    cd_groups = defaultdict(list)
    tech_groups = defaultdict(list)

    filters = filters or ProductFilterState()
    cd_products = (
        CD.objects.select_related("platform").order_by("platform__name", "name", "id")
        if include_cd else CD.objects.none()
    )
    tech_products = (
        Tech.objects.select_related("brand", "product_type").order_by("product_type__name", "name", "id")
        if include_tech else Tech.objects.none()
    )
    cd_products, tech_products = filter_product_querysets(cd_products, tech_products, filters)
    if location_query:
        cd_location_ids, tech_location_ids = storage_location_product_ids(
            warehouse=warehouse,
            raw_query=location_query,
            include_cd=include_cd,
            include_tech=include_tech,
        )
        if include_cd:
            cd_products = cd_products.filter(pk__in=cd_location_ids)
        if include_tech:
            tech_products = tech_products.filter(pk__in=tech_location_ids)

    if include_cd:
        products = cd_products
        if only_available:
            products = products.filter(pk__in=[pk for pk, quantity in cd_quantities.items() if quantity > 0])
        for product in products:
            cd_groups[product.platform].append({
                "product": product,
                "quantity": cd_quantities.get(product.pk, 0),
                "storage_locations": cd_locations.get(product.pk, ""),
                "consignment": cd_consignment.get(product.pk, 0),
                "requested_quantity": requested_quantities.get(("cd", product.pk), ""),
            })

    if include_tech:
        products = tech_products
        if only_available:
            products = products.filter(pk__in=[pk for pk, quantity in tech_quantities.items() if quantity > 0])
        for product in products:
            tech_groups[product.product_type].append({
                "product": product,
                "quantity": tech_quantities.get(product.pk, 0),
                "storage_locations": tech_locations.get(product.pk, ""),
                "consignment": tech_consignment.get(product.pk, 0),
                "requested_quantity": requested_quantities.get(("tech", product.pk), ""),
            })

    return list(cd_groups.items()), list(tech_groups.items())


def global_stock_context(*, include_cd=True, include_tech=True, query="", filters=None):
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
    filters = filters or ProductFilterState(search=query)
    cd_products = (
        CD.objects.select_related("platform").order_by("platform__name", "name", "id")
        if include_cd else CD.objects.none()
    )
    tech_products = (
        Tech.objects.select_related("brand", "product_type").order_by("product_type__name", "name", "id")
        if include_tech else Tech.objects.none()
    )
    cd_products, tech_products = filter_product_querysets(cd_products, tech_products, filters)
    if include_cd:
        products = cd_products
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
        products = tech_products
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
        "query": filters.search,
    }


@permission_required_any("warehouse.view_global_stock", "catalog.view_cd", "catalog.view_tech")
def global_stock(request):
    full_access = request.user.is_superuser or request.user.has_perm("warehouse.view_global_stock")
    filters, filter_context = product_filter_context(request.GET)
    context = global_stock_context(
        include_cd=full_access or request.user.has_perm("catalog.view_cd"),
        include_tech=full_access or request.user.has_perm("catalog.view_tech"),
        filters=filters,
    )
    context.update(filter_context)
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
    filters, filter_context = product_filter_context(request.GET)
    can_view_cd = request.user.is_superuser or request.user.has_perm("catalog.view_cd") or request.user.has_perm(
        "warehouse.view_warehouse_stock"
    )
    can_view_tech = request.user.is_superuser or request.user.has_perm("catalog.view_tech") or request.user.has_perm(
        "warehouse.view_warehouse_stock"
    )
    location_query = (request.GET.get("location") or "").strip()
    location_filter_error = ""
    try:
        cd_groups, tech_groups = _warehouse_stock_groups(
            warehouse, include_cd=can_view_cd, include_tech=can_view_tech,
            only_available=True, filters=filters, location_query=location_query,
        )
    except ValidationError as exc:
        cd_groups, tech_groups = [], []
        location_filter_error = " ".join(exc.messages)
    context = {
        "warehouse": warehouse,
        "cd_groups": cd_groups,
        "tech_groups": tech_groups,
        "query": filters.search,
        "location_query": location_query,
        "location_filter_error": location_filter_error,
        "show_location_filter": True,
        "has_active_filters": filters.is_active or bool(location_query),
        "can_change_storage_location": (
            request.user.is_superuser or request.user.has_perm("warehouse.change_storage_location")
        ),
        "can_view_global": (
            request.user.is_superuser
            or request.user.has_perm("warehouse.view_global_stock")
            or request.user.has_perm("catalog.view_cd")
            or request.user.has_perm("catalog.view_tech")
        ),
    }
    context.update(filter_context)
    return render(request, "warehouse/detail.html", context)


@require_GET
@permission_required_any(
    "warehouse.view_warehouse_stock", "catalog.view_cd", "catalog.view_tech",
    "catalog.view_nomenclature",
)
def storage_location_autocomplete(request, pk):
    warehouse = get_object_or_404(Warehouse, pk=pk)
    full_access = request.user.is_superuser or request.user.has_perm("warehouse.view_warehouse_stock")
    nomenclature_access = request.user.has_perm("catalog.view_nomenclature")
    values = autocomplete_storage_locations(
        warehouse=warehouse,
        raw_query=request.GET.get("q", ""),
        include_cd=full_access or nomenclature_access or request.user.has_perm("catalog.view_cd"),
        include_tech=full_access or nomenclature_access or request.user.has_perm("catalog.view_tech"),
        limit=20,
    )
    return JsonResponse({"results": [{"value": value, "label": value} for value in values]})


@require_POST
@permission_required_any("warehouse.change_storage_location")
def storage_location_update(request, pk, product_type, product_id):
    try:
        result = update_storage_locations(
            actor=request.user,
            warehouse_id=pk,
            product_type=product_type,
            product_id=product_id,
            raw_value=request.POST.get("storage_location", ""),
        )
    except ValidationError as exc:
        return JsonResponse({
            "ok": False,
            "field": "storage_location",
            "error": " ".join(exc.messages),
        }, status=400)
    except (Warehouse.DoesNotExist, CD.DoesNotExist, Tech.DoesNotExist):
        return JsonResponse({"ok": False, "error": "Склад или товар не найден."}, status=404)
    return JsonResponse({
        "ok": True,
        "value": result.value,
        "changed": result.changed,
        "message": "Место хранения сохранено.",
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
