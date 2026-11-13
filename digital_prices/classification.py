"""Публичные характеристики предложений: только текст API, без цен и реквизитов."""
import re

COUNTRIES = {
    'ae': 'ОАЭ', 'ar': 'Аргентина', 'at': 'Австрия', 'au': 'Австралия', 'be': 'Бельгия',
    'bh': 'Бахрейн', 'br': 'Бразилия', 'ca': 'Канада', 'ch': 'Швейцария', 'cn': 'Китай',
    'co': 'Колумбия', 'cz': 'Чехия', 'de': 'Германия', 'es': 'Испания', 'eu': 'Европа',
    'fi': 'Финляндия', 'fr': 'Франция', 'gb': 'Великобритания', 'gr': 'Греция', 'hk': 'Гонконг',
    'hr': 'Хорватия', 'hu': 'Венгрия', 'id': 'Индонезия', 'ie': 'Ирландия', 'in': 'Индия',
    'iq': 'Ирак', 'it': 'Италия', 'jp': 'Япония', 'kr': 'Южная Корея', 'kw': 'Кувейт',
    'kz': 'Казахстан', 'lb': 'Ливан', 'lu': 'Люксембург', 'mx': 'Мексика', 'my': 'Малайзия',
    'ng': 'Нигерия', 'nl': 'Нидерланды', 'no': 'Норвегия', 'nz': 'Новая Зеландия', 'om': 'Оман',
    'ph': 'Филиппины', 'pl': 'Польша', 'pt': 'Португалия', 'qa': 'Катар', 'ro': 'Румыния',
    'ru': 'Россия', 'sa': 'Саудовская Аравия', 'se': 'Швеция', 'sg': 'Сингапур', 'sk': 'Словакия',
    'th': 'Таиланд', 'tr': 'Турция', 'tw': 'Тайвань', 'ua': 'Украина', 'us': 'США',
    'vn': 'Вьетнам', 'za': 'ЮАР', 'sng': 'СНГ', 'global': 'Global',
}
REGION_CODES = {'turkey': 'tr', 'poland': 'pl', 'russia': 'ru', 'usa': 'us', 'xbox_usa': 'us',
                'india': 'in', 'indonesia': 'id', 'uk': 'gb', 'ukraine': 'ua', 'kazakhstan': 'kz', 'cis': 'sng'}
REGION_ORDER = ('tr', 'sng', 'in', 'pl', 'id', 'us')
BRANDS = ('PlayStation', 'Xbox', 'Apple', 'Valorant', 'Google Play', 'Steam', 'Roblox', 'Nintendo', 'Battle.net', 'ChatGPT')


def region_code(value):
    text = str(value).strip().casefold()
    text = next((code for code, label in COUNTRIES.items() if label.casefold() == text), text)
    return REGION_CODES.get(text, text)


def clean_caption(value):
    # Флаги и декоративные emoji заменяет рендерер, а не системный шрифт.
    return ' '.join(re.sub('[\U0001f000-\U0001ffff\u2600-\u27ff\ufe0f]', '', str(value)).split()).strip(' ·-|')


def code_characteristics(name, category):
    flag = re.search('[\U0001f1e6-\U0001f1ff]{2}', name)
    region = ''.join(chr(ord(char)-0x1f1e6+ord('a')) for char in flag[0]) if flag else 'global'
    brand = next((item for item in BRANDS if item.casefold() in category.casefold()), clean_caption(category))
    label = clean_caption(name.split('|', 1)[-1])
    # Сохраняем номинал и единицу, убирая повторяющееся описание gift card.
    nominal = re.match(r'^(?:[A-Z]{3}\s+\d[\d,.]*|\d[\d,.]*\s+(?:[A-Z]{3}\b|Robux\b|VP\b)|[$€£]\s*\d[\d,.]*)', label)
    if nominal:
        label = nominal[0]
    attrs = {'code_category': category, 'family': brand, 'denomination': label}
    if 'подписок' in category.casefold():
        plan = re.match(r'(Core|Ultimate|PC|EA Play)', clean_caption(name), re.I)
        if plan:
            attrs['plan'] = plan[0]
    return region, attrs


def characteristics(kind, name, attributes):
    """Группировка по API-типу, разрешённым характеристикам и названию варианта."""
    attrs = attributes or {}
    name = clean_caption(name)
    family, subgroup, label = '', '', name
    if kind == 'ps':
        family = 'PlayStation'
        parts = name.split('·', 1)
        if len(parts) == 2:
            subgroup, label = parts[0].strip(), parts[1].strip()
            subgroup = {plan.casefold(): plan for plan in ('Essential', 'Extra', 'Deluxe', 'Premium', 'EA Play')}.get(subgroup.casefold(), subgroup)
    elif kind == 'xbox':
        modes = attrs.get('account_modes', [])
        mode = 'Старый аккаунт' if modes == ['existing'] else 'Новый аккаунт' if modes == ['new'] else 'Тип аккаунта уточняется'
        family, subgroup = 'Xbox', mode
        label = name.split('·', 1)[-1].strip()
    elif kind == 'code':
        family, label = clean_caption(attrs.get('family') or 'Цифровые коды'), clean_caption(attrs.get('denomination') or name)
        subscription = ('подпис' in str(attrs.get('code_category', '')).casefold()
                        or family == 'Nintendo' and re.search(r'Switch\s+Online|membership', name, re.I)
                        or family == 'PlayStation' and re.search(r'\b(?:PlayStation|PS)\s*Plus\b', name, re.I))
        if subscription:
            family += ' · подписки'
        subgroup = attrs.get('plan', '')
        if subscription and family.startswith('Xbox'):
            plan = re.search(r'\b(Core|Essential|PC|Premium|Ultimate)\b', name, re.I)
            if plan:
                subgroup = 'PC' if plan[0].casefold() == 'pc' else plan[0].title()
                label = re.sub(r'^Xbox\s+Game\s+Pass\s+'+re.escape(plan[0])+r'\s*:\s*', '', label, flags=re.I)
            label = re.sub(r'\bmonths?\b', 'мес.', label, flags=re.I)
            label = re.sub(r'\bsubscription\b', '', label, flags=re.I).strip()
    elif kind == 'cprod':
        if re.match(r'^(?:invidual|individual|duo|family)\s+\d+\s*мес', name, re.I):
            family = 'Spotify'
            label = re.sub(r'^invidual', 'Individual', name, flags=re.I)
        elif re.match(r'^PLUS\s+\d+\s*мес', name, re.I):
            family = 'ChatGPT'
        else:
            family = 'Настройка'
    elif kind == 'empty':
        family = 'Пустые аккаунты'
    elif kind == 'steam_topup':
        family = 'Пополнение Steam'
        label = 'Кошелёк ' + str(attrs.get('topup_currency', '')).upper()
    else:
        family = kind or 'Другие предложения'
    return family, subgroup, label


def row_sort(label):
    """Числа сортируются численно: 1, 3, 12 месяцев; номиналы не сливаются."""
    return tuple((0, int(part)) if part.isdecimal() else (1, part.casefold())
                 for part in re.split(r'(\d+)', label))
