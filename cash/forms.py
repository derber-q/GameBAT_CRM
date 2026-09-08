from django import forms


class CashOperationForm(forms.Form):
    operation_key = forms.UUIDField(required=False, widget=forms.HiddenInput)
    amount = forms.DecimalField(label="Сумма", min_value=0.01, max_digits=20, decimal_places=2)
    comment = forms.CharField(label="Комментарий / назначение", widget=forms.Textarea(attrs={"rows": 3}))
