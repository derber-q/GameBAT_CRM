from django import forms

from warehouse.models import Warehouse
from .models import Sale


class SaleCreateForm(forms.Form):
    warehouse = forms.ModelChoiceField(label="Склад", queryset=Warehouse.objects.all())
    price_type = forms.ChoiceField(label="Тип цены", choices=Sale.PriceType.choices)
    sale_type = forms.ChoiceField(label="Тип продажи", choices=Sale.SaleType.choices)
    payment_method = forms.ChoiceField(label="Способ оплаты", choices=Sale.PaymentMethod.choices)

    def __init__(self, *args, imported_wholesale=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["price_type"].choices = [
            choice for choice in Sale.PriceType.choices if choice[0] != Sale.PriceType.CONSIGNMENT
        ]
        self.fields["sale_type"].choices = [
            choice for choice in Sale.SaleType.choices if choice[0] != Sale.SaleType.CONSIGNMENT
        ]
        if imported_wholesale:
            self.fields["warehouse"].disabled = True
            self.fields["price_type"].disabled = True


class WholesalePriceImportForm(forms.Form):
    file = forms.FileField(label="Заполненный оптовый XLSX")
