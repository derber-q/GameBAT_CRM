"""Полный комплект PNG из одного публичного снимка, без внешней сети."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from .models import PriceBundle, PricePage
from .public import snapshot, serialize, populated_blocks
from .rendering import render
from .services import require
from .layout import slide_title


def generate_bundle(*, actor, buyer=None):
    actor = require(actor, 'download_prices')
    catalog = populated_blocks(snapshot(actor=actor, buyer=buyer))
    if not catalog.rows:
        raise ValidationError('Нет блоков с заполненной наценкой. Укажите общие или индивидуальные наценки в цифровом каталоге.', code='no_priced_blocks')
    pages = render(catalog, font_directory=settings.BASE_DIR / 'static/resource/fonts')
    if sum(page.row_count for page in pages) != len(catalog.rows):
        raise ValidationError('Комплект сформирован не полностью. Отправка запрещена.')
    with transaction.atomic():
        require(actor, 'download_prices')
        public_snapshot = serialize(catalog)
        public_snapshot['page_titles'] = [slide_title(page.section, page.family) for page in pages]
        bundle = PriceBundle.objects.create(actor=actor, revision=catalog.revision, source_at=catalog.source_at,
            buyer=buyer, buyer_name_snapshot=buyer.name if buyer else '', public_snapshot=public_snapshot)
        for index, page in enumerate(pages, 1):
            PricePage.objects.create(bundle=bundle, index=index, filename=page.filename, png=page.png,
                row_count=page.row_count, width=page.width, height=page.height)
    return bundle
