from django import forms
from digital_sales.models import Supplier


class ConfigurationForm(forms.Form):
    revision = forms.IntegerField(widget=forms.HiddenInput)
    enabled = forms.BooleanField(label='Магазин доступен в подключённых группах', required=False)
    purchases_enabled = forms.BooleanField(label='Разрешить реальные закупки после подтверждения покупателем', required=False)
    supplier = forms.ModelChoiceField(label='Цифровой поставщик для учёта', queryset=Supplier.objects.all(), required=False)


class DiscoveryForm(forms.Form):
    query = forms.CharField(label='Название игры', min_length=2, max_length=150)
    platform = forms.ChoiceField(label='Платформа', choices=[('playstation', 'PlayStation'), ('xbox', 'Xbox'), ('steam', 'Steam')])
    region = forms.CharField(label='Регион (необязательно)', required=False, max_length=80)
