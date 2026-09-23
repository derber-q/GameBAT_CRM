from django import forms

from partners.models import SalesPlatform
from warehouse.models import Warehouse


class TransferForm(forms.Form):
    platform = forms.ModelChoiceField(label="Площадка", queryset=SalesPlatform.objects.all())
    warehouse = forms.ModelChoiceField(label="Склад-источник", queryset=Warehouse.objects.all())
