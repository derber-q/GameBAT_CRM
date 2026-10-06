"""Ручная проверка конкурентных объявлений без изменения товара или Avito-профиля."""
import re
import unicodedata
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode, urlparse

from django.db.models import IntegerField, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from catalog.models import CD, Tech
from .models import AvitoCheckListingCache, AvitoListingConnection, AvitoPriceCheckResult
from .reef_api import ReefApiClient, ReefApiError


CHECK_VERSION = 2
OFFER_LIMIT = 3
CHECK_LIMITS = {"economy": (2, 6), "deep": (10, 20)}
CACHE_TTL = timedelta(hours=24)
DIGITAL_GAME = re.compile(
    r"\b(?:цифр\w*|электронн\w*|аккаунт\w*|акк\b|учетн\w*\s+запис\w*|"
    r"ключ\w*|код\w*\s+(?:активац\w*|загруз\w*)|активац\w*|"
    r"digital|account\w*|download\w*|key|code|game\s*key|activation\s*key|"
    r"e\s*shop|eshop|п[123]|p[123])\b", re.I,
)
PHYSICAL_GAME = re.compile(r"\b(?:диск\w*|картридж\w*|cartridge\w*|disc\w*|blu\s*ray|физическ\w*)\b", re.I)
NO_PHYSICAL_GAME = re.compile(
    r"\b(?:без|нет|не)\s+(?:физическ\w*\s+)?(?:диск\w*|картридж\w*|носител\w*)\b|"
    r"\b(?:диск\w*|картридж\w*)\s+(?:нет|отсутствует)\b|"
    r"\b(?:код\w*\s+в\s+коробк\w*|пуст\w*\s+коробк\w*)\b", re.I,
)


def _media_text(row):
    text = " ".join(str(row.get(field) or "") for field in ("title", "description", "description_snippet"))
    text += " " + _param_text(row)
    return normalize("".join(char for char in text if unicodedata.category(char) != "Cf"))


def physical_game(row):
    """Неизвестный носитель не считается подтверждённым физическим изданием."""
    text = _media_text(row)
    return bool(PHYSICAL_GAME.search(text)) and not (DIGITAL_GAME.search(text) or NO_PHYSICAL_GAME.search(text))


BLOCKED = re.compile(
    r"\b(?:аккаунт\w*|уч[её]тн\w*\s+запис\w*|ключ\w*|"
    r"цифров\w*\s+код\w*|подписк\w*|аренд\w*|общ\w*\s+доступ\w*|"
    r"п[123](?:\b|\s*/)|услуг\w*|помощ\w*\s+(?:в\s+)?(?:покупк\w*|заказ\w*)|"
    r"предоплат\w*|консультац\w*)\b", re.I,
)
PLACEHOLDER = re.compile(
    r"цена\s+(?:в\s+описании|указана\s+условно|от\s+\d)|"
    r"уточняйте\s+цену|актуальная\s+цена|стоимость\s+в\s+описании|"
    r"цена\s+за\s+услугу|ценник\s+условн", re.I,
)
GAME_ACCESSORY = re.compile(
    r"\b(?:чехол|чехлы|сумка|сумки|накладка|накладки|брелок|брелоки|"
    r"стикер|стикеры|постер|постеры|amiibo|амиибо)\b|"
    r"\b(?:пустая|пустую|пустой)\s+(?:коробка|коробку|бокс|кейс)\b", re.I,
)
MONEY = re.compile(r"(?<!\d)(\d[\d\s\u00a0]{0,12})\s*(?:₽|руб(?:лей|ля)?)", re.I)
PLATFORMS = {"ps3", "ps4", "ps5", "xbox360", "xboxone", "xboxseriesx", "xboxseriess", "switch", "switch2"}
GAME_EDITIONS = {"deluxe", "ultimate", "standard", "collector", "goty", "complete", "gold", "remastered", "definitive", "directors", "collection", "trilogy", "anniversary", "limited"}
GAME_STOP_WORDS = {"the", "a", "of", "and", "for", "in", "игра", "диск", "для", "edition", "издание"}
LATIN_LOOKALIKES = str.maketrans("аеорсухкмнвіт", "aeopcyxkmhbit")
CYRILLIC_LOOKALIKES = str.maketrans("aeopcyxkmhbit", "аеорсухкмнвіт")
ROMAN_NUMERALS = {"ii": "2", "iii": "3", "iv": "4", "v": "5", "vi": "6", "vii": "7", "viii": "8", "ix": "9"}


def _fix_mixed_script(match):
    token = match.group()
    latin = sum("a" <= char <= "z" for char in token)
    cyrillic = sum("а" <= char <= "я" for char in token)
    if latin and cyrillic:
        return token.translate(LATIN_LOOKALIKES if latin >= cyrillic else CYRILLIC_LOOKALIKES)
    return token


def normalize(value):
    value = unicodedata.normalize("NFKC", str(value or ""))
    value = value.casefold().replace("ё", "е")
    value = re.sub(r"[a-zа-яі]+", _fix_mixed_script, value)
    value = re.sub(r"(?<=\w)['’`´](?=\w)", "", value)
    value = re.sub(r"(?<=\d)\.(?=\d{3}\b)", "", value)
    value = re.sub(r"\bi(?=\s*[+&/]\s*(?:ii|2)\b)", "1", value)
    value = value.replace("&", " and ")
    value = re.sub(r"\bgame\s+of\s+the\s+year\b", "goty", value)
    value = re.sub(r"\bcollectors\b", "collector", value)
    value = re.sub(r"\b(part|vol|volume|quest)\s+i\b", r"\1 1", value)
    value = re.sub(r"\b(?:viii|vii|vi|iv|iii|ii|ix|v)\b", lambda match: ROMAN_NUMERALS[match.group()], value)
    value = re.sub(r"(?<!\w)(?:nintendo\s*)?switch\s*2(?!\w)|(?<!\w)ns\s*2(?!\w)", "switch2", value)
    value = re.sub(r"(?<!\w)(?:nintendo\s*)?switch(?!\w)|(?<!\w)ns(?!\w)", "switch", value)
    value = re.sub(r"play\s*station\s*([345])|ps\s*([345])", lambda match: "ps" + (match[1] or match[2]), value)
    value = re.sub(r"(?<!\w)(?:xbox\s*)?series\s*([xs])(?!\w)", lambda match: "xboxseries" + match[1], value)
    value = re.sub(r"(?<!\w)xbox\s*(one|360)(?!\w)", lambda match: "xbox" + match[1], value)
    value = re.sub(r"(?<!\w)(\d+)\s*(?:tb|тб)(?!\w)", lambda m: str(int(m[1]) * 1000) + "gb", value)
    value = re.sub(r"(?<!\w)(\d+)\s*(?:gb|гб)(?!\w)", lambda m: str(int(m[1])) + "gb", value)
    value = re.sub(r"\b(fc|gta|wrc|xxl|vr|nba|fifa|ufc)\s*(\d+)\b", r"\1 \2", value)
    value = re.sub(r"[^\w]+", " ", value)
    return " ".join(value.split())


def _words(value):
    return set(normalize(value).split())


def _price(row):
    if not isinstance(row, dict):
        return None
    if any(row.get(field) for field in ("is_free", "price_not_published", "price_is_from")):
        return None
    if row.get("price_min") is not None or row.get("price_max") is not None:
        return None
    if row.get("price_period") or row.get("price_per_unit"):
        return None
    try:
        price = Decimal(str(row.get("price")))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return price if price.is_finite() and price > 0 else None


def suspicious_price(row, product_price, description=""):
    price = _price(row)
    if price is None:
        return True
    text = str(description or "")
    if PLACEHOLDER.search(text):
        return True
    stated = [Decimal(raw.replace(" ", "").replace("\u00a0", "")) for raw in MONEY.findall(text)]
    return bool(stated and any(other > price * 2 for other in stated) and
                product_price and price < Decimal(str(product_price)) / 4)


def _param_text(row):
    parts = []
    for field in ("params", "params_summary"):
        params = row.get(field)
        if isinstance(params, list):
            parts.extend(f"{p.get('name', '')} {p.get('value', '')}" for p in params if isinstance(p, dict))
        elif isinstance(params, dict):
            parts.extend(f"{name} {value}" for name, value in params.items())
        elif isinstance(params, str):
            parts.append(params)
    return " ".join(parts)


def new_condition(row):
    params = row.get("params") or []
    if not isinstance(params, list):
        return False
    values = [normalize(p.get("value")) for p in params if isinstance(p, dict) and normalize(p.get("name")) == "состояние"]
    return len(values) == 1 and values[0] in {"новое", "новый", "new"}


def _variant(value):
    words = _words(value)
    sizes = {word for word in words if re.fullmatch(r"\d+gb", word)}
    platforms = words & PLATFORMS
    editions = words & ({"slim", "pro", "disc", "digital"} | GAME_EDITIONS)
    return sizes, platforms, editions


def _game_title(product):
    """Убирает только известный платформенный префикс и служебный код карточки."""
    title = str(product.name or "").strip()
    platform = next(iter(_variant(product.platform.name)[1]), "")
    prefixes = {"switch2": {"switch2"}, "switch": {"switch"},
                "xboxseriesx": {"xbox", "xboxseriesx"}, "ps4": {"ps4"}, "ps5": {"ps5"}}
    parts = title.split(maxsplit=1)
    if len(parts) == 2 and normalize(parts[0]) in prefixes.get(platform, set()):
        title = parts[1]
    title = re.sub(r"\b(?:CUSA|PPSA)\b(?:\s*\d{4,6}(?:\s*[,;/]\s*\d{4,6})*)?", " ", title, flags=re.I)
    code = str(getattr(product, "cusa_ppsa_code", "") or "")
    for number in re.findall(r"\b\d{4,6}\b", code):
        title = re.sub(rf"(?<!\d){re.escape(number)}(?!\d)", " ", title)
    title = re.sub(r"\(\s*(?:rus|eng|end)(?:\s+(?:sub|lang|voice))?\s*\)", " ", title, flags=re.I)
    return " ".join(title.split())


def _game_identity(product):
    title = _game_title(product)
    core = _words(title) - GAME_STOP_WORDS
    profile_title = str(getattr(getattr(product, "avito_profile", None), "listing_title", "") or "")
    if not profile_title:
        return title
    platform = _variant(product.platform.name)[1]
    profile_platform = _variant(profile_title)[1]
    if profile_platform and profile_platform != platform:
        return title
    profile_title = re.sub(r"\([^)]*\b(?:новый|новая|диск|картридж)\b[^)]*\)", " ", profile_title, flags=re.I)
    profile_title = re.sub(r"(?<!\w)(?:nintendo\s*)?switch\s*2(?!\w)|(?<!\w)ns\s*2(?!\w)|"
                           r"(?<!\w)(?:nintendo\s*)?switch(?!\w)|(?<!\w)ns(?!\w)|"
                           r"(?<!\w)(?:play\s*station|ps)\s*[345](?!\w)|"
                           r"(?<!\w)xbox\s*series\s*[xs](?!\w)", " ", profile_title, flags=re.I)
    core_tokens = [word for word in normalize(title).split() if word not in GAME_STOP_WORDS]
    profile_tokens = [word for word in normalize(profile_title).split() if word not in GAME_STOP_WORDS and word not in {"новый", "новая", "картридж", "диск"}]
    if len(core_tokens) == len(profile_tokens):
        differences = [(old, new) for old, new in zip(core_tokens, profile_tokens) if old != new]
        if len(differences) == 1:
            old, new = differences[0]
            if len(new) == len(old) + 1 and any(old == new[:index] + new[index + 1:] for index in range(len(new))):
                series = getattr(product, "game_series", None)
                series_words = _words(series.name) if series else set()
                if new in series_words and old not in series_words:
                    return " ".join(profile_title.split())
    if len(core) > 2:
        return title
    profile_words = _words(profile_title) - GAME_STOP_WORDS - {"новый", "новая", "картридж", "диск"}
    additions = profile_words - core
    profile_has_other_edition = "edition" in _words(profile_title) and "edition" not in _words(title)
    if (core and core <= profile_words and 1 <= len(additions) <= 3 and
            not additions & (GAME_EDITIONS | {"ea", "fifa", "sports"}) and
            not any(word.isdecimal() for word in additions) and not profile_has_other_edition):
        return " ".join(profile_title.split())
    return title


def _one_typo(left, right):
    if len(left) < 5 or len(right) < 5 or left[0] != right[0] or abs(len(left) - len(right)) > 1:
        return False
    if len(left) == len(right):
        different = [index for index, (a, b) in enumerate(zip(left, right)) if a != b]
        return len(different) == 1 or (len(different) == 2 and different[1] == different[0] + 1 and
                                       left[different[0]] == right[different[1]] and left[different[1]] == right[different[0]])
    shorter, longer = sorted((left, right), key=len)
    return any(shorter == longer[:index] + longer[index + 1:] for index in range(len(longer)))


def _game_words_match(game_title, listing_title):
    required_tokens = [word for word in normalize(game_title).split() if word not in GAME_STOP_WORDS]
    actual_tokens = normalize(listing_title).split()
    actual = set(actual_tokens)
    actual.update(left + right for left, right in zip(actual_tokens, actual_tokens[1:]))
    matched = {word for word in required_tokens if word in actual or
               (not word.isdecimal() and any(_one_typo(word, candidate) for candidate in actual))}
    for left, right in zip(required_tokens, required_tokens[1:]):
        if left + right in actual:
            matched.update((left, right))
    return bool(required_tokens) and set(required_tokens) <= matched


def product_matches(product, kind, row):
    title = str(row.get("title") or "")
    if not title or BLOCKED.search(title + " " + str(row.get("description") or row.get("description_snippet") or "") + " " + _param_text(row)):
        return False
    if kind == "cd" and GAME_ACCESSORY.search(title):
        return False
    if kind == "cd" and (DIGITAL_GAME.search(_media_text(row)) or NO_PHYSICAL_GAME.search(_media_text(row))):
        return False
    category = row.get("category") or {}
    category_text = str(category.get("name") or category.get("slug") or "") if isinstance(category, dict) else str(category)
    if re.search(r"услуг|работа|недвижим|service", category_text, re.I):
        return False
    title_words = _words(title)
    product_words = _words(product.name)
    if kind == "cd":
        if re.search(r"цифров\w*\s+(?:верси\w*|игр\w*|копи\w*)|электронн\w*\s+верси\w*|\b(?:game|activation)[-\s]?key\b", title + " " + str(row.get("description") or ""), re.I):
            return False
        game_title = _game_identity(product)
    else:
        brand = _words(product.brand.name)
        if brand and not brand <= title_words | _words(_param_text(row)):
            return False
        required = product_words - brand - {"для", "консоль", "приставка", "игровая", "новый"}
    if (not _game_words_match(game_title, title) if kind == "cd" else not required or not required <= title_words):
        return False
    expected_sizes, expected_platforms, expected_editions = _variant(product.name + (" " + product.platform.name if kind == "cd" else ""))
    actual_sizes, title_platforms, actual_editions = _variant(title + " " + _param_text(row))
    actual_platforms = _variant(title)[1] or title_platforms
    if expected_sizes and actual_sizes != expected_sizes:
        return False
    if expected_platforms and actual_platforms != expected_platforms and (actual_platforms or "params" in row):
        return False
    if expected_editions & {"disc", "digital"} and (expected_editions & {"disc", "digital"}) != (actual_editions & {"disc", "digital"}):
        return False
    if expected_editions & {"slim", "pro"} and (expected_editions & {"slim", "pro"}) != (actual_editions & {"slim", "pro"}):
        return False
    if kind == "cd" and expected_editions & GAME_EDITIONS != actual_editions & GAME_EDITIONS:
        return False
    return True


def queue():
    stock = Coalesce(Sum("warehouse_stocks__quantity"), Value(0), output_field=IntegerField())
    cds = CD.objects.active().filter(avito_profile__connection__isnull=False).annotate(check_stock=stock).filter(check_stock__gt=0).select_related("platform", "game_series", "avito_profile").order_by("pk")
    tech = Tech.objects.active().filter(avito_profile__connection__isnull=False).annotate(check_stock=stock).filter(check_stock__gt=0).select_related("brand", "product_type", "avito_profile").order_by("pk")
    return [("cd", product) for product in cds] + [("tech", product) for product in tech]


def _avito_url(value):
    parsed = urlparse(str(value or ""))
    return str(value) if parsed.scheme == "https" and parsed.hostname in {"www.avito.ru", "avito.ru"} else ""


def _image(value):
    parsed = urlparse(str(value or ""))
    return str(value) if parsed.scheme == "https" and parsed.hostname and parsed.hostname.endswith(".img.avito.st") else ""


def _city(full, brief):
    for row in (full, brief):
        location = row.get("location") or {}
        if isinstance(location, dict) and location.get("name"):
            return str(location["name"])[:255]
    return ""


def _search_query(product, kind):
    if kind != "cd":
        return product.name
    return normalize(_game_identity(product)) + " " + product.platform.name


def manual_search_url(product, kind):
    """Коды фильтров сверены с формой поиска Avito; платформа остаётся в запросе."""
    query = _search_query(product, kind)
    if kind != "cd":
        return "https://www.avito.ru/all?" + urlencode({"q": query + " новый", "localPriority": 0})
    platforms = _variant(product.platform.name)[1]
    # 110390=431231: новое; 191956=3358159: физический;
    # 167162=3270848: диск, 3270849: картридж. Остальные фильтры не заданы.
    filters = ("ASgBAgICBESSAsYJ7LwN_tE09LMUgqOPA6i3F573mQM"
               if platforms & {"switch", "switch2"}
               else "ASgBAgICBESSAsYJ7LwN_tE09LMUgKOPA6i3F573mQM")
    path = ("https://www.avito.ru/all/igry_pristavki_i_programmy/"
            "igry_pristavki_i_programmy/igry_dlya_pristavok/"
            "fizicheskii-ASgBAgICAkSSAsYJqLcXnveZAw")
    return path + "?" + urlencode({
        "cd": 1, "f": filters,
        "localPriority": 0, "q": query,
    })


def _search_candidates(client, query, product, kind, own_ids, page_limit, stats):
    candidates = {}
    for page in range(1, page_limit + 1):
        stats["search_requests"] += 1
        data = client.search(query, page)
        rows = data.get("listings")
        if not isinstance(rows, list):
            raise ReefApiError("ReefAPI вернул неполную поисковую выдачу.")
        for row in rows:
            if not isinstance(row, dict):
                continue
            ad_id = str(row.get("ad_id") or "")
            if not ad_id.isdecimal() or int(ad_id) in own_ids or ad_id in candidates:
                continue
            if _price(row) is None or not product_matches(product, kind, row):
                continue
            if PLACEHOLDER.search(str(row.get("description_snippet") or "")):
                continue
            candidates[ad_id] = row
        if not data.get("has_more"):
            break
    stats["search_limited"] = bool(data.get("has_more"))
    return sorted(candidates.items(), key=lambda item: (_price(item[1]), -int(item[0])))


def _fetch_listing(client, ad_id):
    try:
        return client.listing(ad_id).get("listing")
    except ReefApiError as exc:
        if exc.code == "NOT_FOUND":
            return None
        raise


def _validated_offer(product, kind, ad_id, brief, full):
    if not isinstance(full, dict) or str(full.get("ad_id")) != ad_id:
        return None
    if str(full.get("status") or "").lower() not in {"active", ""}:
        return None
    if not new_condition(full) or not product_matches(product, kind, full):
        return None
    if kind == "cd" and not physical_game(full):
        return None
    if suspicious_price(full, product.avito_price, full.get("description")):
        return None
    price = _price(full)
    url = _avito_url(full.get("url") or brief.get("url"))
    if not url:
        return None
    images = full.get("images") or brief.get("images") or []
    seller = full.get("seller") or brief.get("seller") or {}
    return {
        "ad_id": ad_id, "title": str(full.get("title") or "")[:500],
        "price": str(price), "url": url,
        "image": _image(images[0]) if isinstance(images, list) and images else "",
        "city": _city(full, brief),
        "seller": str(seller.get("shop_name") or seller.get("name") or "")[:255] if isinstance(seller, dict) else "",
    }


def _rank_candidates(client, product, kind, ordered, detail_limit, stats, *, force=False):
    offers = []
    changed_price = False
    position = 0
    cutoff = timezone.now() - CACHE_TTL
    cached = {} if force else {
        row.ad_id: row.data for row in AvitoCheckListingCache.objects.filter(
            ad_id__in=[ad_id for ad_id, _ in ordered[:detail_limit]], checked_at__gte=cutoff,
        )
    }
    limit = min(len(ordered), detail_limit)
    with ThreadPoolExecutor(max_workers=3) as executor:
        while position < limit:
            batch = ordered[position:min(limit, position + min(3, max(1, OFFER_LIMIT - len(offers))))]
            position += len(batch)
            listing_cache = {
                ad_id: cached[ad_id] for ad_id, brief in batch if ad_id in cached
                and _price(cached[ad_id]) == _price(brief)
                and normalize(cached[ad_id].get("title")) == normalize(brief.get("title"))
            }
            stats["cached_listings"] += len(listing_cache)
            missing = [ad_id for ad_id, _ in batch if ad_id not in listing_cache]
            stats["listing_requests"] += len(missing)
            for ad_id, full in zip(missing, executor.map(lambda item: _fetch_listing(client, item), missing)):
                listing_cache[ad_id] = full
                if isinstance(full, dict) and str(full.get("ad_id")) == ad_id:
                    AvitoCheckListingCache.objects.update_or_create(
                        ad_id=ad_id, defaults={"data": full, "checked_at": timezone.now()},
                    )
            for ad_id, brief in batch:
                full = listing_cache[ad_id]
                offer = _validated_offer(product, kind, ad_id, brief, full)
                if offer is not None:
                    changed_price = changed_price or Decimal(offer["price"]) != _price(brief)
                    offers.append(offer)
            if len(offers) >= OFFER_LIMIT and not changed_price:
                last = sorted(offers, key=lambda row: (Decimal(row["price"]), -int(row["ad_id"])))[OFFER_LIMIT - 1]
                next_price = _price(ordered[position][1]) if position < len(ordered) else None
                if next_price is None or next_price > Decimal(last["price"]):
                    break
    stats["listing_limited"] = position == detail_limit and position < len(ordered)
    return sorted(offers, key=lambda row: (Decimal(row["price"]), -int(row["ad_id"])))[:OFFER_LIMIT]


def search_offers(product, kind, *, client=None, mode="economy", stats=None, force=False):
    page_limit, detail_limit = CHECK_LIMITS[mode]
    stats = stats if stats is not None else {}
    stats.update(search_requests=0, listing_requests=0, cached_listings=0, mode=mode)
    client = client or ReefApiClient()
    query = _search_query(product, kind)
    own_ids = set(AvitoListingConnection.objects.values_list("remote_listing__avito_item_id", flat=True))
    ordered = _search_candidates(client, query, product, kind, own_ids, page_limit, stats)
    offers = _rank_candidates(client, product, kind, ordered, detail_limit, stats, force=force)
    stats["credits"] = 2 * stats["search_requests"] + stats["listing_requests"]
    return offers


def _check_signature(product, kind):
    price = str(Decimal(str(product.avito_price)).normalize()) if product.avito_price is not None else None
    values = [kind, product.pk, product.name, _search_query(product, kind), price,
              getattr(product, "brand_id", None), getattr(product, "platform_id", None)]
    return hashlib.sha256(json.dumps(values, ensure_ascii=False).encode()).hexdigest()


def display_result(product, kind):
    result = AvitoPriceCheckResult.objects.filter(profile=product.avito_profile).first()
    if result:
        result.requires_update = (result.metadata.get("version") != CHECK_VERSION or
                                  result.metadata.get("signature") != _check_signature(product, kind))
        result.expired = result.checked_at < timezone.now() - CACHE_TTL
    return result


def run_check(product, kind, *, client=None, mode="economy", force=False):
    if mode not in CHECK_LIMITS:
        raise ValueError("Неизвестный режим проверки.")
    result = display_result(product, kind)
    if (not force and result and not result.requires_update and not result.expired and
            (mode == "economy" or result.metadata.get("mode") == "deep")):
        return result.offers
    stats = {}
    offers = search_offers(product, kind, client=client, mode=mode, stats=stats, force=force)
    stats.update(version=CHECK_VERSION, signature=_check_signature(product, kind))
    AvitoPriceCheckResult.objects.update_or_create(
        profile=product.avito_profile, defaults={"offers": offers, "checked_at": timezone.now(), "metadata": stats},
    )
    return offers
