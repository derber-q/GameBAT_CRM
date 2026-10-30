"""Общий явный выбор заказчика без поиска контрагента по имени или телефону."""
import re
from django import forms
from django.core.exceptions import ValidationError
from .models import Partner


def resolve_customer(*, partner_id=None, partner_name="", required=False, allow_archived=False):
    name = str(partner_name or "").strip()
    if partner_id:
        if name:
            raise ValidationError("Выберите партнёра или введите произвольное название, а не оба сразу.")
        try:
            partner = Partner.objects.get(pk=partner_id)
        except (Partner.DoesNotExist, ValueError, TypeError) as exc:
            raise ValidationError("Выбранный партнёр не найден.") from exc
        if partner.is_archived and not allow_archived:
            raise ValidationError("Партнёр в архиве. Выберите действующего партнёра.")
        return partner, partner.name
    if len(name) > 255:
        raise ValidationError("Название заказчика не должно превышать 255 символов.")
    if required and not name:
        raise ValidationError("Для оптовой продажи укажите заказчика.")
    return None, name


def customer_filename(name):
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', str(name or '')).strip(' .')[:100] or 'Без_заказчика'


class CustomerSelectionForm(forms.Form):
    customer = forms.ChoiceField(label="Заказчик", required=False)
    custom_partner_name = forms.CharField(label="Название произвольного партнёра", max_length=255, required=False)

    def __init__(self, *args, allow_archived_initial=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['customer'].choices = [('', 'Выберите заказчика'), ('custom', 'Произвольный партнёр')] + [
            (str(partner.pk), partner.display_name) for partner in
            Partner.objects.filter(is_archived=False).only('pk', 'name', 'contact_person')]
        initial = self.initial.get('customer')
        if allow_archived_initial and initial and str(initial).isdecimal():
            archived = Partner.objects.filter(pk=initial, is_archived=True).first()
            if archived:
                self.fields['customer'].choices += [(str(archived.pk), f'{archived.display_name} (в архиве)')]

    def clean(self):
        data = super().clean()
        choice, name = data.get('customer'), data.get('custom_partner_name', '').strip()
        if choice == 'custom' and not name:
            self.add_error('custom_partner_name', 'Введите название произвольного партнёра.')
        if choice != 'custom' and name:
            self.add_error('custom_partner_name', 'Для ручного названия выберите «Произвольный партнёр».')
        data['partner_id'] = int(choice) if choice and choice != 'custom' else None
        data['partner_name'] = name if choice == 'custom' else ''
        return data


class PartnerChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, partner):
        return partner.display_name


class PartnerMultipleChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, partner):
        return partner.display_name
