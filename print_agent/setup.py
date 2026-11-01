"""Создаёт локальный секрет; сервер получает только публичные параметры регистрации."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import uuid

from .__main__ import default_config
from .transport import server_origin


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server-url',required=True)
    parser.add_argument('--printer',required=True)
    parser.add_argument('--name',default='ReSOURCE Xprinter')
    parser.add_argument('--config',type=Path,default=default_config())
    parser.add_argument('--register-docker')
    parser.add_argument('--rotate',action='store_true')
    args=parser.parse_args()
    if os.environ.get('GAMEBAT_ENV')=='local_test':
        raise SystemExit('local_test: регистрация настоящего агента запрещена.')
    origin=server_origin(args.server_url)
    config=json.loads(args.config.read_text('utf-8-sig')) if args.config.exists() else {}
    config.update(server_url=origin,printer_name=args.printer)
    config['agent_id']=config.get('agent_id') or str(uuid.uuid4())
    if args.rotate or not config.get('token'):
        config['token']=secrets.token_urlsafe(48)
    registration={'id':config['agent_id'],'name':args.name,'printer_name':args.printer,
                  'token_hash':hashlib.sha256(config['token'].encode()).hexdigest()}
    if args.register_docker:
        if not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]*',args.register_docker):
            raise SystemExit('Неверное имя контейнера.')
        subprocess.run(['docker','exec','-i',args.register_docker,'python','manage.py','register_print_agent'],
                       input=json.dumps(registration),text=True,encoding='utf-8',check=True)
    args.config.parent.mkdir(parents=True,exist_ok=True)
    temporary=args.config.with_suffix('.tmp')
    temporary.write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
    temporary.chmod(0o600)
    temporary.replace(args.config)
    (args.config.parent/'registration.json').write_text(json.dumps(registration,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Конфигурация агента сохранена. Токен не выводится; registration.json содержит только публичные параметры.')


if __name__=='__main__':
    main()
