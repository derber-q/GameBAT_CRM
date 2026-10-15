import re
import unicodedata
from decimal import Decimal


def _normalized(value):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value).casefold()).strip()


def tech_postpayment_surcharge(product):
    """Первоначальные доплаты по согласованной модели; неизвестным товарам нужна ставка сотрудника."""
    kind = _normalized(product.product_type.name)
    brand = _normalized(product.brand.name)
    name = _normalized(product.name)
    amount = None
    if kind in {"ssd", "hdd", "внешний ssd", "внешний hdd"}:
        amount = 1000
    elif kind in {"microsd-карта", "sd-карта", "карта памяти", "карта памяти для игровой консоли"}:
        amount = 100
    elif kind in {"ar-очки", "умные очки"}:
        amount = 500
    elif kind == "адаптер для геймпада":
        amount = 200
    elif kind == "внешний привод для консоли" and brand == "sony" and "ps5" in name:
        amount = 200
    elif kind == "vr-аксессуар" or (kind == "vr-шлем" and any(token in name for token in ("strap", "ремеш", "креплен"))):
        amount = 100
    elif kind == "ретро-консоль":
        amount = 200
    elif kind == "коллекционная фигурка" and "labubu" in name:
        amount = 100
    elif kind in {"наушники", "игровая гарнитура", "гарнитура"}:
        amount = 200
    elif kind in {"руль", "игровой руль"}:
        amount = 500
    elif kind in {"ручная коробка передач для симрейсинга", "кпп", "коробка передач"}:
        amount = 200
    elif kind in {"подставка для игровой консоли", "подставка для консоли"}:
        amount = 50
    elif kind in {"сменные панели для игровой консоли", "панели для консоли"} and brand == "sony":
        amount = 200
    elif kind == "vr-шлем" and not any(token in name for token in ("strap", "ремеш", "креплен")):
        amount = 500
    elif kind == "стриминговая приставка" and brand == "sony" and "portal" in name:
        amount = 500
    elif kind in {"геймпад", "контроллер"}:
        if brand in {"backbone", "sega", "без бренда"}:
            amount = 100
        elif brand == "valve":
            amount = 500
        elif brand == "sony" and "edge" in name:
            amount = 500
        elif brand in {"sony", "nintendo", "microsoft", "xbox", "nacon", "victrix"}:
            amount = 200
        elif brand != "backbone" and re.search(r"\b(?:ps[45]|playstation [45]|nintendo|switch|xbox)\b", name):
            amount = 200
    elif kind in {"портативная игровая консоль", "портативная консоль"}:
        amount = 500
    elif kind in {"игровая консоль", "консоли", "консоль"}:
        if brand == "sony":
            amount = 1000 if re.search(r"\bpro\b", name) else 500
        elif brand in {"nintendo", "microsoft", "xbox"}:
            amount = 500
        elif brand == "valve":
            amount = 1000
    elif brand in {"sony", "nintendo", "microsoft", "xbox"} and kind in {
        "vr-аксессуар", "адаптер", "аксессуар для игровой консоли", "док-станция для игровой консоли",
        "запасная часть", "зарядная станция", "зарядная станция для геймпадов", "защитная плёнка",
        "кабель hdmi", "кабель usb-c", "камера для игровой консоли", "сетевое зарядное устройство",
        "сумка для игровой консоли", "чехол для игровой консоли", "умный будильник",
    }:
        amount = 100
    elif kind == "зарядная станция для геймпадов" and re.search(r"\b(?:ps[45]|xbox|nintendo|switch)\b", name):
        amount = 100
    elif brand == "без бренда" and kind in {
        "кабель питания", "кабель hdmi", "кабель usb-c", "кабель", "переходник", "адаптер",
        "охлаждающая подставка для консоли", "защитное стекло", "защитная плёнка", "мышь", "клавиатура",
        "зарядная станция", "зарядная станция для геймпадов", "аксессуар для игровой консоли",
    }:
        amount = 100
    return Decimal(amount) if amount is not None else None
