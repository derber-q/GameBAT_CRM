from django import forms

from catalog.models import Brand, GameSeries, Platform, ProductType
from warehouse.models import Warehouse

from .models import Sale


CHANNEL_CHOICES = (
    ("retail", "Розница"),
    ("wholesale", "Оптовые"),
    ("avito", "Avito"),
    ("yandex_market", "Яндекс Маркет"),
    ("consignment", "Реализация"),
)
GROUP_CHOICES = (("day", "По дням"), ("week", "По неделям"), ("month", "По месяцам"))
SALE_SORT_CHOICES = (
    ("-date", "Сначала новые"), ("date", "Сначала старые"),
    ("-revenue", "Выручка ↓"), ("revenue", "Выручка ↑"),
    ("-cost", "Себестоимость ↓"), ("cost", "Себестоимость ↑"),
    ("-profit", "Прибыль ↓"), ("profit", "Прибыль ↑"),
    ("-margin", "Маржа ↓"), ("margin", "Маржа ↑"),
    ("-units", "Количество ↓"), ("units", "Количество ↑"),
)
PRODUCT_SORT_CHOICES = (
    ("-units", "Популярные"), ("-profit", "Топ прибыльных"),
    ("profit", "Наименее прибыльные"), ("-revenue", "Выручка ↓"),
    ("-sales", "Число продаж ↓"),
)


class SaleStatisticsFilterForm(forms.Form):
    date_from = forms.DateField(label="Дата с", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    date_to = forms.DateField(label="Дата по", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    channels = forms.MultipleChoiceField(label="Каналы продаж", choices=CHANNEL_CHOICES, required=False,
                                         widget=forms.CheckboxSelectMultiple)
    warehouse = forms.ModelChoiceField(label="Склад", queryset=Warehouse.objects.all(), required=False,
                                       empty_label="Все склады")
    payment_methods = forms.MultipleChoiceField(label="Способ оплаты", choices=Sale.PaymentMethod.choices,
                                                required=False, widget=forms.CheckboxSelectMultiple)
    product_query = forms.CharField(label="Товар: ID, артикул, название, штрихкод, CUSA/PPSA", required=False)
    platform = forms.ModelChoiceField(label="Платформа CD", queryset=Platform.objects.all(), required=False)
    game_series = forms.ModelChoiceField(label="Игровая серия", queryset=GameSeries.objects.all(), required=False)
    brand = forms.ModelChoiceField(label="Бренд Tech", queryset=Brand.objects.all(), required=False)
    product_type = forms.ModelChoiceField(label="Тип Tech", queryset=ProductType.objects.all(), required=False)
    sale_ids_text = forms.CharField(label="Номера продаж через запятую", required=False,
                                    help_text="Можно указать ID продаж вручную или отметить продажи в таблице.")
    min_profit = forms.DecimalField(label="Минимальная прибыль продажи, ₽", required=False, decimal_places=2)
    max_profit = forms.DecimalField(label="Максимальная прибыль продажи, ₽", required=False, decimal_places=2)
    grouping = forms.ChoiceField(label="Группировка", choices=GROUP_CHOICES, initial="day")
    sale_sort = forms.ChoiceField(label="Сортировка продаж", choices=SALE_SORT_CHOICES, initial="-date")
    product_sort = forms.ChoiceField(label="Сортировка товаров", choices=PRODUCT_SORT_CHOICES, initial="-units")

    def clean(self):
        data = super().clean()
        date_from, date_to = data.get("date_from"), data.get("date_to")
        if date_from and date_to and date_from > date_to:
            raise forms.ValidationError("Дата начала не может быть позже даты окончания.")
        minimum, maximum = data.get("min_profit"), data.get("max_profit")
        if minimum is not None and maximum is not None and minimum > maximum:
            raise forms.ValidationError("Минимальная прибыль не может быть больше максимальной.")
        raw_ids = self.data.getlist("sale_id") if hasattr(self.data, "getlist") else []
        raw_ids += str(data.get("sale_ids_text") or "").replace(";", ",").split(",")
        ids = set()
        for raw in raw_ids:
            value = str(raw).strip()
            if not value:
                continue
            if not value.isdecimal():
                raise forms.ValidationError("Укажите числовые ID продаж через запятую.")
            ids.add(int(value))
        data["sale_ids"] = frozenset(ids)
        return data
