"""Согласованный SQLite + стабильные файлы; публикация только после всех проверок."""
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import tempfile
import time
import uuid
import zipfile

from cryptography.fernet import Fernet, InvalidToken
from .crypto import encrypt, decrypt, public_id, BLOCK


def digest(path, check=lambda: None):
    with path.open('rb') as stream:
        result = hashlib.sha256()
        while block := stream.read(BLOCK):
            check(); result.update(block)
        return result.hexdigest()


def safe_name(value):
    path = PurePosixPath(value)
    if not value or '\\' in value or ':' in value or path.is_absolute() or any(p in ('', '.', '..') for p in value.split('/')):
        raise ValueError('Небезопасный путь архива.')
    return path


def inventory(root, check):
    root = Path(root)
    result = {}
    if root.is_symlink() or root.is_junction() or not root.is_dir():
        raise ValueError('Каталог файлов отсутствует или является ссылкой.')
    for path in root.rglob('*'):
        check()
        if path.is_symlink() or path.is_junction() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError('Ссылки в полном снимке запрещены.')
        if path.is_file():
            if path.stat().st_nlink != 1:
                raise ValueError('Жёсткие ссылки в снимке запрещены.')
            name = path.relative_to(root).as_posix()
            safe_name(name)
            result[name] = {'size': path.stat().st_size, 'sha256': digest(path, check)}
    return result


def copy_file(source, target, check):
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with source.open('rb') as reader, target.open('xb') as writer:
        os.chmod(target, 0o600)
        while block := reader.read(BLOCK):
            check()
            writer.write(block)


def file_stamps(root,check=lambda:None):
    """Версия файла: inode/device/size/mtime/ctime, без чтения большого payload.

    Нужна для короткой финальной сверки уже скопированного и хешированного
    набора. Смена любого файла/состава прекращает снимок, а не замалчивается.
    """
    root=Path(root);result={}
    if root.resolve()!=root.absolute() or not root.is_dir():raise ValueError('Небезопасный каталог снимка.')
    for path in root.rglob('*'):
        check()
        if path.is_symlink() or path.is_junction():raise ValueError('Ссылка в файлах снимка.')
        if path.is_file():
            stat=path.stat()
            if stat.st_nlink!=1:raise ValueError('Жёсткая ссылка в файлах снимка.')
            name=path.relative_to(root).as_posix();safe_name(name)
            result[name]=(stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns)
    return result


def _quote(value):
    return '"' + value.replace('"', '""') + '"'


def verify_database(database, media, secrets, file_columns, encrypted_columns, check=lambda:None,applications=None):
    with closing(sqlite3.connect(database.resolve().as_uri() + '?mode=ro&immutable=1', uri=True)) as con:
        con.set_progress_handler(lambda:check() or 0,10000)
        if con.execute('PRAGMA integrity_check').fetchall() != [('ok',)] or con.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Снимок SQLite не прошёл integrity/FK.')
        for table, column in file_columns:
            for (name,) in con.execute(f'SELECT {_quote(column)} FROM {_quote(table)}'):
                check()
                if name:
                    relative = safe_name(name)
                    path = media / relative
                    if not path.is_file() or not path.resolve().is_relative_to(media.resolve()):
                        raise ValueError('Отсутствует файл, указанный в снимке БД.')
        for table, column, key_name in encrypted_columns:
            for (value,) in con.execute(f'SELECT {_quote(column)} FROM {_quote(table)}'):
                check()
                if value:
                    try:
                        Fernet(secrets[key_name].encode()).decrypt(value.encode())
                    except (KeyError, InvalidToken, ValueError):
                        raise ValueError('Секрет восстановления не соответствует зашифрованной записи.') from None
        if con.execute("SELECT 1 FROM sqlite_master WHERE name='crm_backups_applicationartifact'").fetchone():
            for identifier,expected,size in con.execute('SELECT id,sha256,size FROM crm_backups_applicationartifact'):
                check()
                if applications is None:raise ValueError('В копии отсутствуют опубликованные программы.')
                path=applications/(str(uuid.UUID(identifier))+'.zip')
                if not path.is_file() or path.stat().st_size!=size or digest(path,check)!=expected:
                    raise ValueError('Опубликованная программа отсутствует или повреждена.')


def create_bundle(*, database, media, secrets_loader, metadata, public_key, destination,
                  file_columns=(), encrypted_columns=(), window_seconds=15, minimum_free_bytes=64 * 1024 * 1024,
                  phase=lambda value: None,extra_roots=None):
    database, media, destination = map(Path, (database, media, destination))
    if not database.is_file() or database.is_symlink() or database.stat().st_nlink != 1 or destination.exists():
        raise ValueError('Недопустимая БД или существующий архив.')
    public_id(public_key)
    extras={key:Path(value) for key,value in (extra_roots or {}).items()}
    if set(extras)-{'client_applications'}:raise ValueError('Неизвестный дополнительный каталог полного снимка.')
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if destination.parent.resolve().is_relative_to(media.resolve()):
        raise ValueError('Архив нельзя сохранять внутри медиа.')
    estimate = database.stat().st_size + sum(p.stat().st_size for p in media.rglob('*') if p.is_file())
    estimate+=sum(p.stat().st_size for root in extras.values() for p in root.rglob('*') if p.is_file())
    occupied=sum(p.stat().st_size for p in destination.parent.rglob('*') if p.is_file())
    if occupied+estimate*3>20*1024**3:
        raise OSError('Превышен лимит 20 ГиБ серверного временного хранилища.')
    if shutil.disk_usage(destination.parent).free < minimum_free_bytes + estimate * 3:
        raise OSError('Недостаточно места для безопасного полного снимка.')
    if window_seconds<=0:raise TimeoutError('Нулевое окно снимка.')
    deadline = None
    def check():
        if deadline is not None and time.monotonic() >= deadline:
            raise TimeoutError('Превышено окно согласованного снимка.')
    with tempfile.TemporaryDirectory(prefix='resource-snapshot-', dir=destination.parent) as tmp:
        stage = Path(tmp); os.chmod(stage, 0o700)
        if os.name=='nt':
            from local_agent.configuration import private_folder
            private_folder(stage)
        from .staging import mark
        mark(stage)
        payload = stage / 'payload'; payload.mkdir(mode=0o700)
        snapshot = payload / 'database.sqlite3'
        phase('staging')
        roots={'protected_media':media,**extras}
        stamps={key:file_stamps(root) for key,root in roots.items()}
        prepared={key:inventory(root,check) for key,root in roots.items()}
        # Медленное копирование выполняется без блокировки торговых записей.
        # Каталог staging приватный; его содержимое затем независимо проверяется.
        for key,entries in prepared.items():
            target=payload/key;target.mkdir(mode=0o700)
            for name in entries:copy_file(roots[key]/name,target/name,check)
            if entries!=inventory(target,check) or stamps[key]!=file_stamps(roots[key]):
                raise ValueError('Файлы изменились во время подготовки снимка.')
        # RESERVED блокирует всех SQLite-писателей, но позволяет отдельному reader
        # получить последнюю завершённую транзакцию и сделать Online Backup.
        with closing(sqlite3.connect(database, timeout=0.2)) as guard:
            guard.execute('BEGIN IMMEDIATE')
            try:
                frozen_start=time.monotonic();deadline=frozen_start+window_seconds
                started=datetime.now(timezone.utc).isoformat()
                check()
                phase('snapshot')
                secrets = secrets_loader()
                if any(stamps[key]!=file_stamps(root,check) for key,root in roots.items()):
                    raise ValueError('Набор файлов изменился перед снимком БД.')
                with closing(sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True)) as reader, closing(sqlite3.connect(snapshot)) as output:
                    reader.backup(output, pages=256, progress=lambda *_: check(), sleep=0.01)
                snapshot.chmod(0o600)
                with closing(sqlite3.connect(snapshot)) as captured:
                    for table in ('sales_marketprintjob','sales_avitoshippingprintjob'):
                        if not captured.execute('SELECT 1 FROM sqlite_master WHERE name=?',(table,)).fetchone():continue
                        fields={row[1] for row in captured.execute(f'PRAGMA table_info({table})')}
                        active="state IN ('agent_claimed','agent_printing','agent_spooled','printing')"
                        if 'lease' in fields:active+=" OR (state='pending' AND lease IS NOT NULL)"
                        if captured.execute(f'SELECT 1 FROM {table} WHERE '+active+' LIMIT 1').fetchone():
                            raise ValueError('Снимок отложен: есть активная физическая печать.')
                if any(stamps[key]!=file_stamps(root,check) for key,root in roots.items()) or secrets != secrets_loader():
                    raise ValueError('Файлы или ключи изменились во время согласованного снимка.')
                with closing(sqlite3.connect(snapshot)) as captured:
                    if captured.execute("SELECT 1 FROM sqlite_master WHERE name='django_migrations'").fetchone():
                        migrations = list(captured.execute('SELECT app,name FROM django_migrations ORDER BY app,name'))
                    else: migrations = []
                check()
                recovery = payload / 'recovery'; recovery.mkdir(mode=0o700)
                (recovery / 'secrets.json').write_text(json.dumps(secrets, ensure_ascii=False), encoding='utf-8')
                (recovery / 'secrets.json').chmod(0o600)
                window_elapsed=time.monotonic()-frozen_start;check()
            finally:
                guard.rollback()
                deadline=None
        # Долгая упаковка, шифрование и последующая передача уже не держат БД.
        phase('checking')
        verify_database(snapshot,payload/'protected_media',secrets,file_columns,encrypted_columns,
            applications=payload/'client_applications')
        phase('encrypting')
        files = inventory(payload, lambda: None)
        manifest = {'format': 1, 'database_engine': 'sqlite', 'snapshot_at': started,
                    'snapshot_completed_at': datetime.now(timezone.utc).isoformat(),
                    'metadata': metadata, 'key_id': public_id(public_key), 'files': files,
                    'file_columns': list(file_columns), 'encrypted_columns': list(encrypted_columns),
                    'integrity_check': 'ok', 'foreign_key_errors': 0, 'migrations': migrations,
                    'write_window_seconds':window_elapsed}
        plain = stage / 'payload.zip'
        with zipfile.ZipFile(plain, 'w', zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
            archive.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False))
            for name in files:
                archive.write(payload / name, name)
        encrypted = stage / 'encrypted.partial'
        with plain.open('rb') as source, encrypted.open('xb') as target:
            os.chmod(encrypted, 0o600)
            encrypt(source, target, public_key)
            target.flush(); os.fsync(target.fileno())
        result = {'sha256': digest(encrypted), 'size': encrypted.stat().st_size,
                  'key_id': manifest['key_id'], 'snapshot_at': started, 'manifest': manifest}
        # Не перезаписываем существующий UUID; оба пути на одной файловой системе.
        with destination.open('xb') as reserved:
            os.chmod(destination, 0o600)
        try:
            os.replace(encrypted, destination)
        except OSError:
            destination.unlink()
            raise
        return result


def restore_bundle(archive_path, destination, private_pem, password, *, maximum_bytes=100 * 1024**3):
    """Только новый каталог. Не запускает Django, миграции или интеграции."""
    destination = Path(destination)
    if destination.exists() or destination.is_symlink() or destination.is_junction():
        raise ValueError('Восстановление допускается только в новый отдельный каталог.')
    with tempfile.TemporaryDirectory(prefix='resource-restore-', dir=destination.parent) as tmp:
        stage = Path(tmp); os.chmod(stage, 0o700)
        if os.name=='nt':
            from local_agent.configuration import private_folder
            private_folder(stage)
        verified = stage / 'verified.zip'
        with Path(archive_path).open('rb') as source, verified.open('xb') as target:
            os.chmod(verified, 0o600)
            header = decrypt(source, target, private_pem, password)
        payload = stage / 'payload'; payload.mkdir(mode=0o700)
        with zipfile.ZipFile(verified) as archive:
            infos = archive.infolist()
            names = [i.filename for i in infos]
            if len(names) != len(set(names)) or sum(i.file_size for i in infos) > maximum_bytes:
                raise ValueError('Превышен лимит или повторены имена архива.')
            if archive.getinfo('manifest.json').file_size > 16 * 1024**2:
                raise ValueError('Манифест слишком большой.')
            manifest = json.loads(archive.read('manifest.json'))
            if manifest['format'] != 1 or manifest['key_id'] != header['key_id'] or manifest['database_engine'] != 'sqlite':
                raise ValueError('Несовместимый формат восстановления.')
            if set(names) != set(manifest['files']) | {'manifest.json'}:
                raise ValueError('Состав не совпадает с манифестом.')
            for name, expected in manifest['files'].items():
                safe_name(name)
                if archive.getinfo(name).file_size != expected['size']:
                    raise ValueError('Размер файла не совпадает.')
                path = payload / name
                path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                with archive.open(name) as source, path.open('xb') as target:
                    os.chmod(path, 0o600)
                    shutil.copyfileobj(source, target, BLOCK)
                if digest(path) != expected['sha256']:
                    raise ValueError('Контрольная сумма файла не совпадает.')
        secrets = json.loads((payload / 'recovery/secrets.json').read_text(encoding='utf-8'))
        verify_database(payload / 'database.sqlite3', payload / 'protected_media', secrets,
                        manifest['file_columns'], manifest['encrypted_columns'],applications=payload/'client_applications')
        (payload / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        destination.mkdir(mode=0o700)  # Эксклюзивное резервирование, не замена каталога пользователя.
        for path in payload.iterdir():
            path.rename(destination / path.name)
        return manifest
