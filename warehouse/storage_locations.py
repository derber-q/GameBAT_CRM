"""Единый parser и normalizer физических мест хранения склада."""
from dataclasses import dataclass
import re

from django.core.exceptions import ValidationError


LOCATION_ERROR = (
    "Некорректный формат места хранения. Используйте, например: "
    r"A1-2-1\2, A6-3, B12-6-1."
)
MAX_NUMBER = 2_147_483_647
_LOCATION_RE = re.compile(
    r"^([A-Za-z])\s*(\d+)\s*-\s*(\d+)"
    r"(?:\s*-\s*(\d+(?:\s*\\\s*\d+)*))?$"
)
_QUERY_RE = re.compile(
    r"^([A-Za-z])(?:\s*(\d+))?"
    r"(?:\s*-\s*(\d+))?"
    r"(?:\s*-\s*(\d+(?:\s*\\\s*\d+)*))?$"
)


@dataclass(frozen=True)
class StorageLocationValue:
    room: str
    rack: int
    shelf: int
    columns: tuple[int, ...] = ()

    @property
    def canonical(self):
        value = f"{self.room}{self.rack}-{self.shelf}"
        if self.columns:
            value += "-" + "\\".join(str(column) for column in self.columns)
        return value


@dataclass(frozen=True)
class StorageLocationQuery:
    room: str
    rack: int | None = None
    shelf: int | None = None
    columns: tuple[int, ...] = ()


def _normalised_text(value):
    return str(value or "").replace("–", "-").replace("—", "-").strip()


def _positive_number(value):
    number = int(value)
    if number <= 0 or number > MAX_NUMBER:
        raise ValidationError(LOCATION_ERROR)
    return number


def parse_storage_location(value):
    """Разбирает одно место хранения по новому каноническому формату."""
    match = _LOCATION_RE.fullmatch(_normalised_text(value))
    if match is None:
        raise ValidationError(LOCATION_ERROR)
    room, rack, shelf, raw_columns = match.groups()
    columns = ()
    if raw_columns:
        columns = tuple(sorted({_positive_number(part.strip()) for part in raw_columns.split("\\")}))
    return StorageLocationValue(
        room=room.upper(),
        rack=_positive_number(rack),
        shelf=_positive_number(shelf),
        columns=columns,
    )


def parse_storage_location_list(value):
    """Разбирает список locations, где запятая разделяет только разные места."""
    text = _normalised_text(value)
    if not text:
        return ()
    tokens = text.split(",")
    if any(not token.strip() for token in tokens):
        raise ValidationError(LOCATION_ERROR)
    result = []
    seen = set()
    for token in tokens:
        location = parse_storage_location(token)
        if location.canonical not in seen:
            seen.add(location.canonical)
            result.append(location)
    return tuple(result)


def normalize_storage_location_list(value):
    return ", ".join(location.canonical for location in parse_storage_location_list(value))


def parse_storage_location_query(value):
    """Разбирает иерархический GET-фильтр: A, A1, A1-2 или A1-2-1\2."""
    text = _normalised_text(value)
    if not text:
        return None
    match = _QUERY_RE.fullmatch(text)
    if match is None:
        raise ValidationError(LOCATION_ERROR)
    room, rack, shelf, raw_columns = match.groups()
    if shelf is not None and rack is None:
        raise ValidationError(LOCATION_ERROR)
    columns = ()
    if raw_columns:
        columns = tuple(sorted({_positive_number(part.strip()) for part in raw_columns.split("\\")}))
    return StorageLocationQuery(
        room=room.upper(),
        rack=_positive_number(rack) if rack is not None else None,
        shelf=_positive_number(shelf) if shelf is not None else None,
        columns=columns,
    )


def normalize_location_autocomplete_token(value):
    """Безопасно упрощает только последний незавершённый token для подсказок."""
    token = _normalised_text(value).rsplit(",", 1)[-1]
    return re.sub(r"\s+", "", token).upper()
