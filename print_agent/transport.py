"""Закреплённый сервер, проверяемый TLS и запрет перенаправлений с Bearer-токеном."""
import json
import ssl
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, ProxyHandler, HTTPSHandler, HTTPRedirectHandler
import uuid

MAX_PDF = 30*1024*1024


class TransportError(Exception):
    def __init__(self, code, status=0):
        self.code, self.status = code, status


def server_origin(value):
    parsed=urlsplit(value)
    if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('','/'):
        raise ValueError('Нужен origin CRM без пути, логина, query и fragment.')
    if parsed.scheme!='https' and not (parsed.scheme=='http' and parsed.hostname in ('localhost','127.0.0.1','::1')):
        raise ValueError('Удалённый сервер требует HTTPS. HTTP разрешён только на loopback.')
    if not parsed.hostname:
        raise ValueError('Не задан сервер CRM.')
    return value.rstrip('/')


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise TransportError('redirect_refused')


class API:
    def __init__(self, config, instance):
        self.origin=server_origin(config['server_url'])
        self.headers={'Authorization':'Bearer '+config['token'],'X-Print-Agent':str(uuid.UUID(config['agent_id'])),
                      'X-Print-Session':str(instance),'X-Print-Protocol':'1'}
        self.opener=build_opener(ProxyHandler({}),HTTPSHandler(context=ssl.create_default_context()),NoRedirect())

    def request(self,path,data=None,pdf=False):
        request=Request(self.origin+'/crm/print-agent/'+path,
            data=None if pdf else json.dumps(data or {}).encode(),
            headers={**self.headers,'Content-Type':'application/json','Accept':'application/pdf' if pdf else 'application/json'})
        try:
            with self.opener.open(request,timeout=20) as response:
                limit=MAX_PDF if pdf else 16384
                if int(response.headers.get('Content-Length',0))>limit:
                    raise TransportError('response_too_large')
                body=response.read(limit+1)
                if len(body)>limit:
                    raise TransportError('response_too_large')
                if pdf:
                    if response.headers.get_content_type()!='application/pdf':
                        raise TransportError('invalid_pdf_response')
                    return body
                result=json.loads(body)
                if not isinstance(result,dict):
                    raise TransportError('invalid_response')
                return result
        except HTTPError as error:
            raise TransportError('http_error',error.code) from None
        except (OSError,URLError,ValueError):
            raise TransportError('connection_failed') from None

    def heartbeat(self, data):
        return self.request('heartbeat/',data)

    def claim(self):
        return self.request('claim/').get('job')

    def document(self, job):
        return self.request('jobs/'+str(uuid.UUID(job['id']))+'/document/',pdf=True)

    def result(self,job,state,spool_job_id=None):
        data={'claim':job['claim'],'sha256':job['sha256'],'state':state}
        if spool_job_id is not None:
            data['spool_job_id']=spool_job_id
        return self.request('jobs/'+str(uuid.UUID(job['id']))+'/result/',data)
