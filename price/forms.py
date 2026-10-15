from decimal import Decimal

from django import forms

from partners.models import Supplier
from warehouse.models import Warehouse

from .models import PriceDocumentSettings


class SafeSupplierChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.safe_label


class PriceDocumentSettingsForm(forms.ModelForm):
    class Meta:
        model = PriceDocumentSettings
        fields = (
            "company_name", "address", "phone_1", "phone_2", "email",
            "website", "telegram", "logo", "additional_text",
        )
        widgets = {"additional_text": forms.Textarea(attrs={"rows": 3})}


class WarehousePriceForm(forms.Form):
    warehouse = forms.ModelChoiceField(label="Склад", queryset=Warehouse.objects.all())


class SupplierPriceUploadForm(forms.Form):
    supplier = SafeSupplierChoiceField(label="Поставщик", queryset=Supplier.objects.all())
    cd_file = forms.FileField(label="Прайс дисков .xlsx", required=False)
    tech_file = forms.FileField(label="Прайс техники .xlsx", required=False)

    def clean(self):
        data = super().clean()
        if not data.get("cd_file") and not data.get("tech_file"):
            raise forms.ValidationError("Выберите прайс дисков, техники или оба файла.")
        return data


class ProcurementPriceCreateForm(forms.Form):
    exchange_rate_usdt_aed = forms.DecimalField(
        label="AED → USDT: AED за 1 USDT", min_value=0.000001, max_digits=20, decimal_places=6,
        help_text="Например, 3,67. Цена в AED делится на этот курс.",
    )
    exchange_rate_usdt_rub = forms.DecimalField(
        label="USDT → RUB: RUB за 1 USDT", min_value=0.000001, max_digits=20, decimal_places=6,
        help_text="Например, 90. Сумма в USDT умножается на этот курс.",
    )
    delivery_general_usdt_per_kg = forms.DecimalField(
        label="Доставка прочей техники, USDT за кг", min_value=Decimal("0"),
        max_digits=20, decimal_places=6,
        help_text="Геймпады, гарнитуры, аксессуары и остальные типы техники без специального тарифа.",
    )
    delivery_devices_usdt_per_kg = forms.DecimalField(
        label="Доставка консолей, мини-ПК и VR/AR, USDT за кг", min_value=Decimal("0"),
        max_digits=20, decimal_places=6,
        help_text="Включая портативные и ретро-консоли. Тариф выбирается по типу товара.",
    )
    delivery_storage_usdt_per_kg = forms.DecimalField(
        label="Доставка памяти и накопителей, USDT за кг", min_value=Decimal("0"),
        max_digits=20, decimal_places=6,
        help_text="HDD, SSD, карты памяти, оперативная память и флеш-накопители.",
    )
    delivery_cd_rub = forms.DecimalField(
        label="Доставка одного диска, RUB", min_value=Decimal("0"), initial=Decimal("0"),
        max_digits=20, decimal_places=2,
        help_text="Фиксированная сумма за один диск. Добавляется к цене каждого диска без пересчёта валюты; можно указать 0.",
    )


class ProcurementWeightsForm(forms.Form):
    def __init__(self, *args, products, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.can_change_weight = user.is_superuser or user.has_perm("catalog.change_tech_weight")
        for product in products:
            self.fields[f"weight_{product.pk}"] = forms.IntegerField(
                label=f"{product.name} · {product.sku or product.pk}", min_value=1,
                max_value=2147483647, disabled=not self.can_change_weight,
                help_text=f"{product.product_type} · {product.product_type.get_procurement_delivery_group_display()}",
                widget=forms.NumberInput(attrs={"class": "compact-input", "inputmode": "numeric"}),
            )

    @property
    def weights(self):
        return {int(name.removeprefix("weight_")): value for name, value in self.cleaned_data.items()}


class ProcurementSurchargesForm(forms.Form):
    def __init__(self, *args, products, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.can_change_surcharge = user.is_superuser or user.has_perm("price.change_procurement_markup")
        for product in products:
            self.fields[f"surcharge_{product.pk}"] = forms.DecimalField(
                label=f"{product.name} · {product.sku or product.pk}", min_value=Decimal("0"),
                max_digits=20, decimal_places=2, disabled=not self.can_change_surcharge,
                help_text=f"{product.product_type} · {product.brand}",
                widget=forms.NumberInput(attrs={"class": "compact-input", "inputmode": "decimal"}),
            )

    @property
    def surcharges(self):
        return {int(name.removeprefix("surcharge_")): value for name, value in self.cleaned_data.items()}
