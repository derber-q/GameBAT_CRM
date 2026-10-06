import json
from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError

from .content import CONTENT_FIELDS, LOCKED_CARD, validate_parameters, validate_schema
from .models import CategorySchema, Integration

LABELS = {
    "name": "Название", "description": "Описание", "vendor": "Производитель / бренд",
    "vendorCode": "Артикул производителя", "barcodes": "Штрихкоды GTIN", "manufacturerCountries": "Страны производства",
    "pictures": "Ссылки на изображения", "videos": "Ссылки на видео", "weightDimensions": "Размеры и вес",
    "length": "Длина, см", "width": "Ширина, см", "height": "Высота, см", "weight": "Вес, кг (из CRM)",
    "tags": "Теги", "shelfLife": "Срок годности", "lifeTime": "Срок службы", "guaranteePeriod": "Гарантийный срок",
    "timePeriod": "Количество", "timeUnit": "Единица периода", "comment": "Комментарий",
    "boxCount": "Число упаковок товара", "type": "Тип", "condition": "Состояние", "quality": "Качество", "reason": "Причина уценки",
    "adult": "Товар для взрослых", "downloadable": "Цифровой товар", "age": "Возрастное ограничение", "value": "Значение", "ageUnit": "Единица возраста",
    "certificates": "Сертификаты", "manuals": "Инструкции", "commodityCodes": "Товарные коды",
}


class ObjectListWidget(forms.Widget):
    template_name = "yandex_market/object_list_widget.html"

    def __init__(self, schema):
        self.schema = schema
        super().__init__()

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"]["columns"] = [{"key": key, "label": {"url": "Ссылка HTTPS", "title": "Название", "code": "Код", "type": "Тип кода"}.get(key, key),
                                          "choices": spec.get("enum", [])} for key, spec in self.schema.get("properties", {}).items()]
        return context


class IntegrationForm(forms.ModelForm):
    new_api_key = forms.CharField(label="Новый API-Key", required=False, max_length=4096, widget=forms.PasswordInput(render_value=False), help_text="Оставьте пустым, чтобы сохранить ключ. Смена ключа выключает обмен до повторной проверки подключения.")
    class Meta:
        model = Integration
        fields = ["name", "business_id", "campaign_id", "partner_warehouse_id", "stock_api", "price_scope", "fulfillment_warehouse", "operator", "import_orders_from", "enabled"]
        widgets = {"import_orders_from": forms.DateTimeInput(format="%Y-%m-%d %H:%M:%S")}

    def clean(self):
        data = super().clean()
        if data.get("new_api_key") and any(char.isspace() for char in data["new_api_key"].strip()):
            self.add_error("new_api_key", "Ключ не должен содержать пробелы.")
        if data.get("enabled") and not self.instance.checked_at:
            raise ValidationError("Сохраните настройки и проверьте подключение перед включением обмена.")
        if data.get("stock_api") == "partner" and not data.get("partner_warehouse_id"):
            raise ValidationError("Укажите один целевой склад Маркета.")
        if self.instance.pk and self.instance.connections.exists():
            if any(data.get(field) != getattr(self.instance, field) for field in ("business_id", "campaign_id")):
                raise ValidationError("Нельзя менять кабинет существующих связей и заказов. Создайте отдельное подключение.")
        return data


class ContentForm(forms.Form):
    revision = forms.IntegerField(widget=forms.HiddenInput)

    def __init__(self, *args, connection, **kwargs):
        self.connection = connection
        self.paths = {}
        remote = connection.remote_offer.snapshot.get("offer", {})
        self.baseline = {key: value for key, value in remote.items() if key in CONTENT_FIELDS}
        self.baseline.update(connection.content)
        initial = {"revision": connection.revision}
        super().__init__(*args, initial=initial, **kwargs)
        for key, schema in CONTENT_FIELDS.items():
            if key == "marketCategoryId":
                continue
            self._add_field((key,), schema, self.baseline.get(key))
        self.parameter_schema = CategorySchema.objects.filter(category_id=connection.category_id).first()
        self.initial_parameters = connection.parameters if "parameterValues" in connection.dirty_fields else (connection.remote_offer.card.get("parameterValues") or [])
        for parameter in (self.parameter_schema.schema.get("parameters", []) if self.parameter_schema else []):
            name = f"param_{parameter['id']}"
            values = [v for v in self.initial_parameters if v["parameterId"] == parameter["id"]]
            options = [(str(v["id"]), v["value"]) for v in parameter.get("values", [])]
            label = parameter.get("name", str(parameter["id"]))
            required = parameter.get("required", False)
            if options:
                if parameter.get("multivalue"):
                    field = forms.MultipleChoiceField(label=label, required=False, choices=options, initial=[str(v["valueId"]) for v in values if "valueId" in v])
                else:
                    field = forms.ChoiceField(label=label, required=False, choices=[("", "Не задано"), *options], initial=str(values[0].get("valueId", "")) if values else "")
                self.fields[name] = field
                if parameter.get("allowCustomValues"):
                    self.fields[name + "_custom"] = forms.CharField(label=f"{label}: своё значение", required=False, widget=forms.Textarea(attrs={"rows": 2}), initial="\n".join(v.get("value", "") for v in values if "valueId" not in v))
            elif parameter["type"] == "BOOLEAN":
                self.fields[name] = forms.ChoiceField(label=label, required=required, choices=[("", "Не задано"), ("true", "Да"), ("false", "Нет")], initial=values[0].get("value", "") if values else "")
            else:
                self.fields[name] = forms.CharField(label=label, required=required, widget=forms.Textarea(attrs={"rows": 2}) if parameter.get("multivalue") else forms.TextInput(), initial="\n".join(v.get("value", "") for v in values))
            self.fields[name].help_text = "Обязательно. " if required else ""
            if parameter.get("multivalue"):
                self.fields[name].help_text += "Можно несколько значений."
            units = parameter.get("unit", {})
            if units:
                self.fields[name + "_unit"] = forms.TypedChoiceField(label=f"{label}: единица", coerce=int, required=False, choices=[("", "Не задано"), *[(u["id"], u["name"]) for u in units["units"]]], initial=values[0].get("unitId", units["defaultUnitId"]) if values else units["defaultUnitId"])
        if connection.remote_offer.card_status == LOCKED_CARD:
            for field in self.fields.values():
                field.disabled = True

    def _add_field(self, path, schema, value):
        name = "content_" + "__".join(path)
        label = " · ".join(LABELS.get(p, p) for p in path)
        kind = schema.get("type")
        if kind == "object":
            for key, child in schema.get("properties", {}).items():
                self._add_field((*path, key), child, (value or {}).get(key))
            return
        self.paths[name] = (path, schema)
        if schema.get("enum"):
            field = forms.ChoiceField(label=label, required=False, choices=[("", "Не задано"), *[(v, v) for v in schema["enum"]]], initial=value)
        elif kind == "boolean":
            field = forms.ChoiceField(label=label, required=False, choices=[("", "Не задано"), ("true", "Да"), ("false", "Нет")], initial="" if value is None else str(value).lower())
        elif kind == "integer":
            field = forms.IntegerField(label=label, required=False, initial=value)
        elif kind == "number":
            field = forms.DecimalField(label=label, required=False, initial=value)
        elif kind == "array":
            complex_items = schema.get("items", {}).get("type") == "object"
            field = forms.CharField(label=label, required=False, widget=ObjectListWidget(schema["items"]) if complex_items else forms.Textarea(attrs={"rows": 3}),
                                    initial=json.dumps(value, ensure_ascii=False, default=str) if value and complex_items else "\n".join(value or []),
                                    help_text="Добавьте необходимые строки." if complex_items else "Каждое значение с новой строки. Пустое поле не удаляет данные Маркета.")
        else:
            field = forms.CharField(label=label, required=False, initial=value or "", max_length=schema.get("maxLength"), widget=forms.Textarea(attrs={"rows": 5}) if path[-1] == "description" else forms.TextInput())
        if path == ("weightDimensions", "weight"):
            field.disabled = True
            field.initial = Decimal(self.connection.product.weight_grams) / 1000 if self.connection.product.weight_grams else None
        self.fields[name] = field

    def clean(self):
        data = super().clean()
        if self.connection.remote_offer.card_status == LOCKED_CARD:
            raise ValidationError("Эту карточку Маркет разрешает только просматривать.")
        content = {}
        for name, (path, schema) in self.paths.items():
            value = data.get(name)
            if value in (None, "", []):
                continue
            if schema.get("type") == "boolean":
                value = value == "true"
            elif schema.get("type") == "array":
                if schema.get("items", {}).get("type") == "object":
                    try:
                        value = json.loads(value, parse_float=Decimal)
                    except ValueError:
                        self.add_error(name, "Некорректный список объектов.")
                        continue
                else:
                    value = [line.strip() for line in value.splitlines() if line.strip()]
                if value == []:
                    continue
            target = content
            for segment in path[:-1]:
                target = target.setdefault(segment, {})
            target[path[-1]] = value
        # Один вес без размеров не должен случайно начать отправку неполного блока.
        if set(content.get("weightDimensions", {})) == {"weight"}:
            content.pop("weightDimensions")
        for key, value in content.items():
            validate_schema(value, CONTENT_FIELDS[key], LABELS.get(key, key))
        parameters = []
        for parameter in (self.parameter_schema.schema.get("parameters", []) if self.parameter_schema else []):
            name = f"param_{parameter['id']}"
            value = data.get(name)
            has_options = bool(parameter.get("values"))
            values = value if isinstance(value, list) else ([value] if has_options else str(value or "").splitlines())
            for selected in values:
                if selected in (None, ""):
                    continue
                row = {"parameterId": parameter["id"]}
                row["valueId" if has_options else "value"] = int(selected) if has_options else selected
                if data.get(name + "_unit"):
                    row["unitId"] = data[name + "_unit"]
                parameters.append(row)
            for custom in str(data.get(name + "_custom", "")).splitlines():
                if custom.strip():
                    row = {"parameterId": parameter["id"], "value": custom.strip()}
                    if data.get(name + "_unit"):
                        row["unitId"] = data[name + "_unit"]
                    parameters.append(row)
        if self.parameter_schema:
            validate_parameters(parameters, self.parameter_schema.schema)
        data["content"] = content
        data["parameters"] = parameters
        return data
