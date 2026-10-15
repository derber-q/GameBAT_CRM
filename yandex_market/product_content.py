"""Показ сохранённых данных Маркета в карточке товара без запросов к API."""
from django.urls import reverse

from .content import CONTENT_FIELDS
from .forms import LABELS
from .models import CategorySchema


def _text(value):
    if isinstance(value, bool):
        return "Да" if value else "Нет"
    if isinstance(value, dict):
        return "; ".join(f"{LABELS.get(key, key)}: {_text(item)}" for key, item in value.items())
    if isinstance(value, list):
        return "\n".join(_text(item) for item in value)
    return str(value)


def _fields(values, prefix=()):
    for key, value in values.items():
        if value is None or value == "" or value == [] or value == {}:
            continue
        path = (*prefix, key)
        if isinstance(value, dict):
            yield from _fields(value, path)
        else:
            yield {"label": " · ".join(LABELS.get(part, part) for part in path), "value": _text(value)}


def saved_product_content(connection):
    remote = connection.remote_offer
    offer = remote.snapshot.get("offer", {})
    content = {key: value for key, value in offer.items() if key in CONTENT_FIELDS}
    content.update(connection.content)
    fields = list(_fields({key: value for key, value in content.items() if key != "marketCategoryId"}))
    category = CategorySchema.objects.filter(category_id=connection.category_id).first()
    definitions = {row["id"]: row for row in (category.schema.get("parameters", []) if category else [])}
    parameters = connection.parameters if "parameterValues" in connection.dirty_fields else (remote.card.get("parameterValues", offer.get("parameterValues")) or [])
    for row in parameters:
        definition = definitions.get(row["parameterId"], {})
        choices = {item["id"]: item["value"] for item in definition.get("values", [])}
        value = row.get("value", choices.get(row.get("valueId"), row.get("valueId", "")))
        units = {item["id"]: item["name"] for item in definition.get("unit", {}).get("units", [])}
        if row.get("unitId") in units:
            value = f"{value} {units[row['unitId']]}"
        fields.append({"label": definition.get("name", f"Характеристика {row['parameterId']}"), "value": _text(value)})
    pictures = content.get("pictures", [])
    if "pictures" in connection.dirty_fields or connection.is_new:
        media = [item for item in connection.media.all() if item.active]
        if media:
            pictures = [reverse("yandex_market:media", args=[item.public_id]) for item in media]
    return {"fields": fields, "pictures": pictures}
