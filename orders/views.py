from collections import defaultdict

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from core.decorators import permission_required_all, permission_required_any
from price.excel import import_procurement_order_xlsx
from price.models import ProcurementPriceListItem

from .forms import ProcurementOrderHeaderForm, ProcurementOrderUploadForm, ReceivingAdjustmentForm
from .models import CustomerProcurementOrder, SupplierOrderBatch
from .services import (
    advance_order_status,
    create_customer_procurement_order,
    create_supplier_order_batch,
    edit_created_order,
    reduce_receiving_order,
)

DRAFT_SESSION_KEY = "procurement_order_import_draft"


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
        "price_list", "payment_warehouse", "created_by"
    ).prefetch_related(
        "items__selected_supplier", "items__cd", "items__tech",
        "status_events__actor", "adjustments__actor", "adjustments__changes", "cash_transactions",
    )


@require_GET
@permission_required_any("orders.view_orders")
def order_list(request):
    can_generate_batches = (
        request.user.is_superuser
        or (
            request.user.has_perm("orders.generate_supplier_orders")
            and request.user.has_perm("partners.view_supplier_details")
        )
    )
    return render(request, "orders/list.html", {
        "orders": _order_queryset(),
        "batches": (
            SupplierOrderBatch.objects.select_related("created_by").prefetch_related("source_orders")[:20]
            if can_generate_batches else []
        ),
        "can_create": request.user.is_superuser or request.user.has_perm("orders.create_order"),
        "can_generate_batches": can_generate_batches,
    })


@permission_required_any("orders.create_order")
def order_upload(request):
    form = ProcurementOrderUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            price_list, lines = import_procurement_order_xlsx(form.cleaned_data["file"])
        except ValidationError as exc:
            form.add_error("file", exc)
        else:
            request.session[DRAFT_SESSION_KEY] = {
                "price_list_id": price_list.pk,
                "recipient": form.cleaned_data["recipient"],
                "comment": form.cleaned_data["comment"],
                "lines": lines,
            }
            return redirect("orders:preview")
    return render(request, "orders/upload.html", {"form": form})


@permission_required_any("orders.create_order")
def order_preview(request):
    draft = request.session.get(DRAFT_SESSION_KEY)
    if not draft:
        messages.error(request, "Сначала загрузите заполненный закупочный прайс.")
        return redirect("orders:upload")
    item_ids = [row["price_list_item_id"] for row in draft["lines"]]
    items = {
        item.pk: item
        for item in ProcurementPriceListItem.objects.filter(
            price_list_id=draft["price_list_id"], pk__in=item_ids
        )
    }
    preview_rows = []
    for row in draft["lines"]:
        item = items.get(row["price_list_item_id"])
        if item is None:
            messages.error(request, "Сохранённый прайс изменён. Загрузите файл повторно.")
            request.session.pop(DRAFT_SESSION_KEY, None)
            return redirect("orders:upload")
        preview_rows.append({"item": item, **row})
    if request.method == "POST":
        try:
            order = create_customer_procurement_order(actor=request.user, **draft)
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        else:
            request.session.pop(DRAFT_SESSION_KEY, None)
            messages.success(request, f"Заказ №{order.pk} создан без проведения оплаты.")
            return redirect("orders:detail", pk=order.pk)
    return render(request, "orders/preview.html", {"draft": draft, "rows": preview_rows})


@require_GET
@permission_required_any("orders.view_order_detail")
def order_detail(request, pk):
    order = get_object_or_404(_order_queryset(), pk=pk)
    can_view_supplier = request.user.is_superuser or request.user.has_perm("price.view_supplier_prices")
    return render(request, "orders/detail.html", {
        "order": order,
        "can_view_supplier": can_view_supplier,
        "can_view_supplier_details": (
            request.user.is_superuser or request.user.has_perm("partners.view_supplier_details")
        ),
        "can_view_cash": request.user.is_superuser or request.user.has_perm("cash.view_cash_history"),
        "can_edit_created": order.status == order.Status.CREATED and (
            request.user.is_superuser or request.user.has_perm("orders.edit_created_order")
        ),
        "can_confirm": order.status == order.Status.CREATED and (
            request.user.is_superuser
            or (
                request.user.has_perm("orders.confirm_order")
                and (order.prepayment_total == 0 or request.user.has_perm("cash.deposit_cash"))
            )
        ),
        "can_start_receiving": order.status == order.Status.CONFIRMED and (
            request.user.is_superuser or request.user.has_perm("orders.start_receiving")
        ),
        "can_adjust": order.status == order.Status.RECEIVING and (
            request.user.is_superuser or request.user.has_perm("orders.edit_receiving_order")
        ),
        "can_complete": order.status == order.Status.RECEIVING and (
            request.user.is_superuser
            or (
                request.user.has_perm("orders.complete_order")
                and (order.postpayment_total == 0 or request.user.has_perm("cash.deposit_cash"))
            )
        ),
        "can_view_adjustments": request.user.is_superuser or request.user.has_perm("orders.view_order_adjustments"),
    })


@permission_required_any("orders.edit_created_order")
def order_edit(request, pk):
    order = get_object_or_404(_order_queryset(), pk=pk)
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
        request.POST or None, initial={"recipient": order.recipient, "comment": order.comment}
    )
    if request.method == "POST" and form.is_valid():
        try:
            edit_created_order(
                actor=request.user, order_id=order.pk,
                recipient=form.cleaned_data["recipient"], comment=form.cleaned_data["comment"],
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
    if order.prepayment_total > 0 and not (
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
        messages.success(request, "Заказ подтверждён; предоплата проведена один раз.")
    return redirect("orders:detail", pk=pk)


@require_POST
@permission_required_any("orders.start_receiving")
def order_start_receiving(request, pk):
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
            messages.success(request, "Корректировка сохранена; необходимый возврат проведён атомарно.")
            return redirect("orders:detail", pk=pk)
    return render(request, "orders/adjust.html", {"order": order, "form": form})


@require_POST
@permission_required_any("orders.complete_order")
def order_complete(request, pk):
    order = get_object_or_404(CustomerProcurementOrder, pk=pk)
    if order.postpayment_total > 0 and not (
        request.user.is_superuser or request.user.has_perm("cash.deposit_cash")
    ):
        raise PermissionDenied("Для постоплаты требуется право внесения наличных в кассу.")
    try:
        advance_order_status(
            actor=request.user, order_id=pk, next_status=CustomerProcurementOrder.Status.COMPLETED,
            warehouse_id=request.POST.get("warehouse"),
        )
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        messages.success(request, "Заказ выполнен; актуальная постоплата проведена один раз.")
    return redirect("orders:detail", pk=pk)


@require_POST
@permission_required_all("orders.generate_supplier_orders", "partners.view_supplier_details")
def supplier_batch_create(request):
    try:
        batch = create_supplier_order_batch(actor=request.user, order_ids=request.POST.getlist("order_id"))
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect("orders:list")
    messages.success(request, f"Подборка поставщикам №{batch.pk} сформирована.")
    return redirect("orders:supplier_batch_detail", pk=batch.pk)


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
