from django import forms

from partners.models import SalesPlatform
from sales.models import Sale
from warehouse.models import Warehouse


class ProductOperationForm(forms.Form):
    PRODUCT_TYPES = (("cd", "CD"), ("tech", "Tech"))
    platform = forms.ModelChoiceField(label="Площадка", queryset=SalesPlatform.objects.all())
    warehouse = forms.ModelChoiceField(label="Склад", queryset=Warehouse.objects.all())
    product_search = forms.CharField(
        label="Товар", widget=forms.TextInput(attrs={"autocomplete": "off", "placeholder": "Начните вводить название товара..."})
    )
    product_type = forms.ChoiceField(choices=PRODUCT_TYPES, widget=forms.HiddenInput)
    product_id = forms.IntegerField(widget=forms.HiddenInput)
    quantity = forms.IntegerField(label="Количество", min_value=1)


class TransferForm(forms.Form):
    platform = forms.ModelChoiceField(label="Площадка", queryset=SalesPlatform.objects.all())
    warehouse = forms.ModelChoiceField(label="Склад-источник", queryset=Warehouse.objects.all())


class ReturnForm(ProductOperationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["warehouse"].label = "Склад возврата"


class ConsignmentSaleForm(forms.Form):
    payment_method = forms.ChoiceField(
        label="Форма оплаты",
        choices=(
            (Sale.PaymentMethod.CASH, Sale.PaymentMethod.CASH.label),
            (Sale.PaymentMethod.BANK_ACCOUNT, Sale.PaymentMethod.BANK_ACCOUNT.label),
        ),
    )
    quantity = forms.IntegerField(label="Реализовано, шт.", min_value=1)

    def __init__(self, *args, stock, **kwargs):
        super().__init__(*args, **kwargs)
        self.stock = stock
        self.fields["quantity"].widget.attrs["max"] = stock.quantity
        self.fields["quantity"].help_text = f"Доступно на реализации: {stock.quantity} шт."

    def clean_quantity(self):
        quantity = self.cleaned_data["quantity"]
        if quantity > self.stock.quantity:
            raise forms.ValidationError(f"На реализации осталось только {self.stock.quantity} шт.")
        return quantity
