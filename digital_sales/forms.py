import uuid
from decimal import Decimal
from django import forms
from .models import Buyer, Supplier, DigitalBot, RETAIL_LABEL
from .services import normalized_items


class BuyerForm(forms.ModelForm):
    class Meta:
        model = Buyer
        fields = ['name', 'partner', 'contact', 'comment']


class BalanceForm(forms.Form):
    buyer = forms.ModelChoiceField(label='Покупатель', queryset=Buyer.objects.all(), required=False)
    supplier = forms.ModelChoiceField(label='Поставщик', queryset=Supplier.objects.all(), required=False)
    kind = forms.ChoiceField(label='Операция', choices=[('topup', 'Пополнение'), ('opening', 'Начальный остаток'), ('adjustment', 'Корректировка')])
    amount = forms.DecimalField(label='Сумма со знаком, ₽', max_digits=20, decimal_places=2)
    reason = forms.CharField(label='Причина', max_length=500)
    operation_key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)


class BuyerChoiceField(forms.ChoiceField):
    """Розница — способ расчёта, а не счёт с балансом в справочнике Buyer."""
    def __init__(self, **kwargs):
        super().__init__(label='Покупатель', choices=self.buyer_choices, **kwargs)

    @staticmethod
    def buyer_choices():
        return [('', 'Выберите покупателя'), ('retail', RETAIL_LABEL),
                *((str(buyer.pk), buyer.name) for buyer in Buyer.objects.order_by('name', 'pk'))]

    def clean(self, value):
        value = super().clean(value)
        if value == 'retail':
            return value
        try:
            return Buyer.objects.get(pk=value)
        except (Buyer.DoesNotExist, ValueError):
            raise forms.ValidationError('Выберите существующего покупателя.') from None


class DraftForm(forms.Form):
    revision = forms.IntegerField(widget=forms.HiddenInput)
    buyer = BuyerChoiceField()
    price = forms.DecimalField(label='Общая цена продажи, ₽', min_value=Decimal('0.01'), max_digits=20, decimal_places=2)


class ItemsField(forms.CharField):
    def __init__(self, **kwargs):
        super().__init__(label='Цифровые позиции', widget=forms.Textarea(attrs={'rows': 5}),
            help_text='По строке на товар: название | себестоимость RUB. Например: Test Game | 1500.00', **kwargs)

    def clean(self, value):
        text = super().clean(value)
        if len(text) > 32768:
            raise forms.ValidationError('Состав слишком велик.')
        rows = []
        for line in text.splitlines():
            if not line.strip():
                continue
            parts = line.split('|')
            if len(parts) not in (2, 3):
                raise forms.ValidationError('В каждой строке нужны название и себестоимость через |.')
            rows.append({'name': parts[0].strip(), 'cost': parts[1].strip(), 'number': parts[2].strip() if len(parts) == 3 else ''})
        return normalized_items(rows)


class SecretTextarea(forms.Textarea):
    """Новый комплект допускает переводы строк, но не отражается в HTML после ошибки."""
    def format_value(self, value):
        return None


class ManualForm(forms.Form):
    supplier = forms.ModelChoiceField(label='Поставщик', queryset=Supplier.objects.all())
    buyer = BuyerChoiceField()
    items = ItemsField()
    price = forms.DecimalField(label='Общая цена продажи, ₽', min_value=Decimal('0.01'), max_digits=20, decimal_places=2)
    numbers = forms.CharField(label='Номера заказов поставщика через запятую', required=False, max_length=1000)
    secret = forms.CharField(label='Данные цифрового товара', required=False, max_length=32768,
                             strip=False, widget=SecretTextarea(attrs={'autocomplete': 'off', 'rows': 5}))
    comment = forms.CharField(label='Комментарий', required=False, widget=forms.Textarea(attrs={'rows': 2}))
    source_url = forms.URLField(label='Ссылка на источник', required=False)
    creation_key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)


class SupplierForm(forms.ModelForm):
    chat_ids = forms.CharField(label='Разрешённые chat ID через запятую')
    sender_ids = forms.CharField(label='Разрешённые ID отправителей через запятую')

    class Meta:
        model = Supplier
        fields = ['name', 'chat_ids', 'sender_ids']

    def _ids(self, name, negative=False):
        try:
            values = sorted(set(int(value.strip()) for value in self.cleaned_data[name].split(',')))
        except ValueError:
            raise forms.ValidationError('Укажите числовые Telegram ID через запятую.') from None
        if not 1 <= len(values) <= 30 or any(not (-2**63 < value < 0 if negative else 0 < value < 2**63) for value in values):
            raise forms.ValidationError('Проверьте диапазон ID; chat ID группы должен быть отрицательным.')
        if name == 'chat_ids':
            for row in Supplier.objects.exclude(pk=self.instance.pk):
                if set(values) & set(row.chat_ids):
                    raise forms.ValidationError('Этот чат уже принадлежит другому цифровому поставщику.')
        return values

    def clean_chat_ids(self):
        return self._ids('chat_ids', negative=True)

    def clean_sender_ids(self):
        return self._ids('sender_ids')


class BotForm(forms.ModelForm):
    class Meta:
        model = DigitalBot
        fields = ['enabled', 'username']
