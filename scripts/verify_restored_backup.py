"""Пробное восстановление проверяется offline/read-only, без сайта и worker.

Аргумент — новый каталог, созданный restore_crm_backup. Рабочая БД и рабочие
fallback-ключи CRM не открываются. Приватный ключ владельца здесь не требуется:
архив уже должен быть аутентифицирован и распакован командой восстановления.
"""
import argparse
import json
import os
from pathlib import Path
import socket
import sys

ROOT=Path(__file__).resolve().parent.parent


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path)
    args=parser.parse_args();directory=args.directory.absolute()
    if directory.resolve()!=directory or directory.is_symlink() or directory.is_junction():raise ValueError('Ссылки запрещены.')
    database=directory/'database.sqlite3'
    if not database.is_file() or database.stat().st_nlink!=1 or ((ROOT/'db.sqlite3').exists() and database.samefile(ROOT/'db.sqlite3')):
        raise ValueError('Нужна отдельная восстановленная SQLite, не рабочая БД.')
    # Эта команда никогда не запускает сайт и не получает рабочее окружение.
    sys.path.insert(0,str(ROOT));os.environ['DJANGO_SETTINGS_MODULE']='deployment.ci_sqlite_settings'
    from django.conf import settings
    settings.DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3',
        'NAME':database.as_uri()+'?mode=ro&immutable=1','OPTIONS':{'uri':True}}}
    settings.MEDIA_ROOT=directory/'protected_media'
    def blocked(*args,**kwargs):raise RuntimeError('Сеть запрещена при проверке восстановления.')
    socket.create_connection=socket.getaddrinfo=blocked
    socket.socket.connect=socket.socket.connect_ex=blocked
    import django
    django.setup()
    from crm_backups.snapshot import verify_database,digest,safe_name
    manifest=json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('format')!=1:raise ValueError('Несовместимый манифест.')
    for name,value in manifest['files'].items():
        safe_name(name);path=directory/name
        if path.resolve()!=path or path.stat().st_size!=value['size'] or digest(path)!=value['sha256']:
            raise ValueError('Восстановленный файл изменён.')
    secrets=json.loads((directory/'recovery/secrets.json').read_text(encoding='utf-8'))
    verify_database(database,settings.MEDIA_ROOT,secrets,manifest['file_columns'],manifest['encrypted_columns'],applications=directory/'client_applications')
    from django.core.management import call_command
    call_command('verify_inventory');call_command('verify_cash');call_command('migrate',check=True)
    print('Восстановленная CRM проверена: файлы, ключи, integrity/FK, склад, касса и схема. Сеть отключена, БД read-only.')


if __name__=='__main__':main()
