from django import forms

from warehouse.form_defaults import SingleWarehouseInitialMixin
from warehouse.models import Warehouse
from .models import Sale
from partners.customers import CustomerSelectionForm


class SaleCreateForm(SingleWarehouseInitialMixin, CustomerSelectionForm):
    warehouse = forms.ModelChoiceField(label="Склад", queryset=Warehouse.objects.all())
    sale_type = forms.ChoiceField(label="Тип продажи", choices=Sale.SaleType.choices)
    price_type = forms.ChoiceField(label="Тип цены", choices=Sale.PriceType.choices)
    payment_method = forms.ChoiceField(label="Способ оплаты", choices=[choice for choice in Sale.PaymentMethod.choices if choice[0] != Sale.PaymentMethod.UNDEFINED])
    cash_received_amount = forms.DecimalField(
        label="Получено от покупателя", required=False, min_value=0,
        max_digits=20, decimal_places=2,
        help_text="Пустое поле — стоимость товаров. Наличные с суммой 0 для партнёра из базы — продажа в долг. При постоплате сумму указывают при подтверждении оплаты.",
    )
    note = forms.CharField(
        label="Примечание", required=False, widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *args, imported_wholesale=False, imported_report=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["price_type"].choices = [
            choice for choice in Sale.PriceType.choices
            if choice[0] not in {Sale.PriceType.CONSIGNMENT, Sale.PriceType.YANDEX_MARKET}
        ]
        self.fields["sale_type"].choices = [
            choice for choice in Sale.SaleType.choices
            if choice[0] not in {Sale.SaleType.CONSIGNMENT, Sale.SaleType.YANDEX_MARKET}
        ]
        if imported_wholesale:
            self.fields["warehouse"].disabled = True
            self.fields["price_type"].disabled = True
            self.fields["sale_type"].disabled = True
            if self.initial.get('customer'):
                self.fields['customer'].disabled = True
                self.fields['custom_partner_name'].disabled = True
        if imported_report:
            self.fields['payment_method'].disabled = True
            if self.initial.get('customer') == 'custom':
                self.fields['custom_partner_name'].disabled = False
        self.order_fields(('warehouse', 'sale_type', 'price_type', 'customer', 'custom_partner_name', 'payment_method', 'cash_received_amount', 'note'))

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('sale_type') == Sale.SaleType.WHOLESALE and not cleaned.get('customer'):
            self.add_error('customer', 'Для оптовой продажи укажите заказчика.')
        if (cleaned.get("price_type") == Sale.PriceType.WHOLESALE
                and cleaned.get("sale_type") not in (None, Sale.SaleType.WHOLESALE)):
            self.add_error("price_type", "Оптовая цена доступна только для оптовой продажи.")
        if cleaned.get('payment_method') == Sale.PaymentMethod.PARTNER_DEBT:
            if cleaned.get('sale_type') != Sale.SaleType.WHOLESALE or not cleaned.get('partner_id'):
                self.add_error('payment_method', 'Продажа в долг доступна только партнёру из справочника в оптовой продаже.')
            if cleaned.get('cash_received_amount') not in (None, 0):
                self.add_error('cash_received_amount', 'При продаже в долг полученная сумма должна быть равна нулю.')
        return cleaned


class WholesalePriceImportForm(CustomerSelectionForm):
    file = forms.FileField(label="Заполненный оптовый XLSX", required=False)
