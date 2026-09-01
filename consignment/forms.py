from django import forms

from partners.models import SalesPlatform


class ProductOperationForm(forms.Form):
    PRODUCT_TYPES = (("cd", "CD"), ("tech", "Tech"))
    platform = forms.ModelChoiceField(label="Площадка", queryset=SalesPlatform.objects.all())
    product_search = forms.CharField(
        label="Товар", widget=forms.TextInput(attrs={"autocomplete": "off", "placeholder": "Начните вводить название товара..."})
    )
    product_type = forms.ChoiceField(choices=PRODUCT_TYPES, widget=forms.HiddenInput)
    product_id = forms.IntegerField(widget=forms.HiddenInput)
    quantity = forms.IntegerField(label="Количество", min_value=1)


class TransferForm(ProductOperationForm):
    reward_per_unit = forms.DecimalField(
        label="Вознаграждение GameBAT за единицу", min_value=0, max_digits=16, decimal_places=2
    )


class ReturnForm(ProductOperationForm):
    pass
