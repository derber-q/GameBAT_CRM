"""Консервативный отпечаток всех версионируемых файлов миграций для совместимости кода."""
import hashlib
from pathlib import Path
import subprocess


def fingerprint():
    names=subprocess.check_output(['git','ls-files','--','*/migrations/*.py'],text=True).splitlines()
    if not names:
        raise RuntimeError('Файлы миграций не найдены.')
    # Обновление Django/драйвера может менять встроенные миграции и требует отдельного допуска.
    names += ['requirements.txt','deploy/updater/requirements.txt']
    result=hashlib.sha256()
    for name in sorted(names):
        result.update(name.encode()+b'\0'+Path(name).read_bytes()+b'\0')
    return result.hexdigest()


if __name__=='__main__':print(fingerprint())
