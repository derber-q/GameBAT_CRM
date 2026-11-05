"""Реальное восстановление искусственного WAL, файлов и зашифрованных данных."""
import json
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from cryptography.fernet import Fernet
from .crypto import generate_keys
from .snapshot import create_bundle, restore_bundle


class FullSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.media = self.root / 'media'; self.media.mkdir()
        (self.media / 'label.pdf').write_bytes(b'%PDF-test fixture')
        self.database = self.root / 'live.sqlite3'
        self.writer = sqlite3.connect(self.database)
        self.addCleanup(self.writer.close)
        self.writer.execute('PRAGMA journal_mode=WAL')
        self.writer.executescript('CREATE TABLE stock(id INTEGER PRIMARY KEY, quantity INTEGER, file TEXT);'
                                  'CREATE TABLE cash(id INTEGER PRIMARY KEY, amount TEXT);'
                                  'CREATE TABLE credential(id INTEGER PRIMARY KEY, encrypted TEXT);')
        self.key = Fernet.generate_key()
        self.writer.execute('INSERT INTO stock VALUES(1, 7, ?)', ('label.pdf',))
        self.writer.execute('INSERT INTO cash VALUES(1, ?)', ('1234.56',))
        self.writer.execute('INSERT INTO credential VALUES(1, ?)', (Fernet(self.key).encrypt(b'fake-API-secret').decode(),))
        self.writer.commit()
        self.private, self.public = generate_keys(b'owner-passphrase-for-tests')
        self.target = self.root / 'copy.backup'
        self.options = dict(database=self.database, media=self.media,
            secrets_loader=lambda: {'INTEGRATION_ENCRYPTION_KEY': self.key.decode()},
            metadata={'environment': 'artificial', 'sha': 'a' * 40, 'dirty': True},
            public_key=self.public, destination=self.target,
            file_columns=[('stock', 'file')],
            encrypted_columns=[('credential', 'encrypted', 'INTEGRATION_ENCRYPTION_KEY')])

    def test_restore_wal_files_money_stock_and_secret_in_separate_database(self):
        result = create_bundle(**self.options)
        restored = self.root / 'restored'
        manifest = restore_bundle(self.target, restored, self.private, b'owner-passphrase-for-tests')
        self.assertTrue(result['sha256'])
        self.assertEqual(manifest['metadata']['dirty'], True)
        with closing(sqlite3.connect(restored / 'database.sqlite3')) as con:
            self.assertEqual(con.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            self.assertEqual(con.execute('PRAGMA foreign_key_check').fetchall(), [])
            self.assertEqual(con.execute('SELECT quantity FROM stock').fetchone()[0], 7)
            self.assertEqual(con.execute('SELECT amount FROM cash').fetchone()[0], '1234.56')
            encrypted = con.execute('SELECT encrypted FROM credential').fetchone()[0]
        saved = json.loads((restored / 'recovery/secrets.json').read_text())
        self.assertEqual(Fernet(saved['INTEGRATION_ENCRYPTION_KEY'].encode()).decrypt(encrypted.encode()), b'fake-API-secret')
        self.assertEqual((restored / 'protected_media/label.pdf').read_bytes(), (self.media / 'label.pdf').read_bytes())
        self.assertEqual(self.writer.execute('SELECT quantity FROM stock').fetchone()[0], 7)

    def test_missing_referenced_file_and_wrong_recovery_secret_fail_closed(self):
        (self.media / 'label.pdf').unlink()
        with self.assertRaises(ValueError): create_bundle(**self.options)
        self.assertFalse(self.target.exists())
        (self.media / 'label.pdf').write_bytes(b'pdf')
        self.options['secrets_loader'] = lambda: {'INTEGRATION_ENCRYPTION_KEY': Fernet.generate_key().decode()}
        with self.assertRaises(ValueError): create_bundle(**self.options)
        self.assertFalse(self.target.exists())

    def test_restore_never_overwrites_existing_directory(self):
        create_bundle(**self.options)
        destination = self.root / 'existing'; destination.mkdir()
        (destination / 'important').write_text('keep')
        with self.assertRaises(ValueError):
            restore_bundle(self.target, destination, self.private, b'owner-passphrase-for-tests')
        self.assertEqual((destination / 'important').read_text(), 'keep')

    def test_changed_media_and_timeout_do_not_publish(self):
        from . import snapshot
        original = snapshot.copy_file
        def changing(source, target, check):
            result = original(source, target, check)
            source.write_bytes(b'changed during copy')
            return result
        with patch.object(snapshot, 'copy_file', changing), self.assertRaises(ValueError):
            create_bundle(**self.options)
        self.assertFalse(self.target.exists())
        with self.assertRaises(TimeoutError): create_bundle(**self.options, window_seconds=0)

    def test_uncommitted_writer_is_not_silently_ignored(self):
        self.writer.execute('UPDATE stock SET quantity=9')
        with self.assertRaises(sqlite3.OperationalError): create_bundle(**self.options)
        self.assertFalse(self.target.exists())

    def test_published_applications_are_included_in_full_copy(self):
        apps=self.root/'programs';apps.mkdir();(apps/'installer.zip').write_bytes(b'artificial installer')
        create_bundle(**self.options,extra_roots={'client_applications':apps})
        destination=self.root/'restored-apps'
        restore_bundle(self.target,destination,self.private,b'owner-passphrase-for-tests')
        self.assertEqual((destination/'client_applications/installer.zip').read_bytes(),b'artificial installer')

    def test_slow_file_copy_happens_before_short_database_write_window(self):
        from . import snapshot
        original=snapshot.copy_file
        def copy_with_business_write(source,target,check):
            # Продажа/остаток ещё могут измениться во время предварительной
            # подготовки файлов. Финальная БД должна включать завершённую запись.
            self.writer.execute('UPDATE stock SET quantity=9');self.writer.commit()
            return original(source,target,check)
        with patch.object(snapshot,'copy_file',copy_with_business_write):create_bundle(**self.options)
        destination=self.root/'restored-staged'
        restore_bundle(self.target,destination,self.private,b'owner-passphrase-for-tests')
        with closing(sqlite3.connect(destination/'database.sqlite3')) as restored:
            self.assertEqual(restored.execute('SELECT quantity FROM stock').fetchone()[0],9)
