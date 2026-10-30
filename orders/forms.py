from django import forms

from warehouse.form_defaults import SingleWarehouseInitialMixin
from warehouse.models import Warehouse
from partners.customers import CustomerSelectionForm, resolve_customer


class ProcurementOrderUploadForm(CustomerSelectionForm):
    recipient = forms.CharField(label="Получатель / название закупки", max_length=255, required=False,
                               help_text="Для клиентского заказа обязателен; для закупки на наличие можно оставить пустым.")
    comment = forms.CharField(label="Комментарий", required=False, widget=forms.Textarea(attrs={"rows": 3}))
    cd_file = forms.FileField(label="Заполненный прайс дисков .xlsx", required=False)
    tech_file = forms.FileField(label="Заполненный прайс техники .xlsx", required=False)
    stock_file = forms.FileField(label="Прайс для заказа на склад .xlsx", required=False)

    def clean(self):
        data = super().clean()
        if data.get('customer'):
            _, name = resolve_customer(partner_id=data.get('partner_id'), partner_name=data.get('partner_name', ''))
            data['recipient'] = data.get('recipient') or name
        uploads = {kind: data[f"{kind}_file"] for kind in ("cd", "tech") if data.get(f"{kind}_file")}
        if data.get("stock_file"):
            if uploads or self.files.get("file"):
                raise forms.ValidationError("Заказ на склад загружается отдельно от клиентских файлов.")
            data["uploads"] = {"stock": data["stock_file"]}
            return data
        # Совместимость с ранее открытой формой загрузки общего клиентского файла.
        legacy_file = self.files.get("file")
        if legacy_file and uploads:
            raise forms.ValidationError("Загрузите либо прежний общий файл, либо отдельные прайсы.")
        if legacy_file:
            uploads = {None: legacy_file}
        if not uploads:
            raise forms.ValidationError("Загрузите клиентский прайс или прайс для заказа на склад.")
        if not data.get("recipient"):
            self.add_error("recipient", "Для клиентского заказа укажите получателя.")
        data["uploads"] = uploads
        return data


class ProcurementOrderHeaderForm(CustomerSelectionForm):
    recipient = forms.CharField(label="Получатель", max_length=255)
    comment = forms.CharField(label="Комментарий", required=False, widget=forms.Textarea(attrs={"rows": 3}))


class PaymentWarehouseForm(SingleWarehouseInitialMixin, forms.Form):
    warehouse = forms.ModelChoiceField(label="Склад оплаты", queryset=Warehouse.objects.all(), required=False)


class ReceivingAdjustmentForm(forms.Form):
    comment = forms.CharField(label="Причина корректировки", widget=forms.Textarea(attrs={"rows": 3}))


class TripAssignmentForm(forms.Form):
    target_trip = forms.ChoiceField(label="Рейс назначения", error_messages={
        "invalid_choice": "Выберите актуальный рейс из списка. Если он изменился, обновите страницу.",
    })
    source_trip = forms.IntegerField(required=False, min_value=1, widget=forms.HiddenInput)
    source_revision = forms.IntegerField(required=False, min_value=0, widget=forms.HiddenInput)

    def __init__(self, *args, trips, order, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["target_trip"].choices = [("", "Выберите рейс")] + [
            (f"{trip.pk}:{trip.revision}", f"{trip} · " + (
                f"прайс №{trip.price_list_id}" if trip.price_list_id else "прайс определится первым заказом")) for trip in trips
        ]
        self.fields["source_trip"].initial = order.trip_id
        self.fields["source_revision"].initial = order.trip.revision if order.trip_id else None

    def clean_target_trip(self):
        batch_id, revision = self.cleaned_data["target_trip"].split(":")
        return int(batch_id), int(revision)


class EmptyTripForm(forms.Form):
    name = forms.CharField(label='Название рейса', max_length=255, required=False)
    creation_key = forms.UUIDField(widget=forms.HiddenInput)


class TripOrdersChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, order):
        return f'Заказ №{order.pk} · {order.recipient} · Прайс №{order.price_list_id}'


class TripAddOrdersForm(forms.Form):
    orders = TripOrdersChoiceField(label='Заказы без рейса', queryset=None, widget=forms.CheckboxSelectMultiple)
    revision = forms.IntegerField(min_value=0, widget=forms.HiddenInput)

    def __init__(self, *args, batch, **kwargs):
        from .models import CustomerProcurementOrder
        super().__init__(*args, **kwargs)
        orders = CustomerProcurementOrder.objects.filter(trip__isnull=True, status='created',
            price_list__is_trip_addition=False).select_related('price_list').order_by('pk')
        if batch.price_list_id:
            orders = orders.filter(price_list_id=batch.price_list_id)
        self.fields['orders'].queryset = orders
        self.fields['revision'].initial = batch.revision
