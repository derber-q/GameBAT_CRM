"""Регистрация администратором: stdin содержит только публичный хеш, не токен."""
import json
import re
import sys
import uuid
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from core.external_policy import require_live_operation
from sales.models import PrintAgent, MarketPrintJob


class Command(BaseCommand):
    help='Регистрирует/обновляет агент по JSON из stdin; полный токен серверу не передаётся.'

    def add_arguments(self,parser):
        parser.add_argument('--disable',type=uuid.UUID)

    def handle(self,*args,**options):
        require_live_operation('register_print_agent')
        if options.get('disable'):
            with transaction.atomic():
                agent=PrintAgent.objects.select_for_update().get(pk=options['disable'])
                for job in MarketPrintJob.objects.filter(agent=agent,state__in=['agent_printing','agent_spooled']):
                    job.state='uncertain';job.last_error='Агент отключён. Проверьте результат печати.'
                    job.save(update_fields=['state','last_error','updated_at'])
                agent.enabled=False;agent.session=None;agent.last_seen_at=None
                agent.save(update_fields=['enabled','session','last_seen_at'])
            self.stdout.write('Агент отключён; старый токен больше не принимается.')
            return
        try:
            data=json.loads(sys.stdin.read(4097))
            agent_id=uuid.UUID(data['id'])
            if not re.fullmatch('[a-f0-9]{64}',data['token_hash']):raise ValueError
            if not isinstance(data['name'],str) or not 1<=len(data['name'])<=120:raise ValueError
            if not isinstance(data['printer_name'],str) or not 1<=len(data['printer_name'])<=200:raise ValueError
        except (ValueError,TypeError,KeyError):
            raise CommandError('Нужны id UUID, name, printer_name и SHA-256 token_hash.') from None
        with transaction.atomic():
            agent=PrintAgent.objects.select_for_update().filter(pk=agent_id).first()
            changed=agent and (agent.token_hash!=data['token_hash'] or agent.printer_name!=data['printer_name'])
            if changed:
                for job in MarketPrintJob.objects.filter(agent=agent,state__in=['agent_claimed','agent_printing','agent_spooled']):
                    job.state='agent_waiting' if job.state=='agent_claimed' else 'uncertain'
                    if job.state=='agent_waiting':job.agent_claim=None;job.agent_claimed_at=None
                    else:job.last_error='Настройка агента изменилась. Проверьте результат печати.'
                    job.save(update_fields=['state','agent_claim','agent_claimed_at','last_error','updated_at'])
            if agent is None:agent=PrintAgent(id=agent_id)
            agent.name,agent.printer_name,agent.token_hash=data['name'],data['printer_name'],data['token_hash']
            agent.enabled=True
            if changed:agent.session=None;agent.last_seen_at=None
            agent.save()
        self.stdout.write('Агент зарегистрирован: '+str(agent.pk))
