"""Запрещает включать рабочие данные и артефакты в Git-индекс CRM.

Проверяет именно индекс, поэтому обнаруживает и принудительное `git add -f`,
и SQLite под неверным расширением. Ничего не удаляет и не читает рабочую БД.
"""
from __future__ import annotations

import argparse
from pathlib import Path, PurePosixPath
import re
import subprocess


PRIVATE_DIRECTORIES = {
    'backups', 'outputs', 'output', 'tmp', 'reports', 'protected_media',
    '.venv', 'venv', 'env', 'node_modules', '__pycache__', 'staticfiles',
    '.tools', '.pytest_cache', '.ruff_cache', '.mypy_cache',
}
PRIVATE_NAMES = {
    '.django-secret-key', '.integration-encryption-key', '.resource-token-encryption-key',
    '.yandex-market-key', '.label-printer.json', '.ds_store', 'thumbs.db',
    '.telegram-staff-bot-token',
}
SQLITE_HEADER = b'SQLite format 3\x00'


def violations(path: str, content: bytes) -> list[str]:
    """Возвращает причины запрета без печати содержимого или значений секретов."""
    parts = PurePosixPath(path).parts
    name = parts[-1].lower()
    reasons = []
    if any(part.lower() in PRIVATE_DIRECTORIES for part in parts[:-1]):
        reasons.append('локальные данные, среда или генерируемые артефакты')
    if name in PRIVATE_NAMES or name.startswith('.telegram-') or (name.startswith('.env') and name != '.env.example'):
        reasons.append('локальный секрет или конфигурация рабочего места')
    if re.search(r'\.(?:sqlite\w*|db)(?:$|[.-])|\.(?:bak|pyc|pyo|log)$', name):
        reasons.append('база данных, резервная копия, байткод или журнал')
    if content.startswith(SQLITE_HEADER):
        reasons.append('содержимое SQLite независимо от расширения')
    if re.search(rb'(?m)^-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----\s*$', content):
        reasons.append('закрытый криптографический ключ')
    if re.search(rb'(?<![A-Za-z0-9_])[0-9]{5,20}:[A-Za-z0-9_-]{30,100}(?![A-Za-z0-9_-])', content):
        reasons.append('потенциальный токен Telegram независимо от имени файла')
    return reasons


def check_index(root: Path) -> list[tuple[str, list[str]]]:
    """Читает blob из индекса, не подменяя его незакоммиченным файлом на диске."""
    paths = subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode('utf-8').split('\0')
    found = []
    # cat-file --batch читает все blob одним процессом вместо процесса на файл.
    with subprocess.Popen(['git', 'cat-file', '--batch'], cwd=root,
                          stdin=subprocess.PIPE, stdout=subprocess.PIPE) as git:
        for path in filter(None, paths):
            git.stdin.write((':' + path + '\n').encode('utf-8'))
            git.stdin.flush()
            header = git.stdout.readline().decode('utf-8').rstrip('\n')
            if header.endswith(' missing'):
                found.append((path, ['не удалось прочитать файл индекса']))
                continue
            _, kind, size = header.split()
            content = git.stdout.read(int(size))
            assert git.stdout.read(1) == b'\n'
            reasons = violations(path, content)
            if reasons:
                found.append((path, reasons))
        git.stdin.close()
        if git.wait() != 0:
            raise RuntimeError('git cat-file failed')
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--staged', action='store_true', help='Совместимость с pre-commit; индекс проверяется всегда.')
    parser.parse_args()
    root = Path(subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], text=True).strip())
    found = check_index(root)
    if found:
        print('ОШИБКА: в Git-индексе обнаружены локальные данные/артефакты:')
        for path, reasons in found:
            print(f'  {path}: {"; ".join(reasons)}')
        print('Уберите файл только из индекса: git rm --cached -- <путь>. Рабочий файл сохраняйте.')
        return 1
    print('Git-индекс CRM: базы, секретные файлы и локальные артефакты не обнаружены.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
