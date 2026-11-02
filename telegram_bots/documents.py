"""Тонкий адаптер существующего Excel; формулы и отбор товаров остаются в price.excel."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from warehouse.models import Warehouse
from price.excel import generate_wholesale_price_xlsx
from .access import check_access


def wholesale_document(access, warehouse_id):
    user = check_access(access)
    if not Warehouse.objects.filter(pk=warehouse_id).exists():
        raise ValidationError('Выбранный склад больше не доступен.')
    data = generate_wholesale_price_xlsx(warehouse_id=warehouse_id, actor=user, partner_id=None, partner_name='')
    if len(data) > getattr(settings, 'TELEGRAM_STAFF_MAX_DOCUMENT_BYTES', 45 * 1024 * 1024):
        raise ValidationError('Прайс превышает допустимый размер Telegram.')
    return f'ReSOURCE Price List Опт {timezone.localdate():%d.%m.%Y}.xlsx', data
