"""Оригинальный символ Avito на этикетке 58×40; печать не меняет статусы продажи."""
import base64
from datetime import timedelta
import hashlib
import logging
from io import BytesIO
from pathlib import Path
import uuid
import re

from PIL import Image
import pymupdf
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from core.external_policy import require_live_operation
from .models import AvitoShippingPrintJob
from .avito_orders import prepare_order


def label_pdf(encoded, carrier):
    try:
        if not isinstance(encoded, str) or len(encoded) > 2*1024*1024 or not carrier.strip() or len(carrier) > 100:
            raise ValueError
        data = base64.b64decode(encoded, validate=True)
        with Image.open(BytesIO(data)) as image:
            if image.format not in ('PNG','JPEG') or not 20 <= image.width <= 3000 or not 20 <= image.height <= 3000:
                raise ValueError
            # Пересохранение убирает метаданные; SVG/HTML и URL сервер не принимает.
            clean = BytesIO()
            width,height=image.size
            image.convert('RGB').save(clean, 'PNG')
        with pymupdf.open() as doc:
            mm = 72/25.4
            page = doc.new_page(width=58*mm, height=40*mm)
            area=pymupdf.Rect(2*mm,2*mm,56*mm,30*mm)
            # Явный расчёт области сохраняет геометрию QR независимо от поведения
            # версии PDF-библиотеки: квадрат нельзя растягивать до ширины этикетки.
            scale=min(area.width/width,area.height/height)
            x=area.x0+(area.width-width*scale)/2
            y=area.y0+(area.height-height*scale)/2
            fitted=pymupdf.Rect(x,y,x+width*scale,y+height*scale)
            page.insert_image(fitted, stream=clean.getvalue(), keep_proportion=True)
            font = Path(settings.BASE_DIR)/'static/resource/fonts/manrope.ttf'
            page.insert_font(fontname='carrier', fontfile=str(font))
            text = carrier.strip()
            size = min(11, 54*mm/max(pymupdf.Font(fontfile=str(font)).text_length(text, fontsize=1), 1))
            page.insert_textbox(pymupdf.Rect(2*mm,31*mm,56*mm,39*mm), text, fontname='carrier', fontsize=size, align=1)
            return doc.tobytes()
    except (ValueError, OSError, Image.DecompressionBombError):
        raise ValidationError('Не удалось прочитать оригинальное изображение штрихкода/QR Avito.') from None


def check_actor(actor):
    if not actor.is_active or not actor.has_perm('sales.create_sale'):
        raise PermissionDenied


@transaction.atomic
def request_label(*, actor, data):
    require_live_operation('avito_shipping_print')
    check_actor(actor)
    key = uuid.UUID(data['request_id'])
    from .models import MarketPrintJob
    if MarketPrintJob.objects.filter(request_id=key).exists():
        raise ValidationError('Ключ уже принадлежит другому заданию печати.')
    order = prepare_order(data['order'], actor)
    existing = AvitoShippingPrintJob.objects.filter(request_id=key).first()
    if existing:
        if existing.order_id != order.pk or existing.actor_id != actor.pk:
            raise ValidationError('Ключ печати уже использован.')
        return existing
    pending = order.print_jobs.exclude(state__in=['done','error']).first()
    if pending:
        return pending
    carrier = str(data['order'].get('carrier','')).strip()
    image=data.get('image')
    if symbol:=data.get('symbol'):
        if not isinstance(symbol,dict) or symbol.get('type') not in ('128','QR') or not isinstance(symbol.get('content'),str):
            raise ValidationError('Неподдерживаемые данные исходного кода Avito.')
        output=BytesIO()
        content=symbol['content']
        if symbol['type']=='128':
            from barcode import Code128
            from barcode.writer import ImageWriter
            if not re.fullmatch(r'[\x20-\x7e]{1,100}',content):
                raise ValidationError('Неподдерживаемые данные исходного кода Avito.')
            Code128(content,writer=ImageWriter()).write(output,options={'module_width':0.25,'module_height':12,'quiet_zone':3,'font_size':8,'dpi':300})
        else:
            import qrcode
            # Содержимое берётся из исходного генератора Avito, без числового
            # преобразования: начальные нули и UTF-8 должны остаться неизменными.
            try:
                encoded=content.encode('utf-8')
                if not 1<=len(encoded)<=2048:raise ValueError
                qr=qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M,box_size=8,border=4)
                qr.add_data(encoded,optimize=0)
                qr.make(fit=True)
                qr.make_image(fill_color='black',back_color='white').save(output,format='PNG')
            except (ValueError,UnicodeError,qrcode.exceptions.DataOverflowError):
                raise ValidationError('Некорректное содержимое исходного QR Avito.') from None
        image=base64.b64encode(output.getvalue()).decode()
    pdf = label_pdf(image, carrier)
    from .market_fulfillment import _printer_target
    target = _printer_target()
    job = AvitoShippingPrintJob(order=order, actor=actor, request_id=key,
        document_digest=hashlib.sha256(pdf).hexdigest(), **target,
        state='agent_waiting' if target['print_backend']=='agent' else 'pending')
    job.file.save(f'{key}.pdf', ContentFile(pdf), save=False)
    job.save()
    return job


def process_jobs(stop=None):
    require_live_operation('avito_shipping_worker')
    if getattr(settings,'LABEL_PRINT_BACKEND','native') != 'native':
        return
    from .label_printing import print_pdf, print_job_completed, release_print_job
    now = timezone.now()
    # Маркер printing выставлен до Windows: после сбоя нельзя печатать повторно.
    for job in AvitoShippingPrintJob.objects.filter(print_backend='native', state__in=['printing','spooled']):
        if job.updated_at < now-timedelta(minutes=3):
            job.state, job.last_error = 'uncertain', 'Печать не подтверждена. Проверьте стикер; автоматического повтора нет.'
            job.save(update_fields=['state','last_error','updated_at'])
    for pk in list(AvitoShippingPrintJob.objects.filter(print_backend='native', state__in=['pending','spooled']).values_list('pk',flat=True)[:30]):
        if stop is not None and stop.is_set():
            return
        with transaction.atomic():
            job = AvitoShippingPrintJob.objects.select_for_update().get(pk=pk)
            if job.state not in ('pending','spooled'):
                continue
            try:
                check_actor(job.actor)
            except PermissionDenied:
                job.state,job.last_error='error','У сотрудника больше нет прав на печать.'
                job.save(update_fields=['state','last_error','updated_at'])
                continue
            if job.state=='pending':
                job.state='printing'
                job.save(update_fields=['state','updated_at'])
                submit=True
            else:
                submit=False
        title = 'Avito shipment '+str(job.request_id)
        try:
            if submit:
                with job.file.open('rb') as file:
                    pdf=file.read(3*1024*1024)
                job.printer_job_id=print_pdf(pdf, printer_name=job.printer_name, title=title)
                job.state,job.spooled_at='spooled',timezone.now()
                job.save(update_fields=['printer_job_id','state','spooled_at','updated_at'])
            elif print_job_completed(job.printer_name,job.printer_job_id,expected_title=title):
                job.printed_at,job.state=timezone.now(),'done'
                job.save(update_fields=['printed_at','state','updated_at'])
                try:
                    release_print_job(job.printer_name,job.printer_job_id,expected_title=title)
                except Exception:
                    logging.getLogger('gamebat.business').warning('avito_label_release_failed job_id=%s',job.pk)
        except Exception:
            job.state,job.last_error='uncertain','Не удалось подтвердить печать. Проверьте принтер и стикер.'
            job.save(update_fields=['state','last_error','updated_at'])


def agent_claim(agent, instance):
    from .print_agents import _session, AGENT_ACTIVE
    _session(agent, instance)
    jobs = AvitoShippingPrintJob.objects.select_for_update().filter(agent=agent,print_backend='agent')
    for old in jobs.filter(state__in=AGENT_ACTIVE):
        if old.agent_claimed_at < timezone.now()-timedelta(minutes=3):
            old.state,old.last_error='uncertain','Агент не подтвердил печать. Проверьте стикер.'
            old.save(update_fields=['state','last_error','updated_at'])
    job=jobs.filter(state__in=AGENT_ACTIVE).order_by('pk').first() or jobs.filter(state='agent_waiting').order_by('pk').first()
    if not job:
        return {'job':None}
    check_actor(job.actor)
    if job.state=='agent_waiting':
        job.state,job.agent_claim,job.agent_claimed_at='agent_claimed',uuid.uuid4(),timezone.now()
        job.save(update_fields=['state','agent_claim','agent_claimed_at','updated_at'])
    return {'job':{'id':str(job.request_id),'claim':str(job.agent_claim),'sha256':job.document_digest,
                   'state':job.state,'title':'Avito shipment '+str(job.request_id)}}


def agent_owned(agent_id, instance, request_id, lock=False):
    from .print_agents import _session, AgentError
    from .models import PrintAgent
    agent=PrintAgent.objects.get(pk=agent_id,enabled=True)
    _session(agent,instance)
    qs=AvitoShippingPrintJob.objects.select_for_update() if lock else AvitoShippingPrintJob.objects
    job=qs.filter(request_id=request_id,agent=agent,print_backend='agent').first()
    if not job:
        raise AgentError('job_not_found',404)
    check_actor(job.actor)
    return job


@transaction.atomic
def agent_result(agent_id, instance, request_id, data):
    from .models import PrintAgent
    from .print_agents import AgentError, AGENT_ACTIVE
    PrintAgent.objects.select_for_update().get(pk=agent_id,enabled=True)
    job=agent_owned(agent_id,instance,request_id,lock=True)
    if data.get('claim')!=str(job.agent_claim) or data.get('sha256')!=job.document_digest:
        raise AgentError('claim_mismatch')
    state=data.get('state')
    if job.printed_at and state=='confirmed' and data.get('spool_job_id')==job.printer_job_id:
        return {'ok':True,'state':job.state}
    if job.state not in AGENT_ACTIVE or job.agent_claimed_at < timezone.now()-timedelta(minutes=3):
        raise AgentError('employee_review_required')
    if state=='begin' and job.state in ('agent_claimed','agent_printing'):
        if job.agent.printer_name!=job.printer_name:
            raise AgentError('target_changed')
        job.state='agent_printing'
    elif state in ('spooled','confirmed') and job.state in ('agent_printing','agent_spooled'):
        spool=data.get('spool_job_id')
        if type(spool) is not int or not 0<spool<=2147483647 or job.printer_job_id not in (None,spool):
            raise AgentError('invalid_spool_id',400)
        job.printer_job_id,job.spooled_at=spool,job.spooled_at or timezone.now()
        job.state='agent_spooled'
        if state=='confirmed':
            job.state,job.printed_at='done',timezone.now()
    elif state in ('error','uncertain'):
        job.state='error' if job.state=='agent_claimed' and state=='error' else 'uncertain'
        job.last_error='Проверьте отправительный стикер и принтер.'
    else:
        raise AgentError('invalid_state')
    job.save(update_fields=['state','printer_job_id','spooled_at','printed_at','last_error','updated_at'])
    return {'ok':True,'state':job.state}
