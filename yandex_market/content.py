"""Контент отправляется только по изменённым полям, очистка всегда явная."""
import ipaddress
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

from django.conf import settings
from django.core.exceptions import ValidationError

from .client import CONTRACTS

OFFER_SCHEMA = CONTRACTS["updateOfferMappings"]["request"]["properties"]["offerMappings"]["items"]["properties"]["offer"]
LOCKED_CARD = "HAS_CARD_CAN_NOT_UPDATE"
RESERVED = {"offerId", "basicPrice", "purchasePrice", "additionalExpenses", "deleteParameters", "parameterValues", "onlyPartnerMediaContent"}
CONTENT_FIELDS = {key: value for key, value in OFFER_SCHEMA["properties"].items() if not value.get("deprecated") and key not in RESERVED}
DELETE_FIELDS = {name: name.lower().split("_")[0] + "".join(part.title() for part in name.lower().split("_")[1:])
                 for name in OFFER_SCHEMA["properties"]["deleteParameters"]["items"]["enum"]}
DELETE_FIELDS["PARAMETERS"] = "parameterValues"
DELETE_FIELDS = {key: value for key, value in DELETE_FIELDS.items() if value in CONTENT_FIELDS or value == "parameterValues"}


def public_https(value):
    parsed = urlparse(value)
    host = parsed.hostname or ""
    if parsed.scheme != "https" or not host or parsed.username or parsed.password or parsed.fragment:
        raise ValidationError("Нужна постоянная публичная ссылка HTTPS.")
    if host.lower() == "localhost" or "." not in host or host.lower().endswith((".local", ".internal", ".localhost")):
        raise ValidationError("Локальный адрес недоступен Маркету.")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if not address.is_global:
            raise ValidationError("Локальный адрес недоступен Маркету.")
    return value


def validate_schema(value, schema, path="Поле"):
    if schema.get("deprecated"):
        raise ValidationError(f"{path}: устаревшее поле API.")
    if value is None:
        raise ValidationError(f"{path}: очистка выполняется отдельным действием.")
    kind = schema.get("type")
    if kind == "object":
        if not isinstance(value, dict):
            raise ValidationError(f"{path}: ожидается объект.")
        properties = schema.get("properties", {})
        for required in schema.get("required", []):
            if required not in value:
                raise ValidationError(f"{path}: не заполнено {required}.")
        for key, item in value.items():
            if key not in properties:
                raise ValidationError(f"{path}: неизвестное поле {key}.")
            validate_schema(item, properties[key], f"{path}.{key}")
    elif kind == "array":
        if not isinstance(value, list) or len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", 10000):
            raise ValidationError(f"{path}: некорректный размер списка.")
        for item in value:
            validate_schema(item, schema.get("items", {}), path)
    elif kind in {"integer", "number"}:
        try:
            number = Decimal(str(value))
        except (ValueError, InvalidOperation):
            raise ValidationError(f"{path}: требуется число.")
        if isinstance(value, bool) or not number.is_finite() or (kind == "integer" and number != int(number)):
            raise ValidationError(f"{path}: некорректное число.")
        if "minimum" in schema and (number < Decimal(str(schema["minimum"])) or (schema.get("exclusiveMinimum") and number == Decimal(str(schema["minimum"])))):
            raise ValidationError(f"{path}: значение ниже допустимого.")
        if "maximum" in schema and number > Decimal(str(schema["maximum"])):
            raise ValidationError(f"{path}: значение выше допустимого.")
    elif kind == "boolean" and not isinstance(value, bool):
        raise ValidationError(f"{path}: требуется логическое значение.")
    elif kind == "string":
        if not isinstance(value, str) or len(value) > schema.get("maxLength", 100000) or len(value) < schema.get("minLength", 0):
            raise ValidationError(f"{path}: некорректный текст.")
    if "enum" in schema and value not in schema["enum"]:
        raise ValidationError(f"{path}: недопустимый вариант.")


def valid_gtin(value):
    if not value.isascii() or not value.isdigit() or len(value) not in (8, 12, 13, 14):
        return False
    total = sum(int(digit) * (3 if index % 2 == 0 else 1) for index, digit in enumerate(reversed(value[:-1])))
    return (10 - total % 10) % 10 == int(value[-1])


def api_numbers(value, schema):
    """JSONField хранит Decimal строкой; по контракту API возвращаем числовой тип."""
    kind = schema.get("type")
    if kind == "number":
        return Decimal(str(value))
    if kind == "integer":
        return int(value)
    if kind == "object":
        return {key: api_numbers(item, schema.get("properties", {}).get(key, {})) for key, item in value.items()}
    if kind == "array":
        return [api_numbers(item, schema.get("items", {})) for item in value]
    return value


def validate_parameters(values, schema, *, require_all=True):
    definitions = {int(p["id"]): p for p in schema.get("parameters", [])}
    grouped = {}
    for value in values:
        parameter = definitions.get(value.get("parameterId"))
        if not parameter:
            raise ValidationError("Характеристика не принадлежит выбранной категории. Обновите форму.")
        validate_schema(value, OFFER_SCHEMA["properties"]["parameterValues"]["items"], parameter.get("name", "Характеристика"))
        grouped.setdefault(parameter["id"], []).append(value)
        choices = {int(row["id"]) for row in parameter.get("values", [])}
        if value.get("valueId") is not None and value["valueId"] not in choices:
            raise ValidationError(f"{parameter['name']}: неизвестное значение.")
        if "valueId" not in value and not parameter.get("allowCustomValues") and parameter["type"] == "ENUM":
            raise ValidationError(f"{parameter['name']}: выберите значение из списка.")
        if "valueId" not in value and value.get("value", "") == "":
            raise ValidationError(f"{parameter['name']}: пустое значение.")
        if parameter["type"] == "BOOLEAN" and str(value.get("value", "")).lower() not in {"true", "false"}:
            raise ValidationError(f"{parameter['name']}: выберите да или нет.")
        constraints = parameter.get("constraints", {})
        if parameter["type"] == "NUMERIC":
            numeric_schema = {"type": "number"}
            numeric_schema.update({target: constraints[source] for source, target in (("minValue", "minimum"), ("maxValue", "maximum")) if source in constraints})
            validate_schema(value.get("value"), numeric_schema, parameter["name"])
        if constraints.get("maxLength") and len(str(value.get("value", ""))) > constraints["maxLength"]:
            raise ValidationError(f"{parameter['name']}: слишком длинное значение.")
        units = parameter.get("unit", {}).get("units", [])
        if units and value.get("unitId") not in {unit["id"] for unit in units}:
            raise ValidationError(f"{parameter['name']}: выберите единицу измерения.")
    for parameter_id, parameter in definitions.items():
        selected = grouped.get(parameter_id, [])
        if require_all and parameter.get("required") and not selected:
            raise ValidationError(f"Заполните обязательную характеристику: {parameter['name']}.")
        if not parameter.get("multivalue") and len(selected) > 1:
            raise ValidationError(f"{parameter['name']}: допускается одно значение.")
        for restriction in parameter.get("valueRestrictions", []):
            limiting = {v.get("valueId") for v in grouped.get(restriction["limitingParameterId"], [])}
            allowed = {v for row in restriction["limitedValues"] if row["limitingOptionValueId"] in limiting for v in row["optionValueIds"]}
            if limiting and any(v.get("valueId") not in allowed for v in selected):
                raise ValidationError(f"{parameter['name']}: значение не соответствует зависимой характеристике.")
    return values


def build_content(connection):
    fields = set(connection.content) if connection.is_new else set(connection.dirty_fields)
    payload = {key: connection.content[key] for key in fields if key in CONTENT_FIELDS and key in connection.content}
    if connection.category_id and (connection.is_new or "marketCategoryId" in fields or "parameterValues" in fields):
        payload["marketCategoryId"] = connection.category_id
    if connection.is_new or "parameterValues" in fields:
        from .models import CategorySchema
        schema = CategorySchema.objects.filter(category_id=connection.category_id).first()
        if not schema or "parameters" not in schema.schema:
            raise ValidationError("Сначала загрузите характеристики категории.")
        validate_parameters(connection.parameters, schema.schema)
        if connection.parameters:
            payload["parameterValues"] = connection.parameters
    if "pictures" in fields and connection.media.filter(active=True).exists():
        base = public_https(settings.YANDEX_MARKET_PUBLIC_URL)
        payload["pictures"] = [f"{base}/integrations/yandex/media/{media.public_id}/" for media in connection.media.filter(active=True)]
    if "weightDimensions" in payload:
        from .product_dimensions import dimensions_payload
        payload["weightDimensions"] = dimensions_payload(connection.product, payload["weightDimensions"])
    if connection.delete_fields:
        payload["deleteParameters"] = connection.delete_fields
        for name in connection.delete_fields:
            if name not in DELETE_FIELDS:
                raise ValidationError("Очистка этого поля не поддерживается текущей интеграцией.")
            payload.pop(DELETE_FIELDS[name], None)
    for key in ("pictures", "videos"):
        for url in payload.get(key, []):
            public_https(url)
    for manual in payload.get("manuals", []):
        public_https(manual["url"])
    if any(not valid_gtin(code) for code in payload.get("barcodes", [])):
        raise ValidationError("Для Маркета нужны корректные GTIN; внутренний Code128 не подходит.")
    if connection.is_new:
        missing = [key for key in ("name", "description", "vendor", "marketCategoryId", "pictures") if not payload.get(key)]
        if missing:
            raise ValidationError("Для нового товара заполните: " + ", ".join(missing))
    if payload and connection.remote_offer.card_status == LOCKED_CARD:
        raise ValidationError("Маркет запретил редактирование системной карточки. Обновите статус или используйте кабинет.")
    payload["offerId"] = connection.remote_offer.offer_id
    validate_schema(payload, OFFER_SCHEMA, "Карточка Маркета")
    return api_numbers(payload, OFFER_SCHEMA)
