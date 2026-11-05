"""Блоки 1 MiB, неизменяемый UUID/ETag, rename после проверки. Очистка по журналу."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import uuid

BLOCK=1024*1024


def digest(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream,'sha256').hexdigest()


def archive_folder(folder):
    folder=Path(folder).absolute()
    if folder.resolve()!=folder or folder.is_symlink() or folder.is_junction():
        raise ValueError('Папка архивов не должна содержать ссылки.')
    folder.mkdir(parents=True,exist_ok=True)
    return folder


def _regular(path,folder):
    return path.parent==folder and path.is_file() and not path.is_symlink() and path.resolve()==path.absolute() and path.stat().st_nlink==1


def download(meta,folder,journal,open_stream,*,minimum_free_bytes=512*1024**2,progress=lambda current,total:None):
    folder=archive_folder(folder)
    identifier=str(uuid.UUID(meta['id']))
    if identifier!=meta['id'] or type(meta['size']) is not int or meta['size']<=0 or not re.fullmatch('[a-f0-9]{64}',meta['sha256']):
        raise ValueError('Некорректные метаданные архива.')
    existing=journal.get(identifier)
    if existing:
        previous=json.loads(existing['meta'])
        if any(previous.get(k)!=meta.get(k) for k in ('id','size','sha256','environment_id')):
            raise ValueError('Архив изменился: продолжение запрещено.')
        if existing['state']=='corrupt':
            raise ValueError('Повреждённая копия требует явного решения пользователя.')
        path=Path(existing['path'])
        if existing['state']=='publishing' and _regular(path,folder) and path.stat().st_size==meta['size'] and digest(path)==meta['sha256']:
            journal.put(meta,path,'verified');return path
        if existing['state']=='publishing' and _regular(path,folder) and path.stat().st_size==0 and identifier in path.name:
            path.unlink()  # Только зарегистрированный пустой файл резервирования rename.
        if existing['state']=='verified':
            if _regular(path,folder) and path.stat().st_size==meta['size'] and digest(path)==meta['sha256']: return path
            raise ValueError('Сохранённая копия повреждена или перемещена.')
    partial=folder/(identifier+'.partial')
    if partial.exists() and not _regular(partial,folder): raise ValueError('Небезопасный частичный файл.')
    if partial.exists() and not existing: raise ValueError('Частичный файл не принадлежит журналу.')
    offset=partial.stat().st_size if partial.exists() else 0
    if offset>meta['size']: raise ValueError('Частичный файл слишком большой.')
    if shutil.disk_usage(folder).free<minimum_free_bytes+meta['size']-offset:
        raise OSError('Недостаточно свободного места.')
    journal.put(meta,partial,'downloading')
    publishing=False
    try:
        if offset<meta['size']:
            with open_stream(offset,meta) as response:
                expected_status=206 if offset else 200
                if response.status!=expected_status or response.headers.get('ETag')!='"'+meta['sha256']+'"':
                    raise ValueError('Сервер вернул другой архив.')
                if int(response.headers.get('Content-Length','-1'))!=meta['size']-offset:
                    raise ValueError('Размер ответа не совпадает.')
                if offset and response.headers.get('Content-Range')!=f"bytes {offset}-{meta['size']-1}/{meta['size']}":
                    raise ValueError('Неправильный диапазон продолжения.')
                with partial.open('ab' if partial.exists() else 'xb') as stream:
                    os.chmod(partial,0o600)
                    while block:=response.read(BLOCK):
                        if offset+len(block)>meta['size']: raise ValueError('Лишние данные ответа.')
                        if shutil.disk_usage(folder).free<minimum_free_bytes+len(block): raise OSError('Диск заполнен.')
                        stream.write(block); offset+=len(block); progress(offset,meta['size'])
                    stream.flush();os.fsync(stream.fileno())
        journal.put(meta,partial,'checking')
        if offset!=meta['size'] or digest(partial)!=meta['sha256']: raise ValueError('SHA-256/размер не совпадает.')
        date=datetime.fromisoformat(meta['snapshot_at']).strftime('%Y-%m-%d_%H-%M-%S')
        version=meta.get('version','')[:7]
        if not re.fullmatch('[a-f0-9]{7}',version): version='unknown'
        target=folder/f'ReSOURCE_Backup_{date}_{version}_{identifier}.backup'
        if target.exists(): raise ValueError('Готовый файл уже существует.')
        # После сбоя между rename/журналом целый файл проверяется при следующем
        # запуске отдельно; автоматическая перезапись запрещена.
        journal.put(meta,target,'publishing');publishing=True
        with target.open('xb'): pass
        os.replace(partial,target)
        journal.put(meta,target,'verified')
        return target
    except Exception as exc:
        if not publishing:journal.put(meta,partial,'error',type(exc).__name__)
        raise


def verify_record(record,folder):
    path=Path(record['path']);meta=json.loads(record['meta']);folder=archive_folder(folder)
    return _regular(path,folder) and path.stat().st_size==meta['size'] and digest(path)==meta['sha256']


def cleanup(folder,journal,*,keep=7,days=0,weekly=0,enabled=False):
    if not enabled: return []
    folder=archive_folder(folder);rows=journal.rows()
    # Не сокращаем исправную историю после неудачной или ещё активной загрузки.
    if not rows or rows[0]['state']!='verified': return []
    verified=sorted((r for r in rows if r['state']=='verified'),key=lambda r:r['verified_at'],reverse=True)
    if not verified: return []
    healthy=next((row for row in verified if verify_record(row,folder)),None)
    if healthy is None:return []
    survivors={healthy['id']}
    daily=[r for r in verified if json.loads(r['meta']).get('kind')=='daily']
    survivors.update(r['id'] for r in daily[:max(1,keep)])
    weeks=set()
    for row in daily:
        week=datetime.fromisoformat(row['verified_at']).isocalendar()[:2]
        if week not in weeks and len(weeks)<weekly:
            survivors.add(row['id']);weeks.add(week)
    cutoff=datetime.now(timezone.utc)-timedelta(days=max(0,days))
    removed=[]
    for row in verified:
        if row['id'] in survivors or row['pinned'] or datetime.fromisoformat(row['verified_at'])>cutoff: continue
        if verify_record(row,folder):
            path=Path(row['path']);path.unlink()
            journal.put(json.loads(row['meta']),path,'deleted');removed.append(row['id'])
    return removed
