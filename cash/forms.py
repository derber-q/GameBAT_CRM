from django import forms


class CashOperationForm(forms.Form):
    amount = forms.DecimalField(label="Сумма", min_value=0.01, max_digits=20, decimal_places=2)
    comment = forms.CharField(label="Комментарий / назначение", widget=forms.Textarea(attrs={"rows": 3}))
