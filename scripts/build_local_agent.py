"""Воспроизводимая Windows-сборка из allowlist, без поиска Django-проекта и БД."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))


def build(target):
    if sys.platform!='win32':raise ValueError('Windows-сборку нужно выполнять на Windows.')
    target=target.resolve()
    if target.exists() or not target.is_relative_to(ROOT/'outputs') or target==ROOT/'outputs':
        raise ValueError('Нужен новый отдельный каталог внутри outputs.')
    target.mkdir(parents=True)
    source=target/'source';source.mkdir()
    files=[]
    for package in ('local_agent','print_agent'):
        files += [p for p in (ROOT/package).glob('*.py') if not p.name.startswith('test_')]
    files += [ROOT/name for name in ('crm_backups/__init__.py','crm_backups/crypto.py',
        'core/__init__.py','core/external_policy.py','sales/__init__.py','sales/label_printing.py')]
    for path in files:
        dest=source/path.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest)
    (source/'launch.py').write_text('from local_agent.__main__ import main\nif __name__ == "__main__": main()\n',encoding='utf-8')
    hooks=target/'hooks';hooks.mkdir()
    # Стандартный hook-django ищет manage.py и копирует db.*. Здесь только
    # библиотека Django для существующего драйвера; проекта/ключей в сборке нет.
    (hooks/'hook-django.py').write_text('from PyInstaller.utils.hooks import collect_all\ndatas,binaries,hiddenimports=collect_all("django",on_error="ignore")\n',encoding='utf-8')
    env=dict(os.environ);env.pop('DJANGO_SETTINGS_MODULE',None)
    command=[sys.executable,'-m','PyInstaller','--noconfirm','--onedir','--windowed',
        '--name','ReSOURCE Local Agent','--distpath',str(target/'dist'),'--workpath',str(target/'work'),
        '--specpath',str(target),'--additional-hooks-dir',str(hooks),'--hidden-import','win32timezone',
        '--hidden-import','pystray._win32','--exclude-module','GameBAT_CRM','--exclude-module','crm_backups.models',str(source/'launch.py')]
    subprocess.run(command,cwd=source,env=env,check=True)
    folder=target/'dist/ReSOURCE Local Agent'
    shutil.copy2(ROOT/'local_agent/README.md',folder/'README.md')
    # Испытываем отдельную копию сборки вне Git-репозитория, без исходников и
    # системного Python в PATH. Только искусственные данные, без реальной печати.
    with tempfile.TemporaryDirectory(prefix='resource-exe-check-') as tmp:
        separate=Path(tmp)/'program';shutil.copytree(folder,separate)
        result_dir=Path(tmp)/'self-test'
        subprocess.run([str(separate/'ReSOURCE Local Agent.exe'),'--self-test',str(result_dir)],
            cwd=separate,env={**env,'PATH':os.environ.get('SystemRoot',r'C:\Windows')+r'\System32'},
            timeout=120,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
        proof=json.loads((result_dir/'self-test.json').read_text('utf-8'))
        if proof.get('ok') is not True or proof.get('physical_prints')!=0 or proof.get('network_calls')!=0:
            raise ValueError('Сборка не прошла автономную самопроверку.')
    source_hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    payload={}
    for path in folder.rglob('*'):
        if not path.is_file():continue
        name=path.relative_to(folder).as_posix()
        if path.is_symlink() or path.name in ('settings.json','config.json','journal.sqlite3','db.sqlite3') or path.suffix in ('.backup','.key','.pem'):
            raise ValueError('В сборке недопустимый файл: '+name)
        with path.open('rb') as stream:
            if stream.read(16)==b'SQLite format 3\0':raise ValueError('В сборку попала SQLite.')
        payload[name]=hashlib.sha256(path.read_bytes()).hexdigest()
    from local_agent import VERSION
    from datetime import datetime,timezone
    metadata={'kind':'local_agent','version':VERSION,'platform':'Windows 10/11 x64','signed':False,
        'built_at':datetime.now(timezone.utc).isoformat(),'tested_on_windows':True,'self_test':proof,
        'source_files':source_hashes,'files':payload}
    (folder/'portable-manifest.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    archive=target/f'ReSOURCE-Local-Agent-{VERSION}-Windows-x64.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,allowZip64=True) as stream:
        for path in folder.rglob('*'):
            if path.is_file():stream.write(path,path.relative_to(folder).as_posix())
    (target/'build-result.json').write_text(json.dumps({'file':str(archive),'size':archive.stat().st_size,
        'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'manifest':metadata},ensure_ascii=False,indent=2),encoding='utf-8')
    print(str(archive))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('target',type=Path)
    build(parser.parse_args().target)
