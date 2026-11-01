"""Локальный журнал с FULL-коммитом до возможной физической печати; PDF не хранится."""
import json
import sqlite3


class Journal:
    def __init__(self,path,scope):
        self.scope=scope
        self.connection=sqlite3.connect(path)
        self.connection.execute('PRAGMA journal_mode=WAL')
        self.connection.execute('PRAGMA synchronous=FULL')
        self.connection.execute('CREATE TABLE IF NOT EXISTS deliveries (scope TEXT, job TEXT, claim TEXT, record TEXT, PRIMARY KEY(scope,job,claim))')
        self.connection.commit()

    def get(self,job):
        row=self.connection.execute('SELECT record FROM deliveries WHERE scope=? AND job=? AND claim=?',
            (self.scope,job['id'],job['claim'])).fetchone()
        return json.loads(row[0]) if row else None

    def put(self,job,state,spool=None):
        record={'job':job,'state':state,'spool':spool}
        with self.connection:
            self.connection.execute('INSERT INTO deliveries VALUES (?,?,?,?) ON CONFLICT(scope,job,claim) DO UPDATE SET record=excluded.record',
                (self.scope,job['id'],job['claim'],json.dumps(record)))
        return record

    def pending(self):
        rows=self.connection.execute('SELECT record FROM deliveries WHERE scope=? ORDER BY rowid',(self.scope,)).fetchall()
        return [item for row in rows if (item:=json.loads(row[0]))['state'] not in ('done','review')]

    def close(self):
        self.connection.close()
