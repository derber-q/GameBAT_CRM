"""Подготовленный адаптер pg_dump. Пока не допущен к созданию полных копий.

Для PostgreSQL отдельно требуется согласованность медиа с MVCC-снимком и реальное
испытание восстановления. Этот низкоуровневый dump не объявляется полной копией.
"""
import os
import subprocess


def dump_database(config, destination, *, timeout=600):
    if destination.exists(): raise ValueError('Файл уже существует.')
    env = {**os.environ, 'PGPASSWORD': config.get('PASSWORD', '')}
    command = ['pg_dump', '--format=custom', '--no-owner', '--no-acl', '--file', str(destination),
               '--dbname', config['NAME'], '--username', config['USER']]
    if config.get('HOST'): command += ['--host', config['HOST']]
    if config.get('PORT'): command += ['--port', str(config['PORT'])]
    result = subprocess.run(command, env=env, capture_output=True, timeout=timeout)
    if result.returncode or not destination.is_file() or destination.stat().st_size < 5:
        raise ValueError('pg_dump не завершён; файл не готов к восстановлению.')
    with destination.open('rb') as stream:
        if stream.read(5) != b'PGDMP': raise ValueError('Неверный формат pg_dump.')
