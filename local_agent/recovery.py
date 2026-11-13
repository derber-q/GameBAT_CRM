"""Пробное восстановление только в новый локальный каталог, без запуска CRM."""
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid

from .configuration import private_folder
from .downloads import verify_record


def verify_restore(record, config, profile, password):
    if record['state']!='verified' or not verify_record(record,config['backup_folder']):
        raise ValueError('Сначала нужна скачанная и проверенная копия.')
    key=Path(config['recovery_key_path'])
    if key.is_symlink() or not key.is_file():raise ValueError('Не найден ключ восстановления.')
    parent=private_folder(Path(profile)/'restore_checks')
    destination=parent/uuid.uuid4().hex
    from crm_backups.snapshot import restore_bundle
    manifest=restore_bundle(Path(record['path']),destination,key.read_bytes(),password.encode('utf-8'))
    # restore_bundle проверяет GCM, все файлы, SQLite integrity/FK и соответствие
    # ключей зашифрованным полям. Ни сайт, ни worker этой копии не запускаются.
    proof={'archive_id':record['id'],'verified_at':datetime.now(timezone.utc).isoformat(),
           'destination':str(destination),'file_count':len(manifest['files']),
           'database_integrity':'ok','foreign_keys':'ok','files_and_keys':'ok'}
    target=Path(profile)/'last-restore-check.json'
    temporary=target.with_suffix('.tmp')
    temporary.write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
    temporary.replace(target)
    return proof
