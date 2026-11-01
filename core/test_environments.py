"""Запуски настроек проверяются в отдельных процессах без чтения рабочей БД."""
import json
import os
from pathlib import Path
import subprocess
import sys

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parent.parent


class EnvironmentProcessTests(SimpleTestCase):
    def run_child(self, code, *, mode='local_test', extra=None, success=True):
        env = os.environ.copy()
        for key in tuple(env):
            if key.startswith(('DJANGO_', 'GAMEBAT_', 'INTEGRATION_', 'RESOURCE_TOKEN_', 'YANDEX_', 'GOOGLE_', 'DATABASE_')):
                env.pop(key)
        env.update(GAMEBAT_ENV=mode, DJANGO_SETTINGS_MODULE='GameBAT_CRM.settings',
                   PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1')
        env.update(extra or {})
        result = subprocess.run([sys.executable, '-c', code], cwd=ROOT, env=env,
                                capture_output=True, encoding='utf-8', timeout=40)
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout)
        return result

    def test_isolated_paths_keys_sessions_and_default_live(self):
        code = """
import json
from django.conf import settings as s
print(json.dumps({'mode':s.GAMEBAT_ENV,'db':str(s.DATABASES['default']['NAME']),
 'media':str(s.MEDIA_ROOT),'key':str(s.INTEGRATION_ENCRYPTION_KEY_FILE),
 'cookie':s.SESSION_COOKIE_NAME,'locks':str(s.WORKER_RUNTIME_DIR)}))
"""
        test = json.loads(self.run_child(code).stdout)
        self.assertEqual(test['mode'], 'local_test')
        for key in ('db', 'media', 'key', 'locks'):
            self.assertIn('local_test', test[key])
        live = json.loads(self.run_child(code, mode='local_live').stdout)
        self.assertEqual(live['db'], str(ROOT / 'db.sqlite3'))
        self.assertNotEqual(live['cookie'], test['cookie'])

    def test_rejects_inherited_secrets_foreign_roots_and_unknown_mode(self):
        for extra in ({'GOOGLE_SERVICE_ACCOUNT_FILE':str(ROOT / 'secret.json')},
                      {'DJANGO_SECRET_KEY':'must-not-be-used'},
                      {'GAMEBAT_TEST_ROOT':str(ROOT)},
                      {'GAMEBAT_TEST_ROOT':str(ROOT / 'protected_media')},
                      {'DATABASE_URL':'sqlite:///db.sqlite3'}):
            result = self.run_child('from django.conf import settings; print(settings.GAMEBAT_ENV)', extra=extra, success=False)
            self.assertNotIn('must-not-be-used', result.stderr)
        self.run_child('from django.conf import settings; print(settings.GAMEBAT_ENV)', mode='wrong', success=False)

    def test_direct_sqlite_open_secret_read_network_and_shell_are_blocked(self):
        code = """
import json, sqlite3, socket, subprocess, urllib.request, requests, ctypes, _sqlite3
raw_connection=sqlite3.Connection
raw_connect=_sqlite3.connect
from django.conf import settings as s
assert s.GAMEBAT_ENV == 'local_test'
checks = {}
actions = {
 'db':lambda:sqlite3.connect(str(s.BASE_DIR/'db.sqlite3')),
 'secret':lambda:(s.BASE_DIR/'.integration-encryption-key').read_bytes(),
 'urlopen':lambda:urllib.request.urlopen('https://api.avito.ru/', timeout=.1),
 'requests':lambda:requests.get('https://api.reefapi.com/', timeout=.1),
 'socket':lambda:socket.create_connection(('1.1.1.1',443), timeout=.1),
 'live_loopback':lambda:socket.create_connection(('127.0.0.1',8000), timeout=.1),
 'shell':lambda:subprocess.run(['cmd.exe','/c','echo','not-allowed']),
 'native_library':lambda:ctypes.CDLL('untrusted-library'),
 'raw_sqlite_class':lambda:raw_connection(':memory:'),
 'raw_sqlite_connect':lambda:raw_connect(':memory:'),
}
for name, action in actions.items():
 try: action()
 except Exception as error:
  assert 'local_test' in str(error), (name, type(error).__name__)
  checks[name] = True
 else: raise AssertionError(name+' unexpectedly allowed')
connection=sqlite3.connect(str(s.DATABASES['default']['NAME']))
try: connection.execute('ATTACH DATABASE ? AS forbidden', (str(s.BASE_DIR/'db.sqlite3'),))
except sqlite3.DatabaseError: checks['attach'] = True
else: raise AssertionError('ATTACH to live database allowed')
connection.close()
print(json.dumps(checks))
"""
        self.assertTrue(all(json.loads(self.run_child(code).stdout).values()))

    def test_production_fails_closed_before_creating_keys_or_opening_db(self):
        result = self.run_child('from django.conf import settings; print(settings.SECRET_KEY)', mode='production', success=False)
        self.assertIn('production', result.stderr)

    def test_test_runtime_never_uses_windows_process_adapter(self):
        code = """
import django
django.setup()
from integrations.worker_processes import WindowsProcesses
from django.core.exceptions import ValidationError
try: WindowsProcesses().inventory()
except (ValidationError, PermissionError): print('blocked')
else: raise AssertionError('live adapter allowed')
"""
        self.assertIn('blocked', self.run_child(code).stdout)

    def test_sqlite_uri_and_shared_memory_cannot_escape_test_root(self):
        code = """
import sqlite3
from django.conf import settings as s
assert s.GAMEBAT_ENV == 'local_test'
for value in (str(s.BASE_DIR/'db.sqlite3'), (s.BASE_DIR/'db.sqlite3').as_uri()+'?mode=ro',
              'file:memorydb_fake?mode=rw'):
 try: sqlite3.connect(value,uri=True)
 except PermissionError: pass
 else: raise AssertionError('foreign sqlite URI accepted')
sqlite3.connect('file:memorydb_safe?mode=memory&cache=shared',uri=True).close()
print('safe')
"""
        self.assertIn('safe',self.run_child(code).stdout)
