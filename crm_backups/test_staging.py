from datetime import datetime,timezone,timedelta
import json
from pathlib import Path
import tempfile
import unittest
from .staging import mark,expire,MARKER


class StagingCleanupTests(unittest.TestCase):
    def test_only_owned_expired_staging_is_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            old=root/'resource-snapshot-owned';old.mkdir();mark(old);(old/'secret.tmp').write_bytes(b'artificial')
            value=json.loads((old/MARKER).read_text());value['created_at']=(datetime.now(timezone.utc)-timedelta(days=2)).isoformat()
            (old/MARKER).write_text(json.dumps(value))
            unknown=root/'resource-snapshot-foreign';unknown.mkdir();(unknown/'keep').write_text('keep')
            fresh=root/'resource-snapshot-fresh';fresh.mkdir();mark(fresh)
            backup=root/'current_state_20261031.sqlite3';backup.write_bytes(b'protected artificial fixture')
            self.assertEqual(expire(root),[old.name])
            self.assertTrue(unknown.exists());self.assertTrue(fresh.exists());self.assertTrue(backup.exists())
