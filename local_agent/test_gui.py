"""Настоящие Tk-виджеты, искусственные файлы, без фоновой сети/печати."""
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
import uuid
from .configuration import initial,save,private_folder
if os.name=='nt':
    import tkinter as tk
    from .gui import Application


@unittest.skipUnless(os.name=='nt','Tk/DPAPI-клиент проверяется на Windows')
class ArchiveHistoryUITests(unittest.TestCase):
    def test_failed_integrity_check_marks_copy_corrupt_without_automatic_deletion(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=private_folder(Path(tmp)/'profile');archives=Path(tmp)/'archives';archives.mkdir()
            config=initial();config['backup_folder']=str(archives);save(folder,config)
            root=tk.Tk();root.withdraw();app=Application(root,folder,'test',testing=True)
            try:
                body=b'artificial encrypted file';identifier=str(uuid.uuid4())
                path=archives/f'ReSOURCE_Backup_test_{identifier}.backup';path.write_bytes(body)
                meta={'id':identifier,'sha256':hashlib.sha256(body).hexdigest(),'size':len(body),
                    'snapshot_at':'2026-11-03T03:00:00+03:00','version':'a'*40,'kind':'daily'}
                app.journal.put(meta,path,'verified');app.refresh_history()
                app.tree.selection_set(identifier);path.write_bytes(b'corrupted')
                app.background=lambda function:function()
                app.verify();app.refresh_history()
                self.assertEqual(app.journal.get(identifier)['state'],'corrupt')
                self.assertEqual(app.tree.item(identifier,'values')[4],'Повреждена')
                self.assertTrue(path.exists())
                self.assertFalse(app.runtime.threads)
            finally:app.journal.close();root.destroy()

    def test_printer_check_error_is_shown_in_print_channel(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            folder=private_folder(Path(tmp)/'profile')
            config=initial();config['backup_folder']=str(Path(tmp)/'archives');save(folder,config)
            root=tk.Tk();root.withdraw();app=Application(root,folder,'test',testing=True)
            try:
                with patch('print_agent.driver.WindowsDriver',side_effect=OSError('artificial printer failure')):
                    app.check_printer()
                    channel,_=app.runtime.events.get(timeout=3)
                self.assertEqual(channel,'print')
            finally:app.journal.close();root.destroy()
