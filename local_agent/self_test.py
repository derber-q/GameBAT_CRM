"""Проверка собранного EXE без сети, автозапуска и физической печати."""
import json
from pathlib import Path
import tempfile
import tkinter as tk
from .configuration import initial,save,load,private_folder,protect,unprotect
from .gui import Application


def run(destination):
    destination=Path(destination).absolute()
    if destination.exists() or destination.resolve()!=destination:
        raise ValueError('Самопроверка требует новый отдельный каталог.')
    # Секреты только искусственные. Каталог должен быть в temp или outputs,
    # никогда в текущем профиле установленной программы.
    if not destination.is_relative_to(Path(tempfile.gettempdir()).resolve()) and 'outputs' not in destination.parts:
        raise ValueError('Самопроверка допускается только в отдельном temp/outputs.')
    private_folder(destination)
    config=initial();config['backup_folder']=str(destination/'archives')
    config['print_token']='fake-print-test-token';config['backup_token']='fake-backup-test-token'
    save(destination,config)
    assert load(destination)==config
    assert 'fake-print-test-token' not in (destination/'settings.json').read_text('utf-8')
    assert unprotect(protect('artificial-secret'))=='artificial-secret'
    root=tk.Tk();root.withdraw()
    app=Application(root,destination,'self-test',testing=True)
    root.update_idletasks()
    assert len(app.tabs.tabs())==4
    assert not app.runtime.threads
    from print_agent.engine import Engine
    from print_agent.journal import Journal
    from print_agent.driver import WindowsDriver
    WindowsDriver('__ReSOURCE_self_test_no_print__')  # Только импорт существующего PDF-драйвера, без Spooler.
    import win32print
    printers=win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL|win32print.PRINTER_ENUM_CONNECTIONS,None,2)
    result={'ok':True,'tabs':4,'dpapi_roundtrip':True,'tokens_encrypted':True,
            'printers_enumerated':len(printers),'physical_prints':0,'network_calls':0}
    app.journal.close();root.destroy()
    (destination/'self-test.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
