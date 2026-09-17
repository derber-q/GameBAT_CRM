from django import forms

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


class DebtAdjustmentForm(forms.Form):
    warehouse = forms.ModelChoiceField(label="Склад", queryset=Warehouse.objects.all())
    money_source_type = forms.ChoiceField(
        label="Денежное хранилище", choices=CreditorTransaction.MoneySourceType.choices,
    )
    new_debt = forms.DecimalField(
        label="Новое значение задолженности", min_value=0, max_digits=20, decimal_places=2,
    )
    comment = forms.CharField(
        label="Комментарий", required=False, widget=forms.Textarea(attrs={"rows": 3}),
    )
