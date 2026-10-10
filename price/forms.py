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
