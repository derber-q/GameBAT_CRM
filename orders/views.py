from collections import defaultdict
from uuid import uuid4

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Prefetch
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import content_disposition_header
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from core.decorators import permission_required_all, permission_required_any
from price.excel import import_procurement_order_files
from price.models import ProcurementPriceListItem

from .forms import ProcurementOrderHeaderForm, ProcurementOrderUploadForm, ReceivingAdjustmentForm
from .models import CustomerProcurementOrder, SupplierOrderBatch, SupplierTripAllocation
from .order_excel import order_xlsx
from .order_supplier_excel import build_order_supplier_rows, order_suppliers_xlsx
from .trips import can_manage_trips
from .trip_prices import order_financials
from .order_editing import downstream_lock_reason
from .services import (
    advance_order_status,
    create_customer_procurement_order,
    edit_created_order,
    reduce_receiving_order,
)

DRAFT_SESSION_KEY = "procurement_order_import_draft"


def _require_stock_prices(user, purpose):
    if purpose == CustomerProcurementOrder.Purpose.STOCK and not user.has_perm("price.view_supplier_prices"):
        raise PermissionDenied("Для заказа на склад требуется право просмотра закупочных цен.")


def _parse_item_lines(post, *, id_field):
    ids = post.getlist(id_field)
    prepayments = post.getlist("prepayment_quantity")
    postpayments = post.getlist("postpayment_quantity")
    if not (len(ids) == len(prepayments) == len(postpayments)):
        raise ValidationError("Переданы не все количества заказа.")
    return [
        {
            id_field: ids[index],
            "prepayment_quantity": prepayments[index],
            "postpayment_quantity": postpayments[index],
        }
        for index in range(len(ids))
    ]


def _order_queryset():
    return CustomerProcurementOrder.objects.select_related(
        "price_list", "payment_warehouse", "created_by", "trip", "supply__warehouse"
    ).prefetch_related(
        "items__selected_supplier", "items__cd", "items__tech",
        "items__trip_allocations__line__supplier",
        "status_events__actor", "adjustments__actor", "adjustments__changes", "cash_transactions",
        "operations",
    )


@require_GET
@permission_required_any("orders.view_orders")
def order_list(request):
    from .fulfillment import operation_actions
    orders = _order_queryset()
    if not request.user.has_perm('price.view_supplier_prices'):
        orders = orders.filter(purpose=CustomerProcurementOrder.Purpose.CUSTOMER)
    orders = operation_actions(request.user, list(orders))
    can_generate_batches = (
        request.user.is_superuser
        or (
            request.user.has_perm("orders.generate_supplier_orders")
            and request.user.has_perm("partners.view_supplier_details")
        )
    )
    return render(request, "orders/list.html", {
        "orders": orders,
        "unassigned_orders": [order for order in orders if order.trip_id is None],
        "batches": (
            SupplierOrderBatch.objects.select_related("created_by").prefetch_related("source_orders")[:20]
            if can_generate_batches else []
        ),
        "can_create": request.user.is_superuser or request.user.has_perm("orders.create_order"),
        "can_export": request.user.has_perm("orders.view_order_detail"),
        "can_generate_batches": can_generate_batches,
        "can_export_trips": can_generate_batches and request.user.has_perm("price.view_supplier_prices"),
        "can_create_trip": can_manage_trips(request.user),
        "trip_creation_key": str(uuid4()),
    })


@permission_required_any("orders.create_order")
def order_upload(request):
    form = ProcurementOrderUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            price_list, lines, purpose = import_procurement_order_files(form.cleaned_data["uploads"], with_purpose=True)
            _require_stock_prices(request.user, purpose)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            request.session[DRAFT_SESSION_KEY] = {
                "price_list_id": price_list.pk,
                "recipient": form.cleaned_data["recipient"],
                "comment": form.cleaned_data["comment"],
                "lines": lines,
                "purpose": purpose,
                'partner_id': form.cleaned_data['partner_id'],
                'partner_name': form.cleaned_data['partner_name'],
            }
            return redirect("orders:preview")
    return render(request, "orders/upload.html", {
        "form": form, "can_create_stock": request.user.has_perm("price.view_supplier_prices"),
    })


@never_cache
@require_GET
@permission_required_any("orders.view_order_detail")
def order_export(request, pk):
    with transaction.atomic():
        order = get_object_or_404(CustomerProcurementOrder, pk=pk)
        _require_stock_prices(request.user, order.purpose)
        items = list(order.items.select_related(
            "cd__platform", "cd__game_series", "tech__brand", "tech__product_type",
        ).order_by("pk"))
    response = HttpResponse(order_xlsx(order=order, items=items),
                            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    from partners.customers import customer_filename
    response["Content-Disposition"] = content_disposition_header(True, f"zakaz_{pk}_{customer_filename(order.partner_name_snapshot or order.recipient)}.xlsx")
    return response


@never_cache
@require_GET
@permission_required_all("orders.view_order_detail", "price.view_supplier_prices")
def order_suppliers_export(request, pk):
    try:
        with transaction.atomic():
            order = get_object_or_404(CustomerProcurementOrder, pk=pk)
            items = order.items.select_related(
                "selected_supplier", "cd__platform", "cd__game_series", "tech__brand", "tech__product_type",
            ).order_by("pk")
            if order.trip_id:
                items = items.prefetch_related(Prefetch(
                    "trip_allocations", queryset=SupplierTripAllocation.objects.filter(
                        line__batch_id=order.trip_id,
                    ).select_related("line__supplier").order_by("pk"),
                ))
            rows = build_order_supplier_rows(order=order, items=list(items))
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect("orders:detail", pk=pk)
    response = HttpResponse(order_suppliers_xlsx(
        order=order, rows=rows,
        show_supplier_details=request.user.is_superuser or request.user.has_perm("partners.view_supplier_details"),
    ), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    from partners.customers import customer_filename
    response["Content-Disposition"] = content_disposition_header(True, f"zakaz_{pk}_{customer_filename(order.partner_name_snapshot or order.recipient)}_suppliers.xlsx")
    response["X-Content-Type-Options"] = "nosniff"
    return response


@permission_required_any("orders.create_order")
def order_preview(request):
    draft = request.session.get(DRAFT_SESSION_KEY)
    if not draft:
        messages.error(request, "Сначала загрузите заполненный закупочный прайс.")
        return redirect("orders:upload")
    _require_stock_prices(request.user, draft.get("purpose"))
    from_form = draft.get("entry_method") == "form"
    back_url = (f"{reverse('orders:stock_create')}?price_list={draft['price_list_id']}"
                if from_form else reverse("orders:upload"))
    item_ids = [row["price_list_item_id"] for row in draft["lines"]]
    items = {
        item.pk: item
        for item in ProcurementPriceListItem.objects.select_related("cd", "tech").filter(
            price_list_id=draft["price_list_id"], pk__in=item_ids
        ) if not item.product.is_archived
    }
    preview_rows = []
    for row in draft["lines"]:
        item = items.get(row["price_list_item_id"])
        if item is None:
            messages.error(request, "Выбранная позиция больше недоступна. Проверьте состав заказа заново.")
            request.session.pop(DRAFT_SESSION_KEY, None)
            return redirect(back_url)
        preview_rows.append({"item": item, **row})
    if request.method == "POST":
        try:
            order = create_customer_procurement_order(actor=request.user, **{
                key: value for key, value in draft.items() if key != "entry_method"
            })
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        else:
            request.session.pop(DRAFT_SESSION_KEY, None)
            messages.success(request, f"Заказ №{order.pk} создан без проведения оплаты.")
            return redirect("orders:detail", pk=order.pk)
    return render(request, "orders/preview.html", {"draft": draft, "rows": preview_rows,
                  "is_stock_order": draft.get("purpose") == CustomerProcurementOrder.Purpose.STOCK,
                  "back_url": back_url, "from_form": from_form})


@require_GET
@permission_required_any("orders.view_order_detail")
def order_detail(request, pk):
    order = get_object_or_404(_order_queryset(), pk=pk)
    _require_stock_prices(request.user, order.purpose)
    can_view_supplier = request.user.is_superuser or request.user.has_perm("price.view_supplier_prices")
    locked = downstream_lock_reason(order)
    from .fulfillment import available, require_permissions
    can_create_operation = available(order)
    if can_create_operation:
        try:
            require_permissions(request.user, order)
        except PermissionDenied:
            can_create_operation = False
    financial, financial_error = None, ''
    if can_view_supplier:
        try:
            financial = order_financials(order)
        except ValidationError as exc:
            financial_error = ' '.join(exc.messages)
    return render(request, "orders/detail.html", {
        "order": order,
        'can_create_operation': can_create_operation,
        'operation_history': order.operations.select_related('sale', 'supply', 'created_by'),
        'financial': financial, 'financial_error': financial_error, 'downstream_lock': locked,
        "can_view_supplier": can_view_supplier,
        "can_view_supplier_details": (
            request.user.is_superuser or request.user.has_perm("partners.view_supplier_details")
        ),
        "can_view_cash": request.user.is_superuser or request.user.has_perm("cash.view_cash_history"),
        "can_assign_trip": not locked and can_manage_trips(request.user) and order.status == order.Status.CREATED and (
            not order.trip_id or not order.trip.trip_orders.exclude(status=order.Status.CREATED).exists()
        ),
        "can_edit_created": not locked and not order.trip_id and order.status == order.Status.CREATED and (
            request.user.is_superuser or request.user.has_perm("orders.edit_created_order")
        ),
        "can_confirm": not locked and order.status == order.Status.CREATED and (
            request.user.is_superuser
            or (
                request.user.has_perm("orders.confirm_order")
                and (order.is_stock_order or order.prepayment_total == 0 or request.user.has_perm("cash.deposit_cash"))
            )
        ),
        "can_start_receiving": not locked and order.status == order.Status.CONFIRMED and (
            request.user.is_superuser or request.user.has_perm("orders.start_receiving")
        ),
        "can_adjust": not locked and order.status == order.Status.RECEIVING and (
            request.user.is_superuser or request.user.has_perm("orders.edit_receiving_order")
        ),
        "can_complete": not locked and order.status == order.Status.RECEIVING and (
            request.user.is_superuser
            or (
                request.user.has_perm("orders.complete_order")
                and ((order.is_stock_order and request.user.has_perm("supplies.add_supply"))
                     or (not order.is_stock_order and (order.postpayment_total == 0 or request.user.has_perm("cash.deposit_cash"))))
            )
        ),
        "can_view_adjustments": request.user.is_superuser or request.user.has_perm("orders.view_order_adjustments"),
        "can_review_supply": request.user.has_perm("supplies.add_supply"),
        "can_view_supply": request.user.has_perm("supplies.view_supply"),
    })


@permission_required_any("orders.edit_created_order")
def order_edit(request, pk):
    order = get_object_or_404(_order_queryset(), pk=pk)
    _require_stock_prices(request.user, order.purpose)
    if order.status != order.Status.CREATED:
        messages.error(request, "Изменять можно только заказ в статусе «Создан».")
        return redirect("orders:detail", pk=pk)
    current = {item.price_list_item_id: item for item in order.items.all()}
    source_items = list(order.price_list.items.all())
    rows = [{
        "source": source,
        "prepayment_quantity": current[source.pk].prepayment_quantity if source.pk in current else 0,
        "postpayment_quantity": current[source.pk].postpayment_quantity if source.pk in current else 0,
    } for source in source_items]
    form = ProcurementOrderHeaderForm(
        request.POST or None, allow_archived_initial=True, initial={"recipient": order.recipient, "comment": order.comment,
            'customer': str(order.partner_id) if order.partner_id else 'custom' if order.partner_name_snapshot else '',
            'custom_partner_name': order.partner_name_snapshot if not order.partner_id else ''}
    )
    if request.method == "POST" and form.is_valid():
        try:
            edit_created_order(
                actor=request.user, order_id=order.pk,
                recipient=form.cleaned_data["recipient"], comment=form.cleaned_data["comment"],
                partner_id=form.cleaned_data['partner_id'], partner_name=form.cleaned_data['partner_name'],
                lines=_parse_item_lines(request.POST, id_field="price_list_item_id"),
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Состав созданного заказа обновлён.")
            return redirect("orders:detail", pk=pk)
    return render(request, "orders/edit.html", {"order": order, "form": form, "rows": rows})


@require_POST
@permission_required_any("orders.confirm_order")
def order_confirm(request, pk):
    order = get_object_or_404(CustomerProcurementOrder, pk=pk)
    _require_stock_prices(request.user, order.purpose)
    if not order.is_stock_order and order.prepayment_total > 0 and not (
        request.user.is_superuser or request.user.has_perm("cash.deposit_cash")
    ):
        raise PermissionDenied("Для предоплаты требуется право внесения наличных в кассу.")
    try:
        advance_order_status(
            actor=request.user, order_id=pk, next_status=CustomerProcurementOrder.Status.CONFIRMED,
            warehouse_id=request.POST.get("warehouse"),
        )
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        messages.success(request, "Заказ на склад подтверждён." if order.is_stock_order
                         else "Заказ подтверждён; предоплата проведена один раз.")
    return redirect("orders:detail", pk=pk)


@require_POST
@permission_required_any("orders.start_receiving")
def order_start_receiving(request, pk):
    order = get_object_or_404(CustomerProcurementOrder, pk=pk)
    _require_stock_prices(request.user, order.purpose)
    try:
        advance_order_status(
            actor=request.user, order_id=pk, next_status=CustomerProcurementOrder.Status.RECEIVING
        )
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        messages.success(request, "Заказ переведён в приёмку.")
    return redirect("orders:detail", pk=pk)


@permission_required_any("orders.edit_receiving_order")
def order_adjust(request, pk):
    order = get_object_or_404(_order_queryset(), pk=pk)
    _require_stock_prices(request.user, order.purpose)
    if order.status != order.Status.RECEIVING:
        messages.error(request, "Корректировка доступна только в статусе «Принимается».")
        return redirect("orders:detail", pk=pk)
    form = ReceivingAdjustmentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            reduce_receiving_order(
                actor=request.user, order_id=pk, comment=form.cleaned_data["comment"],
                rows=_parse_item_lines(request.POST, id_field="item_id"),
                allow_refund=request.user.is_superuser or request.user.has_perm("cash.collect_cash"),
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Количество закупки на склад скорректировано." if order.is_stock_order
                             else "Корректировка сохранена; необходимый возврат проведён атомарно.")
            return redirect("orders:detail", pk=pk)
    return render(request, "orders/adjust.html", {"order": order, "form": form})


@require_POST
@permission_required_any("orders.complete_order")
def order_complete(request, pk):
    order = get_object_or_404(CustomerProcurementOrder, pk=pk)
    _require_stock_prices(request.user, order.purpose)
    if order.is_stock_order and not request.user.has_perm("supplies.add_supply"):
        raise PermissionDenied("Для заказа на склад требуется право оформления прихода.")
    if not order.is_stock_order and order.postpayment_total > 0 and not (
        request.user.is_superuser or request.user.has_perm("cash.deposit_cash")
    ):
        raise PermissionDenied("Для постоплаты требуется право внесения наличных в кассу.")
    try:
        completed_order = advance_order_status(
            actor=request.user, order_id=pk, next_status=CustomerProcurementOrder.Status.COMPLETED,
            warehouse_id=request.POST.get("warehouse"),
        )
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        if order.is_stock_order:
            messages.success(request, f"Приход №{completed_order.supply_id} создан. Проверьте цены и поставьте товары на баланс.")
            return redirect("supplies:price_review", pk=completed_order.supply_id)
        messages.success(request, "Заказ выполнен; актуальная постоплата проведена один раз.")
    return redirect("orders:detail", pk=pk)


@require_POST
@permission_required_all("orders.generate_supplier_orders", "partners.view_supplier_details", "orders.edit_created_order", "price.view_supplier_prices")
def supplier_batch_create(request):
    from .trip_views import trip_create
    return trip_create(request)


@require_GET
@permission_required_all("orders.generate_supplier_orders", "partners.view_supplier_details")
def supplier_batch_detail(request, pk):
    batch = get_object_or_404(
        SupplierOrderBatch.objects.select_related("created_by").prefetch_related(
            "source_orders", "lines__supplier", "lines__cd", "lines__tech"
        ), pk=pk,
    )
    grouped = defaultdict(list)
    for line in batch.lines.all():
        grouped[line.supplier].append(line)
    return render(request, "orders/supplier_batch_detail.html", {
        "batch": batch,
        "supplier_groups": grouped.items(),
        "can_view_supplier_prices": (
            request.user.is_superuser or request.user.has_perm("price.view_supplier_prices")
        ),
    })
