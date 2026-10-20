"""Календарный срок новинки от неизменной даты создания карточки."""
import calendar

from django.core.exceptions import ValidationError
from django.utils import timezone


def newness_expiry(created_at, months):
    if not months:
        return None
    if not isinstance(months, int) or isinstance(months, bool) or months < 0:
        raise ValidationError({'newness_months': 'Укажите положительное целое количество месяцев.'})
    if created_at is None or timezone.is_naive(created_at):
        raise ValidationError({'newness_months': 'Дата создания товара не подтверждена; срок новинки назначить нельзя.'})
    local = timezone.localtime(created_at)
    year, month = divmod(local.year * 12 + local.month - 1 + months, 12)
    month += 1
    if not 1 <= year <= 9999:
        raise ValidationError({'newness_months': 'Срок выходит за пределы допустимой календарной даты.'})
    return local.replace(year=year, month=month, day=min(local.day, calendar.monthrange(year, month)[1]))


def customer_product_name(name, product, *, at=None):
    at = at or timezone.now()
    active = bool(product.created_at and product.created_at <= at and product.newness_until and at < product.newness_until)
    return ('🌟 ' + name) if active else name
