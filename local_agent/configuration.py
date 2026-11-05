"""Профили и DPAPI CurrentUser: исполняемые файлы не содержат настроек/токенов."""
import base64
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import uuid
from print_agent.transport import server_origin


def app_root():
    return Path(os.environ.get('LOCALAPPDATA',Path.home()/'.local/share'))/'ReSOURCE/LocalAgent'


def profile_folder(name):
    if not re.fullmatch('[A-Za-z0-9_-]{1,64}',name): raise ValueError('Неверное имя профиля.')
    return app_root()/'profiles'/name


def private_folder(path):
    path=Path(path).absolute()
    if path.resolve()!=path or path.is_symlink() or path.is_junction(): raise ValueError('Ссылки в каталоге настроек запрещены.')
    path.mkdir(parents=True,exist_ok=True,mode=0o700)
    if os.name=='nt':
        import win32api,win32security,win32con
        token=win32security.OpenProcessToken(win32api.GetCurrentProcess(),win32con.TOKEN_QUERY)
        try: sid=win32security.ConvertSidToStringSid(win32security.GetTokenInformation(token,win32security.TokenUser)[0])
        finally: token.Close()
        subprocess.run(['icacls',str(path),'/inheritance:r','/grant:r',f'*{sid}:(OI)(CI)F',
            '/grant:r','*S-1-5-18:(OI)(CI)F'],check=True,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
    return path


def protect(value):
    import win32crypt
    return base64.b64encode(win32crypt.CryptProtectData(value.encode(),'ReSOURCE Local Agent',None,None,None,0)).decode()


def private_file(path):
    """Не меняет ACL выбранного пользователем родительского каталога."""
    path=Path(path);path.chmod(0o600)
    if os.name=='nt':
        import win32api,win32security,win32con
        token=win32security.OpenProcessToken(win32api.GetCurrentProcess(),win32con.TOKEN_QUERY)
        try:sid=win32security.GetTokenInformation(token,win32security.TokenUser)[0]
        finally:token.Close()
        acl=win32security.ACL();acl.AddAccessAllowedAce(win32security.ACL_REVISION,win32con.GENERIC_ALL,sid)
        system=win32security.CreateWellKnownSid(win32security.WinLocalSystemSid,None)
        acl.AddAccessAllowedAce(win32security.ACL_REVISION,win32con.GENERIC_ALL,system)
        descriptor=win32security.SECURITY_DESCRIPTOR();descriptor.SetSecurityDescriptorDacl(1,acl,0)
        win32security.SetFileSecurity(str(path),win32security.DACL_SECURITY_INFORMATION|
            win32security.PROTECTED_DACL_SECURITY_INFORMATION,descriptor)


def unprotect(value):
    import win32crypt
    return win32crypt.CryptUnprotectData(base64.b64decode(value),None,None,None,0)[1].decode()


def initial():
    return {'server_url':'http://127.0.0.1:8000','name':'ReSOURCE Local Agent',
        'device_id':str(uuid.uuid4()),'agent_id':str(uuid.uuid4()),'printer_name':'',
        'print_enabled':False,'backup_enabled':False,'legacy_config':'',
        'backup_folder':str(Path.home()/'ReSOURCE/Backups'),'keep':7,'days':0,'weekly':0,
        'cleanup_enabled':False,'minimum_free_mb':512,'autostart':False}


def load(folder):
    path=folder/'settings.json'
    if not path.exists(): return initial()
    data=json.loads(path.read_text(encoding='utf-8'))
    for name in ('print_token','backup_token'):
        if name in data: data[name]=unprotect(data[name])
    return data


def save(folder,data):
    private_folder(folder)
    data=dict(data); data['server_url']=server_origin(data['server_url'])
    for name in ('print_token','backup_token'):
        if data.get(name): data[name]=protect(data[name])
    temporary=folder/'settings.tmp'
    with temporary.open('w',encoding='utf-8') as stream:
        json.dump(data,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
    temporary.replace(folder/'settings.json')


def new_secret(): return secrets.token_urlsafe(48)
