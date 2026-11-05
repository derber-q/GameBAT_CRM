"""Собственный долговечный журнал архивов; не открывает БД CRM."""
import datetime
import json
import sqlite3
import threading


class BackupJournal:
    def __init__(self,path):
        self.lock=threading.RLock()
        self.db=sqlite3.connect(path,check_same_thread=False)
        self.db.row_factory=sqlite3.Row
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('''CREATE TABLE IF NOT EXISTS archives(
            id TEXT PRIMARY KEY, meta TEXT NOT NULL, path TEXT NOT NULL, state TEXT NOT NULL,
            pinned INTEGER NOT NULL DEFAULT 0, verified_at TEXT, attempted_at TEXT NOT NULL, error TEXT NOT NULL DEFAULT '')''')
        self.db.commit()

    def get(self,identifier):
        with self.lock:
            row=self.db.execute('SELECT * FROM archives WHERE id=?',(identifier,)).fetchone()
            return dict(row) if row else None

    def rows(self):
        with self.lock: return [dict(row) for row in self.db.execute('SELECT * FROM archives ORDER BY attempted_at DESC')]

    def put(self,meta,path,state,error=''):
        now=datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self.lock:
            self.db.execute('''INSERT INTO archives(id,meta,path,state,attempted_at,error,verified_at)
                VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                path=excluded.path,state=excluded.state,attempted_at=excluded.attempted_at,
                error=excluded.error,verified_at=COALESCE(excluded.verified_at,archives.verified_at)''',
                (meta['id'],json.dumps(meta,sort_keys=True),str(path),state,now,error,now if state=='verified' else None))
            self.db.commit()

    def pin(self,identifier,value):
        with self.lock:
            self.db.execute('UPDATE archives SET pinned=? WHERE id=?',(bool(value),identifier));self.db.commit()

    def close(self):
        with self.lock: self.db.close()
