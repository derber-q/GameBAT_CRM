"""Ручной подбор закупки на склад из сохранённой версии импортного прайса."""
from django import forms
from django.db.models import Q, Sum

from catalog.nomenclature_grouping import nomenclature_product_groups
from catalog.supplier_exclusions import exclusion_keys
from price.models import ProcurementPriceList
from warehouse.models import CDWarehouseStock, TechWarehouseStock
from .models import CustomerProcurementOrder, CustomerProcurementOrderItem, SupplierOrderBatch


class StockOrderPriceListForm(forms.Form):
    price_list = forms.ModelChoiceField(
        label="Версия импортного прайса", queryset=ProcurementPriceList.objects.filter(is_trip_addition=False),
        empty_label=None,
    )


class StockOrderCreateForm(forms.Form):
    recipient = forms.CharField(label="Название закупки", max_length=255, required=False,
                               help_text="Если оставить пустым, заказ будет называться «На склад».")
    comment = forms.CharField(label="Комментарий", required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, items, **kwargs):
        super().__init__(*args, **kwargs)
        self.items = items
        for item in items:
            self.fields[f"quantity_{item.pk}"] = forms.IntegerField(
                label=f"Количество: {item.product_name_snapshot}", min_value=0, max_value=2147483647,
                required=False, initial=0, widget=forms.NumberInput(attrs={
                    "class": "compact-input", "step": "1", "inputmode": "numeric",
                    "aria-label": f"Количество: {item.product_name_snapshot}",
                    "data-stock-order-quantity": "", "data-unit-kopecks": int(item.stock_unit_cost * 100),
                }),
            )

    def clean(self):
        data = super().clean()
        # Поля чужой версии или уже архивированного товара не должны теряться молча.
        for name in self.data:
            if name.startswith("quantity_") and name not in self.fields and self.data.get(name) not in ("", "0"):
                raise forms.ValidationError("Одна из выбранных позиций недоступна в этом прайсе. Обновите состав.")
        if not self.errors and not any(data.get(f"quantity_{item.pk}") for item in self.items):
            raise forms.ValidationError("Укажите количество хотя бы одного товара.")
        return data

    def order_lines(self):
        return [{"price_list_item_id": item.pk,
                 "prepayment_quantity": self.cleaned_data[f"quantity_{item.pk}"], "postpayment_quantity": 0}
                for item in self.items if self.cleaned_data.get(f"quantity_{item.pk}")]


def stock_order_items(price_list):
    items = list(price_list.items.select_related(
        "cd__platform", "cd__game_series", "tech__brand", "tech__product_type",
    ).filter(Q(cd__is_archived=False) | Q(tech__is_archived=False)))
    excluded = exclusion_keys((item.product_kind, item.product_id) for item in items)
    allowed = [item for item in items if (item.product_kind, item.product_id, item.selected_supplier_id) not in excluded]
    price_list.excluded_item_count = len(items) - len(allowed)
    return allowed


def previous_trip_stock_quantities():
    trip = SupplierOrderBatch.objects.filter(price_list__isnull=False).first()
    if trip is None:
        return None, {}
    rows = CustomerProcurementOrderItem.objects.filter(
        order__trip=trip, order__purpose=CustomerProcurementOrder.Purpose.STOCK,
    ).values('product_kind', 'cd_id', 'tech_id').annotate(
        total=Sum('prepayment_quantity') + Sum('postpayment_quantity'),
    )
    return trip, {(row['product_kind'], row[f"{row['product_kind']}_id"]): row['total'] for row in rows}


def stock_order_groups(items, form, *, previous_trip_quantities=None):
    previous_trip_quantities = previous_trip_quantities or {}
    totals = {}
    for kind, model in (("cd", CDWarehouseStock), ("tech", TechWarehouseStock)):
        ids = [item.product_id for item in items if item.product_kind == kind]
        for row in model.objects.filter(**{f"{kind}_id__in": ids}).values(f"{kind}_id").annotate(total=Sum("quantity")):
            totals[(kind, row[f"{kind}_id"])] = row["total"]
    groups = nomenclature_product_groups(
        [item for item in items if item.product_kind == "tech"],
        [item for item in items if item.product_kind == "cd"], product_of=lambda item: item.product,
    )
    return [{"name": name, "rows": [{
        "item": item, "stock": totals.get((item.product_kind, item.product_id), 0),
        "previous_trip_quantity": previous_trip_quantities.get((item.product_kind, item.product_id), 0),
        "current_cost": item.product.cost, "quantity": form[f"quantity_{item.pk}"],
    } for item in group]} for _kind, name, group in groups]
