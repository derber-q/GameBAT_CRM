"""Упаковка расширения и неизменяемая публикация проверенных файлов, не в HTTP GET."""
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import zipfile
from django.conf import settings
from django.db import transaction
from core.external_policy import require_live_operation
from .devices import administrator
from .jobs import audit,locked_config
from .models import ApplicationArtifact
from .snapshot import safe_name,digest


def artifact_root():
    require_live_operation('application_artifacts')
    root=Path(getattr(settings,'CRM_APP_ARTIFACT_ROOT',settings.BASE_DIR/'.local-app-artifacts')).absolute()
    if root.resolve()!=root or root.is_symlink() or root.is_junction():raise ValueError('Небезопасное хранилище сборок.')
    root.mkdir(parents=True,exist_ok=True,mode=0o700)
    return root


def artifact_path(artifact):return artifact_root()/(str(artifact.pk)+'.zip')


def extension_references(manifest):
    resources=[]
    if manifest.get('background',{}).get('service_worker'):resources.append(manifest['background']['service_worker'])
    resources+=manifest.get('background',{}).get('scripts',[])
    resources+=list(manifest.get('icons',{}).values())
    for entry in manifest.get('content_scripts',[]):resources+=entry.get('js',[])+entry.get('css',[])
    for name in ('action','browser_action','page_action'):
        entry=manifest.get(name,{})
        if entry.get('default_popup'):resources.append(entry['default_popup'])
        icon=entry.get('default_icon',{})
        resources+=list(icon.values()) if isinstance(icon,dict) else [icon]
    return resources


def package_extension(source,target):
    source,target=Path(source),Path(target)
    if target.exists() or source.is_symlink() or source.resolve()!=source.absolute():raise ValueError('Нужны проверенный каталог и новый ZIP.')
    files=[]
    for path in source.rglob('*'):
        if path.is_symlink() or path.is_junction():raise ValueError('Ссылки в расширении запрещены.')
        if not path.is_file():continue
        if path.name=='README.md' or path.name.startswith('test_') and path.suffix=='.cjs':continue
        if path.name.startswith('.') or path.suffix not in ('.json','.js','.css','.html','.png','.svg','.ico'):
            raise ValueError('Посторонний файл в каталоге расширения.')
        if path.suffix=='.json' and path.name!='manifest.json':raise ValueError('Неизвестный JSON-файл расширения.')
        files.append(path)
    manifest=json.loads((source/'manifest.json').read_text('utf-8'))
    for reference in extension_references(manifest):
        safe_name(reference)
        if source/reference not in files:raise ValueError('Ресурс manifest отсутствует.')
    target.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(target,'x',zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files):
            name=path.relative_to(source).as_posix();safe_name(name)
            info=zipfile.ZipInfo(name,date_time=(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
            archive.writestr(info,path.read_bytes())
    validate('opera',target)
    return manifest['version']


def validate(kind,path):
    if path.stat().st_size>256*1024**2:raise ValueError('Сборка слишком большая.')
    with zipfile.ZipFile(path) as archive:
        infos=archive.infolist();names=[i.filename for i in infos]
        if len(names)!=len(set(names)) or len(names)>50000 or sum(i.file_size for i in infos)>2*1024**3:raise ValueError('Некорректный состав ZIP.')
        for name in names:
            safe_name(name)
            if any(part.startswith('.') for part in Path(name).parts) or name.endswith(('.backup','.sqlite3','.pem','.key','.env')):
                raise ValueError('В ZIP есть приватный файл.')
        if kind=='opera':
            metadata=json.loads(archive.read('manifest.json'))
            if metadata['manifest_version']!=3 or not re.fullmatch(r'\d+(?:\.\d+){1,3}',metadata['version']):raise ValueError('Неверный manifest.')
            for reference in extension_references(metadata):
                safe_name(reference)
                if reference not in names:raise ValueError('Нет ресурса manifest.')
            if any(name.startswith('test_') or name.endswith('.cjs') for name in names):raise ValueError('Тесты в установочном ZIP.')
            return {'version':metadata['version'],'built_at':datetime.now(timezone.utc).isoformat(),'platform':'Opera GX / Chromium',
                    'name':metadata['name'],'tested':True}
        if kind!='local_agent':raise ValueError('Неизвестная программа.')
        if archive.getinfo('portable-manifest.json').file_size>8*1024**2:raise ValueError('Манифест сборки слишком большой.')
        metadata=json.loads(archive.read('portable-manifest.json'))
        if metadata.get('tested_on_windows') is not True or metadata.get('self_test',{}).get('ok') is not True:
            raise ValueError('Нет подтверждённой проверки Windows-сборки.')
        if set(names)!=set(metadata['files'])|{'portable-manifest.json'}:raise ValueError('Состав сборки изменён.')
        if not archive.read('ReSOURCE Local Agent.exe')[:2]==b'MZ':raise ValueError('Нет Windows EXE.')
        for name,expected in metadata['files'].items():
            with archive.open(name) as stream:
                if hashlib.file_digest(stream,'sha256').hexdigest()!=expected:raise ValueError('Хеш сборки не совпадает.')
        return {key:metadata[key] for key in ('version','platform','built_at','signed','tested_on_windows','self_test')}


def publish(kind,path,actor,*,notes=''):
    require_live_operation('publish_client_application');administrator(actor)
    path=Path(path);metadata=validate(kind,path)
    artifact=ApplicationArtifact(kind=kind,version=metadata['version'],sha256=digest(path),size=path.stat().st_size,
        metadata=metadata,notes=notes,published_by=actor)
    target=artifact_path(artifact)
    with path.open('rb') as source,target.open('xb') as dest:
        os.chmod(target,0o600);shutil.copyfileobj(source,dest,1024*1024);dest.flush();os.fsync(dest.fileno())
    if digest(target)!=artifact.sha256:raise ValueError('Копирование сборки не подтверждено.')
    with transaction.atomic():
        locked_config()
        for previous in ApplicationArtifact.objects.filter(kind=kind,current=True):
            previous.current=False;previous.save(update_fields=['current'])
        artifact.save()
        audit('application_published',actor=actor,kind=kind,version=artifact.version,sha256=artifact.sha256)
    return artifact
