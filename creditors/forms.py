from django import forms

from warehouse.form_defaults import SingleWarehouseInitialMixin
from warehouse.models import Warehouse
from .models import Creditor, CreditorTransaction


class CreditorCreateForm(forms.ModelForm):
    class Meta:
        model = Creditor
        fields = ("name",)


class CreditorEditForm(forms.ModelForm):
    class Meta:
        model = Creditor
        fields = ("name", "description")
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}


class DebtAdjustmentForm(SingleWarehouseInitialMixin, forms.Form):
    warehouse = forms.ModelChoiceField(label="Склад", queryset=Warehouse.objects.all())
    money_source_type = forms.ChoiceField(
        label="Источник расчёта", choices=CreditorTransaction.MoneySourceType.choices,
    )
    new_debt = forms.DecimalField(
        label="Новое значение задолженности", max_digits=20, decimal_places=2,
        help_text="Плюс — контрагент должен GameBAT. Минус — GameBAT должен партнёру. Для старого счёта без партнёра доступен только плюс.",
    )
    comment = forms.CharField(
        label="Комментарий", required=False, widget=forms.Textarea(attrs={"rows": 3}),
    )
