"""Крупный номер и QR со ссылкой на стикере 58×40; печать не проводит продажу."""
from io import BytesIO
import hashlib
import re
import uuid
from urllib.parse import urlsplit

import pymupdf
import qrcode
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from core.external_policy import require_live_operation
from .models import Sale, SaleLabelPrintJob, MarketPrintJob, AvitoShippingPrintJob

SALE_CODE = re.compile(r'SALE-[0-9]{6,18}\Z')


def check_actor(actor):
    user = get_user_model().objects.filter(pk=getattr(actor, 'pk', None), is_active=True).first()
    if not user or not user.has_perm('sales.view_sale_detail'):
        raise PermissionDenied('Нет права печатать стикер этой продажи.')


def render_label(visible_id, sale_url):
    """QR содержит обычную ссылку на продажу без ключей доступа."""
    if not isinstance(visible_id, str) or not SALE_CODE.fullmatch(visible_id):
        raise ValidationError('Некорректный номер продажи.')
    url = urlsplit(sale_url)
    if (url.scheme not in ('http', 'https') or not url.netloc or url.username or url.password
            or url.query or url.fragment or len(sale_url) > 512):
        raise ValidationError('Некорректная ссылка на продажу.')
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4)
    qr.add_data(sale_url)
    qr.make(fit=True)
    qr_data = BytesIO()
    qr.make_image(fill_color='black', back_color='white').save(qr_data, format='PNG')
    mm = 72 / 25.4
    with pymupdf.open() as document:
        page = document.new_page(width=58 * mm, height=40 * mm)
        page.insert_image(pymupdf.Rect(1 * mm, 7 * mm, 25 * mm, 31 * mm), stream=qr_data.getvalue())
        font = pymupdf.Font('hebo')
        number = visible_id.removeprefix('SALE-')
        size = min(25, 30 * mm / font.text_length(number, fontsize=1))
        # Одна строка с явной базовой линией: textbox может молча не нарисовать
        # текст, если высоты маленькой этикетки не хватает метрикам шрифта.
        page.insert_text((41.5 * mm - font.text_length('SALE', fontsize=12) / 2, 14 * mm),
                         'SALE', fontname='hebo', fontsize=12)
        page.insert_text((41.5 * mm - font.text_length(number, fontsize=size) / 2, 26 * mm),
                         number, fontname='hebo', fontsize=size)
        small = pymupdf.Font('helv')
        page.insert_text((29 * mm - small.text_length(visible_id, fontsize=7) / 2, 35 * mm),
                         visible_id, fontname='helv', fontsize=7)
        return document.tobytes(garbage=4, deflate=True)


@transaction.atomic
def request_label(*, actor, sale_id, request_id, sale_url):
    require_live_operation('sale_label_print')
    check_actor(actor)
    try:
        key = uuid.UUID(str(request_id))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError('Некорректный ключ печати.') from None
    sale = Sale.objects.select_for_update().get(pk=sale_id)
    if MarketPrintJob.objects.filter(request_id=key).exists() or AvitoShippingPrintJob.objects.filter(request_id=key).exists():
        raise ValidationError('Ключ принадлежит другому заданию печати.')
    existing = SaleLabelPrintJob.objects.filter(request_id=key).first()
    if existing:
        if existing.sale_id != sale.pk or existing.actor_id != actor.pk:
            raise ValidationError('Ключ печати уже использован.')
        return existing
    # Ошибка сети и двойное нажатие не должны напечатать несколько экземпляров.
    pending = sale.label_print_jobs.exclude(state__in=['done', 'error', 'uncertain']).order_by('pk').first()
    if pending:
        return pending
    from .market_fulfillment import _printer_target
    target = _printer_target()
    pdf = render_label(sale.visible_id, sale_url)
    job = SaleLabelPrintJob(sale=sale, actor=actor, request_id=key, **target,
        document_digest=hashlib.sha256(pdf).hexdigest(),
        state='agent_waiting' if target['print_backend'] == 'agent' else 'pending')
    job.file.save(f'{key}.pdf', ContentFile(pdf), save=False)
    job.save()
    return job


def process_jobs(stop=None):
    from .avito_shipping import process_jobs as process
    return process(stop=stop, model=SaleLabelPrintJob, check_permission=check_actor, title_prefix='CRM sale ')


def agent_claim(agent, instance):
    from .avito_shipping import agent_claim as claim
    return claim(agent, instance, model=SaleLabelPrintJob, check_permission=check_actor, title_prefix='CRM sale ')


def agent_owned(agent_id, instance, request_id):
    from .avito_shipping import agent_owned as owned
    return owned(agent_id, instance, request_id, model=SaleLabelPrintJob, check_permission=check_actor)


def agent_result(agent_id, instance, request_id, data):
    from .avito_shipping import agent_result as result
    return result(agent_id, instance, request_id, data, model=SaleLabelPrintJob, check_permission=check_actor)
