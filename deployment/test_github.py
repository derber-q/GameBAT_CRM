import unittest
from . import CI_CONTEXT, IMAGE
from .github import GitHub
from .store import UpdateError


class GitHubMetadataTests(unittest.TestCase):
    def setUp(self):
        self.status = {'context': CI_CONTEXT, 'state': 'success', 'description': 'sha256:'+'1'*64,
                       'creator': {'login': 'github-actions[bot]'}}
        self.paths = []
        self.github = GitHub()
        def read(path):
            self.paths.append(path)
            if path.startswith('/compare/'):return {'commits':[{'sha':'b'*40,'commit':{'message':'Test release'}}]}
            return {'sha':'b'*40,'commit':{'message':'Test release'}} if path=='/commits/main' else [self.status]
        self.github.read = read

    def test_pins_sha_and_digest_from_successful_ci(self):
        latest = self.github.latest({'sha':'a'*40})
        self.assertTrue(latest['approved'])
        self.assertEqual(latest['image'], IMAGE+'@sha256:'+'1'*64)
        self.assertEqual(self.paths, ['/commits/main','/commits/'+'b'*40+'/statuses','/compare/'+'a'*40+'...'+'b'*40])
        self.github.verify(latest)
        self.assertNotEqual(self.paths[-1], '/commits/main')

    def test_missing_failed_or_foreign_ci_cannot_approve(self):
        for changes in ({'state':'pending'}, {'state':'failure'}, {'description':'latest'},
                        {'creator':{'login':'someone'}}, {'context':'unrelated'}):
            before = self.status.copy()
            self.status.update(changes)
            self.assertFalse(self.github.latest({})['approved'])
            self.status = before

    def test_changed_artifact_and_invalid_commit_are_rejected(self):
        latest = self.github.latest({})
        self.status['description'] = 'sha256:'+'2'*64
        with self.assertRaises(UpdateError): self.github.verify(latest)
        self.github.read = lambda path: {'sha':'--exec=evil','commit':{'message':'bad'}}
        with self.assertRaises(UpdateError): self.github.latest({})

    def test_failed_new_run_overrides_older_success(self):
        self.github.read=lambda path:[{**self.status,'state':'failure'},self.status]
        self.assertFalse(self.github.artifact('b'*40))
