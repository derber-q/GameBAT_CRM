"""Проверка/генерация файлов миграций без доступа к рабочим данным и transport."""
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from GameBAT_CRM.environments import SECRET_VARIABLES

if len(sys.argv) < 2 or sys.argv[1] not in ('check', 'makemigrations'):
    raise SystemExit('Разрешены только check и makemigrations; применения миграций и запуска CRM здесь нет.')
for name in SECRET_VARIABLES:
    os.environ.pop(name, None)  # Только дочерний процесс; окружение рабочей CRM не меняется.
os.environ['DJANGO_SETTINGS_MODULE'] = 'digital_prices.check_settings'
from django.core.management import execute_from_command_line
execute_from_command_line(sys.argv)
