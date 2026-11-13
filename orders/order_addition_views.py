"""Дополнение одного созданного клиентского заказа товарами из каталога."""
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import OperationalError
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from catalog.models import CD, Tech
from catalog.product_search import filter_products_by_text
from core.decorators import permission_required_all
from partners.models import Supplier

from .models import CustomerProcurementOrder
from .order_editing import downstream_lock_reason
from .services import add_catalog_items_to_order
from .trips import can_manage_trips
from .views import _order_queryset, _require_stock_prices


class OrderAdditionLineForm(forms.Form):
    label = forms.CharField(label="Товар", required=False, widget=forms.TextInput(attrs={
        "data-addition-search": True, "autocomplete": "off", "placeholder": "Начните вводить товар",
    }))
    product = forms.CharField(widget=forms.HiddenInput)
    supplier = forms.ModelChoiceField(label="Поставщик", queryset=Supplier.objects.all())
    supplier_price_aed = forms.DecimalField(label="Цена поставщика, AED", max_digits=20,
        decimal_places=6, min_value=Decimal("0.000001"))
    customer_price = forms.DecimalField(label="Цена заказчику, ₽", max_digits=20,
        decimal_places=2, min_value=0)
    quantity = forms.IntegerField(label="Количество", min_value=1, max_value=2147483647)


OrderAdditionFormSet = forms.formset_factory(
    OrderAdditionLineForm, extra=1, min_num=1, max_num=100, validate_min=True, validate_max=True,
)


@require_GET
@permission_required_all("orders.edit_created_order", "price.view_supplier_prices", "partners.view_supplier_details")
def product_search(request, pk):
    get_object_or_404(CustomerProcurementOrder, pk=pk)
    query = str(request.GET.get("q") or "").strip()
    if len(query) < 2:
        return JsonResponse({"results": []})
    results = []
    for kind, model, group in (("cd", CD, "platform"), ("tech", Tech, "product_type")):
        products = filter_products_by_text(model.objects.active(), query, product_kind=kind)
        products = products.annotate(available=Coalesce(Sum('warehouse_stocks__quantity'), 0))
        for product in products.select_related(group).order_by("name")[:20]:
            results.append({"type": kind, "id": product.pk, "sku": product.sku,
                "available":product.available,
                "label": f"{product.name} · {getattr(product, group).name} · {product.sku}"})
    return JsonResponse({"results": results})


@require_http_methods(["GET", "POST"])
@permission_required_all("orders.edit_created_order", "price.view_supplier_prices", "partners.view_supplier_details")
def add_catalog_items(request, pk):
    order = get_object_or_404(_order_queryset(), pk=pk)
    _require_stock_prices(request.user, order.purpose)
    if order.status != CustomerProcurementOrder.Status.CREATED:
        messages.error(request, "Изменять можно только заказ в статусе «Создан».")
        return redirect("orders:detail", pk=pk)
    lock_reason = downstream_lock_reason(order)
    if lock_reason:
        messages.error(request, lock_reason)
        return redirect("orders:detail", pk=pk)
    if order.trip_id and not can_manage_trips(request.user):
        messages.error(request, "Для изменения состава заказа в рейсе требуется право управления рейсами.")
        return redirect("orders:trip_detail", pk=order.trip_id)

    formset = OrderAdditionFormSet(request.POST or None, prefix="lines")
    if order.is_stock_order:
        for form in [*formset.forms, formset.empty_form]:
            form.fields["customer_price"].required = False
    if request.method == "POST" and formset.is_valid():
        lines = [{key: str(form.cleaned_data[key]) for key in
                  ("product", "supplier_price_aed", "customer_price", "quantity")}
                 | {"supplier": form.cleaned_data["supplier"].pk}
                 for form in formset if form.cleaned_data]
        try:
            add_catalog_items_to_order(actor=request.user, order_id=order.pk,
                revision=request.POST.get("revision"), lines=lines)
        except (ValidationError, OperationalError) as exc:
            message = " ".join(exc.messages) if isinstance(exc, ValidationError) else "База занята. Обновите страницу и повторите."
            messages.error(request, message)
        else:
            messages.success(request, f"Дополнительные товары добавлены в заказ №{order.pk}.")
            return redirect("orders:trip_detail", pk=order.trip_id) if order.trip_id else redirect("orders:detail", pk=order.pk)
    return render(request, "orders/add_catalog_items.html", {
        "order": order, "formset": formset,
        "trip_revision": order.trip.revision if order.trip_id else None,
        "search_url": reverse("orders:order_addition_search", args=(order.pk,)),
    })
