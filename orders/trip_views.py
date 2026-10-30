import json
from uuid import uuid4
from collections import defaultdict

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import OperationalError, transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import content_disposition_header
from django.utils.text import get_valid_filename
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from core.decorators import permission_required_all
from partners.models import Supplier
from catalog.supplier_exclusions import exclusion_keys
from catalog.product_ordering import normalized_order_name, platform_order_key
from .models import CustomerProcurementOrder, SupplierOrderBatch
from .trip_invoices import require_page_editable
from .forms import TripAssignmentForm, EmptyTripForm, TripAddOrdersForm
from .trips import (MANAGE_PERMISSIONS, can_manage_trips, change_trip_line, create_trip, trip_queryset,
                    is_m_order_in_f, return_line_to_m, available_trips, assign_order_to_trip,
                    trip_supplier_chains, supplier_priority_state, create_empty_trip, add_orders_to_trip)
from .trip_excel import supplier_order_xlsx, trip_order_xlsx
from .trip_prices import line_price_lock_reason, trip_financials
from .order_editing import downstream_lock_reason

VIEW_PERMISSIONS = ("orders.generate_supplier_orders", "partners.view_supplier_details")


@require_http_methods(['GET', 'POST'])
@permission_required_all(*MANAGE_PERMISSIONS)
def trip_empty_create(request):
    form = EmptyTripForm(request.POST if request.method == 'POST' else None, initial={'creation_key': uuid4()})
    if request.method == 'POST' and form.is_valid():
        try:
            batch = create_empty_trip(actor=request.user, **form.cleaned_data)
        except (ValidationError, OperationalError) as exc:
            form.add_error(None, ' '.join(exc.messages) if isinstance(exc, ValidationError) else 'База занята. Повторите создание.')
        else:
            messages.success(request, f'{batch} создан. Можно добавлять заказы и дополнительные товары.')
            return redirect('orders:trip_detail', pk=batch.pk)
    return render(request, 'orders/trip_empty_create.html', {'form': form})


@require_http_methods(['GET', 'POST'])
@permission_required_all(*MANAGE_PERMISSIONS)
def trip_add_orders(request, pk):
    batch = get_object_or_404(SupplierOrderBatch.objects.trips(), pk=pk)
    form = TripAddOrdersForm(request.POST if request.method == 'POST' else None, batch=batch)
    if request.method == 'POST' and form.is_valid():
        try:
            batch = add_orders_to_trip(actor=request.user, batch_id=batch.pk,
                order_ids=[order.pk for order in form.cleaned_data['orders']], revision=form.cleaned_data['revision'])
        except (ValidationError, OperationalError) as exc:
            form.add_error(None, ' '.join(exc.messages) if isinstance(exc, ValidationError) else 'База занята. Повторите добавление.')
        else:
            messages.success(request, 'Заказы добавлены в рейс.')
            return redirect('orders:trip_detail', pk=batch.pk)
    return render(request, 'orders/trip_add_orders.html', {'batch': batch, 'form': form})


def _trip_line_order_key(line):
    if line.product_kind == 'cd':
        group = line.cd.platform.name
        line.product_group = f'Диски · {group}'
        return (1, platform_order_key(group), normalized_order_name(line.product_name_snapshot), line.pk)
    group = line.tech.product_type.name
    line.product_group = f'Техника · {group}'
    return (0, normalized_order_name(group), normalized_order_name(line.product_name_snapshot), line.pk)


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
    price_id = order.trip.price_list_id if order.trip_id and order.price_list.is_trip_addition else order.price_list_id
    trips = list(available_trips(price_list_id=price_id, exclude_id=order.trip_id))
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
    batch = get_object_or_404(trip_queryset().trips(), pk=pk)
    from .arrival_models import TripArrival
    batch._arrival_locked = TripArrival.objects.filter(trip=batch,arrived_at__isnull=False).exists()
    from .fulfillment import operation_actions
    operation_actions(request.user, batch.trip_orders.all())
    manager = can_manage_trips(request.user)
    can_assign = manager and not batch._arrival_locked and all(order.status == CustomerProcurementOrder.Status.CREATED
        and not downstream_lock_reason(order) for order in batch.trip_orders.all())
    grouped, editor, price_editor = defaultdict(list), {}, {}
    accepted_suppliers = set(batch.invoice_flags.filter(accepted=True).values_list('supplier_id', flat=True))
    suppliers = list(Supplier.objects.all()) if manager else []
    lines = list(batch.lines.all())
    excluded = exclusion_keys((line.product_kind, line.product_id) for line in lines) if manager else set()
    chains = trip_supplier_chains(lines, excluded=excluded) if manager else {}
    priorities = {supplier.pk: supplier.priority for supplier in suppliers}
    for line in lines:
        line.supplier.invoice_accepted = line.supplier_id in accepted_suppliers
        line.invoice_accepted = line.supplier.invoice_accepted
        active = [row for row in line.allocations.all() if row.quantity]
        line.price_lock_reason = line_price_lock_reason(line)
        line.can_edit_price = manager and not line.price_lock_reason and not line.invoice_accepted
        line.can_edit_quantity = manager and not line.price_lock_reason and not line.invoice_accepted and all(
            row.order_item.order.status == CustomerProcurementOrder.Status.CREATED for row in active)
        line.can_return_to_m = (is_m_order_in_f(line) and line.price_supplier_id not in accepted_suppliers
            and (line.product_kind, line.product_id, line.price_supplier_id) not in excluded)
        grouped[line.supplier].append(line)
        if line.can_edit_price:
            price_editor[str(line.pk)] = {'name': line.product_name_snapshot, 'supplier': line.supplier.name,
                'price': str(line.supplier_price_aed_snapshot), 'quantity': line.quantity,
                'preview_url': reverse('orders:trip_price_preview', args=(batch.pk, line.pk)),
                'save_url': reverse('orders:trip_price_update', args=(batch.pk, line.pk))}
        if line.can_edit_quantity:
            targets = sorted((supplier for supplier in suppliers if supplier.pk != line.supplier_id
                              and (line.product_kind, line.product_id, supplier.pk) not in excluded),
                             key=lambda supplier: (-supplier.priority, supplier.name.casefold(), supplier.pk))
            allocations = []
            for allocation in line.allocations.all():
                item = allocation.order_item
                current = item.prepayment_quantity + item.postpayment_quantity
                allocations.append({"allocation_id": allocation.pk, "order_id": item.order_id,
                                    "recipient": item.order.recipient, "current": current,
                                    "elsewhere": current - allocation.quantity})
            editor[str(line.pk)] = {
                **supplier_priority_state(line.supplier_id, {pk: priorities[pk] for pk in chains[line.price_list_item_id]}),
                "name": line.product_name_snapshot, "quantity": line.quantity,
                "url": reverse("orders:trip_line_update", args=(batch.pk, line.pk)),
                "targets": [{"id": supplier.pk, "name": supplier.name, "priority": supplier.priority,
                    "disabled": supplier.pk in accepted_suppliers} for supplier in targets],
                "prices": [{"id": offer.supplier_id, "name": offer.supplier.name, "price": str(offer.price_aed)}
                           for offer in line.price_list_item.supplier_offers.all()
                           if (line.product_kind, line.product_id, offer.supplier_id) not in excluded],
                "price_supplier_id": line.price_supplier_id, "allocations": allocations,
            }
    for supplier_lines in grouped.values():
        supplier_lines.sort(key=_trip_line_order_key)
    financial, financial_error = None, ''
    if request.user.has_perm('price.view_supplier_prices'):
        try:
            financial = trip_financials(batch)
        except ValidationError as exc:
            financial_error = ' '.join(exc.messages)
    from .arrival_views import panel_context
    return render(request, "orders/trip_detail.html", {
        **panel_context(request,batch),
        "batch": batch, "supplier_groups": grouped.items(), "editor": editor, "can_edit": bool(editor),
        'can_add_goods': manager and request.user.has_perm('orders.create_order') and not batch._arrival_locked,
        'can_assign_orders': can_assign, 'price_editor': price_editor, 'can_manage_invoices': manager,
        'financial': financial, 'financial_error': financial_error,
        "can_view_supplier_prices": request.user.is_superuser or request.user.has_perm("price.view_supplier_prices"),
    })


@require_POST
@permission_required_all(*MANAGE_PERMISSIONS)
def trip_line_update(request, pk, line_pk):
    try:
        distribution = json.loads(request.POST.get("distribution", "null"))
        with transaction.atomic():
            returning = request.POST.get('action') == 'return_to_m'
            require_page_editable(batch_id=pk, line_id=line_pk, returning_to_m=returning,
                target_supplier_id=request.POST.get('target_supplier') if request.POST.get('action') == 'transfer' else None)
            if returning:
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
@permission_required_all(*VIEW_PERMISSIONS, "price.view_supplier_prices")
def trip_full_export(request, pk):
    with transaction.atomic():
        batch = get_object_or_404(SupplierOrderBatch.objects.trips(), pk=pk)
        lines = list(batch.lines.select_related(
            "supplier", "cd__platform", "cd__game_series", "tech__brand", "tech__product_type",
        ).order_by("pk"))
    response = HttpResponse(trip_order_xlsx(lines),
                            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = content_disposition_header(True, f"trip_{pk}_all.xlsx")
    response["X-Content-Type-Options"] = "nosniff"
    return response


@never_cache
@require_GET
@permission_required_all(*VIEW_PERMISSIONS)
def trip_export(request, pk, supplier_pk):
    batch = get_object_or_404(SupplierOrderBatch.objects.trips(), pk=pk)
    supplier = get_object_or_404(Supplier, pk=supplier_pk)
    lines = list(batch.lines.filter(supplier=supplier).select_related(
        "cd__platform", "cd__game_series", "tech__brand", "tech__product_type",
    ).order_by("pk"))
    if not lines:
        from django.http import Http404
        raise Http404
    show_prices = request.user.is_superuser or request.user.has_perm("price.view_supplier_prices")
    response = HttpResponse(supplier_order_xlsx(batch, supplier, lines, show_prices=show_prices),
                            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    filename = get_valid_filename(f"trip_{pk}_{supplier.letter}.xlsx")
    response["Content-Disposition"] = content_disposition_header(True, filename)
    return response
