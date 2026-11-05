"""Загрузка/возобновление/очистка только на искусственных файлах в temp."""
import hashlib
import io
from pathlib import Path
import tempfile
import unittest
import uuid
from .downloads import download, cleanup
from .journal import BackupJournal


class Reply(io.BytesIO):
    status=200
    headers={}


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); self.folder=self.root/'archives'; self.folder.mkdir()
        self.journal=BackupJournal(self.root/'journal.sqlite3'); self.addCleanup(self.journal.close)
        self.body=b'encrypted test archive'*100
        self.meta={'id':str(uuid.uuid4()),'size':len(self.body),'sha256':hashlib.sha256(self.body).hexdigest(),
            'snapshot_at':'2026-11-03T03:00:00+03:00','version':'a'*40,'environment_id':'test','kind':'daily'}

    def source(self, offset, meta):
        reply=Reply(self.body[offset:]); reply.status=206 if offset else 200
        reply.headers={'Content-Length':str(len(self.body)-offset),'ETag':'"'+meta['sha256']+'"',
                       'Content-Range':f'bytes {offset}-{len(self.body)-1}/{len(self.body)}'}
        return reply

    def test_success_repeat_and_pinning(self):
        path=download(self.meta,self.folder,self.journal,self.source,minimum_free_bytes=0)
        self.assertEqual(path.read_bytes(),self.body)
        self.assertEqual(download(self.meta,self.folder,self.journal,self.source,minimum_free_bytes=0),path)
        self.journal.pin(self.meta['id'],True)
        cleanup(self.folder,self.journal,keep=0,enabled=True)
        self.assertTrue(path.exists())

    def test_broken_connection_resumes_same_archive(self):
        class Broken(Reply):
            def read(self,size=-1):
                if self.tell(): raise OSError('disconnected')
                return super().read(10)
        def broken(offset,meta):
            reply=Broken(self.body);reply.headers={'Content-Length':str(len(self.body)),'ETag':'"'+meta['sha256']+'"'}
            return reply
        with self.assertRaises(OSError): download(self.meta,self.folder,self.journal,broken,minimum_free_bytes=0)
        self.assertNotEqual(self.journal.get(self.meta['id'])['state'],'verified')
        path=download(self.meta,self.folder,self.journal,self.source,minimum_free_bytes=0)
        self.assertEqual(path.read_bytes(),self.body)

    def test_hash_size_changed_id_and_no_space_fail_closed(self):
        bad={**self.meta,'sha256':'0'*64}
        with self.assertRaises(ValueError): download(bad,self.folder,self.journal,self.source,minimum_free_bytes=0)
        with self.assertRaises(ValueError): download(self.meta,self.folder,self.journal,self.source,minimum_free_bytes=0)
        with self.assertRaises(OSError): download({**self.meta,'id':str(uuid.uuid4())},self.folder,self.journal,self.source,minimum_free_bytes=10**20)
        self.assertFalse(any(self.folder.glob('*.backup')))

    def test_cleanup_keeps_last_pinned_foreign_and_failed_new_download(self):
        first=download(self.meta,self.folder,self.journal,self.source,minimum_free_bytes=0)
        foreign=self.folder/'foreign.backup';foreign.write_bytes(b'never delete')
        cleanup(self.folder,self.journal,keep=0,enabled=True)
        self.assertTrue(first.exists());self.assertTrue(foreign.exists())
        second={**self.meta,'id':str(uuid.uuid4()),'sha256':'0'*64}
        with self.assertRaises(ValueError): download(second,self.folder,self.journal,self.source,minimum_free_bytes=0)
        cleanup(self.folder,self.journal,keep=0,enabled=True)
        self.assertTrue(first.exists())

    def test_seven_daily_copies_and_hardlinked_foreign_file_are_preserved(self):
        paths=[]
        for _ in range(9):
            meta={**self.meta,'id':str(uuid.uuid4())}
            paths.append(download(meta,self.folder,self.journal,self.source,minimum_free_bytes=0))
        removed=cleanup(self.folder,self.journal,keep=7,days=0,enabled=True)
        self.assertEqual(len(removed),2)
        self.assertEqual(sum(path.exists() for path in paths),7)

    def test_restart_between_rename_and_journal_commit_recovers_without_redownload(self):
        from unittest.mock import patch
        original=self.journal.put
        def fail(meta,path,state,error=''):
            if state=='verified':raise OSError('simulated crash after rename')
            return original(meta,path,state,error)
        with patch.object(self.journal,'put',fail),self.assertRaises(OSError):
            download(self.meta,self.folder,self.journal,self.source,minimum_free_bytes=0)
        def forbidden(*args):raise AssertionError('Не должно быть повторной загрузки')
        path=download(self.meta,self.folder,self.journal,forbidden,minimum_free_bytes=0)
        self.assertEqual(path.read_bytes(),self.body)
