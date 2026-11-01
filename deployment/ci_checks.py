"""Запуск обязательных проверок кандидата, только с искусственными CI-настройками."""
import argparse
import multiprocessing
import os
import py_compile
from pathlib import Path
import subprocess
import sys


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--postgres',action='store_true')
    args=parser.parse_args()
    paths=subprocess.check_output(['git','ls-files','-z'],text=True).split('\0')
    for path in paths:
        if path.endswith('.py'):
            py_compile.compile(path,doraise=True)
    os.environ['DJANGO_SETTINGS_MODULE']='deployment.ci_postgres_settings' if args.postgres else 'deployment.ci_sqlite_settings'
    if os.name=='posix':
        multiprocessing.set_start_method('fork',force=True)
    from django.core.management import execute_from_command_line
    for command in (['check'],['makemigrations','--check','--dry-run'],['test','--parallel','4','--noinput']):
        execute_from_command_line(['manage.py',*command])
    if not args.postgres:
        for path in paths:
            if Path(path).name.startswith('test_') and path.endswith('.cjs'):
                subprocess.run(['node',path],check=True)
        for script in ('check_repository.py','check_project_links.py','build_technical_reference.py'):
            subprocess.run([sys.executable,'scripts/'+script,*(['--check'] if script.startswith('build_') else [])],check=True)


if __name__=='__main__':main()
