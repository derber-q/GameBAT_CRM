"""Проверки очереди без настоящего Docker, GitHub, БД CRM и маркетплейсов."""
import tempfile
from pathlib import Path
import unittest
import uuid

from .store import Store, UpdateError
from .manager import Manager

OLD = {'sha': 'a'*40, 'image': 'old@sha256:'+'1'*64, 'schema': 'f'*64}
NEW = {'sha': 'b'*40, 'image': 'new@sha256:'+'2'*64, 'schema': 'f'*64, 'approved': True}


class Backend:
    def __init__(self):
        self.calls = []
        self.failure = ''

    def call(self, name):
        self.calls.append(name)
        if self.failure == name:
            raise UpdateError('Проверка не пройдена.')

    def prepare(self, candidate, current, *, rollback=False):
        self.call('prepare')
        if candidate['schema'] != current['schema']:
            raise UpdateError('Миграции требуют отдельного процесса.')
        return candidate.copy()

    def preflight(self, release): self.call('preflight')
    def stop(self): self.call('stop')
    def backup(self, operation):
        self.call('backup')
        return {'verified': True, 'path': 'private-snapshot'}
    def activate(self, release): self.call('activate:'+release['sha'][0])
    def health(self, release): self.call('health:'+release['sha'][0])


class GitHub:
    def __init__(self): self.calls = 0
    def latest(self, current):
        self.calls += 1
        return NEW.copy()
    def verify(self, candidate): self.calls += 1


class DeploymentManagerTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.store = Store(Path(tmp.name).resolve()/'operations.sqlite3')
        self.store.initialize()
        self.store.set('current', OLD)
        self.store.set('latest', NEW)
        self.backend, self.github = Backend(), GitHub()
        self.manager = Manager(self.store, self.github, self.backend)

    def request(self, action='install', target=NEW['sha']):
        self.store.enqueue(action, 1, uuid.uuid4(), target if action != 'check' else '')
        self.manager.tick()

    def test_idle_does_not_check_or_install_even_with_new_version(self):
        for _ in range(3): self.manager.tick()
        self.assertEqual(self.github.calls, 0)
        self.assertEqual(self.backend.calls, [])

    def test_check_only_fetches_metadata_and_never_deploys(self):
        self.request('check')
        self.assertEqual(self.github.calls, 1)
        self.assertEqual(self.backend.calls, [])
        self.assertEqual(self.store.get('current'), OLD)

    def test_install_checks_then_stops_backs_up_switches_and_confirms(self):
        self.request()
        self.assertEqual(self.backend.calls, ['prepare','preflight','stop','backup','activate:b','health:b'])
        self.assertEqual(self.store.get('current')['sha'], NEW['sha'])
        self.assertEqual(self.store.get('rollback')['sha'], OLD['sha'])
        self.assertEqual(self.store.operations()[0]['state'], 'done')

    def test_unhealthy_candidate_recovers_code_without_restoring_database(self):
        self.backend.failure = 'health:b'
        self.request()
        self.assertEqual(self.backend.calls[-2:], ['activate:a','health:a'])
        self.assertEqual(self.store.get('current')['sha'], OLD['sha'])
        self.assertEqual(self.store.operations()[0]['state'], 'error')

    def test_schema_change_is_blocked_before_downtime(self):
        self.store.set('latest', {**NEW, 'schema': 'e'*64})
        self.request()
        self.assertEqual(self.backend.calls, ['prepare'])
        self.assertEqual(self.store.get('current'), OLD)

    def test_backup_failure_starts_old_code_without_switching_new(self):
        self.backend.failure = 'backup'
        self.request()
        self.assertNotIn('activate:b', self.backend.calls)
        self.assertEqual(self.backend.calls[-2:], ['activate:a','health:a'])

    def test_rollback_only_to_compatible_saved_version(self):
        self.request()
        self.backend.calls.clear()
        self.request('rollback', OLD['sha'])
        self.assertEqual(self.store.get('current')['sha'], OLD['sha'])
        self.assertEqual(self.backend.calls[-2:], ['activate:a','health:a'])

    def test_forged_or_unapproved_target_does_not_call_docker(self):
        self.request(target='c'*40)
        self.assertEqual(self.backend.calls, [])
        self.store.set('latest', {**NEW, 'approved': False})
        self.request()
        self.assertEqual(self.backend.calls, [])

    def test_failed_recovery_blocks_further_installations(self):
        def fail_health(release):raise UpdateError('Нет подтверждения запуска.')
        self.backend.health=fail_health
        self.request()
        self.assertTrue(self.store.get('recovery_required'))
        with self.assertRaises(UpdateError):self.store.enqueue('install',1,uuid.uuid4(),NEW['sha'])
