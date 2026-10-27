from django import forms
from .models import Supplier, Partner, SalesPlatform
import uuid


class PartnerForm(forms.ModelForm):
    request_key = forms.UUIDField(required=False, widget=forms.HiddenInput, initial=uuid.uuid4)
    create_platform = forms.BooleanField(label='Создать новую площадку реализации', required=False)

    def clean_telegram(self):
        from .telegram import normalize_telegram
        return normalize_telegram(self.cleaned_data.get('telegram'))

    def __init__(self, *args, can_create_platform=False, **kwargs):
        super().__init__(*args, **kwargs)
        if not can_create_platform:
            self.fields.pop('create_platform')
        self.order_fields(('request_key', 'name', 'contact_person', 'phone_1', 'phone_2', 'telegram', 'address',
            'platform', 'create_platform', 'is_archived'))

    def clean(self):
        data = super().clean()
        if data.get('create_platform') and data.get('platform'):
            self.add_error('platform', 'Выберите существующую площадку или создайте новую.')
        return data

    class Meta:
        model = Partner
        fields = ('name', 'contact_person', 'phone_1', 'phone_2', 'telegram', 'address', 'platform', 'is_archived')
        widgets = {'address': forms.Textarea(attrs={'rows': 3})}
        help_texts = {'telegram': '@username или ссылка t.me/username. Кнопка чата открывает Telegram в браузере.'}


class SalesPlatformForm(forms.ModelForm):
    class Meta:
        model = SalesPlatform
        fields = ('name', 'address', 'legal_entity', 'phone_1', 'phone_2', 'phone_3', 'email', 'telegram')


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = (
            "name", "letter", "highlight_color", "legal_entity", "email", "phone_1",
            "phone_2", "phone_3", "website", "telegram",
            "priority",
        )
        widgets = {"highlight_color": forms.TextInput(attrs={"type": "color"})}
        help_texts = {
            "priority": "1 — самый высокий приоритет. При равной цене выбирается меньшее число.",
        }
