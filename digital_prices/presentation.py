"""Подписи для пересылки покупателю: только данные публичного снимка прайса."""
from zoneinfo import ZoneInfo

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .public import safe_text


def _clip(text, units):
    """Telegram измеряет подписи в UTF-16; emoji не должны удваивать лимит."""
    encoded = text.encode('utf-16-le')
    return text if len(encoded) <= units * 2 else encoded[:(units - 1) * 2].decode('utf-16-le', errors='ignore') + '…'


def page_title(bundle, page):
    titles = bundle.public_snapshot.get('page_titles', [])
    if 0 < page.index <= len(titles):
        return safe_text(titles[page.index - 1]) or 'Цифровые товары'
    # Старые комплекты не содержат заголовков. Они не перегенерируются по новым ценам.
    if page.filename.startswith('GameBAT_services_'):
        return 'Главная — подписки и цифровые услуги'
    platforms = {'playstation': 'PlayStation', 'xbox': 'Xbox', 'nintendoswitch': 'Nintendo',
                 'steam': 'Steam', 'apple': 'Apple', 'googleplay': 'Google Play',
                 'valorant': 'Valorant', 'roblox': 'Roblox', 'battledotnet': 'Battle.net', 'openai': 'ChatGPT'}
    for slug, label in platforms.items():
        if page.filename.startswith(f'GameBAT_codes_{slug}_'):
            return label + (' — коды подписок' if '_subscriptions_' in page.filename else ' — коды пополнения')
    return 'Цифровые товары'


def product_types(bundle):
    """Перечень строится по отправляемым строкам, без скрытых пустых разделов."""
    labels = []
    for row in bundle.public_snapshot.get('rows', []):
        family = safe_text(row.get('family') or row.get('category') or 'Цифровые товары')
        if row.get('section') == 'codes':
            label = family.split(' ·')[0] + (' — коды подписок' if family.endswith(' · подписки') else ' — коды пополнения')
        elif family == 'PlayStation':
            label = 'Подписки PlayStation'
        elif family == 'Xbox':
            label = 'Подписки Xbox'
        else:
            label = family
        if label not in labels:
            labels.append(label)
    # Оставляем запас в лимите Telegram даже при длинных пользовательских категориях.
    result = ''
    for label in labels:
        candidate = (result + '; ' if result else '') + label
        if len(candidate) > 320:
            return _clip((result or label[:300]) + '; другие цифровые товары', 350)
        result = candidate
    return _clip(result or 'Цифровые товары', 350)


def page_caption(bundle, page, total):
    buyer = _clip(safe_text(bundle.buyer_name_snapshot) or 'Общий прайс', 160)
    # Только что созданный ORM-объект ещё хранит ISO-строку из PublicCatalog;
    # прочитанный из БД — datetime. Форматируем оба пути одинаково.
    source_at = parse_datetime(bundle.source_at) if isinstance(bundle.source_at, str) else bundle.source_at
    source = (timezone.localtime(source_at, ZoneInfo('Europe/Moscow')).strftime('%d.%m.%Y в %H:%M')
              if source_at else 'дата обновления не подтверждена')
    lines = ['🎮 GameBAT — цифровой прайс', f'👤 Для: {buyer}',
             f'🖼 {page.index}/{total} · {_clip(page_title(bundle, page), 110)}']
    if page.index == 1:
        lines.append('📋 В прайсе: ' + product_types(bundle))
    # Это условие оформления для покупателя, а не изменение цены товара
    # или автоматическая доплата в продаже. Остальным покупателям его не показываем.
    account_fees = {'gns': 150, 'подписки gns': 150, 'играть': 100, 'подписки играть': 100}
    account_fee = account_fees.get(' '.join(bundle.buyer_name_snapshot.casefold().split()))
    if account_fee is not None:
        lines.append(f'🆕 Оформление на новый аккаунт: +{account_fee} ₽')
    lines.extend([f'🕒 Данные обновлены: {source}' + (' (МСК)' if source_at else ''),
                  '📩 Для заказа: @GameBAT_Store'])
    if bundle.public_snapshot.get('stale'):
        lines.append('⚠️ Актуальность цен и наличие уточняйте при заказе.')
    return '\n\n'.join(lines)
