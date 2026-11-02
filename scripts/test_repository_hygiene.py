"""Интеграционные проверки защиты Git на отдельных временных репозиториях."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from scripts.check_repository import check_index


class RepositoryHygieneTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)

    def stage(self, path, content):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        subprocess.run(['git', 'add', '-f', '--', path], cwd=self.root, check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return target

    def test_source_migrations_and_example_environment_are_allowed(self):
        self.stage('cash/migrations/0002_create_registers.py', b'from django.db import migrations\n')
        self.stage('.env.example', b'DJANGO_SECRET_KEY=replace-me\n')
        self.stage('docs/technical.md', b'# Architecture\n')
        self.assertEqual(check_index(self.root), [])

    def test_forced_database_and_generated_paths_are_rejected(self):
        self.stage('archive/customer.sqlite3.bak', b'not-a-real-db')
        self.stage('outputs/result.txt', b'temporary')
        self.stage('backups/copy.data', b'local-backup')
        self.assertEqual({p for p, _ in check_index(self.root)},
                         {'archive/customer.sqlite3.bak', 'outputs/result.txt', 'backups/copy.data'})

    def test_disguised_sqlite_blob_is_rejected_even_if_worktree_is_cleaned(self):
        target = self.stage('catalog/fixture.data', b'SQLite format 3\0' + bytes(100))
        target.write_bytes(b'safe text now')
        self.assertEqual(check_index(self.root)[0][0], 'catalog/fixture.data')

    def test_staged_deletion_of_database_is_not_rejected(self):
        self.stage('db.sqlite3', b'SQLite format 3\0')
        subprocess.run(['git', 'rm', '--cached', '--', 'db.sqlite3'], cwd=self.root, check=True,
                       stdout=subprocess.PIPE)
        self.assertEqual(check_index(self.root), [])
        self.assertTrue((self.root / 'db.sqlite3').exists())

    def test_telegram_token_is_rejected_under_an_arbitrary_filename(self):
        self.stage('config/bot.txt', b'123456:' + b'x' * 35)
        result = check_index(self.root)
        self.assertEqual(result[0][0], 'config/bot.txt')
        self.assertNotIn('123456:', repr(result))

    def test_local_keys_and_environment_are_rejected_without_revealing_contents(self):
        self.stage('.env.production', b'PRIVATE_VALUE=do-not-print\n')
        self.stage('.integration-encryption-key', b'do-not-print')
        self.stage('.telegram-staff-bot-token', b'do-not-print')
        self.stage('config/key.pem', b'-----BEGIN PRIVATE KEY-----\nprivate\n')
        result = check_index(self.root)
        self.assertEqual(len(result), 4)
        self.assertNotIn('do-not-print', repr(result))


if __name__ == '__main__':
    unittest.main()
