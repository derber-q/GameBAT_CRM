"""Сведения установленного образа или базового Git HEAD; без git subprocess и сети."""
import os
from pathlib import Path
import re


def current_version(base_dir):
    value = os.environ.get('GAMEBAT_RELEASE_SHA', '')
    if re.fullmatch('[a-f0-9]{40}', value):
        return {'sha': value, 'ref': 'main'}
    git = Path(base_dir) / '.git'
    if not git.is_dir() or git.is_symlink():
        return {'sha': '', 'ref': ''}
    try:
        head = (git / 'HEAD').read_text('ascii').strip()
        ref = ''
        if head.startswith('ref: refs/heads/'):
            name = head[5:]
            path = git / name
            if not path.resolve().is_relative_to(git.resolve()) or path.is_symlink():
                return {'sha': '', 'ref': ''}
            ref = name.removeprefix('refs/heads/')
            if path.is_file():
                head = path.read_text('ascii').strip()
            else:
                head = next((line.split(' ')[0] for line in (git/'packed-refs').read_text('ascii').splitlines()
                             if line.endswith(' '+name)), '')
        return {'sha': head if re.fullmatch('[a-f0-9]{40}', head) else '', 'ref': ref}
    except (OSError, UnicodeError):
        return {'sha': '', 'ref': ''}
