"""Публичные сообщения создаются из разрешённых полей, не из ответа API."""
from dataclasses import dataclass
import re
import unicodedata
from django.core.exceptions import ValidationError
from digital_sales.customer_receipts import public_title

PRIVATE = re.compile(r'pan[\W_]*yan|yan[\W_]*store|пан[\W_]*ян|ян[\W_]*стор|себес|закуп|наценк|поставщик|'
    r'\b(?:cost|cogs|supplier|markup)\b|(?:pv2|ov2|qv2)_[\w-]+|https?://|www\.', re.I)


def title(value):
    value = unicodedata.normalize('NFKC', str(value or ''))
    return 'Цифровой товар' if PRIVATE.search(value) else public_title(value)[:160]


def checked(text):
    if not isinstance(text, str) or PRIVATE.search(unicodedata.normalize('NFKC', text)):
        raise ValidationError('Публичное сообщение остановлено проверкой конфиденциальности.')
    if len(text.encode('utf-16-le')) // 2 > 4000:
        raise ValidationError('Сообщение слишком большое. Разделите корзину.')
    return text


@dataclass(frozen=True)
class CustomerResult:
    heading: str
    values: tuple[str, ...]

    def text(self):
        return checked(self.heading + '\n' + '\n'.join(self.values))

    def parts(self):
        result, lines = [], []
        for value in self.values:
            candidate = self.heading + '\n' + '\n'.join([*lines, value])
            if len(candidate.encode('utf-16-le')) // 2 > 3800 and lines:
                result.append(checked(self.heading + '\n' + '\n'.join(lines)))
                lines = []
            lines.append(value)
        result.append(checked(self.heading + '\n' + '\n'.join(lines)))
        return result


def result_dto(result, *, name, quantity, completed):
    """Неизвестный текст/ссылка/сумма блокируют выдачу целиком, секреты не редактируются."""
    if not isinstance(result, dict):
        raise ValidationError('Результат требует проверки сотрудником.')
    heading = '✅ ' + title(name)
    if set(result) == {'codes'}:
        values = result['codes']
        if (not isinstance(values, list) or len(values) != quantity or
                any(not isinstance(v, str) or not 1 <= len(v) <= 512 or '\n' in v or '\r' in v or PRIVATE.search(v) for v in values)
                or len(set(values)) != len(values)):
            raise ValidationError('Неоднозначный комплект кодов.')
        return CustomerResult(heading, tuple('Код: ' + v for v in values))
    if result == {'completed': True} and completed:
        return CustomerResult(heading, ('Заказ выполнен.',))
    if set(result) == {'data'} and isinstance(result['data'], str):
        data = result['data']
        if PRIVATE.search(unicodedata.normalize('NFKC', data)):
            raise ValidationError('В результате найдены закрытые данные.')
        labels = {'login': 'Логин', 'логин': 'Логин', 'email': 'Почта', 'почта': 'Почта',
                  'password': 'Пароль', 'пароль': 'Пароль', 'email_password': 'Пароль почты',
                  'пароль почты': 'Пароль почты', 'code': 'Код', 'код': 'Код'}
        values, used = [], set()
        for line in data.splitlines():
            if not line.strip():
                continue
            key, sep, value = line.partition(':')
            key = key.strip().casefold()
            if not sep or key not in labels or key in used or not value.strip() or len(value) > 1024:
                raise ValidationError('Свободный результат требует проверки сотрудником.')
            used.add(key)
            # Убирается лишь форматирующий пробел после двоеточия; сами данные не меняются.
            values.append(labels[key] + ':' + value)
        if values:
            return CustomerResult(heading, tuple(values))
    raise ValidationError('Автоматическая выдача этого формата не подтверждена.')
