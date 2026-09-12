"""Явные формы карточек с серверной проверкой прав на каждое поле."""
import hashlib
import json
from decimal import Decimal

from django import forms
from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.urls import reverse

from warehouse.models import CDWarehouseStock, TechWarehouseStock, Warehouse
from warehouse.storage_locations import normalize_storage_location_list

from .models import CD, Tech
from .product_fields import (
    CD_CARD_FIELDS,
    CD_FIELD_PERMISSIONS,
    TECH_CARD_FIELDS,
    TECH_FIELD_PERMISSIONS,
)


def product_version(instance):
    """Возвращает optimistic-lock token для карточки и её складских остатков."""
    values = {}
    field_names = CD_CARD_FIELDS if isinstance(instance, CD) else TECH_CARD_FIELDS
    for field_name in field_names:
        field = instance._meta.get_field(field_name)
        value = getattr(instance, field.attname if field.is_relation else field_name)
        if isinstance(value, Decimal):
            value = format(value, "f")
        values[field_name] = value
    if instance.pk:
        stocks = list(
            instance.warehouse_stocks.order_by("warehouse_id").prefetch_related(
                "storage_assignments__location"
            )
        )
        values["warehouse_stocks"] = [
            (stock.warehouse_id, stock.quantity) for stock in stocks
        ]
        values["warehouse_storage_locations"] = [
            (
                stock.warehouse_id,
                [
                    assignment.location.canonical_value
                    for assignment in stock.storage_assignments.all()
                ],
            )
            for stock in stocks
        ]
    payload = json.dumps(values, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ProductCardFormMixin(forms.ModelForm):
    version = forms.CharField(widget=forms.HiddenInput)
    field_permissions = {}

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.allowed_fields = {
            field_name
            for field_name, permission in self.field_permissions.items()
            if user.is_superuser or user.has_perm(permission)
        }
        self.forbidden_fields = []
        stock_model = CDWarehouseStock if isinstance(self.instance, CD) else TechWarehouseStock
        stock_permission = (
            "warehouse.change_cdwarehousestock"
            if isinstance(self.instance, CD)
            else "warehouse.change_techwarehousestock"
        )
        self.can_change_stock = user.is_superuser or user.has_perm(stock_permission)
        stocks = list(
            stock_model.objects.filter(
                **{self.instance._meta.model_name: self.instance}
            ).prefetch_related("storage_assignments__location")
        ) if self.instance.pk else []
        stock_values = {stock.warehouse_id: stock.quantity for stock in stocks}
        storage_location_values = {
            stock.warehouse_id: ", ".join(
                assignment.location.canonical_value
                for assignment in stock.storage_assignments.all()
            )
            for stock in stocks
        }
        self.stock_fields = []
        self.storage_location_fields = []
        self.warehouse_field_pairs = []
        self.warehouses_by_id = {warehouse.pk: warehouse for warehouse in Warehouse.objects.all()}
        self.can_change_storage_location = (
            user.is_superuser or user.has_perm("warehouse.change_storage_location")
        )
        for warehouse in self.warehouses_by_id.values():
            stock_field_name = f"stock_{warehouse.pk}"
            self.fields[stock_field_name] = forms.IntegerField(
                label=warehouse.name,
                min_value=0,
                initial=stock_values.get(warehouse.pk, 0),
                disabled=not self.can_change_stock,
                required=self.can_change_stock,
                widget=forms.NumberInput(attrs={"min": 0, "step": 1}),
            )
            if not self.can_change_stock:
                self.fields[stock_field_name].widget.attrs["aria-readonly"] = "true"
            else:
                self.allowed_fields.add(stock_field_name)
            self.stock_fields.append(stock_field_name)

            location_field_name = f"storage_location_{warehouse.pk}"
            self.fields[location_field_name] = forms.CharField(
                label=f"Место хранения: {warehouse.name}",
                initial=storage_location_values.get(warehouse.pk, ""),
                required=False,
                disabled=not self.can_change_storage_location,
                widget=forms.TextInput(attrs={
                    "placeholder": "",
                    "autocomplete": "off",
                    "data-storage-location-autocomplete": "true",
                    "data-autocomplete-url": reverse(
                        "warehouse:storage_location_autocomplete", args=(warehouse.pk,)
                    ),
                    "aria-label": f"Место хранения: {warehouse.name}",
                }),
            )
            if not self.can_change_storage_location:
                self.fields[location_field_name].widget.attrs["aria-readonly"] = "true"
            else:
                self.allowed_fields.add(location_field_name)
            self.storage_location_fields.append(location_field_name)
            self.warehouse_field_pairs.append((stock_field_name, location_field_name))
        self.fields["version"].initial = product_version(self.instance)
        for field_name in ("sku",):
            if not getattr(self.instance, field_name):
                # Старые импортированные карточки могут содержать пустой артикул.
                # Это не должно блокировать изменение другого разрешённого поля.
                self.fields[field_name].required = False
        for field_name in self.field_permissions:
            field = self.fields[field_name]
            if field_name not in self.allowed_fields:
                field.disabled = True
                field.required = False
                field.widget.attrs["aria-readonly"] = "true"
        for field_name in ("description", "comment"):
            self.fields[field_name].widget.attrs.setdefault("rows", 4)
        self.can_edit = bool(self.allowed_fields)

    def clean(self):
        cleaned_data = super().clean()
        if not self.is_bound:
            return cleaned_data
        accepted_keys = self.allowed_fields | {"version", "csrfmiddlewaretoken"}
        self.forbidden_fields = sorted(set(self.data.keys()) - accepted_keys)
        if self.forbidden_fields:
            labels = []
            for field_name in self.forbidden_fields:
                if field_name in self.fields:
                    labels.append(str(self.fields[field_name].label))
                else:
                    try:
                        labels.append(str(self.instance._meta.get_field(field_name).verbose_name))
                    except FieldDoesNotExist:
                        labels.append(field_name)
            raise ValidationError(
                "Нет права изменять поля: %(fields)s.",
                params={"fields": ", ".join(labels)},
                code="forbidden_fields",
            )
        for field_name in self.storage_location_fields:
            if field_name not in self.allowed_fields or field_name not in cleaned_data:
                continue
            try:
                cleaned_data[field_name] = normalize_storage_location_list(cleaned_data[field_name])
            except ValidationError as exc:
                self.add_error(field_name, exc)
        return cleaned_data


class CDCardForm(ProductCardFormMixin):
    field_permissions = CD_FIELD_PERMISSIONS

    class Meta:
        model = CD
        fields = CD_CARD_FIELDS


class TechCardForm(ProductCardFormMixin):
    field_permissions = TECH_FIELD_PERMISSIONS

    class Meta:
        model = Tech
        fields = TECH_CARD_FIELDS


class ProductCreateFormMixin:
    """Форма создаёт только карточку — без остатков, себестоимости и цен."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ("description", "comment"):
            self.fields[field_name].widget.attrs.setdefault("rows", 4)


class CDCreateForm(ProductCreateFormMixin, forms.ModelForm):
    class Meta:
        model = CD
        fields = ("platform", "name", "description", "sku", "barcode", "cusa_ppsa_code", "comment")


class TechCreateForm(ProductCreateFormMixin, forms.ModelForm):
    class Meta:
        model = Tech
        fields = ("brand", "product_type", "name", "description", "sku", "barcode", "comment")
