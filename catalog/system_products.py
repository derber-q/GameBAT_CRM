"""Идемпотентная инициализация двух внутренних позиций и их штрихкодов."""
import logging

from django.db import transaction

from .models import BarcodeRegistry, SystemProduct
from .product_identifiers import allocate_unique_barcode


@transaction.atomic
def ensure_system_products():
    for kind in SystemProduct.Kind.values:
        product, created = SystemProduct.objects.get_or_create(kind=kind)
        if not BarcodeRegistry.objects.filter(system_product=product).exists():
            entry = allocate_unique_barcode(BarcodeRegistry, product_kind="system", system_product=product)
            logging.getLogger("gamebat.business").info("Системная позиция инициализирована: kind=%s barcode_id=%s", kind, entry.pk)
    return SystemProduct.objects.select_related("barcode_entry").order_by("kind")
