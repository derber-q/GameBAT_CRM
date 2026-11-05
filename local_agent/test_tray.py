"""Настоящие Windows tray/Tk и фоновые потоки, обе рабочие функции выключены."""
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch


@unittest.skipUnless(os.name=='nt','Область уведомлений Windows')
class WindowsTrayLifecycleTests(unittest.TestCase):
    def test_closing_window_keeps_background_and_explicit_quit_stops_both_threads(self):
        import tkinter as tk
        from .configuration import private_folder,initial,save
        from .gui import Application
        with tempfile.TemporaryDirectory() as tmp:
            folder=private_folder(Path(tmp)/'profile');config=initial()
            config['backup_folder']=str(Path(tmp)/'archives');save(folder,config)
            root=tk.Tk();root.withdraw()
            with patch('local_agent.runtime.BackupAPI',side_effect=AssertionError('Не должно быть сети')) as api:
                app=Application(root,folder,'tray-artificial')
                try:
                    root.update();app.hide();root.update()
                    self.assertEqual(root.state(),'withdrawn')
                    self.assertFalse(app.runtime.stop.is_set())
                    self.assertTrue(all(thread.is_alive() for thread in app.runtime.threads))
                    self.assertIsNotNone(app.tray)
                    # Тот же путь команды, которым значок возвращает окно.
                    app.runtime.report('ui','show')
                    until=time.monotonic()+3
                    while root.state()=='withdrawn' and time.monotonic()<until:
                        root.update();time.sleep(.02)
                    self.assertEqual(root.state(),'normal')
                    app.quit()
                    until=time.monotonic()+5
                    while any(thread.is_alive() for thread in app.runtime.threads) and time.monotonic()<until:
                        root.update();time.sleep(.02)
                    self.assertFalse(any(thread.is_alive() for thread in app.runtime.threads))
                    api.assert_not_called()
                finally:
                    app.runtime.stop.set()
                    if root.winfo_exists():
                        for thread in app.runtime.threads:thread.join(timeout=3)
                        app.tray.stop();app.journal.close();root.destroy()
