from django import forms
from django.contrib.auth import get_user_model
from .models import BotConfig


class ConfigurationForm(forms.ModelForm):
    class Meta:
        model = BotConfig
        fields = ['enabled', 'username', 'warehouse', 'operator']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['enabled'].label = 'Подключение обработчика Telegram'
        self.fields['enabled'].help_text = 'Для временной остановки заказов используйте переключатель на странице «Прайсы наличие»: он сохраняет ответы покупателям.'
        self.fields['operator'].queryset = get_user_model().objects.filter(is_active=True, is_staff=True)
        self.fields['warehouse'].required = True
        self.fields['operator'].required = True

    def clean(self):
        data = super().clean()
        actor = data.get('operator')
        if actor and not actor.has_perms(['sales.create_sale', 'sales.import_wholesale_price',
                                         'sales.view_sale_detail', 'price.generate_wholesale_price']):
            self.add_error('operator', 'Сотруднику нужны права создания продаж, импорта прайса, просмотра продажи и экспорта оптового прайса.')
        return data

    def clean_username(self):
        import re
        value = self.cleaned_data['username'].lstrip('@')
        if not re.fullmatch(r'[A-Za-z0-9_]{5,64}', value) or not value.lower().endswith('bot'):
            raise forms.ValidationError('Укажите username этого бота без @.')
        return value
