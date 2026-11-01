"""Дополнительный запрет стандартных транспортов и чужой SQLite в local_test.

Это защита от случайного обхода клиентской политики, не ОС-песочница для враждебного
Python/C-кода. Отдельная инфраструктурная сеть остаётся обязательной для такого кода.
"""
import os
from pathlib import Path
import sys
import sqlite3
from urllib.parse import unquote, urlsplit, parse_qs

_installed = False


def install(base, root):
    global _installed
    if _installed:
        return
    forbidden = tuple((base/name).resolve() for name in (
        'protected_media','backups','db.sqlite3','db.sqlite3-wal','db.sqlite3-shm',
        '.django-secret-key','.integration-encryption-key','.resource-token-encryption-key',
        '.yandex-market-key','.label-printer.json','.env'))
    def check_path(path, *, database=False):
        if isinstance(path, int):
            return
        value = os.fsdecode(path)
        if database and value == ':memory:':
            return
        if database and value.startswith('file:'):
            parsed = urlsplit(value)
            if parse_qs(parsed.query).get('mode') == ['memory']:
                return
            value = unquote(parsed.path)
            if os.name == 'nt' and value.startswith('/') and len(value)>3 and value[2] == ':':
                value = value[1:]
        resolved = Path(value).resolve()
        lexical = Path(value).absolute()
        if lexical.is_relative_to(root) and not resolved.is_relative_to(root):
            raise PermissionError('local_test: выход из каталога данных через ссылку запрещён.')
        if database and not resolved.is_relative_to(root):
            raise PermissionError('local_test: доступ к БД другого окружения запрещён.')
        if any(resolved == item or resolved.is_relative_to(item) for item in forbidden):
            raise PermissionError('local_test: доступ к рабочим данным и ключам запрещён.')
        if resolved.is_relative_to(root) and resolved.exists() and resolved.stat().st_nlink > 1:
            raise PermissionError('local_test: жёсткая ссылка вместо БД запрещена.')

    def audit(event, args):
        if event in ('urllib.Request','socket.connect','socket.connect_ex','socket.getaddrinfo',
                     'socket.gethostbyname','socket.sendto','socket.sendmsg',
                     'subprocess.Popen','os.system','os.exec','os.posix_spawn','os.spawn','os.kill','os.killpg',
                     'os.startfile','os.startfile/2','ctypes.dlopen'):
            raise PermissionError('local_test: сеть, внешние процессы и управление процессами ОС запрещены.')
        if event == 'import' and args[0] in ('win32print','win32ui','win32gui'):
            raise PermissionError('local_test: прямой доступ к Windows-принтеру запрещён.')
        if event == 'sqlite3.connect':
            check_path(args[0], database=True)
        elif event == 'sqlite3.connect/handle' and type(args[0]) is not RestrictedConnection:
            raise PermissionError('local_test: соединение без защиты ATTACH запрещено.')
        elif event == 'sqlite3.enable_load_extension':
            raise PermissionError('local_test: загрузка расширений SQLite запрещена.')
        elif event == 'open':
            check_path(args[0])
    def authorize(action, first, second, database, trigger):
        if action == sqlite3.SQLITE_ATTACH:
            try:
                check_path(first, database=True)
            except (OSError, ValueError):
                return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK
    # Событие connect/handle происходит ДО окончания Connection.__init__ в
    # CPython 3.14. Authorizer устанавливается после инициализации подкласса;
    # сырые Connection и ранее импортированные native connect блокируются.
    original_connect = sqlite3.connect
    class RestrictedConnection(sqlite3.Connection):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.set_authorizer(authorize)

    def restricted_connect(*args, **kwargs):
        if len(args)>5 or kwargs.get('factory', RestrictedConnection) is not RestrictedConnection:
            raise PermissionError('local_test: подмена SQLite factory запрещена.')
        kwargs['factory'] = RestrictedConnection
        return original_connect(*args, **kwargs)
    sys.addaudithook(audit)
    sqlite3.connect = sqlite3.dbapi2.connect = restricted_connect
    sqlite3.Connection = sqlite3.dbapi2.Connection = RestrictedConnection
    _installed = True
