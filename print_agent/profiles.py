"""Общая блокировка принтера для CLI/GUI, при этом старые журналы не перемещаются."""
from contextlib import contextmanager,ExitStack
import hashlib
import json
import os
from pathlib import Path


@contextmanager
def printer_lock(printer_name,state):
    from .__main__ import exclusive,default_config
    root=Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.local/share')))/'ReSOURCE/PrintAgent/printer-locks'
    if root.resolve()!=root.absolute():raise ValueError('Ссылка в каталоге блокировок принтера.')
    root.mkdir(parents=True,exist_ok=True)
    name=hashlib.sha256(printer_name.casefold().encode()).hexdigest()+'.lock'
    with ExitStack() as stack:
        stack.enter_context(exclusive(root/name))
        # Совместимость с уже запущенным прежним агентом, ещё не знающим
        # общую блокировку принтера. Его config/journal не изменяются.
        previous=default_config()
        if previous.is_file() and previous.parent.resolve()!=Path(state).resolve():
            data=json.loads(previous.read_text('utf-8-sig'))
            if data.get('printer_name','').casefold()==printer_name.casefold():
                stack.enter_context(exclusive(previous.parent/'agent.lock'))
        yield
