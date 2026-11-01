"""Самостоятельный пакет менеджера: без Django, БД, конфигурации установки и секретов."""
import argparse
from pathlib import Path
import shutil
import zipfile

ROOT=Path(__file__).resolve().parent.parent
MODULES=('__init__','__main__','docker_backend','gateway','github','manager','store')


def package(target):
    target=target.resolve()
    if not target.is_relative_to(ROOT/'outputs') or target.exists() or target.with_suffix('.zip').exists():
        raise ValueError('Нужен новый каталог внутри outputs и новое имя архива.')
    target.mkdir(parents=True)
    for name in MODULES:
        destination=target/'deployment'/f'{name}.py'
        destination.parent.mkdir(exist_ok=True)
        shutil.copy2(ROOT/'deployment'/f'{name}.py',destination)
    for name,target_name in (('README.manager.md','README.md'),('manager.example.json','manager.example.json'),
                             ('resource-updater.service','resource-updater.service')):
        shutil.copy2(ROOT/'deploy/updater'/name,target/target_name)
    with zipfile.ZipFile(target.with_suffix('.zip'),'x',zipfile.ZIP_DEFLATED) as stream:
        for path in sorted(target.rglob('*')):
            if path.is_file():stream.write(path,path.relative_to(target).as_posix())
    print('Пакет менеджера без рабочих данных: '+str(target.with_suffix('.zip')))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('target',type=Path)
    package(parser.parse_args().target)
