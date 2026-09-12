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
    file = forms.FileField(label="Заполненный прайс .xlsx")


class ProcurementPriceCreateForm(forms.Form):
    exchange_rate = forms.DecimalField(
        label="Курс AED → RUB", min_value=0.000001, max_digits=20, decimal_places=6
    )
