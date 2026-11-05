"""Настройка явных платформ/категорий без подмены номенклатуры."""
from django import forms
from .customs_models import CustomsGroup,CUSTOMS_FIELDS,CONFIRMABLE_FIELDS


class CustomsGroupForm(forms.ModelForm):
    expected_updated=forms.CharField(required=False,widget=forms.HiddenInput)
    confirm_values=forms.BooleanField(required=False,label='Непустые характеристики проверены ответственным сотрудником')

    class Meta:
        model=CustomsGroup
        fields=('name','medium','platform','product_type','ru_description','en_description','material',
            'country','manufacturer','hs_code','marking','unit','active')
        widgets={'ru_description':forms.Textarea(attrs={'rows':2}),'en_description':forms.Textarea(attrs={'rows':2})}

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.before={f:getattr(self.instance,f) for f in CUSTOMS_FIELDS}
        if self.instance.pk:self.fields['expected_updated'].initial=self.instance.updated_at.isoformat()
        self.fields['platform'].label='Платформа игр (либо выберите категорию техники)'
        self.fields['product_type'].label='Категория техники (либо выберите платформу игр)'

    def clean(self):
        data=super().clean()
        if bool(data.get('platform'))==bool(data.get('product_type')):
            raise forms.ValidationError('Выберите ровно одну платформу игр или категорию техники.')
        if data.get('platform') and data.get('medium') not in ('disc','cartridge'):
            raise forms.ValidationError('Для игровой платформы выберите диск или картридж.')
        if data.get('product_type') and data.get('medium')!='tech':
            raise forms.ValidationError('Для категории техники выберите тип «Техника».')
        if data.get('confirm_values'):
            self.instance.confirmed_fields=[f for f in CONFIRMABLE_FIELDS if data.get(f)]
        else:
            self.instance.confirmed_fields=[f for f in self.instance.confirmed_fields if
                data.get(f)==self.before.get(f) and data.get(f)]
        return data
