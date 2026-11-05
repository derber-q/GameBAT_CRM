from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
from django import forms
from .crypto import public_id
from .models import BackupConfiguration


class ConfigurationForm(forms.ModelForm):
    class Meta:
        model=BackupConfiguration
        fields=['enabled','public_key','recovery_key_saved','schedule_time','timezone','max_pending','retention_days']
        labels={'enabled':'Ежедневное резервирование','public_key':'Публичный ключ владельца (PEM)',
            'recovery_key_saved':'Приватный ключ и пароль сохранены отдельно; прежние ключи при ротации сохранены',
            'schedule_time':'Время ежедневного снимка','timezone':'Часовой пояс','max_pending':'Максимум архивов в ожидании устройства',
            'retention_days':'Хранить доставленные архивы на сервере, дней'}
        widgets={'public_key':forms.Textarea(attrs={'rows':4}),'schedule_time':forms.TimeInput(attrs={'type':'time'})}

    def clean_timezone(self):
        value=self.cleaned_data['timezone']
        try:ZoneInfo(value)
        except (ZoneInfoNotFoundError,ValueError):raise forms.ValidationError('Неизвестный часовой пояс.')
        return value

    def clean(self):
        result=super().clean()
        if result.get('public_key'):
            try:public_id(result['public_key'].encode())
            except (ValueError,TypeError):self.add_error('public_key','Нужен публичный X25519 PEM. Приватный ключ на сервер не передавайте.')
        if result.get('enabled') and (not result.get('recovery_key_saved') or not result.get('public_key')):
            raise forms.ValidationError('Сначала сохраните отдельный ключ владельца и подтвердите его сохранение.')
        if not 1<=result.get('max_pending',0)<=10:self.add_error('max_pending','Допустимо от 1 до 10.')
        if not 1<=result.get('retention_days',0)<=30:self.add_error('retention_days','Допустимо от 1 до 30.')
        return result
