"""Разбор свободного сообщения для ручной услуги без выдуманных реквизитов API."""
import re
from django.core.exceptions import ValidationError
from django.views.decorators.debug import sensitive_variables


@sensitive_variables()
def manual_credentials(text):
    """Исходный текст передаётся исполнителю целиком в additional_data, только зашифрованным."""
    labels = {'login': 'login', 'логин': 'login', 'email': 'login', 'e-mail': 'login', 'почта': 'login',
              'password': 'password', 'pass': 'password', 'пароль': 'password',
              'email_password': 'email_password', 'пароль почты': 'email_password',
              'пароль от почты': 'email_password', 'пароль аккаунта': 'password', 'пароль от аккаунта': 'password'}
    pattern = r'(?im)(?:^|(?<=\s))(' + '|'.join(re.escape(k) for k in sorted(labels, key=len, reverse=True)) + r')[ \t]*([:=])'
    matches = list(re.finditer(pattern, text))
    values = {}
    for index, match in enumerate(matches):
        key = labels[match[1].casefold()]
        # На одной строке допускаются «логин: … пароль: …»; на следующих
        # строках остаются любые дополнительные сведения для ручного выполнения.
        end = min(text.find('\n', match.end()) if '\n' in text[match.end():] else len(text),
                  matches[index + 1].start() if index + 1 < len(matches) else len(text))
        value = text[match.end():end].rstrip('\r')
        if match[2] == ':' and value.startswith(' '):
            value = value[1:]  # Один форматирующий пробел после подписи; после «=» данные буквальны.
        if index + 1 < len(matches) and matches[index + 1].start() == end:
            value = value.rstrip()
        if key in values or not value.strip():
            raise ValidationError('Не удалось однозначно прочитать реквизиты. Укажите логин и пароль по одному разу.')
        values[key] = value
    if not matches:
        lines = [line for line in text.splitlines() if line.strip()]
        if len(lines) == 2:
            values = {'login': lines[0], 'password': lines[1]}
        else:
            pair = re.fullmatch(r'\s*([^\s@]+@[^\s@]+)\s+([^\r\n]+)', text)
            if pair:
                values = {'login': pair[1], 'password': pair[2]}
    if (not values.get('login', '').strip() or not values.get('password', '').strip()
            or len(values['login']) > 320 or len(values['password']) > 1024
            or len(values.get('email_password', '')) > 1024):
        raise ValidationError('Для выполнения нужен логин и пароль. Пришлите их одним сообщением, например: '
                              '«Логин: …» и «Пароль: …». Остальные сведения можно написать свободно.')
    return {**values, 'additional_data': text}
