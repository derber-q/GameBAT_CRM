"""Фиксированный rootless Compose-адаптер. Все пути задаёт администратор сервера."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import ssl
import subprocess
import tarfile
import time
import urllib.request
import uuid

from . import IMAGE, SOURCE
from .github import NoRedirect
from .store import UpdateError, sha, now

SERVICES = ('web', 'supervisor')


def digest_file(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def image_reference(value):
    if not isinstance(value, str) or not re.fullmatch(re.escape(IMAGE)+r'@sha256:[a-f0-9]{64}', value):
        raise UpdateError('Образ должен быть из разрешённого GHCR и закреплён по digest.')
    return value


class Runner:
    def __init__(self):
        self.docker = shutil.which('docker')
        if not self.docker:
            raise UpdateError('Docker CLI недоступен менеджеру.')

    def run(self, args, *, input_file=None, output_file=None, timeout=300):
        try:
            result = subprocess.run([self.docker, *args], stdin=input_file, stdout=output_file or subprocess.PIPE,
                                    stderr=subprocess.PIPE, timeout=timeout, check=False)
        except (OSError, subprocess.TimeoutExpired):
            raise UpdateError('Серверная команда не завершилась в установленный срок.') from None
        if result.returncode:
            # stdout/stderr могут содержать окружение или секреты драйверов. Не журналируем их.
            raise UpdateError(f'Серверная команда завершилась с кодом {result.returncode}.')
        return result.stdout or b''


class DockerBackend:
    def __init__(self, config, runner=None):
        self.config = config
        self.root = Path(config['root'])
        self.shared = Path(config['shared_dir'])
        self.compose_file = Path(config['compose_file'])
        self.runner = runner or Runner()

    def compose(self, release=None):
        args = ['compose', '-p', self.config['project'], '-f', str(self.compose_file)]
        if release:
            args += ['-f', str(self.release_files(release))]
        return args

    def verify_runtime(self):
        info = json.loads(self.runner.run(['info', '--format', '{{json .SecurityOptions}}']))
        if not any('rootless' in value for value in info):
            raise UpdateError('Менеджер поддерживает только отдельный rootless Docker.')
        compose = json.loads(self.runner.run([*self.compose(),'config','--format','json']))
        for service in SERVICES:
            item = compose['services'][service]
            if (item.get('build') or item.get('privileged') or item.get('devices') or item.get('pid')=='host'
                    or item.get('network_mode')=='host' or str(item.get('user'))!='10001:10001'
                    or not item.get('read_only') or item.get('cap_add') or 'ALL' not in item.get('cap_drop',[])
                    or not any(value in ('no-new-privileges','no-new-privileges:true') for value in item.get('security_opt',[]))):
                raise UpdateError('Production Compose не соответствует ограничениям сервиса '+service+'.')
            for volume in item.get('volumes',[]):
                source = Path(volume.get('source','')).resolve()
                if volume.get('type')!='bind' or not (source.is_relative_to(self.shared) or
                        (service=='web' and source in (self.root/'gateway.sock',self.root/'public'))):
                    raise UpdateError('Web/worker не должны получать Docker socket, код хоста или служебные файлы менеджера.')
                if source in (self.root/'gateway.sock',self.root/'public') and not volume.get('read_only'):
                    raise UpdateError('Состояние и канал менеджера монтируются read-only.')

    def inspect_image(self, release):
        reference = image_reference(release.get('image'))
        commit = sha(release.get('sha'))
        info = json.loads(self.runner.run(['image', 'inspect', reference]))[0]
        labels = info['Config'].get('Labels') or {}
        schema = labels.get('com.resource.schema', '')
        if (labels.get('org.opencontainers.image.revision') != commit or
                labels.get('org.opencontainers.image.source') != SOURCE or
                not re.fullmatch('[a-f0-9]{64}', schema)):
            raise UpdateError('Источник, коммит или схема образа не подтверждены.')
        return {**release, 'schema': schema}

    def running(self):
        versions = []
        for service in SERVICES:
            container = self.runner.run([*self.compose(), 'ps', '-q', service]).decode().strip()
            if not re.fullmatch('[a-f0-9]{12,64}', container):
                raise UpdateError('Не найден единственный рабочий контейнер '+service+'.')
            info = json.loads(self.runner.run(['container', 'inspect', container]))[0]
            if not info['State']['Running']:
                raise UpdateError('Рабочий контейнер остановлен.')
            env = dict(value.split('=',1) for value in info['Config'].get('Env',[]) if '=' in value)
            if env.get('GAMEBAT_ENV') != 'production':
                raise UpdateError('Установка предназначена только для production.')
            versions.append(self.inspect_image({'sha':env.get('GAMEBAT_RELEASE_SHA'), 'image':info['Config']['Image']}))
        if len({(item['sha'], item['image'], item['schema']) for item in versions}) != 1:
            raise UpdateError('Версии web и supervisor различаются. Требуется проверка сервера.')
        return versions[0]

    def release_files(self, release):
        commit, image = sha(release['sha']), image_reference(release['image'])
        directory = self.root/'releases'/commit
        if directory.resolve() != directory or directory.is_symlink():
            raise UpdateError('Перенаправление каталога версии запрещено.')
        directory.mkdir(parents=True, exist_ok=True)
        manifest = directory/'release.json'
        if manifest.exists():
            saved = json.loads(manifest.read_text('utf-8'))
            if saved['image'] != image or saved['schema'] != release['schema']:
                raise UpdateError('Сохранённая версия с этим SHA имеет другой образ или схему.')
        else:
            manifest.write_text(json.dumps(release), encoding='utf-8')
        override = directory/'image.compose.json'
        if not override.exists():
            override.write_text(json.dumps({'services': {service: {'image':image,
                'environment':{'GAMEBAT_RELEASE_SHA':commit}} for service in SERVICES}}), encoding='utf-8')
        elif json.loads(override.read_text('utf-8')) != {'services': {service: {'image':image,
                'environment':{'GAMEBAT_RELEASE_SHA':commit}} for service in SERVICES}}:
            raise UpdateError('Файл переключения версии изменён.')
        return override

    def prepare(self, candidate, current, *, rollback=False):
        actual = self.running()
        if any(actual[key] != current.get(key) for key in ('sha','image','schema')):
            raise UpdateError('Рабочая версия не совпадает с журналом. Требуется сверка состояния.')
        self.runner.run([*self.compose(),'exec','-T','web','python','-m','deployment.schema_check'])
        reference = image_reference(candidate['image'])
        if not rollback:
            self.runner.run(['pull', reference], timeout=900)
        release = self.inspect_image(candidate)
        if release['schema'] != actual['schema']:
            raise UpdateError('Версия содержит изменения миграций. Нужен проверенный процесс миграций этапа B; установка заблокирована.')
        self.release_files(release)
        return release

    def preflight(self, release):
        # Нет host mount, реальных секретов, сети, Docker socket и привилегий.
        self.runner.run(['run','--rm','--network','none','--read-only','--cap-drop','ALL',
            '--security-opt','no-new-privileges:true','--user','10001:10001','--pids-limit','128',
            '--memory','1g','--cpus','2','--tmpfs','/tmp:rw,nosuid,nodev,size=256m',
            image_reference(release['image']),'python','-m','deployment.candidate'], timeout=300)

    def stop(self):
        self.runner.run([*self.compose(), 'stop', '--timeout', '300', *SERVICES], timeout=660)
        for service in SERVICES:
            active = self.runner.run([*self.compose(), 'ps', '--status','running','-q',service]).strip()
            if active:
                raise UpdateError('Пишущие процессы не остановились. Переключение запрещено.')

    def backup(self, operation_id):
        operation_id = str(uuid.UUID(operation_id))
        directory = self.root/'backups'/operation_id
        if directory.resolve() != directory:
            raise UpdateError('Перенаправление каталога копии запрещено.')
        directory.mkdir(parents=True, exist_ok=False, mode=0o700)
        dump = directory/'postgres.dump'
        with dump.open('xb') as output:
            self.runner.run([*self.compose(),'exec','-T','postgres','pg_dump','--format=custom','--no-owner','--no-acl',
                             '--username',self.config['database_user'],self.config['database_name']], output_file=output, timeout=900)
            output.flush(); os.fsync(output.fileno())
        with dump.open('rb') as header:
            valid = header.read(5)==b'PGDMP'
        if dump.stat().st_size < 5 or not valid:
            raise UpdateError('Копия PostgreSQL не распознана.')
        with dump.open('rb') as source:
            self.runner.run([*self.compose(),'exec','-T','postgres','pg_restore','--list'], input_file=source)
        archive = directory/'shared.tar.gz'
        files = 0
        with tarfile.open(archive,'x:gz') as stream:
            for path in sorted(self.shared.rglob('*')):
                if path.is_symlink() or not (path.is_file() or path.is_dir()):
                    raise UpdateError('В shared обнаружена ссылка или специальный файл. Резервирование остановлено.')
                stream.add(path, arcname=str(path.relative_to(self.shared)), recursive=False)
                files += int(path.is_file())
        with tarfile.open(archive,'r:gz') as stream:
            for member in stream:
                if member.isfile():
                    with stream.extractfile(member) as source:
                        while source.read(1024*1024): pass
        manifest = {'verified':True,'path':str(directory),'postgres_sha256':digest_file(dump),
                    'shared_sha256':digest_file(archive),'shared_files':files,'at':now()}
        (directory/'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        return manifest

    def activate(self, release):
        self.inspect_image(release)
        self.runner.run([*self.compose(release),'up','-d','--no-deps','--force-recreate',*SERVICES], timeout=660)

    def health(self, release):
        url = self.config['health_origin']+'/crm/update-health/'
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
            urllib.request.HTTPSHandler(context=ssl.create_default_context()), NoRedirect())
        deadline = time.monotonic()+120
        while time.monotonic() < deadline:
            try:
                with opener.open(url, timeout=5) as response:
                    data = json.loads(response.read(16384))
                if data.get('status')=='ok' and data.get('sha')==release['sha'] and data.get('environment')=='production':
                    return
            except (OSError, ValueError, UpdateError):
                pass
            time.sleep(2)
        raise UpdateError('Работоспособность версии не подтверждена. Успех установки не зафиксирован.')
