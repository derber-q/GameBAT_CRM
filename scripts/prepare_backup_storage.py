"""Одноразовая подготовка выделенного Docker volume без доступа к рабочей БД.

Запускается в отдельном служебном контейнере. Прежние завершённые архивы
копируются с проверкой SHA-256; исходники, staging и неизвестные файлы не удаляются.
"""
import hashlib
import os
from pathlib import Path
import shutil
import uuid


def prepare(root=Path('/backup'), legacy=Path('/legacy')):
    root,legacy=Path(root),Path(legacy)
    if root.resolve()!=root or root.is_symlink() or legacy.resolve()!=legacy or legacy.is_symlink():
        raise ValueError('Недопустимое хранилище')
    root.mkdir(exist_ok=True)
    os.chown(root,10001,10001);os.chmod(root,0o700)
    copied=0
    def digest(path):
        with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
    for source in legacy.glob('*.backup'):
        try:identifier=str(uuid.UUID(source.stem))
        except ValueError:continue
        if source.name!=identifier+'.backup' or source.is_symlink() or not source.is_file() or source.stat().st_nlink!=1:
            raise ValueError('Недопустимый архив')
        target=root/source.name
        expected=digest(source)
        if target.exists():
            if target.is_symlink() or not target.is_file() or digest(target)!=expected:raise ValueError('Коллизия архивов')
            continue
        temporary=root/('.'+uuid.uuid4().hex+'.partial')
        with source.open('rb') as reader,temporary.open('xb') as writer:
            os.fchmod(writer.fileno(),0o600);shutil.copyfileobj(reader,writer,1024*1024)
            writer.flush();os.fsync(writer.fileno())
        if digest(temporary)!=expected:raise ValueError('Копия архива повреждена')
        os.chown(temporary,10001,10001)
        temporary.replace(target);copied+=1
    print('Backup storage ready; verified archives copied:',copied)


if __name__=='__main__':prepare()
