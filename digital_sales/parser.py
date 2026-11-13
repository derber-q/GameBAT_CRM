"""Детерминированный парсер чек-листов; свободная переписка не является покупкой."""
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from django.core.exceptions import ValidationError

CENT = Decimal('0.01')
MONEY = r'(\d[\d\s\u00a0]*(?:[.,]\d{1,2})?)\s*(?:руб\.?|₽)'


def money(value, *, positive=False):
    try:
        result = Decimal(re.sub(r'\s', '', str(value)).replace(',', '.'))
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError('Укажите корректную сумму.') from None
    if (not result.is_finite() or result.copy_abs() >= Decimal('1e18')
            or result != result.quantize(CENT, rounding=ROUND_HALF_UP) or (positive and result <= 0)):
        raise ValidationError('Сумма должна быть конечной, до копейки и в допустимом диапазоне.')
    return result.quantize(CENT)


def topup_receipt(text, balance):
    """Явное уведомление поставщика, а не просьба пополнить или реквизиты оплаты."""
    import unicodedata
    lines = [unicodedata.normalize('NFKC', line).casefold().replace('ё', 'е').strip() for line in text.splitlines()]
    # Убираются только декоративные символы в начале, сам текст не угадывается.
    lines = [re.sub(r'^[^\w]+', '', line).strip() for line in lines]
    heading = r'(?:пополнение\s+(?:баланса|счета)|(?:ваш\s+)?(?:баланс|счет)\s+(?:успешно\s+)?пополнен|зачисление\s+средств)'
    if not any(re.match(heading + r'(?:\s|[:!✅]|$)', line, re.I) for line in lines):
        return None
    amounts, issues = set(), []
    for line in lines:
        match = re.fullmatch(r'(?:сумма(?:\s+(?:пополнения|зачисления))?\s*:\s*|'
            r'зачислено(?:\s+на\s+(?:счет|баланс))?\s*:?\s*|'
            r'пополнение\s+(?:баланса|счета)\s*:\s*|'
            r'(?:ваш\s+)?(?:баланс|счет)\s+(?:успешно\s+)?пополнен\s+на\s*)'
            r'\+?\s*' + MONEY + r'[.!]?\s*', line, re.I)
        if match:
            try:
                amounts.add(str(money(match[1], positive=True)))
            except ValidationError:
                issues.append('Некорректная сумма пополнения')
    if len(amounts) != 1:
        issues.append('Нет одной однозначной положительной суммы пополнения')
    if re.search(r'отмен[а-я]*|отклон[а-я]*|ошибк[а-я]*|не\s+(?:выполнен[а-я]*|зачислен[а-я]*|подтвержден[а-я]*)|'
                 r'ожида[а-я]*|в\s+обработке|заявка|запрос\s+на\s+пополнение', text, re.I):
        issues.append('Пополнение не подтверждено поставщиком')
    balance_matches = re.findall(r'новый\s+баланс\s*:\s*([+−-]?)\s*' + MONEY, text, re.I)
    if not balance_matches:
        balance_matches = re.findall(r'баланс\s*:\s*([+−-]?)\s*' + MONEY, text, re.I)
    balances = set()
    for sign, value in balance_matches:
        try:
            balances.add(str(money(('-' if sign in ('-', '−') else '') + value)))
        except ValidationError:
            issues.append('Некорректный новый баланс')
    balance = next(iter(balances)) if len(balances) == 1 else None
    if balance is None:
        issues.append('В сообщении нет нового баланса для сверки')
    return {'balance': balance, 'topup_receipt': True, 'topup_amount': next(iter(amounts)) if len(amounts) == 1 else None,
            'topup_issues': issues}


def parse(text):
    if not isinstance(text, str) or len(text) > 32768:
        return None
    # Цитата предыдущего чек-листа не превращает сообщение готовности в новый
    # чек-лист. Оригинальный текст хранится отдельно без этого преобразования.
    text = '\n'.join(line for line in text.splitlines() if not line.lstrip().startswith('>'))
    # Знак разрешён только у баланса; цены и себестоимости чек-листа остаются неотрицательными.
    balance = re.search(r'баланс\s*:\s*([+−-]?)\s*' + MONEY, text, re.I)
    try:
        result = {'balance': str(money(('-' if balance[1] in ('-', '−') else '') + balance[2])) if balance else None}
    except ValidationError:
        result = {'balance': None}
    if re.search(r'чек[ -]лист\s+заказа', text, re.I):
        rows, issues = [], []
        for line in text.splitlines():
            if not line.lstrip().startswith(('●', '•')):
                continue
            match = re.fullmatch(r'\s*[●•]\s*(.+?)\s*[·—–]\s*' + MONEY + r'(?:\s*\|\s*#([0-9]{1,20}))?\s*', line, re.I)
            if not match or not 1 <= len(match[1]) <= 255:
                issues.append('Нераспознанная товарная строка')
                continue
            rows.append({'name': match[1].strip(), 'cost': str(money(match[2])), 'number': match[3] or ''})
        total = re.search(r'итого\s*:\s*' + MONEY, text, re.I)
        total = money(total[1]) if total else None
        numbers = [row['number'] for row in rows if row['number']]
        if not rows or len(rows) > 100 or total is None or sum((money(r['cost']) for r in rows), Decimal(0)) != total:
            issues.append('Сумма строк не совпадает с итогом либо состав неполный')
        if len(numbers) != len(set(numbers)):
            issues.append('Повтор номера внутри группы')
        if not re.search(r'статус\s*:\s*✅\s*выполнено', text, re.I):
            issues.append('Нет выполненного статуса')
        # Поставщик может выдать товар в долг. Его отметка об оплате хранится
        # отдельно и не блокирует оформление при разрешённом отрицательном балансе.
        payment_received = bool(re.search(r'оплата\s*:\s*✅\s*получена', text, re.I))
        if not numbers:
            issues.append('Нет номера поставщика')
        return dict(result, kind='checklist', items=rows, numbers=numbers, total=str(total) if total is not None else None,
                    issues=issues, payment_received=payment_received)
    ready = re.search(r'ваш\s+заказ\s*#(\d{1,20})(?:\+(\d{1,3}))?', text, re.I)
    if ready and ('готов' in text.lower() or '✅' in text):
        return dict(result, kind='goods', numbers=[ready[1]], group_count=int(ready[2] or 0) + 1)
    receipt = topup_receipt(text, result['balance'])
    if receipt:
        return {**result, 'kind': 'balance', 'numbers': [], **receipt}
    if balance:
        return dict(result, kind='balance', numbers=[])
    return None
