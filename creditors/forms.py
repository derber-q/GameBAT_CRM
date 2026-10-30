from decimal import Decimal

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
    amount_mode = forms.ChoiceField(
        label="Как указать задолженность", required=False, initial="total",
        choices=(("total", "Итоговая сумма"), ("change", "Изменить на сумму")),
        widget=forms.RadioSelect,
    )
    new_debt = forms.DecimalField(
        label="Новое значение задолженности", max_digits=20, decimal_places=2, required=False, localize=True,
        help_text="Плюс — контрагент должен GameBAT. Минус — GameBAT должен партнёру. Для старого счёта без партнёра доступен только плюс.",
        widget=forms.TextInput(attrs={"inputmode": "decimal", "autocomplete": "off"}),
    )
    change_direction = forms.ChoiceField(
        label="Изменение задолженности", required=False, initial="+",
        choices=(("+", "+ Увеличить"), ("-", "− Уменьшить")), widget=forms.RadioSelect,
    )
    change_amount = forms.DecimalField(
        label="Сумма изменения, ₽", max_digits=20, decimal_places=2,
        min_value=Decimal("0.01"), required=False, localize=True,
        widget=forms.TextInput(attrs={"inputmode": "decimal", "autocomplete": "off"}),
    )
    comment = forms.CharField(
        label="Комментарий", required=False, widget=forms.Textarea(attrs={"rows": 3}),
    )

    def clean(self):
        data = super().clean()
        # Отсутствие режима сохраняет совместимость с прежней формой и её POST.
        mode = data.get("amount_mode") or "total"
        data["amount_mode"] = mode
        if mode == "change":
            for name in ("change_amount", "change_direction"):
                if not data.get(name) and name not in self.errors:
                    self.add_error(name, "Обязательное поле.")
            if data.get("change_amount") is not None and data.get("change_direction"):
                data["debt_delta"] = data["change_amount"] * (1 if data["change_direction"] == "+" else -1)
        elif mode == "total" and data.get("new_debt") is None and "new_debt" not in self.errors:
            self.add_error("new_debt", "Обязательное поле.")
        return data
