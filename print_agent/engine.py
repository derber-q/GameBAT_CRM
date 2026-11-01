"""Один последовательный исполнитель; повтор сети/рестарт не повторяет Windows StartDoc."""
import hashlib
import re
import uuid
from . import VERSION
from .transport import TransportError


class Engine:
    def __init__(self,api,journal,driver,printer_name):
        self.api,self.journal,self.driver,self.printer_name=api,journal,driver,printer_name

    def report(self,record,state):
        job=record['job']
        try:
            self.api.result(job,state,record['spool'])
        except TransportError as error:
            if error.status in (403,404,409):
                self.journal.put(job,'review',record['spool'])
                return False
            raise
        return True

    def resume(self,record):
        job=record['job'];state=record['state'];spool=record['spool']
        title='ReSOURCE '+job['id']+' '+job['claim'][:8]
        if state=='printing':
            record=self.journal.put(job,'uncertain')
            state='uncertain'
        if state in ('uncertain','error'):
            if self.report(record,state):
                self.journal.put(job,'review',spool)
            return
        if state=='spooled':
            try:
                complete=self.driver.completed(spool,title)
            except Exception:
                record=self.journal.put(job,'uncertain',spool)
                self.report(record,'uncertain')
                return
            if not complete:
                self.report(record,'spooled')
                return
            record=self.journal.put(job,'confirmed',spool)
            state='confirmed'
        if state=='confirmed' and self.report(record,'confirmed'):
            self.journal.put(job,'done',spool)
            try:
                self.driver.release(spool,title)
            except Exception:
                pass  # Сервер уже сохранил результат; оставшееся retained-задание не перепечатываем.

    def step(self):
        try:
            available=self.driver.available()
        except Exception:
            available=False
        self.api.heartbeat({'version':VERSION,'printer_name':self.printer_name,'printer_available':available})
        pending=[row for row in self.journal.pending() if row['state']!='received']
        if pending:
            self.resume(pending[0]);return
        job=self.api.claim()
        if job is None:
            return
        job['id']=str(uuid.UUID(job['id']));job['claim']=str(uuid.UUID(job['claim']))
        if not re.fullmatch('[a-f0-9]{64}',job.get('sha256','')):
            raise TransportError('invalid_document_digest')
        record=self.journal.get(job)
        if record:
            if record['job']['sha256']!=job['sha256']:
                raise TransportError('document_changed')
            if record['state']!='received':
                if record['state'] not in ('done','review'):
                    self.resume(record)
                return
        elif job.get('state')!='agent_claimed':
            self.resume(self.journal.put(job,'uncertain'));return
        else:
            self.journal.put(job,'received')
        if not available:
            return
        try:
            data=self.api.document(job)
            if hashlib.sha256(data).hexdigest()!=job['sha256']:
                raise ValueError('digest')
            self.driver.validate(data)
        except TransportError:
            raise
        except Exception:
            self.resume(self.journal.put(job,'error'));return
        # Маркер пишется ДО begin и Windows. Потеря ответа begin также требует проверки.
        record=self.journal.put(job,'printing')
        self.api.result(job,'begin')
        title='ReSOURCE '+job['id']+' '+job['claim'][:8]
        try:
            spool=self.driver.submit(data,title)
        except Exception:
            self.resume(self.journal.put(job,'uncertain'));return
        record=self.journal.put(job,'spooled',spool)
        self.resume(record)
