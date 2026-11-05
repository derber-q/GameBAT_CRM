"""Тонкий адаптер существующего Excel; формулы и отбор товаров остаются в price.excel."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from warehouse.models import Warehouse
from price.excel import generate_wholesale_price_xlsx, generate_supplier_template
from partners.models import Supplier
from .access import check_function_access, BotDenied
from .menu import WHOLESALE, SUPPLIER_TEMPLATES


def wholesale_document(access, warehouse_id):
    user = check_function_access(access, WHOLESALE.code)
    if not Warehouse.objects.filter(pk=warehouse_id).exists():
        raise ValidationError('Выбранный склад больше не доступен.')
    data = generate_wholesale_price_xlsx(warehouse_id=warehouse_id, actor=user, partner_id=None, partner_name='')
    if len(data) > getattr(settings, 'TELEGRAM_STAFF_MAX_DOCUMENT_BYTES', 45 * 1024 * 1024):
        raise ValidationError('Прайс превышает допустимый размер Telegram.')
    return f'ReSOURCE Price List Опт {timezone.localdate():%d.%m.%Y}.xlsx', data


def supplier_documents(access, supplier_id):
    documents = []
    for kind in ('cd', 'tech'):
        user = check_function_access(access, SUPPLIER_TEMPLATES.code)
        supplier = Supplier.objects.filter(pk=supplier_id).first()
        if supplier is None:
            raise BotDenied('supplier_missing', 'Поставщик не найден. Откройте список заново.')
        data = generate_supplier_template(actor=user, product_kind=kind, supplier_id=supplier.pk)
        if len(data) > getattr(settings, 'TELEGRAM_STAFF_MAX_DOCUMENT_BYTES', 45 * 1024 * 1024):
            raise ValidationError('Шаблон превышает допустимый размер Telegram.')
        documents.append((kind, f'resource-supplier-{supplier.letter}-{kind}-template.xlsx', data))
    return documents
