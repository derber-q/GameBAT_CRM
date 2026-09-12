from django import forms

from warehouse.models import Warehouse


class ProcurementOrderUploadForm(forms.Form):
    recipient = forms.CharField(label="Получатель", max_length=255)
    comment = forms.CharField(label="Комментарий", required=False, widget=forms.Textarea(attrs={"rows": 3}))
    file = forms.FileField(label="Заполненный закупочный XLSX")


class ProcurementOrderHeaderForm(forms.Form):
    recipient = forms.CharField(label="Получатель", max_length=255)
    comment = forms.CharField(label="Комментарий", required=False, widget=forms.Textarea(attrs={"rows": 3}))


class PaymentWarehouseForm(forms.Form):
    warehouse = forms.ModelChoiceField(label="Склад оплаты", queryset=Warehouse.objects.all(), required=False)


class ReceivingAdjustmentForm(forms.Form):
    comment = forms.CharField(label="Причина корректировки", widget=forms.Textarea(attrs={"rows": 3}))
