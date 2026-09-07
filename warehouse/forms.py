from django import forms

from .models import Warehouse


class WarehouseTransferSourceForm(forms.Form):
    source_warehouse = forms.ModelChoiceField(
        label="Склад-отправитель",
        queryset=Warehouse.objects.all(),
        empty_label="Выберите склад-отправитель",
    )


class WarehouseTransferForm(forms.Form):
    destination_warehouse = forms.ModelChoiceField(label="Склад-получатель", queryset=Warehouse.objects.none())

    def __init__(self, *args, source_warehouse, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["destination_warehouse"].queryset = Warehouse.objects.exclude(pk=source_warehouse.pk)
