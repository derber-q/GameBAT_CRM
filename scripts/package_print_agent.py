"""Отдельный комплект агента: только нужные исходники, без CRM, БД, медиа и ключей."""
import argparse
from pathlib import Path
import shutil
import zipfile

ROOT=Path(__file__).resolve().parent.parent


def package(target):
    target=target.resolve()
    if not target.is_relative_to(ROOT/'outputs') or target.exists():
        raise ValueError('Нужен новый каталог внутри outputs.')
    target.mkdir(parents=True)
    files=[p for p in (ROOT/'print_agent').glob('*.py') if not p.name.startswith('test_')]
    files += [ROOT/p for p in ['print_agent/requirements.txt','print_agent/README.md','sales/__init__.py','sales/label_printing.py',
        'core/__init__.py','core/external_policy.py','start_print_agent.ps1','setup_print_agent.ps1']]
    for path in files:
        destination=target/path.relative_to(ROOT);destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,destination)
    archive=target.with_suffix('.zip')
    if archive.exists():raise ValueError('Архив уже существует.')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as stream:
        for path in target.rglob('*'):
            if path.is_file():stream.write(path,path.relative_to(target).as_posix())
    print('Комплект агента подготовлен без рабочих данных: '+str(archive))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target',type=Path)
    package(parser.parse_args().target)
