"""Изолированная подготовка: ни рабочая SQLite, ни ключи, ни внешние действия."""
import os
os.environ['GAMEBAT_ENV'] = 'local_test'
os.environ['GAMEBAT_TEST_ROOT'] = str(__import__('pathlib').Path(__file__).resolve().parents[1] / 'outputs/local_test/digital_prices_prepare')
from GameBAT_CRM.settings import *
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
