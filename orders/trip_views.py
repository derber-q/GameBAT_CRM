import json
from collections import defaultdict

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import OperationalError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import content_disposition_header
from django.utils.text import get_valid_filename
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from core.decorators import permission_required_all
from partners.models import Supplier
from .models import CustomerProcurementOrder
from .forms import TripAssignmentForm
from .trips import (MANAGE_PERMISSIONS, can_manage_trips, change_trip_line, create_trip, trip_queryset,
                    is_m_order_in_f, return_line_to_m, available_trips, assign_order_to_trip)
from .trip_excel import supplier_order_xlsx

VIEW_PERMISSIONS = ("orders.generate_supplier_orders", "partners.view_supplier_details")


@require_POST
@permission_required_all(*MANAGE_PERMISSIONS)
def trip_create(request):
    try:
        trip = create_trip(actor=request.user, order_ids=request.POST.getlist("order_id"),
                           creation_key=request.POST.get("creation_key"), name=request.POST.get("name", ""))
    except (ValidationError, OperationalError) as exc:
        messages.error(request, " ".join(exc.messages) if isinstance(exc, ValidationError) else "База занята. Обновите список и повторите.")
        return redirect("orders:list")
    messages.success(request, f"{trip} создан.")
    return redirect("orders:trip_detail", pk=trip.pk)


@require_http_methods(["GET", "POST"])
@permission_required_all(*MANAGE_PERMISSIONS)
def order_trip_assign(request, pk):
    order = get_object_or_404(CustomerProcurementOrder.objects.select_related("trip"), pk=pk)
    trips = list(available_trips(price_list_id=order.price_list_id, exclude_id=order.trip_id))
    form = TripAssignmentForm(request.POST if request.method == "POST" else None, trips=trips, order=order)
    editable = order.status == order.Status.CREATED and (
        not order.trip_id or not order.trip.trip_orders.exclude(status=order.Status.CREATED).exists())
    if request.method == "POST" and form.is_valid():
        target_id, target_revision = form.cleaned_data["target_trip"]
        try:
            trip = assign_order_to_trip(
                actor=request.user, order_id=order.pk, target_batch_id=target_id, target_revision=target_revision,
                source_batch_id=form.cleaned_data["source_trip"], source_revision=form.cleaned_data["source_revision"],
            )
        except (ValidationError, OperationalError) as exc:
            form.add_error(None, " ".join(exc.messages) if isinstance(exc, ValidationError)
                           else "База занята. Обновите страницу и повторите.")
        else:
            messages.success(request, f"Заказ №{order.pk} добавлен в {trip}.")
            return redirect("orders:trip_detail", pk=trip.pk)
    return render(request, "orders/trip_assign.html", {
        "order": order, "form": form, "has_trips": bool(trips), "editable": editable,
    })


@require_GET
@permission_required_all(*VIEW_PERMISSIONS)
def trip_detail(request, pk):
    batch = get_object_or_404(trip_queryset(), pk=pk, price_list__isnull=False)
    can_edit = can_manage_trips(request.user) and all(order.status == CustomerProcurementOrder.Status.CREATED for order in batch.trip_orders.all())
    grouped, editor = defaultdict(list), {}
    suppliers = list(Supplier.objects.all()) if can_edit else []
    for line in batch.lines.all():
        line.can_return_to_m = is_m_order_in_f(line)
        grouped[line.supplier].append(line)
        if can_edit:
            targets = sorted((supplier for supplier in suppliers if supplier.pk != line.supplier_id),
                             key=lambda supplier: (-supplier.priority, supplier.name.casefold(), supplier.pk))
            allocations = []
            for allocation in line.allocations.all():
                item = allocation.order_item
                current = item.prepayment_quantity + item.postpayment_quantity
                allocations.append({"allocation_id": allocation.pk, "order_id": item.order_id,
                                    "recipient": item.order.recipient, "current": current,
                                    "elsewhere": current - allocation.quantity})
            editor[str(line.pk)] = {
                "name": line.product_name_snapshot, "quantity": line.quantity,
                "url": reverse("orders:trip_line_update", args=(batch.pk, line.pk)),
                "targets": [{"id": supplier.pk, "name": supplier.name, "priority": supplier.priority} for supplier in targets],
                "prices": [{"id": offer.supplier_id, "name": offer.supplier.name, "price": str(offer.price_aed)}
                           for offer in line.price_list_item.supplier_offers.all()],
                "price_supplier_id": line.price_supplier_id, "allocations": allocations,
            }
    return render(request, "orders/trip_detail.html", {
        "batch": batch, "supplier_groups": grouped.items(), "editor": editor, "can_edit": can_edit,
        "can_view_supplier_prices": request.user.is_superuser or request.user.has_perm("price.view_supplier_prices"),
    })


@require_POST
@permission_required_all(*MANAGE_PERMISSIONS)
def trip_line_update(request, pk, line_pk):
    try:
        distribution = json.loads(request.POST.get("distribution", "null"))
        if request.POST.get("action") == "return_to_m":
            trip = return_line_to_m(actor=request.user, batch_id=pk, line_id=line_pk, revision=request.POST.get("revision"))
        else:
            trip = change_trip_line(actor=request.user, batch_id=pk, line_id=line_pk,
                                revision=request.POST.get("revision"), quantity=request.POST.get("quantity"),
                                action=request.POST.get("action"), target_supplier_id=request.POST.get("target_supplier"),
                                price_supplier_id=request.POST.get("price_supplier"), distribution=distribution)
    except (ValidationError, ValueError, OperationalError) as exc:
        message = " ".join(exc.messages) if isinstance(exc, ValidationError) else "Не удалось сохранить. Обновите страницу и повторите."
        return JsonResponse({"success": False, "message": message}, status=409)
    return JsonResponse({"success": True, "revision": trip.revision})


@never_cache
@require_GET
@permission_required_all(*VIEW_PERMISSIONS)
def trip_export(request, pk, supplier_pk):
    batch = get_object_or_404(trip_queryset(), pk=pk, price_list__isnull=False)
    supplier = get_object_or_404(Supplier, pk=supplier_pk)
    lines = [line for line in batch.lines.all() if line.supplier_id == supplier.pk]
    if not lines:
        from django.http import Http404
        raise Http404
    show_prices = request.user.is_superuser or request.user.has_perm("price.view_supplier_prices")
    response = HttpResponse(supplier_order_xlsx(batch, supplier, lines, show_prices=show_prices),
                            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    filename = get_valid_filename(f"trip_{pk}_{supplier.letter}.xlsx")
    response["Content-Disposition"] = content_disposition_header(True, filename)
    return response
