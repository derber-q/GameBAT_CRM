"""Очистка только помеченных приватных временных каталогов своего хранилища."""
from datetime import datetime,timezone,timedelta
import json
from pathlib import Path
import shutil
import uuid

MARKER='.resource-backup-stage.json'


def mark(path):
    value={'kind':'resource-backup-stage-v1','operation':str(uuid.uuid4()),
        'created_at':datetime.now(timezone.utc).isoformat(),'folder':path.name}
    with (path/MARKER).open('x',encoding='utf-8') as stream:json.dump(value,stream)
    (path/MARKER).chmod(0o600)


def expire(root,*,now=None,hours=24):
    root=Path(root).absolute()
    if root.resolve()!=root or root.is_symlink() or root.is_junction():raise ValueError('Небезопасное хранилище staging.')
    cutoff=(now or datetime.now(timezone.utc))-timedelta(hours=max(1,hours));removed=[]
    for path in root.iterdir():
        if not path.name.startswith('resource-snapshot-') or not path.is_dir() or path.is_symlink() or path.is_junction():continue
        if path.resolve().parent!=root:continue
        marker=path/MARKER
        try:
            if marker.is_symlink() or marker.stat().st_nlink!=1 or marker.stat().st_size>1024:continue
            value=json.loads(marker.read_text(encoding='utf-8'))
            uuid.UUID(value['operation'])
            if value['kind']!='resource-backup-stage-v1' or value['folder']!=path.name:continue
            if datetime.fromisoformat(value['created_at'])>cutoff:continue
        except (OSError,ValueError,KeyError,TypeError):continue
        # Root приватен для исполнителя. Проверяем дерево до рекурсивного
        # удаления, чтобы чужая ссылка не стала новым корнем операции.
        if any(p.is_symlink() or p.is_junction() or not p.resolve().is_relative_to(path.resolve()) for p in path.rglob('*')):continue
        shutil.rmtree(path);removed.append(path.name)
    return removed
