"""Параметры FBS и габариты без копирования веса или категорий Маркета."""
from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.forms import formset_factory

from catalog.nomenclature_forms import product_version
from catalog.product_fields import field_permissions_for
from .fbs_pricing import DEFAULTS, INPUT_FIELDS, middle_mile, pricing_configuration, product_context
from .models import CategorySchema, Integration


class FBSSettingsForm(forms.Form):
    tax_rate = forms.DecimalField(label="Налоговая ставка, %", max_digits=5, decimal_places=2, min_value=0, max_value=Decimal("99.99"))
    payment_rate = forms.DecimalField(label="Тариф перевода денежных средств, %", max_digits=5, decimal_places=2, min_value=0, max_value=Decimal("99.99"))
    packaging = forms.DecimalField(label="Стоимость упаковки одного товара, ₽", max_digits=20, decimal_places=2, min_value=0)
    delivery_rate = forms.DecimalField(label="Процент доставки покупателю, %", max_digits=5, decimal_places=2, min_value=0, max_value=Decimal("99.99"))
    delivery_max = forms.DecimalField(label="Максимальная стоимость доставки, ₽", max_digits=20, decimal_places=2, min_value=0)
    fixed_payment = forms.DecimalField(label="Фиксированная комиссия за приём платежа, ₽", max_digits=20, decimal_places=2, min_value=0)
    other_fbs = forms.DecimalField(label="Дополнительные фиксированные расходы FBS, ₽", max_digits=20, decimal_places=2, min_value=0)
    middle_first_l = forms.IntegerField(label="Первый диапазон, до скольких литров включительно", min_value=1)
    middle_first_fee = forms.DecimalField(label="Стоимость первого диапазона, ₽", max_digits=20, decimal_places=2, min_value=0)
    middle_max = forms.DecimalField(label="Максимальная стоимость средней мили, ₽", max_digits=20, decimal_places=2, min_value=0)

    def __init__(self, *args, integration, **kwargs):
        super().__init__(*args, initial=pricing_configuration(integration), **kwargs)

    def clean(self):
        values = super().clean()
        if values.get("tax_rate", 0) + values.get("payment_rate", 0) >= 100:
            raise ValidationError("Сумма налога и тарифа перевода должна быть меньше 100%.")
        return values


class MiddleMileBandForm(forms.Form):
    until_l = forms.IntegerField(label="До литров включительно", required=False, min_value=1, help_text="У последнего диапазона оставьте пустым.")
    per_l = forms.DecimalField(label="Стоимость каждого литра, ₽", max_digits=20, decimal_places=2, min_value=0)


MiddleMileFormSet = formset_factory(MiddleMileBandForm, extra=1, max_num=20, validate_max=True, can_delete=True)


def clean_configuration(form, bands):
    if not form.is_valid() or not bands.is_valid():
        return None
    values = {name: format(value, ".2f") if isinstance(value, Decimal) else str(value) for name, value in form.cleaned_data.items()}
    values["middle_bands"] = [
        {"until_l": str(row["until_l"]) if row.get("until_l") else None, "per_l": str(row["per_l"])}
        for row in bands.cleaned_data if row and not row.get("DELETE")
    ]
    try:
        middle_mile(Decimal(1), values)
    except ValidationError as exc:
        form.add_error(None, exc)
        return None
    return values


class CategoryRateForm(forms.Form):
    category_id = forms.IntegerField(label="ID категории", min_value=1)
    name = forms.CharField(label="Категория Яндекс Маркета", max_length=512, required=False)
    placement_rate = forms.DecimalField(label="Тариф размещения, %", max_digits=5, decimal_places=2, min_value=0, max_value=Decimal("99.99"), required=False)


CategoryRateFormSet = formset_factory(CategoryRateForm, extra=1, max_num=1000, validate_max=True)


class FBSProductForm(forms.Form):
    version = forms.CharField(widget=forms.HiddenInput)
    yandex_desired_profit = forms.DecimalField(label="Желаемая чистая прибыль с товара, ₽", max_digits=20, decimal_places=2, min_value=0, required=False)
    yandex_pricing_integration = forms.ModelChoiceField(label="Подключение Яндекс Маркета", queryset=Integration.objects.all(), required=False)
    yandex_pricing_category = forms.ModelChoiceField(label="Категория Яндекс Маркета", queryset=CategorySchema.objects.all().order_by("name", "category_id"), required=False)
    length_cm = forms.DecimalField(label="Длина упаковки, см", max_digits=8, decimal_places=3, min_value=Decimal("0.001"), required=False)
    width_cm = forms.DecimalField(label="Ширина упаковки, см", max_digits=8, decimal_places=3, min_value=Decimal("0.001"), required=False)
    height_cm = forms.DecimalField(label="Высота упаковки, см", max_digits=8, decimal_places=3, min_value=Decimal("0.001"), required=False)
    weight_grams = forms.IntegerField(label="Вес с упаковкой, г", min_value=1, required=False)

    def __init__(self, *args, product, user, **kwargs):
        self.product = product
        initial = {field: getattr(product, field) for field in INPUT_FIELDS}
        try:
            integration, category = product_context(product)
            initial["yandex_pricing_integration"] = integration
            initial["yandex_pricing_category"] = category
        except ValidationError:
            pass
        initial["version"] = product_version(product)
        super().__init__(*args, initial=initial, **kwargs)
        permissions = field_permissions_for(type(product))
        self.allowed_fields = {field for field in INPUT_FIELDS if user.is_superuser or user.has_perm(permissions[field])}
        for field in INPUT_FIELDS:
            self.fields[field].disabled = field not in self.allowed_fields or product.is_archived
        self.can_edit = bool(self.allowed_fields) and not product.is_archived

    def clean(self):
        values = super().clean()
        if self.is_bound:
            invalid = set(self.data) - self.allowed_fields - {"version", "csrfmiddlewaretoken", "action"}
            if invalid:
                raise ValidationError("Нет права изменять эти параметры: " + ", ".join(sorted(invalid)))
        return values


def category_rates_initial():
    return list(CategorySchema.objects.order_by("name", "category_id").values("category_id", "name", "placement_rate"))
