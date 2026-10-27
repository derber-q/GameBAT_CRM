"""Нормализация контакта и ссылка на чат в браузерном клиенте Telegram."""
import re

from django.core.exceptions import ValidationError


def normalize_telegram(value):
    value = str(value or '').strip()
    if not value:
        return ''
    link = re.fullmatch(r'(?:https?://)?(?:t\.me|telegram\.me)/([A-Za-z][A-Za-z0-9_]{0,31})/?', value, re.I)
    username = link.group(1) if link else value.removeprefix('@')
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,31}', username):
        raise ValidationError('Укажите @username или ссылку t.me/username.', code='invalid_telegram')
    return '@' + username


def telegram_chat_url(value):
    try:
        username = normalize_telegram(value)
    except ValidationError:
        return ''
    return f'https://web.telegram.org/k/#{username}' if username else ''
