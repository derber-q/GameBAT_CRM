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
        except HTTPError as exc:
            # Берём только код из фиксированного протокола, никогда HTML/traceback.
            code='backup_http_error'
            try:
                body=exc.read(4097)
                value=json.loads(body).get('error') if len(body)<=4096 else None
                if value in ('manual_request_forbidden','backup_disabled','recovery_not_configured',
                             'session_conflict','unauthorized','operation_blocked','database_busy','secure_connection_required'):
                    code=value
            except (ValueError,AttributeError):pass
            finally:exc.close()
            raise TransportError(code,exc.code) from None
        except (URLError,OSError,ValueError): raise TransportError('backup_connection_failed') from None

    def heartbeat(self):
        from . import VERSION
        return self.request('heartbeat/',{'version':VERSION})
    def status(self): return self.request('status/',method='GET')['jobs']
    def create(self,request_id): return self.request('create/',{'request_id':str(request_id)})
    def stream(self,offset,meta):
        headers={'If-Match':'"'+meta['sha256']+'"'}
        if offset: headers['Range']='bytes='+str(offset)+'-'
        return self.request('jobs/'+str(uuid.UUID(meta['id']))+'/download/',method='GET',stream=True,extra=headers)
    def confirm(self,meta):
        return self.request('jobs/'+str(uuid.UUID(meta['id']))+'/confirm/',{'size':meta['size'],'sha256':meta['sha256']})


def error_message(exc):
    messages={
        'manual_request_forbidden':'В CRM не разрешено создавать копии с этого компьютера. Откройте настройки устройства в CRM.',
        'backup_disabled':'Создание копий выключено в CRM. Откройте CRM → Резервное копирование и включите расписание.',
        'recovery_not_configured':'Не сохранён ключ восстановления. Нажмите «Настроить резервное копирование».',
        'session_conflict':'Этот профиль недавно работал в другом окне. Закройте второй экземпляр; подключение повторится автоматически.',
        'unauthorized':'Подключение отозвано или устарело. Подключите этот компьютер заново в настройках.',
        'database_busy':'CRM сейчас занята. Повторим подключение автоматически.',
        'secure_connection_required':'Для удалённой CRM нужен HTTPS. На этом компьютере используйте http://127.0.0.1:8000.',
        'operation_blocked':'CRM пока не разрешила создание копии. Проверьте ключ восстановления и настройки резервирования.',
        'backup_connection_failed':'Не удаётся связаться с CRM. Убедитесь, что сайт запущен; повторим подключение автоматически.'}
    return messages.get(getattr(exc,'code',''), 'Не удалось выполнить операцию. Подробности доступны в CRM; сохранённые копии не изменены.')
