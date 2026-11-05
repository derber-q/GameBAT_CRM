"""Клиент архива: отдельные заголовки, без cookie, redirects и выключения TLS."""
import json
import ssl
import uuid
from urllib.request import Request, build_opener, ProxyHandler, HTTPSHandler
from urllib.error import HTTPError, URLError
from print_agent.transport import server_origin, NoRedirect, TransportError


class BackupAPI:
    def __init__(self,config,session):
        self.origin=server_origin(config['server_url'])
        self.headers={'Authorization':'Bearer '+config.get('backup_token',''),
            'X-Backup-Device':str(uuid.UUID(config['device_id'])),'X-Backup-Session':str(session)}
        self.opener=build_opener(ProxyHandler({}),HTTPSHandler(context=ssl.create_default_context()),NoRedirect())

    def request(self,path,data=None,*,method='POST',stream=False,extra=None):
        headers={**self.headers,'Content-Type':'application/json',**(extra or {})}
        request=Request(self.origin+'/crm/backups/api/'+path,
            data=json.dumps(data or {}).encode() if method=='POST' else None,headers=headers,method=method)
        try:
            response=self.opener.open(request,timeout=20)
            if stream: return response
            with response:
                body=response.read(65537)
                if len(body)>65536: raise TransportError('response_too_large')
                result=json.loads(body)
                if not isinstance(result,dict):raise ValueError
                return result
        except HTTPError as exc: raise TransportError('backup_http_error',exc.code) from None
        except (URLError,OSError,ValueError): raise TransportError('backup_connection_failed') from None

    def heartbeat(self): return self.request('heartbeat/',{'version':'1.0.0'})
    def status(self): return self.request('status/',method='GET')['jobs']
    def create(self,request_id): return self.request('create/',{'request_id':str(request_id)})
    def stream(self,offset,meta):
        headers={'If-Match':'"'+meta['sha256']+'"'}
        if offset: headers['Range']='bytes='+str(offset)+'-'
        return self.request('jobs/'+str(uuid.UUID(meta['id']))+'/download/',method='GET',stream=True,extra=headers)
    def confirm(self,meta):
        return self.request('jobs/'+str(uuid.UUID(meta['id']))+'/confirm/',{'size':meta['size'],'sha256':meta['sha256']})
