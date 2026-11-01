"""Экспорт только исходников в новый контекст сборки; БД, ключи и медиа не копируются."""
import argparse
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parent.parent
SOURCE_DIRS=('GameBAT_CRM','accounts','catalog','partners','warehouse','supplies','consignment',
             'pricing','sales','cash','creditors','price','orders','integrations','yandex_market',
             'resource_storefront','core','templates','static')
ALLOWED_SUFFIXES={'.py','.html','.css','.js','.json','.png','.webp','.jpg','.jpeg','.svg','.ico','.mp3','.woff','.woff2','.ttf'}
EXCLUDED_PARTS={'__pycache__','node_modules','.git','.venv','outputs','backups','protected_media'}


def prepare(target):
    target=target.resolve()
    allowed=(ROOT/'outputs').resolve()
    if not target.is_relative_to(allowed) or target==allowed or target.exists():
        raise ValueError('Нужен новый каталог внутри outputs; существующий каталог не перезаписывается.')
    target.mkdir(parents=True)
    for name in SOURCE_DIRS:
        for path in (ROOT/name).rglob('*'):
            rel=path.relative_to(ROOT)
            safe_json = path.suffix.lower() != '.json' or rel.as_posix() == 'yandex_market/contracts.json'
            if path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(ROOT) and not any(part.startswith('.') for part in rel.parts) and safe_json and path.suffix.lower() in ALLOWED_SUFFIXES and not (set(rel.parts)&EXCLUDED_PARTS):
                dest=target/rel; dest.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(path,dest)
    for name in ('manage.py','requirements.txt'):
        shutil.copy2(ROOT/name,target/name)
    shutil.copy2(ROOT/'deploy/local_test/Dockerfile',target/'Dockerfile')
    for name in ('Dockerfile.ingress','ingress.conf'):
        shutil.copy2(ROOT/'deploy/local_test'/name,target/name)
    print('Контекст тестового образа подготовлен без БД, медиа и локальных ключей.')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('target',type=Path)
    prepare(parser.parse_args().target)
