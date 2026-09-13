import importlib.util
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('toggle', Path(__file__).resolve().parents[1] / 'skills/t3/scripts/t3.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class ToggleTests(unittest.TestCase):
    def test_missing_and_conflicting_identity(self):
        for env in ({}, {'CODEX_THREAD_ID':'a','CODEX_SESSION_ID':'b'}, {'CODEX_THREAD_ID':'../a'}):
            with patch.dict(os.environ, env, clear=True), self.assertRaises(m.T3Error): m.identity()

    def test_markers_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            data=Path(tmp)
            for enabled in [True, False, True]:
                m.marker(data,'id',enabled)
                self.assertEqual((data/'registrations/id.thread').exists(),enabled)
                self.assertEqual((data/'registrations/id.unshared').exists(),not enabled)

    def test_archived_registration_is_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            data=Path(tmp);m.marker(data,'id',True)
            self.assertFalse(m.state(data,'id',dict(archived=True,deleted=False,status='stopped'))['enabled'])

    def test_enable_unarchives_and_verifies(self):
        with tempfile.TemporaryDirectory() as tmp:
            data=Path(tmp);row=dict(threadId='t3-id',archived=True,deleted=False,status='stopped')
            class Client:
                def request(self,*args): pass
                def unarchive(self,tid):
                    assert tid=='t3-id'
                    row.update(archived=False,status='running')
            with patch.object(m,'record',return_value=row), patch.object(m,'require_shared_owner'):
                self.assertTrue(m.run('on',data,'id',Client())['attached'])

    def test_timeout_does_not_claim_success_or_undo_intent(self):
        with tempfile.TemporaryDirectory() as tmp:
            data=Path(tmp)
            class Client:
                def request(self,*args): pass
            with patch.object(m,'record',return_value=None), patch.object(m,'require_shared_owner'), self.assertRaises(m.T3Error):
                m.run('on',data,'id',Client(),timeout=0)
            self.assertTrue((data/'registrations/id.thread').exists())

if __name__=='__main__': unittest.main()
