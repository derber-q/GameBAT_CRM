"""Ручная закупка на склад; клиентские назначения не включаются в подсказку уже заказанного складского объёма."""
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from core.decorators import permission_required_all
from price.models import ProcurementPriceList

from .models import CustomerProcurementOrder, SupplierOrderBatch
from .trips import can_manage_trips, _require_editable_trip
from .stock_order_form import StockOrderCreateForm, StockOrderPriceListForm, stock_order_groups, stock_order_items
from .stock_order_form import previous_trip_stock_quantities
from .views import DRAFT_SESSION_KEY


@never_cache
@require_http_methods(["GET", "POST"])
@permission_required_all("orders.create_order", "price.view_supplier_prices")
def stock_order_create(request, trip_pk=None):
    target_trip = None
    if trip_pk is not None:
        if not can_manage_trips(request.user):
            raise PermissionDenied
        target_trip = get_object_or_404(SupplierOrderBatch.objects.trips(), pk=trip_pk)
        try:
            with transaction.atomic():
                _require_editable_trip(target_trip)
        except ValidationError as exc:
            messages.error(request, ' '.join(exc.messages))
            return redirect('orders:trip_detail', pk=target_trip.pk)
    latest = ProcurementPriceList.objects.filter(is_trip_addition=False).first()
    default_id = target_trip.price_list_id if target_trip and target_trip.price_list_id else (latest.pk if latest else '')
    selected_id = (request.POST.get("price_list") if request.method == "POST"
                   else request.GET.get("price_list", default_id))
    choice_form = StockOrderPriceListForm({"price_list": selected_id})
    if target_trip and target_trip.price_list_id:
        choice_form.fields['price_list'].queryset = choice_form.fields['price_list'].queryset.filter(pk=target_trip.price_list_id)
    price_list, form, groups, previous_trip = None, None, [], None
    if latest and choice_form.is_valid():
        price_list = choice_form.cleaned_data["price_list"]
        items = stock_order_items(price_list)
        draft = request.session.get(DRAFT_SESSION_KEY, {})
        initial = {}
        if (draft.get("entry_method") == "form" and draft.get("price_list_id") == price_list.pk
                and draft.get('target_trip_id') == trip_pk):
            initial = {"recipient": draft["recipient"], "comment": draft["comment"], **{
                f"quantity_{row['price_list_item_id']}": row["prepayment_quantity"] for row in draft["lines"]
            }}
        form = StockOrderCreateForm(request.POST if request.method == "POST" else None,
            items=items, initial=initial, target_trip=target_trip)
        if request.method == "POST" and form.is_valid():
            request.session[DRAFT_SESSION_KEY] = {
                "price_list_id": price_list.pk, "recipient": form.cleaned_data["recipient"],
                "comment": form.cleaned_data["comment"], "lines": form.order_lines(),
                "purpose": CustomerProcurementOrder.Purpose.STOCK, "entry_method": "form",
            }
            if target_trip:
                request.session[DRAFT_SESSION_KEY] = {**request.session[DRAFT_SESSION_KEY],
                    'target_trip_id': target_trip.pk, 'target_trip_revision': form.cleaned_data['trip_revision']}
            return redirect("orders:preview")
        previous_trip, previous_trip_quantities = previous_trip_stock_quantities(target_trip)
        groups = stock_order_groups(items, form, previous_trip_quantities=previous_trip_quantities)
    return render(request, "orders/stock_create.html", {
        "choice_form": choice_form, "form": form, "price_list": price_list,
        "groups": groups, "has_price_lists": latest is not None,
        "previous_trip": previous_trip, 'target_trip': target_trip,
    })
