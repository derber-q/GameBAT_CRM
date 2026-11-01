"""Протокол печати проверяется на искусственных заказах и PDF, без оборудования/API."""
import hashlib
import tempfile
import uuid
from datetime import timedelta

from django.core.files.base import ContentFile
from django.test import TestCase, Client, override_settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from unittest.mock import patch

from accounts.models import User
from warehouse.models import Warehouse
from yandex_market.models import Integration, OrderMetadata, LabelDocument
from sales.models import Sale, MarketPrintJob, PrintAgent
from sales.test_label_printing import label_pdf


@override_settings(LABEL_PRINT_BACKEND='agent')
class PrintAgentProtocolTests(TestCase):
    def setUp(self):
        self.media=tempfile.TemporaryDirectory(); self.addCleanup(self.media.cleanup)
        setting=override_settings(MEDIA_ROOT=self.media.name); setting.enable(); self.addCleanup(setting.disable)
        self.actor=User.objects.create_superuser('agent-owner')
        self.warehouse=Warehouse.objects.create(name='Agent test')
        self.integration=Integration.objects.create(business_id=1,campaign_id=2,enabled=True,fulfillment_warehouse=self.warehouse,operator=self.actor)
        self.sale=Sale.objects.create(warehouse=self.warehouse,created_by=self.actor)
        self.order=OrderMetadata.objects.create(integration=self.integration,sale=self.sale,order_id=11,status='PROCESSING',substatus='STARTED')
        self.token='synthetic-agent-token-with-more-than-forty-characters'
        self.agent=PrintAgent.objects.create(name='Test agent',printer_name='Fake printer',token_hash=hashlib.sha256(self.token.encode()).hexdigest())
        self.session=str(uuid.uuid4())
        self.client=Client(enforce_csrf_checks=True)
        self.headers={'HTTP_HOST':'127.0.0.1','HTTP_AUTHORIZATION':'Bearer '+self.token,'HTTP_X_PRINT_AGENT':str(self.agent.pk),'HTTP_X_PRINT_SESSION':self.session,'HTTP_X_PRINT_PROTOCOL':'1'}
        self.document=LabelDocument.objects.create(integration=self.integration,order=self.order,created_by=self.actor,state='done',format='A9_HORIZONTALLY')
        self.pdf=label_pdf(); self.document.file.save('synthetic.pdf',ContentFile(self.pdf))
        self.job=MarketPrintJob.objects.create(order=self.order,actor=self.actor,printer_name='Fake printer',print_backend='agent',agent=self.agent,document=self.document,state='agent_waiting',document_digest=hashlib.sha256(self.pdf).hexdigest())

    def post(self,action,data=None,headers=None):
        return self.client.post('/crm/print-agent/'+action+'/',data=data or {},content_type='application/json',**(headers or self.headers))

    def connect(self):
        r=self.post('heartbeat',{'version':'1.0.0','printer_name':'Fake printer','printer_available':True})
        self.assertEqual(r.status_code,200,r.content)

    def claim(self):
        self.connect(); r=self.post('claim'); self.assertEqual(r.status_code,200,r.content)
        return r.json()['job']

    def report(self,offer,state,**extra):
        return self.post('jobs/'+str(self.job.request_id)+'/result',{'claim':offer['claim'],'sha256':offer['sha256'],'state':state,**extra})

    def test_authentication_test_mode_and_session_do_not_use_cookies(self):
        self.assertEqual(self.post('heartbeat',headers={**self.headers,'HTTP_AUTHORIZATION':'Bearer wrong'}).status_code,401)
        self.connect()
        self.assertEqual(self.post('claim',headers={**self.headers,'HTTP_X_PRINT_SESSION':str(uuid.uuid4())}).status_code,409)
        with override_settings(GAMEBAT_ENV='local_test'):
            self.assertEqual(self.post('claim').status_code,403)
        self.agent.enabled=False; self.agent.save()
        self.assertEqual(self.post('claim').status_code,401)

    def test_claim_and_result_retries_are_idempotent_and_spool_is_not_printed(self):
        offer=self.claim()
        self.assertEqual(self.post('claim').json()['job']['claim'],offer['claim'])
        self.assertEqual(self.report(offer,'begin').status_code,200)
        self.assertEqual(self.report(offer,'spooled',spool_job_id=77).status_code,200)
        self.job.refresh_from_db(); self.assertIsNone(self.job.printed_at)
        self.assertEqual(self.report(offer,'confirmed',spool_job_id=77).status_code,200)
        self.job.refresh_from_db(); at=self.job.printed_at; self.assertIsNotNone(at)
        self.assertEqual(self.report(offer,'confirmed',spool_job_id=77).status_code,200)
        self.job.refresh_from_db(); self.assertEqual(self.job.printed_at,at)

    def test_claim_document_and_result_are_bound_to_agent_and_digest(self):
        offer=self.claim()
        r=self.client.get('/crm/print-agent/jobs/'+str(self.job.request_id)+'/document/',**self.headers)
        self.assertEqual(r.status_code,200); self.assertEqual(b''.join(r.streaming_content),self.pdf)
        self.assertEqual(self.report({**offer,'sha256':'0'*64},'begin').status_code,409)
        other=PrintAgent.objects.create(name='Other',printer_name='Fake printer',token_hash='a'*64)
        self.job.agent=other;self.job.save()
        self.assertEqual(self.report(offer,'begin').status_code,404)

    def test_uncertain_result_never_becomes_ready_by_late_http(self):
        offer=self.claim(); self.report(offer,'begin')
        self.assertEqual(self.report(offer,'uncertain').status_code,200)
        self.assertEqual(self.report(offer,'confirmed',spool_job_id=77).status_code,409)
        self.job.refresh_from_db(); self.assertIsNone(self.job.printed_at); self.assertIsNone(self.job.ready_job_id)

    def test_expired_unstarted_claim_can_be_reissued_but_started_cannot(self):
        offer=self.claim()
        self.job.refresh_from_db(); self.job.agent_claimed_at=timezone.now()-timedelta(minutes=4);self.job.save()
        self.assertEqual(self.post('claim').status_code,200)
        self.assertNotEqual(self.post('claim').json()['job']['claim'],offer['claim'])
        self.assertEqual(self.report(offer,'begin').status_code,409)

    def test_public_http_and_browser_origin_are_rejected(self):
        self.assertEqual(self.post('claim',headers={**self.headers,'HTTP_ORIGIN':'https://other.invalid'}).status_code,403)
        with override_settings(ALLOWED_HOSTS=['example.com']):
            self.assertEqual(self.post('claim',headers={**self.headers,'HTTP_HOST':'example.com'}).status_code,403)

    def test_unknown_result_blocks_a_new_print_and_requires_explicit_employee_review(self):
        from sales.market_fulfillment import request_print
        from sales.print_agents import resolve
        self.job.state='uncertain';self.job.save()
        with self.assertRaises(ValidationError):
            request_print(order=self.order,actor=self.actor,request_id=uuid.uuid4())
        resolve(self.job.request_id,self.actor,'not_printed')
        self.job.refresh_from_db();self.assertEqual(self.job.state,'pending')
        self.assertIsNone(self.job.printed_at);self.assertIsNone(self.job.agent_claim)
        self.assertEqual(self.client.post('/crm/sales/market-print/'+str(self.job.request_id)+'/resolve/',{}).status_code,403)

    def test_server_prepares_and_finishes_agent_job_without_windows_calls(self):
        from sales.market_fulfillment import process_print_jobs
        self.job.state='pending';self.job.save()
        with patch('sales.market_fulfillment.print_pdf') as native:
            process_print_jobs()
            self.job.refresh_from_db();self.assertEqual(self.job.state,'agent_waiting')
            offer=self.claim();self.report(offer,'begin');self.report(offer,'spooled',spool_job_id=77)
            process_print_jobs();self.job.refresh_from_db();self.assertIsNone(self.job.printed_at)
            self.report(offer,'confirmed',spool_job_id=77)
            process_print_jobs();self.job.refresh_from_db();self.assertEqual(self.job.state,'done')
        native.assert_not_called()

    def test_confirmation_cannot_precede_begin_or_change_spool_job(self):
        offer=self.claim()
        self.assertEqual(self.report(offer,'confirmed',spool_job_id=77).status_code,409)
        self.report(offer,'begin');self.report(offer,'spooled',spool_job_id=77)
        self.assertEqual(self.report(offer,'confirmed',spool_job_id=78).status_code,409)

    def test_client_and_server_end_to_end_with_fake_printer(self):
        from print_agent.engine import Engine
        from print_agent.journal import Journal
        from pathlib import Path
        test=self
        class Adapter:
            def heartbeat(self,data):
                response=test.post('heartbeat',data);test.assertEqual(response.status_code,200)
            def claim(self):return test.post('claim').json()['job']
            def document(self,job):
                response=test.client.get('/crm/print-agent/jobs/'+job['id']+'/document/',**test.headers)
                return b''.join(response.streaming_content)
            def result(self,job,state,spool_job_id=None):
                response=test.report(job,state,**({'spool_job_id':spool_job_id} if spool_job_id else {}))
                test.assertEqual(response.status_code,200,response.content)
        class Driver:
            calls=0
            def available(self):return True
            def validate(self,data):
                from sales.label_printing import render_label_pages
                render_label_pages(data,dpi=203)
            def submit(self,data,title):self.calls+=1;return 77
            def completed(self,spool,title):return True
            def release(self,spool,title):pass
        journal=Journal(Path(self.media.name)/'agent.sqlite3',str(self.agent.pk));self.addCleanup(journal.close)
        driver=Driver();engine=Engine(Adapter(),journal,driver,'Fake printer')
        engine.step();engine.step()
        self.job.refresh_from_db();self.assertIsNotNone(self.job.printed_at);self.assertEqual(driver.calls,1)

    def test_printer_failure_incident_is_stable_across_heartbeats(self):
        from sales.print_agents import snapshot
        body={'version':'1.0.0','printer_name':'Fake printer','printer_available':False}
        self.post('heartbeat',body);first=snapshot()[0]['problem_id']
        self.post('heartbeat',body);self.assertEqual(snapshot()[0]['problem_id'],first)
        self.connect();self.post('heartbeat',body)
        self.assertNotEqual(snapshot()[0]['problem_id'],first)
