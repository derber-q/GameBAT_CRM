"""Состояние сервера видно клиенту даже если архив не удалось сформировать."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from .runtime import Runtime


class BackupRuntimeStatusTests(unittest.TestCase):
    def test_intentionally_deleted_verified_archive_is_not_downloaded_again(self):
        import uuid
        from .journal import BackupJournal
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);identifier=str(uuid.uuid4())
            journal=BackupJournal(folder/'backups.sqlite3')
            meta={'id':identifier,'state':'verified','size':1,'sha256':'a'*64,'environment_id':'test'}
            journal.put(meta,folder/'old.backup','deleted');journal.close()
            runtime=Runtime(folder,lambda:{'backup_enabled':True,'backup_token':'fake','backup_folder':str(folder)})
            class API:
                def __init__(self,*args):pass
                def heartbeat(self):return {'ok':True}
                def status(self):runtime.stop.set();return [meta]
                def stream(self,*args):raise AssertionError('Удалённую по политике копию не нужно скачивать заново')
            with patch('local_agent.runtime.BackupAPI',API),patch('local_agent.runtime.download') as downloaded:
                runtime.backup_loop()
            downloaded.assert_not_called()

    def test_double_click_persists_one_request_until_terminal_result(self):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            runtime=Runtime(Path(tmp),lambda:{})
            first=runtime.request_backup();second=runtime.request_backup()
            self.assertEqual(first,second)
            stored=json.loads((Path(tmp)/'backup-request.json').read_text())
            self.assertEqual(stored['request_id'],str(first))
            restarted=Runtime(Path(tmp),lambda:{})
            self.assertEqual(restarted.request_backup(),first)

    def test_server_snapshot_failure_is_reported_without_stopping_print_worker(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime=Runtime(Path(tmp),lambda:{'backup_enabled':True,'backup_token':'artificial-token'})
            class API:
                def __init__(self,*args):pass
                def heartbeat(self):return {'ok':True}
                def status(self):
                    runtime.stop.set()
                    return [{'id':'fake-job','state':'error','error':'TimeoutError'}]
            with patch('local_agent.runtime.BackupAPI',API):runtime.backup_loop()
            messages=[]
            while not runtime.events.empty():messages.append(runtime.events.get_nowait())
            self.assertTrue(any(channel=='backup' and 'Сервер не создал' in text for channel,text in messages))
            self.assertFalse(any(channel=='print' for channel,_ in messages))
