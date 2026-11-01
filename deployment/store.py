"""Собственный административный журнал. Не открывает SQLite/таблицы учёта CRM."""
from contextlib import contextmanager, closing
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
import uuid


class UpdateError(Exception):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-f0-9]{40}', value):
        raise UpdateError('Недопустимый SHA версии.')
    return value


class Store:
    def __init__(self, path):
        self.path = Path(path)
        if not self.path.is_absolute() or self.path.resolve() != self.path or self.path.is_symlink():
            raise UpdateError('Недопустимый путь журнала обновлений.')

    @contextmanager
    def connection(self, *, write=False):
        if not self.path.is_file():
            raise UpdateError('Менеджер обновлений не настроен: журнал не создан.')
        db = sqlite3.connect(self.path.as_uri() + ('?mode=rw' if write else '?mode=ro'), uri=True, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            if write:
                db.execute('BEGIN IMMEDIATE')
            yield db
            if write:
                db.commit()
        except Exception:
            if write:
                db.rollback()
            raise
        finally:
            db.close()

    def initialize(self):
        # Вызывается только отдельным CLI настройки, никогда Django-view.
        if self.path.exists():
            raise UpdateError('Журнал уже существует; повторная инициализация запрещена.')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open('xb'):
            pass
        self.path.chmod(0o600)
        with closing(sqlite3.connect(self.path)) as db:
            db.executescript('''
                CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE operations (
                    id TEXT PRIMARY KEY, action TEXT NOT NULL, actor TEXT NOT NULL,
                    target TEXT NOT NULL, state TEXT NOT NULL, requested_at TEXT NOT NULL,
                    finished_at TEXT, message TEXT NOT NULL DEFAULT '',
                    journal TEXT NOT NULL DEFAULT '[]', result TEXT NOT NULL DEFAULT '{}');
            ''')

    def get(self, key, default=None):
        with self.connection() as db:
            row = db.execute('SELECT value FROM meta WHERE key=?', (key,)).fetchone()
        return json.loads(row['value']) if row else default

    def set(self, key, value):
        with self.connection(write=True) as db:
            db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', (key, json.dumps(value)))

    def delete(self, key):
        with self.connection(write=True) as db:
            db.execute('DELETE FROM meta WHERE key=?', (key,))

    @staticmethod
    def operation(row):
        if row is None:
            return None
        data = dict(row)
        data['journal'], data['result'] = json.loads(data['journal']), json.loads(data['result'])
        return data

    def operations(self):
        with self.connection() as db:
            return [self.operation(row) for row in db.execute('SELECT * FROM operations ORDER BY requested_at DESC LIMIT 30')]

    def enqueue(self, action, actor, request_id, target=''):
        if action not in ('check', 'install', 'rollback'):
            raise UpdateError('Неизвестная операция обновления.')
        try:
            request_id = str(uuid.UUID(str(request_id)))
        except (ValueError, TypeError):
            raise UpdateError('Обновите страницу перед отправкой операции.') from None
        if action != 'check':
            sha(target)
        with self.connection(write=True) as db:
            row = db.execute('SELECT * FROM operations WHERE id=?', (request_id,)).fetchone()
            if row:
                if (row['action'], row['actor'], row['target']) != (action, str(actor), target):
                    raise UpdateError('Этот идентификатор уже использован другой операцией.')
                return request_id
            if db.execute('SELECT 1 FROM operations WHERE finished_at IS NULL').fetchone():
                raise UpdateError('Другая операция уже выполняется. Дождитесь её завершения.')
            if db.execute("SELECT 1 FROM meta WHERE key='recovery_required'").fetchone():
                raise UpdateError('Требуется проверка состояния установки администратором сервера.')
            db.execute('INSERT INTO operations (id,action,actor,target,state,requested_at) VALUES (?,?,?,?,?,?)',
                       (request_id, action, str(actor), target, 'queued', now()))
        return request_id

    def stage(self, operation, phase, message='', *, finished=False, result=None):
        with self.connection(write=True) as db:
            row = db.execute('SELECT * FROM operations WHERE id=?', (operation['id'],)).fetchone()
            journal = json.loads(row['journal'])
            journal.append({'at': now(), 'stage': phase, 'message': message})
            db.execute('UPDATE operations SET state=?,message=?,journal=?,finished_at=?,result=? WHERE id=?',
                       (phase, message, json.dumps(journal), now() if finished else None,
                        json.dumps(result) if result is not None else row['result'], operation['id']))

    def queued(self):
        with self.connection() as db:
            return self.operation(db.execute("SELECT * FROM operations WHERE state='queued' AND finished_at IS NULL ORDER BY requested_at LIMIT 1").fetchone())

    def interrupt_started(self):
        for operation in self.operations():
            if operation['finished_at'] is None and operation['state'] != 'queued':
                self.set('recovery_required', {'operation': operation['id'], 'at': now()})
                self.stage(operation, 'interrupted', 'Менеджер был прерван. Автоматический повтор запрещён.', finished=True)
