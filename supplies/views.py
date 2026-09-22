from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from catalog.models import CD, Tech
from catalog.product_identifiers import set_product_weight
from catalog.product_search import search_product_querysets
from core.decorators import permission_required_any
from partners.models import Supplier
from warehouse.models import (
    CDWarehouseStock, CDWarehouseStorageAssignment,
    TechWarehouseStock, TechWarehouseStorageAssignment, Warehouse,
)
from .finalization import (
    auto_distribute_penalty, calculate_finalization_penalty,
    get_supply_finalization_context, parse_finalization_inputs,
    apply_supply_finalization, rows_from_inputs, supply_has_complete_cost_calculations,
)
from .models import Supply, SupplyRevision
from .services import accept_supply, cancel_supply, revise_supply


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
    return lines, expenses, post.get("weight_transport_cost")


def _parse_finalization_post(post):
    names = (
        "product_type", "product_id", "baseline_quantity", "baseline_cost",
        "corrected_cost", "change_source",
    )
    values = {name: post.getlist(name) for name in names}
    count = len(values["product_type"])
    if not count or any(len(rows) != count for rows in values.values()):
        raise ValidationError("Данные формы финализации повреждены. Обновите расчёт.")
    return [
        {name: values[name][index] for name in names}
        for index in range(count)
    ]


def _submitted_supply_lines(post, user=None):
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
            "supplier_id": value(supplier_ids),
            "quantity": value(quantities),
            "purchase_unit_cost": value(costs),
            "weight_grams": product.weight_grams if product else None,
            "can_set_weight": bool(user and (
                user.is_superuser or user.has_perm(
                    "catalog.change_cd_weight" if product_type == "cd" else "catalog.change_tech_weight"
                )
            )),
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


def _supplier_options(user):
    full_access = user.is_superuser or user.has_perm("partners.view_supplier_details")
    return [
        {
            "id": row["id"], "label": row["name"] if full_access else f"[{row['letter']}]",
            "color": row["highlight_color"],
        }
        for row in Supplier.objects.order_by("letter").values("id", "letter", "highlight_color", "name")
    ]


def _current_supply_lines(supply, user):
    rows = []
    for product_type, related_name, group_name in (
        ("cd", "cd_items", "platform"), ("tech", "tech_items", "product_type")
    ):
        for item in getattr(supply, related_name).select_related("product", f"product__{group_name}"):
            group = getattr(item.product, group_name).name
            rows.append({
                "product_type": product_type,
                "product_id": item.product_id,
                "label": f"{'CD' if product_type == 'cd' else 'Tech'} — {item.product.name} — {group}",
                "supplier_id": item.supplier_id,
                "quantity": item.quantity,
                "purchase_unit_cost": str(item.purchase_unit_cost),
                "weight_grams": item.product.weight_grams,
                "can_set_weight": user.is_superuser or user.has_perm(
                    "catalog.change_cd_weight" if product_type == "cd" else "catalog.change_tech_weight"
                ),
            })
    return rows


@permission_required("supplies.add_supply", raise_exception=True)
def supply_create(request):
    suppliers = _supplier_options(request.user)
    if request.method == "POST":
        try:
            lines, expenses, weight_transport_cost = _parse_supply_post(request.POST)
            supply = accept_supply(
                accepted_by=request.user, warehouse_id=request.POST.get("warehouse_id"),
                lines=lines, expenses=expenses, weight_transport_cost=weight_transport_cost,
            )
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        else:
            messages.success(request, f"Поставка №{supply.pk} принята.")
            return redirect("supplies:detail", pk=supply.pk)
    return render(request, "supplies/create.html", {
        "suppliers": suppliers, "warehouses": Warehouse.objects.all(),
        "selected_warehouse": request.POST.get("warehouse_id", ""),
        "initial_supply_lines": _submitted_supply_lines(request.POST, request.user) if request.method == "POST" else [],
        "initial_expenses": _submitted_expenses(request.POST) if request.method == "POST" else [],
        "weight_transport_cost": request.POST.get("weight_transport_cost", "") if request.method == "POST" else "",
    })


@permission_required("supplies.edit_accepted_supply", raise_exception=True)
def supply_edit(request, pk):
    supply = get_object_or_404(
        Supply.objects.select_related("warehouse", "accepted_by"), pk=pk
    )
    if supply.is_cancelled or supply.status != Supply.Status.ACCEPTED:
        messages.error(request, "Редактировать можно только действующий принятый приход.")
        return redirect("supplies:detail", pk=supply.pk)
    if request.method == "POST":
        try:
            if request.POST.get("revision_confirmed") != "1":
                raise ValidationError("Подтвердите изменение уже принятого прихода.")
            lines, expenses, weight_transport_cost = _parse_supply_post(request.POST)
            result = revise_supply(
                actor=request.user, supply_id=supply.pk,
                expected_revision_number=request.POST.get("expected_revision_number"),
                warehouse_id=request.POST.get("warehouse_id"), lines=lines, expenses=expenses,
                weight_transport_cost=weight_transport_cost,
                reason=request.POST.get("revision_reason"),
            )
        except (ValidationError, Supply.DoesNotExist) as exc:
            messages.error(
                request,
                " ".join(exc.messages) if isinstance(exc, ValidationError) else "Приход не найден.",
            )
            supply.refresh_from_db()
        else:
            messages.success(
                request,
                f"Приход №{result.supply.pk} сохранён как редакция {result.supply.revision_number}.",
            )
            return redirect("supplies:detail", pk=result.supply.pk)
    return render(request, "supplies/create.html", {
        "editing_supply": supply,
        "suppliers": _supplier_options(request.user),
        "warehouses": Warehouse.objects.all(),
        "selected_warehouse": (
            request.POST.get("warehouse_id", "") if request.method == "POST" else str(supply.warehouse_id)
        ),
        "initial_supply_lines": (
            _submitted_supply_lines(request.POST, request.user)
            if request.method == "POST" else _current_supply_lines(supply, request.user)
        ),
        "initial_expenses": (
            _submitted_expenses(request.POST) if request.method == "POST"
            else [{"name": row.name, "amount": str(row.amount)} for row in supply.expenses.all()]
        ),
        "weight_transport_cost": (
            request.POST.get("weight_transport_cost", "")
            if request.method == "POST" else str(supply.weight_transport_cost)
        ),
        "revision_reason": request.POST.get("revision_reason", ""),
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
            "weight": item.weight_grams_snapshot, "line_weight": item.line_weight_grams,
            "transport_total": item.allocated_transport_cost,
            "transport_per_unit": item.transport_cost_per_unit,
            "effective": item.effective_unit_cost, "base_total": item.base_line_total,
            "final_total": item.final_line_total,
        })
    for item in supply.tech_items.all():
        rows.append({
            "type": "Tech", "name": item.product_name_snapshot, "sku": item.product_sku_snapshot,
            "supplier": item.supplier_name_snapshot if full_supplier_access else f"[{item.supplier_letter_snapshot}]",
            "supplier_color": item.supplier_color_snapshot, "quantity": item.quantity,
            "purchase": item.purchase_unit_cost, "allocated": item.allocated_expense_per_unit,
            "weight": item.weight_grams_snapshot, "line_weight": item.line_weight_grams,
            "transport_total": item.allocated_transport_cost,
            "transport_per_unit": item.transport_cost_per_unit,
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
        "can_edit": not supply.is_cancelled and (
            request.user.is_superuser or request.user.has_perm("supplies.edit_accepted_supply")
        ),
        "can_finalize": not supply.is_cancelled and supply_has_complete_cost_calculations(supply) and (
            request.user.is_superuser or request.user.has_perm("supplies.finalize_supply")
        ),
        "revisions": supply.revisions.select_related("created_by", "warehouse"),
        "finalizations": supply.finalizations.select_related("created_by").prefetch_related("items"),
    })


@permission_required("supplies.finalize_supply", raise_exception=True)
def supply_finalization(request, pk):
    supply = get_object_or_404(Supply, pk=pk)
    if request.method == "POST":
        try:
            finalization = apply_supply_finalization(
                actor=request.user,
                supply_id=supply.pk,
                expected_revision_number=request.POST.get("revision_number"),
                raw_rows=_parse_finalization_post(request.POST),
            )
        except (ValidationError, Supply.DoesNotExist) as exc:
            messages.error(
                request,
                " ".join(exc.messages) if isinstance(exc, ValidationError) else "Приход не найден.",
            )
            return redirect("supplies:finalization", pk=pk)
        messages.success(
            request,
            f"Финализация прихода №{supply.pk} применена. Изменено товаров: {finalization.items.count()}.",
        )
        return redirect("supplies:detail", pk=pk)
    try:
        rows = get_supply_finalization_context(supply=supply)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect("supplies:detail", pk=pk)
    return render(request, "supplies/finalization.html", {
        "supply": supply,
        "rows": rows,
        "cd_rows": [row for row in rows if row.product_type == "cd"],
        "tech_rows": [row for row in rows if row.product_type == "tech"],
        "initial_penalty": calculate_finalization_penalty(rows),
    })


@require_POST
@permission_required("supplies.finalize_supply", raise_exception=True)
def supply_finalization_auto(request, pk):
    supply = get_object_or_404(Supply, pk=pk)
    try:
        inputs = parse_finalization_inputs(_parse_finalization_post(request.POST))
        current_rows = get_supply_finalization_context(supply=supply)
        rows = rows_from_inputs(current_rows, inputs)
        selected = set()
        for value in request.POST.getlist("selected_product"):
            product_type, separator, product_id = value.partition(":")
            if separator and product_type in {"cd", "tech"}:
                try:
                    selected.add((product_type, int(product_id)))
                except ValueError:
                    pass
        result = auto_distribute_penalty(rows=rows, selected_keys=selected)
    except ValidationError as exc:
        return JsonResponse({"ok": False, "error": " ".join(exc.messages)}, status=400)
    return JsonResponse({
        "ok": True,
        "penalty": f"{calculate_finalization_penalty(result):.2f}",
        "rows": [
            {
                "key": f"{row.product_type}:{row.product_id}",
                "corrected_cost": f"{row.corrected_cost:.2f}",
                "change_source": row.change_source,
                "row_penalty": f"{row.row_penalty:.2f}",
            }
            for row in result
        ],
    })


@permission_required("supplies.view_supply", raise_exception=True)
def supply_revision_detail(request, pk, revision_number):
    revision = get_object_or_404(
        SupplyRevision.objects.select_related("supply", "warehouse", "created_by"),
        supply_id=pk, revision_number=revision_number,
    )
    full_supplier_access = request.user.is_superuser or request.user.has_perm("partners.view_supplier_details")
    rows = [{
        "type": item.get_product_kind_display(),
        "name": item.product_name_snapshot,
        "sku": item.product_sku_snapshot,
        "supplier": item.supplier_name_snapshot if full_supplier_access else f"[{item.supplier_letter_snapshot}]",
        "supplier_color": item.supplier_color_snapshot,
        "quantity": item.quantity,
        "purchase": item.purchase_unit_cost,
        "allocated": item.allocated_expense_per_unit,
        "weight": item.weight_grams_snapshot,
        "line_weight": item.line_weight_grams,
        "transport_total": item.allocated_transport_cost,
        "transport_per_unit": item.transport_cost_per_unit,
        "effective": item.effective_unit_cost,
        "base_total": item.base_line_total,
        "final_total": item.final_line_total,
    } for item in revision.items.all()]
    return render(request, "supplies/revision_detail.html", {
        "revision": revision, "supply": revision.supply, "rows": rows,
        "expenses": revision.expenses.all(), "position_count": len(rows),
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
    "supplies.add_supply", "supplies.edit_accepted_supply",
    "consignment.transfer_stock", "consignment.return_stock",
    "warehouse.create_transfer", "sales.create_sale",
)
def product_autocomplete(request):
    query = request.GET.get("q", "").strip()
    context = request.GET.get("context", "").strip()
    context_permissions = {
        "supply": ("supplies.add_supply", "supplies.edit_accepted_supply"),
        "sale": ("sales.create_sale", "sales.edit_unpaid_postpay_sale"),
        "consignment": ("consignment.transfer_stock",),
        "transfer": ("warehouse.create_transfer",),
    }
    if context in context_permissions and not (
        request.user.is_superuser or any(request.user.has_perm(p) for p in context_permissions[context])
    ):
        raise PermissionDenied
    include_cost = context in {"", "consignment"} and (
        request.user.is_superuser or request.user.has_perm("consignment.transfer_stock")
    )
    try:
        warehouse_id = int(request.GET.get("warehouse")) if request.GET.get("warehouse") else None
    except (TypeError, ValueError):
        warehouse_id = None
    raw_items = request.GET.get("items", "").strip()
    requested_ids = {"cd": set(), "tech": set()}
    if raw_items:
        if context != "sale" or not warehouse_id:
            return JsonResponse({"error": "Для обновления строк выберите склад."}, status=400)
        tokens = [token.strip() for token in raw_items.split(",") if token.strip()]
        if len(tokens) > 100:
            return JsonResponse({"error": "За один запрос можно обновить не более 100 товаров."}, status=400)
        try:
            for token in tokens:
                product_type, raw_id = token.split(":", 1)
                if product_type not in requested_ids:
                    raise ValueError
                requested_ids[product_type].add(int(raw_id))
        except (TypeError, ValueError):
            return JsonResponse({"error": "Некорректный список товаров."}, status=400)
    if warehouse_id and not Warehouse.objects.filter(pk=warehouse_id).exists():
        return JsonResponse({"error": "Склад не найден."}, status=404)

    exact_refresh = bool(raw_items)
    if len(query) < 2 and not exact_refresh:
        return JsonResponse({"results": []})

    cds = CD.objects.active().select_related("platform").prefetch_related("barcodes").order_by("name", "id")
    tech = Tech.objects.active().select_related("product_type").prefetch_related("barcodes").order_by("name", "id")
    if exact_refresh:
        cds = list(cds.filter(pk__in=requested_ids["cd"])[:100])
        tech = list(tech.filter(pk__in=requested_ids["tech"])[:100])
    else:
        if context in {"sale", "consignment", "transfer"}:
            if not warehouse_id and context != "sale":
                return JsonResponse({"results": []})
            if warehouse_id:
                cds = cds.filter(warehouse_stocks__warehouse_id=warehouse_id, warehouse_stocks__quantity__gt=0)
                tech = tech.filter(warehouse_stocks__warehouse_id=warehouse_id, warehouse_stocks__quantity__gt=0)
            else:
                available_cd_ids = CDWarehouseStock.objects.values("cd_id").annotate(
                    total=Sum("quantity")
                ).filter(total__gt=0).values_list("cd_id", flat=True)
                available_tech_ids = TechWarehouseStock.objects.values("tech_id").annotate(
                    total=Sum("quantity")
                ).filter(total__gt=0).values_list("tech_id", flat=True)
                cds = cds.filter(pk__in=available_cd_ids)
                tech = tech.filter(pk__in=available_tech_ids)
        cds, tech = search_product_querysets(cds, tech, query)
        cds = list(cds[:10])
        tech = list(tech[:10])

    cd_ids = [item.pk for item in cds]
    tech_ids = [item.pk for item in tech]
    if warehouse_id:
        cd_available = dict(CDWarehouseStock.objects.filter(
            warehouse_id=warehouse_id, cd_id__in=cd_ids
        ).values_list("cd_id", "quantity"))
        tech_available = dict(TechWarehouseStock.objects.filter(
            warehouse_id=warehouse_id, tech_id__in=tech_ids
        ).values_list("tech_id", "quantity"))
    else:
        cd_available = dict(CDWarehouseStock.objects.filter(cd_id__in=cd_ids).values(
            "cd_id"
        ).annotate(total=Sum("quantity")).values_list("cd_id", "total"))
        tech_available = dict(TechWarehouseStock.objects.filter(tech_id__in=tech_ids).values(
            "tech_id"
        ).annotate(total=Sum("quantity")).values_list("tech_id", "total"))

    cd_locations = {}
    tech_locations = {}
    if warehouse_id:
        for product_id, canonical in CDWarehouseStorageAssignment.objects.filter(
            stock__warehouse_id=warehouse_id, stock__cd_id__in=cd_ids,
        ).order_by("stock__cd_id", "position", "id").values_list(
            "stock__cd_id", "location__canonical_value"
        ):
            cd_locations.setdefault(product_id, []).append(canonical)
        for product_id, canonical in TechWarehouseStorageAssignment.objects.filter(
            stock__warehouse_id=warehouse_id, stock__tech_id__in=tech_ids,
        ).order_by("stock__tech_id", "position", "id").values_list(
            "stock__tech_id", "location__canonical_value"
        ):
            tech_locations.setdefault(product_id, []).append(canonical)

    cd_warehouse_ids = {}
    tech_warehouse_ids = {}
    if context == "sale" and not warehouse_id:
        for product_id, available_warehouse_id in CDWarehouseStock.objects.filter(
            quantity__gt=0, cd_id__in=cd_ids,
        ).values_list("cd_id", "warehouse_id").order_by("warehouse_id"):
            cd_warehouse_ids.setdefault(product_id, []).append(available_warehouse_id)
        for product_id, available_warehouse_id in TechWarehouseStock.objects.filter(
            quantity__gt=0, tech_id__in=tech_ids,
        ).values_list("tech_id", "warehouse_id").order_by("warehouse_id"):
            tech_warehouse_ids.setdefault(product_id, []).append(available_warehouse_id)

    def barcode_values(item):
        return [entry.value for entry in item.barcodes.all()]

    def selected_barcode(item):
        values = barcode_values(item)
        return next((value for value in values if value == query), values[0] if values else "")

    results = [{
        "type": "cd", "id": item.pk,
        "label": f"CD — {item.name} — {item.platform.name}", "available": cd_available.get(item.pk, 0),
        "warehouse_stock": cd_available.get(item.pk, 0) if warehouse_id else None,
        "storage_locations": ", ".join(cd_locations.get(item.pk, [])),
        "barcode": selected_barcode(item),
        "barcodes": barcode_values(item),
        "availability_label": "На складе" if warehouse_id else "Всего в наличии",
        "available_warehouse_ids": cd_warehouse_ids.get(item.pk, []),
        "sku": item.sku,
        "cusa_ppsa_code": item.cusa_ppsa_code,
        "weight_grams": item.weight_grams,
        "can_set_weight": request.user.is_superuser or request.user.has_perm("catalog.change_cd_weight"),
        "cost": f"{item.cost:.2f}" if include_cost else None,
        "prices": {
            "retail": f"{item.avito_price:.2f}" if item.avito_price is not None else None,
            "wholesale": f"{item.wholesale_price:.2f}" if item.wholesale_price is not None else None,
            "yandex_market": f"{item.yandex_market_price:.2f}" if item.yandex_market_price is not None else None,
        } if context == "sale" else None,
    } for item in cds]
    results.extend({
        "type": "tech", "id": item.pk,
        "label": f"Tech — {item.name} — {item.product_type.name}", "available": tech_available.get(item.pk, 0),
        "warehouse_stock": tech_available.get(item.pk, 0) if warehouse_id else None,
        "storage_locations": ", ".join(tech_locations.get(item.pk, [])),
        "barcode": selected_barcode(item),
        "barcodes": barcode_values(item),
        "availability_label": "На складе" if warehouse_id else "Всего в наличии",
        "available_warehouse_ids": tech_warehouse_ids.get(item.pk, []),
        "sku": item.sku,
        "cusa_ppsa_code": "",
        "weight_grams": item.weight_grams,
        "can_set_weight": request.user.is_superuser or request.user.has_perm("catalog.change_tech_weight"),
        "cost": f"{item.cost:.2f}" if include_cost else None,
        "prices": {
            "retail": f"{item.avito_price:.2f}" if item.avito_price is not None else None,
            "wholesale": f"{item.wholesale_price:.2f}" if item.wholesale_price is not None else None,
            "yandex_market": f"{item.yandex_market_price:.2f}" if item.yandex_market_price is not None else None,
        } if context == "sale" else None,
    } for item in tech)
    return JsonResponse({"results": results[:100] if exact_refresh else results[:20]})


@require_POST
@permission_required_any("supplies.add_supply", "supplies.edit_accepted_supply")
def supply_product_weight(request):
    product_kind = request.POST.get("product_type", "").lower()
    permission = {
        "cd": "catalog.change_cd_weight",
        "tech": "catalog.change_tech_weight",
    }.get(product_kind)
    if permission is None or not (
        request.user.is_superuser or request.user.has_perm(permission)
    ):
        raise PermissionDenied
    try:
        product = set_product_weight(
            actor=request.user,
            product_kind=product_kind,
            product_id=request.POST.get("product_id"),
            weight_grams=request.POST.get("weight_grams"),
        )
    except ValidationError as exc:
        return JsonResponse({"ok": False, "error": " ".join(exc.messages)}, status=400)
    return JsonResponse({"ok": True, "weight_grams": product.weight_grams})
