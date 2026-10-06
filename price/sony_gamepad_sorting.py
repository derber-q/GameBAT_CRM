import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class SonyGamepadCategory:
    code: str
    label: str
    priority: int


PS4 = SonyGamepadCategory("ps4", "PS4", 10)
WHITE = SonyGamepadCategory("white", "PS5 / DualSense White", 20)
BLACK = SonyGamepadCategory("black", "PS5 / DualSense Black", 30)
CAMOUFLAGE = SonyGamepadCategory("camouflage", "PS5 / DualSense Camouflage", 40)
STANDARD_MATTE = SonyGamepadCategory("standard_matte", "PS5 Standard Matte", 50)
TWO_TONE = SonyGamepadCategory("two_tone", "PS5 Two-Tone", 60)
METALLIC = SonyGamepadCategory("metallic", "PS5 Chrome / Metallic", 70)
UNKNOWN = SonyGamepadCategory("unknown", "UNCLASSIFIED / NEEDS REVIEW", 75)
GAME_THEMED = SonyGamepadCategory("game_themed", "PS5 Game-Themed", 80)
LIMITED = SonyGamepadCategory("limited", "PS5 Limited", 90)


# Правила основаны на названиях Sony-геймпадов из рабочей БД на 29.09.2026.
PS4_PATTERNS = ("ps4", "dualshock")
WHITE_PATTERNS = ("original white", "белый", "white")
BLACK_PATTERNS = ("midnight black", "черный", "black")
CAMOUFLAGE_PATTERNS = ("grey camouflage", "camouflage", "камуфляж", "camo")
STANDARD_MATTE_PATTERNS = (
    "alpine green", "альпийский зеленый",
    "starlight blue", "голубой",
    "cosmic red", "красный",
    "nova pink", "розовый",
    "galactic purple", "фиолетовый",
    "volcanic red", "вулканический красный",
    "cobalt blue", "синий",
    "sterling silver", "серебристый",
)
TWO_TONE_PATTERNS = ("hyperpop", "remix green", "techno red", "rhythm blue")
METALLIC_PATTERNS = ("chroma", "chrome", "metallic", "металлик", "хром")
GAME_THEMED_PATTERNS = (
    "007 first light",
    "astro bot",
    "death stranding",
    "final fantasy",
    "fortnite",
    "genshin impact",
    "ghost of yotei",
    "god of war",
    "lebron james",
    "marathon",
    "marvel s spider man",
    "monster hunter",
    "the last of us",
)
LIMITED_PATTERNS = ("limited", "anniversary", "special edition")


def normalize_product_name(value):
    """Нормализовать регистр, пробелы, дефисы и пунктуацию только для matching."""
    value = unicodedata.normalize("NFKC", str(value or "")).casefold().replace("ё", "е")
    return re.sub(r"[^\w]+", " ", value, flags=re.UNICODE).strip()


def _matches_any(value, patterns):
    return any(pattern in value for pattern in patterns)


def is_sony_gamepad(product):
    brand_name = getattr(getattr(product, "brand", None), "name", "")
    product_type_name = getattr(getattr(product, "product_type", None), "name", "")
    return (
        normalize_product_name(brand_name) == "sony"
        and normalize_product_name(product_type_name) in {"геймпад", "gamepad"}
    )


def classify_sony_gamepad(product):
    """Вернуть ровно одну категорию; более поздние специальные группы приоритетнее."""
    name = normalize_product_name(product.name)

    # PS4 остаётся отдельным первым поколением независимо от цвета/оформления.
    if _matches_any(name, PS4_PATTERNS):
        return PS4

    # Проверка идёт от наиболее специальной поздней категории к базовой.
    for category, patterns in (
        (LIMITED, LIMITED_PATTERNS),
        (GAME_THEMED, GAME_THEMED_PATTERNS),
        (METALLIC, METALLIC_PATTERNS),
        (TWO_TONE, TWO_TONE_PATTERNS),
        (CAMOUFLAGE, CAMOUFLAGE_PATTERNS),
        (BLACK, BLACK_PATTERNS),
        (WHITE, WHITE_PATTERNS),
        (STANDARD_MATTE, STANDARD_MATTE_PATTERNS),
    ):
        if _matches_any(name, patterns):
            return category
    return UNKNOWN


def sony_gamepad_sort_key(product):
    """Общий стабильный ключ Sony/Геймпад для розничного и оптового прайса."""
    category = classify_sony_gamepad(product)
    return category.priority, normalize_product_name(product.name), product.pk
