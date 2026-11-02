import os
from django import forms
from .models import StaffBot
from .configuration import token_configured, validate_token


class StaffBotForm(forms.ModelForm):
    token = forms.CharField(label='Новый токен (пусто — сохранить прежний)', required=False,
        widget=forms.PasswordInput(render_value=False, attrs={'autocomplete': 'new-password'}))
    username = forms.RegexField(label='Username бота без @', regex=r'^[A-Za-z][A-Za-z0-9_]{4,31}$', max_length=32)
    cooldown_seconds = forms.IntegerField(label='Интервал запросов сотрудника, секунд', min_value=5, max_value=3600)

    class Meta:
        model = StaffBot
        fields = ['name', 'username', 'enabled', 'cooldown_seconds']
        labels = {'name': 'Название', 'enabled': 'Включить бота сотрудников'}

    def clean_token(self):
        token = self.cleaned_data.get('token', '')
        return validate_token(token) if token else ''

    def clean(self):
        values = super().clean()
        if values.get('token') and os.environ.get('GAMEBAT_TELEGRAM_STAFF_BOT_TOKEN'):
            self.add_error('token', 'Токен задан окружением. Измените его в настройках процесса.')
        if values.get('enabled') and self.initial.get('enabled') and (
                values.get('token') or values.get('username') != self.initial.get('username')):
            self.add_error('enabled', 'Перед заменой токена или username выключите бота и дождитесь остановки обработчика.')
        if values.get('enabled') and not (values.get('token') or token_configured()):
            self.add_error('enabled', 'Сначала настройте токен.')
        return values
