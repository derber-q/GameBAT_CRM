import tempfile
from pathlib import Path
import unittest
import uuid

from .store import Store, UpdateError


class UpdateStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name).resolve()/'updates.sqlite3')
        self.store.initialize()

    def test_idempotency_and_exclusive_operation(self):
        request = uuid.uuid4()
        self.store.enqueue('check', 1, request)
        self.store.enqueue('check', 1, request)
        self.assertEqual(len(self.store.operations()), 1)
        for args in [('check', 2, request), ('install', 1, request), ('check', 1, uuid.uuid4())]:
            with self.assertRaises(UpdateError):
                self.store.enqueue(*args)
        operation = self.store.queued()
        self.store.stage(operation, 'done', finished=True)
        self.store.enqueue('check', 1, uuid.uuid4())

    def test_interrupted_install_is_never_automatically_repeated(self):
        self.store.enqueue('install', 1, uuid.uuid4(), 'a'*40)
        self.store.stage(self.store.queued(), 'switching')
        self.store.interrupt_started()
        self.assertIsNone(self.store.queued())
        self.assertTrue(self.store.get('recovery_required'))
        self.assertEqual(self.store.operations()[0]['state'], 'interrupted')
        with self.assertRaises(UpdateError):
            self.store.enqueue('install', 1, uuid.uuid4(), 'a'*40)

    def test_command_and_sha_injection_are_rejected(self):
        for action, target in [('shell', ''), ('install', '--upload-pack=evil'), ('install', '../main')]:
            with self.assertRaises(UpdateError):
                self.store.enqueue(action, 1, uuid.uuid4(), target)
        with self.assertRaises(UpdateError):
            self.store.initialize()
