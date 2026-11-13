from django import forms
from .models import Product, ManualPriceEntry
from .classification import COUNTRIES, region_code


class ConfigurationForm(forms.Form):
    revision = forms.IntegerField(widget=forms.HiddenInput)
    enabled = forms.BooleanField(label='Включить интеграцию', required=False)
    api_key = forms.CharField(label='Новый API-ключ (пусто — сохранить прежний)', required=False,
        max_length=500, widget=forms.PasswordInput(render_value=False))
    daily_enabled = forms.BooleanField(label='Ежедневное обновление', required=False)
    daily_at = forms.TimeField(label='Время обновления', required=False, widget=forms.TimeInput(attrs={'type': 'time'}))
    timezone_name = forms.CharField(label='Часовая зона', initial='Europe/Moscow')
    manual_sheet_enabled = forms.BooleanField(label='Обновлять ручную себестоимость из Google Sheets вместе с API', required=False)
    manual_sheet_url = forms.URLField(label='Таблица тарифов Google Sheets', required=False, max_length=500)

    def clean(self):
        values = super().clean()
        url = values.get('manual_sheet_url')
        if values.get('manual_sheet_enabled') and not url:
            self.add_error('manual_sheet_url', 'Укажите таблицу тарифов.')
        if url:
            from .sheet_source import spreadsheet_id, SheetSourceError
            try:
                spreadsheet_id(url)
            except SheetSourceError:
                self.add_error('manual_sheet_url', 'Укажите HTTPS-ссылку на таблицу docs.google.com/spreadsheets/d/…')
        return values


class LayoutForm(forms.ModelForm):
    revision = forms.IntegerField(widget=forms.HiddenInput)

    class Meta:
        model = Product
        fields = ['display_name', 'category', 'section', 'position', 'rule']
        labels = {'display_name': 'Название GameBAT', 'category': 'Категория', 'section': 'Раздел комплекта',
                  'position': 'Порядок', 'rule': 'Округление'}


class ManualPriceForm(forms.ModelForm):
    revision = forms.IntegerField(widget=forms.HiddenInput, initial=1)
    region = forms.ChoiceField(label='Страна / регион', required=False,
        choices=[('', 'Без региона')] + sorted(COUNTRIES.items(), key=lambda pair: pair[1]))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.initial['revision'] = self.instance.revision
            self.initial['region'] = region_code(self.instance.region)

    class Meta:
        model = ManualPriceEntry
        fields = ['kind', 'region', 'label', 'position']
        labels = {'kind': 'Блок', 'region': 'Страна / регион', 'label': 'Диапазон или номинал',
                  'position': 'Порядок'}
        widgets = {'position': forms.NumberInput(attrs={'style': 'width:65px'})}


ManualPriceFormSet = forms.modelformset_factory(ManualPriceEntry, form=ManualPriceForm,
    extra=0, max_num=250, absolute_max=300, validate_max=True)
