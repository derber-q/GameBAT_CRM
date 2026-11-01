"""Атомарные назначения агенту; HTTP/Windows никогда не вызываются внутри транзакции."""
from datetime import timedelta
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from core.external_policy import require_live_operation
from .models import MarketPrintJob, PrintAgent

SESSION_SECONDS = 90
MAX_PDF_BYTES = 30*1024*1024
AGENT_ACTIVE = ('agent_claimed', 'agent_printing', 'agent_spooled')


class AgentError(Exception):
    def __init__(self, code, status=409):
        self.code, self.status = code, status


def configured_agent():
    require_live_operation('print_agent_configuration')
    query = PrintAgent.objects.filter(enabled=True)
    if value := getattr(settings, 'PRINT_AGENT_ID', ''):
        try:
            query = query.filter(pk=uuid.UUID(str(value)))
        except ValueError:
            raise ValidationError('Некорректный идентификатор агента печати.') from None
    agents = list(query[:2])
    if len(agents) != 1:
        raise ValidationError('Настройте один агент печати или явно укажите нужный агент.')
    return agents[0]


def _session(agent, instance):
    if agent.session != instance or not agent.last_seen_at or agent.last_seen_at < timezone.now()-timedelta(seconds=SESSION_SECONDS):
        raise AgentError('session_conflict')


@transaction.atomic
def heartbeat(agent_id, instance, data):
    agent = PrintAgent.objects.select_for_update().get(pk=agent_id, enabled=True)
    now = timezone.now()
    if agent.session and agent.session != instance and agent.last_seen_at and agent.last_seen_at > now-timedelta(seconds=SESSION_SECONDS):
        raise AgentError('session_conflict')
    if type(data.get('printer_available')) is not bool or not isinstance(data.get('version'), str) or not 1 <= len(data['version']) <= 32:
        raise AgentError('invalid_heartbeat', 400)
    agent.session, agent.last_seen_at = instance, now
    agent.version = data['version']
    matches = data.get('printer_name') == agent.printer_name
    agent.printer_available = matches and data['printer_available']
    agent.last_error = '' if agent.printer_available else (
        'Принтер недоступен: проверьте подключение, бумагу и очередь.' if matches else 'Имя принтера отличается от настройки сервера.')
    if agent.printer_available:
        agent.incident=agent.incident_started_at=None
    elif not agent.incident:
        agent.incident,agent.incident_started_at=uuid.uuid4(),now
    agent.save(update_fields=['session','last_seen_at','version','printer_available','last_error','incident','incident_started_at'])
    return {'ok': True, 'protocol': 1}


def _audit(job, action, **details):
    from yandex_market.services import audit
    audit(job.order.integration, job.actor, action, job.order.order_id,
          print_job=job.pk, agent=str(job.agent_id), **details)


def _expire(job, now):
    if not job.agent_claimed_at:
        return
    if job.state == 'agent_claimed' and job.agent_claimed_at < now-timedelta(seconds=SESSION_SECONDS):
        job.state, job.agent_claim, job.agent_claimed_at = 'agent_waiting', None, None
        job.save(update_fields=['state','agent_claim','agent_claimed_at','updated_at'])
    elif job.state in ('agent_printing','agent_spooled') and (
            job.agent_claimed_at < now-timedelta(minutes=3) or
            not job.agent.last_seen_at or job.agent.last_seen_at < now-timedelta(seconds=SESSION_SECONDS)):
        job.state = 'uncertain'
        job.last_error = 'Результат печати неизвестен. Проверьте этикетку перед повторением.'
        job.save(update_fields=['state','last_error','updated_at'])
        _audit(job, 'print_agent_uncertain')


@transaction.atomic
def expire_job(pk):
    job = MarketPrintJob.objects.select_for_update(of=('self',)).select_related('agent','order','actor').get(pk=pk)
    _expire(job, timezone.now())


@transaction.atomic
def claim(agent_id, instance):
    agent = PrintAgent.objects.select_for_update().get(pk=agent_id, enabled=True)
    _session(agent, instance)
    for job in MarketPrintJob.objects.select_for_update(of=('self',)).select_related('agent','order','actor').filter(agent=agent,state__in=AGENT_ACTIVE):
        _expire(job, timezone.now())
    if agent.printer_available is not True:
        return {'job': None}
    active = MarketPrintJob.objects.filter(agent=agent,print_backend='agent',state__in=AGENT_ACTIVE).order_by('pk').first()
    if active:
        job = active
    else:
        job = MarketPrintJob.objects.select_for_update().filter(agent=agent,print_backend='agent',state='agent_waiting').order_by('pk').first()
        if job is None:
            from .avito_shipping import agent_claim
            return agent_claim(agent, instance)
        job.agent_claim, job.agent_claimed_at, job.state = uuid.uuid4(), timezone.now(), 'agent_claimed'
        job.save(update_fields=['agent_claim','agent_claimed_at','state','updated_at'])
        _audit(job, 'print_agent_claimed')
    return {'job': {'id': str(job.request_id), 'claim': str(job.agent_claim),
                    'sha256': job.document_digest, 'state':job.state, 'title': f'Yandex order {job.order.order_id}'}}


def owned_job(agent_id, instance, request_id, *, lock=False):
    agent = PrintAgent.objects.get(pk=agent_id, enabled=True)
    _session(agent, instance)
    query = MarketPrintJob.objects.select_related('order__integration','order__sale','actor','agent','document')
    if lock:
        query = query.select_for_update(of=('self',))
    job = query.filter(request_id=request_id,agent=agent,print_backend='agent').first()
    if not job:
        raise AgentError('job_not_found', 404)
    return job


@transaction.atomic
def result(agent_id, instance, request_id, data):
    # Сериализация с heartbeat, сменой экземпляра и выдачей следующего задания.
    PrintAgent.objects.select_for_update().get(pk=agent_id,enabled=True)
    job = owned_job(agent_id, instance, request_id, lock=True)
    if str(job.agent_claim) != data.get('claim') or not job.document_digest or job.document_digest != data.get('sha256'):
        raise AgentError('claim_mismatch')
    state = data.get('state')
    if state in ('begin','spooled','confirmed') and job.state in AGENT_ACTIVE and job.agent_claimed_at < timezone.now()-timedelta(minutes=3):
        raise AgentError('employee_review_required')
    if job.state == 'uncertain':
        raise AgentError('employee_review_required')
    if job.printed_at:
        if state == 'confirmed' and data.get('spool_job_id') == job.printer_job_id:
            return {'ok': True, 'state': job.state}
        raise AgentError('already_finished')
    from .market_fulfillment import _check_actor
    _check_actor(job.actor, scanning=job.ready_after_print)
    if state == 'begin':
        if job.state not in ('agent_claimed','agent_printing'):
            raise AgentError('invalid_state')
        if job.printer_name != job.agent.printer_name or job.order.fake:
            raise AgentError('target_changed')
        job.state = 'agent_printing'
    elif state in ('spooled','confirmed'):
        spool = data.get('spool_job_id')
        if type(spool) is not int or not 0 < spool <= 2147483647:
            raise AgentError('invalid_spool_id', 400)
        if job.state not in ('agent_printing','agent_spooled') or job.printer_job_id not in (None,spool):
            raise AgentError('invalid_state')
        job.printer_job_id = spool
        job.spooled_at = job.spooled_at or timezone.now()
        job.state = 'agent_spooled'
        if state == 'confirmed':
            job.printed_at, job.state = timezone.now(), 'printed'
    elif state in ('error','uncertain'):
        if job.state not in AGENT_ACTIVE:
            raise AgentError('invalid_state')
        job.state = 'uncertain' if state == 'uncertain' or job.state != 'agent_claimed' else 'error'
        job.last_error = ('Результат печати неизвестен. Требуется проверка сотрудником.' if job.state == 'uncertain'
                          else 'Агент не начал печать: проверьте принтер и документ.')
    else:
        raise AgentError('invalid_result', 400)
    job.save(update_fields=['state','printer_job_id','spooled_at','printed_at','last_error','updated_at'])
    _audit(job, 'print_agent_'+str(state), spool_job=job.printer_job_id)
    return {'ok': True, 'state': job.state}


def snapshot():
    agents = []
    for agent in PrintAgent.objects.all():
        connected = bool(agent.enabled and agent.last_seen_at and agent.last_seen_at > timezone.now()-timedelta(seconds=SESSION_SECONDS))
        agents.append({'id':str(agent.pk),'name':agent.name,'enabled':agent.enabled,'connected':connected,'last_seen_at':agent.last_seen_at,
            'printer_name':agent.printer_name,'printer_available':agent.printer_available,
            'version':agent.version,'last_error':agent.last_error,
            'problem_id':str(agent.incident) if connected and agent.incident else 'offline:'+str(agent.pk)+':'+str(agent.last_seen_at),
            'problem_started_at':agent.incident_started_at if connected else agent.last_seen_at,
            'pending':agent.marketprintjob_set.exclude(state__in=['done','error']).count()})
    return agents


@transaction.atomic
def resolve(request_id, actor, decision):
    from .market_fulfillment import _check_actor
    job=MarketPrintJob.objects.select_for_update(of=('self',)).select_related('order','actor','agent').get(request_id=request_id)
    _check_actor(actor,scanning=job.ready_after_print)
    if job.state!='uncertain' or decision not in ('printed','not_printed'):
        raise ValidationError('Решение доступно только после проверки неопределённой печати.')
    from yandex_market.services import audit
    audit(job.order.integration,actor,'print_result_reviewed',job.order.order_id,
          print_job=job.pk,decision=decision,previous_spool_job=job.printer_job_id)
    job.last_error=''
    job.lease=None
    if decision=='printed':
        job.state,job.printed_at='printed',timezone.now()
    else:
        job.state='pending'
        job.printer_job_id=job.spooled_at=job.agent_claim=job.agent_claimed_at=None
        from .market_fulfillment import _printer_target
        target=_printer_target()
        job.printer_name,job.print_backend,job.agent=target['printer_name'],target['print_backend'],target.get('agent')
    job.save(update_fields=['state','printed_at','last_error','lease','printer_job_id','spooled_at','agent_claim','agent_claimed_at','printer_name','print_backend','agent','updated_at'])
    return job
