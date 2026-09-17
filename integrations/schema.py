from django.core.exceptions import ValidationError


def schema_fields(schema):
    fields = (schema or {}).get("fields") or (schema or {}).get("result") or []
    if isinstance(fields, dict):
        fields = fields.get("fields") or []
    return [field for field in fields if isinstance(field, dict)] if isinstance(fields, list) else []


def validate_attributes(attributes, schema):
    fields = schema_fields(schema)
    if not fields:
        return
    definitions = {}
    for field in fields:
        key = field.get("name") or field.get("slug") or field.get("id")
        if key is not None:
            definitions[str(key)] = field
    unknown = sorted(set(attributes) - set(definitions))
    if unknown:
        raise ValidationError("Неизвестные поля Avito: " + ", ".join(unknown))
    errors = []
    for key, field in definitions.items():
        value = attributes.get(key)
        label = str(field.get("label") or field.get("title") or key)
        if field.get("required") and value in (None, "", []):
            errors.append(f"Не заполнено обязательное поле Avito: {label}.")
            continue
        if value in (None, "", []):
            continue
        field_type = str(field.get("type") or "").lower()
        if field_type in {"integer", "int"} and (isinstance(value, bool) or not isinstance(value, int)):
            errors.append(f"Поле «{label}» должно быть целым числом.")
        elif field_type in {"number", "float", "decimal"} and (isinstance(value, bool) or not isinstance(value, (int, float))):
            errors.append(f"Поле «{label}» должно быть числом.")
        elif field_type in {"boolean", "bool"} and not isinstance(value, bool):
            errors.append(f"Поле «{label}» должно иметь значение true или false.")
        values = field.get("values") or field.get("enum") or field.get("options") or []
        if values:
            allowed = {
                option.get("value") if isinstance(option, dict) else option
                for option in values
            }
            if value not in allowed:
                errors.append(f"Недопустимое значение поля Avito «{label}».")
    if errors:
        raise ValidationError(errors)
