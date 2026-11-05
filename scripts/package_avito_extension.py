"""ZIP существующего расширения без тестов, ключей и изменения manifest."""
import argparse
import os
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT));os.environ.setdefault('DJANGO_SETTINGS_MODULE','GameBAT_CRM.settings')
import django
django.setup()
from crm_backups.client_apps import package_extension

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('target',type=Path)
    target=parser.parse_args().target.resolve()
    if not target.is_relative_to(ROOT/'outputs') or target.exists():raise ValueError('Нужен новый ZIP внутри outputs.')
    version=package_extension(ROOT/'browser_extensions/avito_check',target)
    print(f'Opera GX {version}: {target}')
