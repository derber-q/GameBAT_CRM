"""Локальный Unix socket для ограниченных заявок; журнал web-контейнеру недоступен."""
import json
import os
from pathlib import Path
import socket
import socketserver
import struct
import subprocess

from .store import UpdateError, sha


def grant(path, uid, rights):
    # ACL только для заранее настроенного host UID web-контейнера, без world-write.
    try:
        subprocess.run(['setfacl','-m',f'u:{int(uid)}:{rights}',str(path)],check=True,
                       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5)
    except (OSError, subprocess.SubprocessError):
        raise UpdateError('Не удалось настроить ACL канала обновлений.') from None


def submit(path, payload):
    path = Path(path)
    if not path.is_absolute() or path.resolve()!=path:
        raise UpdateError('Неверный путь канала менеджера.')
    data = json.dumps(payload).encode()+b'\n'
    if len(data)>4096:
        raise UpdateError('Слишком большая заявка.')
    try:
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
            client.settimeout(5)
            client.connect(str(path))
            client.sendall(data)
            with client.makefile('rb') as reader:
                result = json.loads(reader.readline(4097))
    except (OSError, ValueError, AttributeError):
        raise UpdateError('Менеджер обновлений недоступен. Заявка не подтверждена; обновите состояние.') from None
    if result.get('error'):
        raise UpdateError(result['error'])
    return result['id']


def request(store, payload):
    if not isinstance(payload,dict) or set(payload)!={'action','actor','request_id','target'}:
        raise UpdateError('Разрешены только фиксированные операции обновления.')
    if not str(payload['actor']).isdigit():
        raise UpdateError('Инициатор операции не указан.')
    action, target = payload['action'], payload['target']
    if action in ('install','rollback'):
        value = store.get('latest' if action=='install' else 'rollback',{})
        if not value.get('approved') or value.get('sha') != sha(target):
            raise UpdateError('Версия не допущена к установке.')
    elif action != 'check' or target:
        raise UpdateError('Разрешены только фиксированные операции обновления.')
    return store.enqueue(action,payload['actor'],payload['request_id'],target)


class Gateway(socketserver.UnixStreamServer if hasattr(socketserver,'UnixStreamServer') else object):
    def __init__(self,path,store,uid):
        self.store,self.uid = store,uid
        class Handler(socketserver.StreamRequestHandler):
            def handle(handler):
                try:
                    handler.request.settimeout(5)
                    _, peer, _ = struct.unpack('3i',handler.request.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
                    if peer != handler.server.uid:
                        raise UpdateError('Отправитель заявки не разрешён.')
                    data = handler.rfile.readline(4097)
                    if len(data)>4096 or not data.endswith(b'\n'):
                        raise UpdateError('Неверный формат заявки.')
                    value = {'id':request(handler.server.store,json.loads(data))}
                except UpdateError as error:
                    value = {'error':str(error)}
                except Exception:
                    value = {'error':'Заявка не принята. Обновите состояние менеджера.'}
                handler.wfile.write(json.dumps(value).encode()+b'\n')
        super().__init__(str(path),Handler)


def publish(root,store,uid):
    directory = root/'public'
    directory.mkdir(exist_ok=True,mode=0o700)
    grant(directory,uid,'rx')
    data = {key:store.get(key,{}) for key in ('heartbeat','current','latest','rollback','recovery_required')}
    data['history'] = store.operations()
    temporary = directory/'status.tmp'
    temporary.write_text(json.dumps(data),encoding='utf-8')
    grant(temporary,uid,'r')
    temporary.replace(directory/'status.json')
