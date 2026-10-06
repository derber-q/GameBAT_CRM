"""Состояние каталога и явное сопоставление редакционных разделов справочнику CRM."""
from django import forms
from django.conf import settings
from django.http import QueryDict

from catalog.models import ProductType


CATEGORY_CHOICES = (
    ("", "Все категории"), ("cd", "Игры"), ("consoles", "Консоли"),
    ("gamepads", "Геймпады"), ("accessories", "Аксессуары"), ("tech", "Вся техника"),
)
# Точные названия справочника, а не поиск фрагментов в названиях товаров.
# При необходимости настройка RESOURCE_CATEGORY_TYPES заменяет эту карту.
CATEGORY_TYPES = {
    "consoles": ("Игровая консоль", "Портативная игровая консоль"),
    "gamepads": ("Геймпад",),
    "accessories": (
        "VR-аксессуар", "VR-шлем", "Внешний привод для консоли", "Запасная часть",
        "Зарядная станция для геймпадов", "Защитное стекло", "Игровая гарнитура",
        "Кабель питания", "Переходник", "Стриминговая приставка", "Чехол для игровой консоли",
    ),
}


def category_type_ids(category):
    mapping = getattr(settings, "RESOURCE_CATEGORY_TYPES", CATEGORY_TYPES)
    return list(ProductType.objects.filter(name__in=mapping.get(category, ())).values_list("pk", flat=True))


def normalized_query(params):
    data = QueryDict(mutable=True)
    for name in CatalogueFilterForm.base_fields:
        data[name] = params.get(name, "").strip()
    if not data["category"]:
        data["category"] = params.get("kind", "")
        if not data["category"]:
            if data["platform"]:
                data["category"] = "cd"
            elif data["brand"] or data["product_type"]:
                data["category"] = "tech"
    if data["category"] == "cd":
        data["brand"] = data["product_type"] = ""
    elif data["category"]:
        data["platform"] = ""
    data["sort"] = data["sort"] or "name"
    return data


class PriceFilterField(forms.DecimalField):
    def to_python(self, value):
        if isinstance(value, str):
            value = value.replace("\u00a0", "").replace(" ", "").replace(",", ".")
        return super().to_python(value)


class CatalogueFilterForm(forms.Form):
    q = forms.CharField(label="Поиск по каталогу", required=False, max_length=120,
                        widget=forms.TextInput(attrs={"placeholder": "Название товара", "type": "search"}))
    category = forms.ChoiceField(label="Категория", required=False, choices=CATEGORY_CHOICES)
    platform = forms.ChoiceField(label="Платформа", required=False)
    brand = forms.ChoiceField(label="Бренд", required=False)
    product_type = forms.ChoiceField(label="Тип техники", required=False)
    price_min = PriceFilterField(label="От, ₽", required=False, min_value=0, max_digits=20, decimal_places=2,
                                   error_messages={"invalid": "Введите корректную цену."})
    price_max = PriceFilterField(label="До, ₽", required=False, min_value=0, max_digits=20, decimal_places=2,
                                   error_messages={"invalid": "Введите корректную цену."})
    sort = forms.ChoiceField(label="Сортировка", choices=(
        ("name", "По названию"), ("price", "Сначала дешевле"), ("price_desc", "Сначала дороже"),
        ("newest", "По дате добавления в новинки"),
    ))

    def __init__(self, data, *, filters, **kwargs):
        super().__init__(data, **kwargs)
        for field, key in (("platform", "platforms"), ("brand", "brands"), ("product_type", "product_types")):
            self.fields[field].choices = [("", "Все")] + [(str(x.pk), x.name) for x in filters[key]]
            self.fields[field].error_messages["invalid_choice"] = "Выберите доступное значение из списка."
        for name in ("price_min", "price_max"):
            self.fields[name].widget = forms.TextInput(attrs={"inputmode": "decimal", "placeholder": "Любая"})
        for field in self.fields.values():
            field.widget.attrs["form"] = "rs-catalog-form"

    def clean(self):
        data = super().clean()
        low, high = data.get("price_min"), data.get("price_max")
        if low is not None and high is not None and low > high:
            self.add_error("price_max", "Цена до должна быть не меньше цены от.")
        return data
