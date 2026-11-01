import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
import uuid

from .gateway import Gateway, request, submit
from .store import Store, UpdateError


class GatewayRequestTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name).resolve()
        self.store=Store(self.root/'updates.sqlite3');self.store.initialize()

    def test_only_fixed_request_schema_is_accepted(self):
        payload={'action':'check','actor':1,'request_id':str(uuid.uuid4()),'target':''}
        for value in ({**payload,'command':'git pull'},{**payload,'action':'shell'},
                      {**payload,'target':'main'},{**payload,'actor':'anonymous'}):
            with self.assertRaises(UpdateError):request(self.store,value)
        self.assertFalse(self.store.operations())
        request(self.store,payload)
        self.assertEqual(len(self.store.operations()),1)

    @unittest.skipUnless(os.name=='posix','Проверка Unix peer credentials выполняется в Linux.')
    def test_real_unix_socket_queues_once_and_rejects_other_uid(self):
        path=self.root/'gateway.sock'
        with Gateway(path,self.store,os.geteuid()) as server:
            thread=threading.Thread(target=server.serve_forever);thread.start()
            try:
                payload={'action':'check','actor':1,'request_id':str(uuid.uuid4()),'target':''}
                self.assertEqual(submit(path,payload),submit(path,payload))
                server.uid=os.geteuid()+1
                with self.assertRaises(UpdateError):submit(path,payload)
            finally:
                server.shutdown();thread.join()
