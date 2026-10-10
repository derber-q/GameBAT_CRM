"""Порядок шаблона поставщика по структуре и вариантам моделей прайса Ali."""
import json
import re
from collections import OrderedDict
from functools import lru_cache
from pathlib import Path

from .sony_gamepad_sorting import normalize_product_name


def _name_key(value):
    name = normalize_product_name(value).replace("dualsence", "dualsense")
    name = name.replace("dual sense", "dualsense").replace("playstation 5", "ps5").replace("playstation 4", "ps4")
    name = name.replace("nintendo switch lite", "nintendo lite")
    # Отсутствие пометки Original не отдаляет обычный вариант от его модели.
    name = re.sub(r"\b(original|оригинал|ростест)\b", "", name)
    return " ".join(name.split())


def _family(name):
    """Новая разновидность остаётся возле семейства из референса."""
    name = _name_key(name)
    if "steam deck" in name and any(token in name for token in ("стекло", "screen", "case")):
        return "deck"
    for family, tokens in (
        ("covers", ("console covers",)),
        ("stick", ("stick module",)),
        ("edge", ("dualsense edge",)),
        ("vr", ("vr1", "vr2", "quest", "pico 4")),
        ("portal", ("portal",)),
        ("headphones", ("наушники", "headset")),
        ("memory", ("microsd", "ssd", "nvme")),
        ("charging", ("charging station", "док станци")),
        ("joy accessories", ("straps", "strap", "charging grip", "joy con 2 grip", "joy con 2 wheel")),
        ("joy con", ("joy con",)),
        ("cases", ("carrying case", "game traveler", "protective filter", "защитное стекло", "стекло защитное")),
        ("camera", ("camera",)),
        ("power", ("ac adapter", "usb ac adapter", "cable", "кабель")),
        ("stand", ("vertical stand", "подставка", "вентилятор")),
        ("wheel", ("racing wheel", "shifter", "руль")),
        ("deck", ("steam deck",)),
        ("machine", ("steam machine",)),
        ("ally", ("rog xbox ally",)),
        ("lenovo", ("lenovo go",)),
        ("msi", ("msi claw",)),
        ("ps5 pro", ("ps5 pro",)),
        ("ps5 slim digital", ("slim digital",)),
        ("slim", ("slim",)),
        ("ps4 pro", ("ps4 pro",)),
        ("oled", ("oled",)),
        ("lite", ("nintendo lite",)),
        ("controllers", ("геймпад", "dualshock", "controller", "split pad",)),
        ("dock", ("dock",)),
    ):
        if any(token in name for token in tokens):
            return family
    return name.split(" ", 1)[0]


@lru_cache(maxsize=1)
def _reference():
    sections = json.loads(Path(__file__).with_name("supplier_reference_order.json").read_text(encoding="utf-8"))
    names = {}
    families = {}
    for section_index, section in enumerate(sections):
        for position, product in enumerate(section["products"]):
            for name in (product["name"], *product["aliases"]):
                names.setdefault(_name_key(name), (section_index, position))
            families[(section_index, _family(product["name"]))] = position
    return sections, names, families


def _fallback_section(product):
    name = _name_key(product.name)
    brand = normalize_product_name(product.brand.name)
    product_type = normalize_product_name(product.product_type.name)
    # Совместимость платформы важнее бренда аксессуара: PowerA, Nacon и WD
    # из референса находятся рядом с соответствующими PlayStation/Nintendo.
    if any(token in name for token in ("wh 1000", "xbox one head")):
        return 11
    if any(token in name for token in ("quest", "oculus", "pico")) or ("vr" in product_type and brand != "sony"):
        return 12
    if brand == "valve" or "steam deck" in name or "steam machine" in name:
        return 7
    if "asus" in brand or "rog ally" in name:
        return 8
    if brand == "lenovo":
        return 9
    if brand == "msi":
        return 10
    if any(token in name for token in ("playstation classic", "ps vita", "psp")):
        return 0
    if any(token in name for token in ("ps5", "dualsense", "vr2", "portal", "pulse")):
        return 2
    if "ps4" in name or "dualshock" in name or "vr1" in name:
        return 1
    if "virtual boy" in name or "alarmo" in name or "talking flower" in name:
        return 5
    if re.search(r"\bns2\b|\bnintendo switch 2\b", name):
        return 3
    if brand == "nintendo" or re.search(r"\bns\b|\bnintendo\b", name):
        return 4
    if "xbox" in name or brand == "microsoft":
        return 6
    if brand == "sony":
        return 2
    if "гарнитура" in product_type or "наушники" in name:
        return 11
    if "руль" in product_type or "симрейсинг" in product_type:
        return 13
    return 14


def _natural_name(value):
    return tuple((0, int(part)) if part.isdigit() else (1, part) for part in re.split(r"(\d+)", _name_key(value)))


def _tech_order(product):
    sections, names, families = _reference()
    matched = names.get(_name_key(product.name))
    if matched:
        section, position = matched
        slot = position * 2
    else:
        section = _fallback_section(product)
        position = families.get((section, _family(product.name)))
        # Отсутствующие в Ali модели не исключаем: новые варианты идут после
        # своего семейства, прочие позиции — в конце соответствующего раздела.
        slot = position * 2 + 1 if position is not None else 10000
    title = sections[section]["title"] if section < len(sections) else "Tech · Прочие товары"
    return (section, slot, _natural_name(product.name), product.pk), title


def _platform_order(platform_name):
    name = normalize_product_name(platform_name)
    order = {
        "nintendo switch 2": 0, "ns2": 0,
        "nintendo switch": 1, "nintendo switch 1": 1, "ns": 1, "ns1": 1,
        "playstation 4": 2, "ps4": 2,
        "playstation 5": 3, "ps5": 3,
        "xbox series x": 4, "xbox": 4,
    }
    return order.get(name, 100), name


def supplier_product_groups(tech_items, cd_items):
    groups = OrderedDict()
    for product in sorted(tech_items, key=lambda item: _tech_order(item)[0]):
        title = _tech_order(product)[1]
        groups.setdefault(("tech", title), []).append(product)
    for product in sorted(cd_items, key=lambda item: (_platform_order(item.platform.name), _natural_name(item.name), item.pk)):
        title = f"CD · Платформа: {product.platform.name}"
        groups.setdefault(("cd", title), []).append(product)
    return [(kind, title, items) for (kind, title), items in groups.items()]
