import json
from pathlib import Path
import tempfile
import unittest
import uuid

from . import IMAGE, SOURCE
from .docker_backend import DockerBackend
from .store import UpdateError

OLD = {'sha':'a'*40,'image':IMAGE+'@sha256:'+'1'*64,'schema':'f'*64}
NEW = {'sha':'b'*40,'image':IMAGE+'@sha256:'+'2'*64,'schema':'f'*64}


class FakeRunner:
    def __init__(self):
        self.calls=[]
        self.schema=NEW['schema']
        self.rootless=True
        self.compose={'services':{service:{'user':'10001:10001','read_only':True,'cap_drop':['ALL'],
            'security_opt':['no-new-privileges:true'],'volumes':[]} for service in ('web','supervisor')}}
    def run(self,args,**kwargs):
        self.calls.append(args)
        if args[0]=='info': return b'["name=rootless"]' if self.rootless else b'[]'
        if 'config' in args:return json.dumps(self.compose).encode()
        if args[:2]==['image','inspect']:
            new = args[2]==NEW['image']
            value = NEW if new else OLD
            return json.dumps([{'Config':{'Labels':{'org.opencontainers.image.revision':value['sha'],
                'org.opencontainers.image.source':SOURCE,'com.resource.schema':self.schema if new else OLD['schema']}}}]).encode()
        if args[:2]==['container','inspect']:
            return json.dumps([{'State':{'Running':True},'Config':{'Image':OLD['image'],
                'Env':['GAMEBAT_ENV=production','GAMEBAT_RELEASE_SHA='+OLD['sha']]}}]).encode()
        if 'ps' in args: return b'c'*64
        if 'pg_dump' in args:
            kwargs['output_file'].write(b'PGDMP-synthetic-dump')
        if 'pg_restore' in args:
            assert kwargs['input_file'].read().startswith(b'PGDMP')
        return b''


class DockerAdapterTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name).resolve()
        self.shared=self.root/'shared';self.shared.mkdir()
        self.runner=FakeRunner()
        self.backend=DockerBackend({'root':str(self.root/'manager'),'shared_dir':str(self.shared),
            'compose_file':str(self.root/'compose.yaml'),'project':'resource','database_user':'crm','database_name':'crm'},self.runner)

    def test_candidate_has_no_network_mounts_or_production_secrets(self):
        release=self.backend.prepare(NEW,OLD)
        self.backend.preflight(release)
        command=self.runner.calls[-1]
        self.assertIn('--read-only',command)
        self.assertEqual(command[command.index('--network')+1],'none')
        self.assertNotIn('--volume',command);self.assertNotIn('--mount',command)
        self.assertNotIn('--env-file',command)
        self.assertEqual(command[command.index('--user')+1],'10001:10001')

    def test_schema_change_and_shell_reference_fail_closed(self):
        self.runner.schema='e'*64
        with self.assertRaises(UpdateError): self.backend.prepare(NEW,OLD)
        with self.assertRaises(UpdateError): self.backend.prepare({**NEW,'image':'--privileged'},OLD)
        self.assertFalse(any('stop' in call or 'up' in call for call in self.runner.calls))

    def test_snapshot_preserves_files_and_only_lists_postgres_backup(self):
        (self.shared/'secret.key').write_text('synthetic-key',encoding='utf-8')
        backup=self.backend.backup(str(uuid.uuid4()))
        self.assertTrue(backup['verified'])
        self.assertEqual(backup['shared_files'],1)
        restore=next(call for call in self.runner.calls if 'pg_restore' in call)
        self.assertEqual(restore[-1],'--list')
        self.assertNotIn('--dbname',restore)
        self.assertEqual((self.shared/'secret.key').read_text('utf-8'),'synthetic-key')

    def test_release_override_is_immutable_and_only_restarts_fixed_services(self):
        self.backend.release_files(OLD)
        self.backend.activate(OLD)
        self.assertEqual(self.runner.calls[-1][-2:],['web','supervisor'])
        changed={**OLD,'image':NEW['image']}
        with self.assertRaises(UpdateError): self.backend.release_files(changed)

    def test_rootful_privileged_or_host_socket_runtime_is_rejected(self):
        self.backend.verify_runtime()
        self.runner.rootless=False
        with self.assertRaises(UpdateError):self.backend.verify_runtime()
        self.runner.rootless=True
        self.runner.compose['services']['web']['privileged']=True
        with self.assertRaises(UpdateError):self.backend.verify_runtime()
        del self.runner.compose['services']['web']['privileged']
        self.runner.compose['services']['web']['volumes']=[{'type':'bind','source':'/var/run/docker.sock'}]
        with self.assertRaises(UpdateError):self.backend.verify_runtime()
