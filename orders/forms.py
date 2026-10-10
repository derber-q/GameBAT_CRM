from django import forms

from warehouse.models import Warehouse


class ProcurementOrderUploadForm(forms.Form):
    recipient = forms.CharField(label="Получатель", max_length=255)
    comment = forms.CharField(label="Комментарий", required=False, widget=forms.Textarea(attrs={"rows": 3}))
    cd_file = forms.FileField(label="Заполненный прайс дисков .xlsx", required=False)
    tech_file = forms.FileField(label="Заполненный прайс техники .xlsx", required=False)

    def clean(self):
        data = super().clean()
        uploads = {kind: data[f"{kind}_file"] for kind in ("cd", "tech") if data.get(f"{kind}_file")}
        # Совместимость с ранее открытой формой загрузки общего клиентского файла.
        legacy_file = self.files.get("file")
        if legacy_file and uploads:
            raise forms.ValidationError("Загрузите либо прежний общий файл, либо отдельные прайсы.")
        if legacy_file:
            uploads = {None: legacy_file}
        if not uploads:
            raise forms.ValidationError("Загрузите заполненный прайс дисков, техники или оба файла.")
        data["uploads"] = uploads
        return data


class ProcurementOrderHeaderForm(forms.Form):
    recipient = forms.CharField(label="Получатель", max_length=255)
    comment = forms.CharField(label="Комментарий", required=False, widget=forms.Textarea(attrs={"rows": 3}))


class PaymentWarehouseForm(forms.Form):
    warehouse = forms.ModelChoiceField(label="Склад оплаты", queryset=Warehouse.objects.all(), required=False)


class ReceivingAdjustmentForm(forms.Form):
    comment = forms.CharField(label="Причина корректировки", widget=forms.Textarea(attrs={"rows": 3}))
