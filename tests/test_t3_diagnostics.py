import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('diagnostics', Path(__file__).resolve().parents[1]/'skills/t3/scripts/diagnose.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class DiagnosticsTests(unittest.TestCase):
    def test_report_correlates_stale_request_without_content_or_database_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            path = data/'t3/userdata/state.sqlite'
            path.parent.mkdir(parents=True)
            db = sqlite3.connect(path)
            db.executescript('''CREATE TABLE projection_threads(thread_id, archived_at, deleted_at, pending_approval_count, pending_user_input_count);
                CREATE TABLE provider_session_runtime(thread_id, status, last_seen_at, resume_cursor_json);
                CREATE TABLE projection_thread_activities(activity_id, thread_id, kind, created_at, payload_json, turn_id);
                INSERT INTO projection_threads VALUES ('t3-one',NULL,NULL,0,0);
                INSERT INTO provider_session_runtime VALUES ('t3-one','stopped','2026-09-21','{"threadId":"native-one"}');''')
            for i, kind, payload in [(1,'user-input.requested',{'requestId':'req-one','questions':['private question'],'responseMode':'message'}),
                                     (2,'provider.user-input.respond.failed',{'requestId':'req-one','detail':'Stale pending user-input request: private details'})]:
                db.execute('INSERT INTO projection_thread_activities VALUES (?,?,?,?,?,?)',(str(i),'t3-one',kind,f'2026-09-21T00:00:0{i}Z',json.dumps(payload),'turn-one'))
            db.commit(); db.close()
            before = path.read_bytes()
            result = m.snapshot(data, 'native-one')
            self.assertEqual(result['threads'][0]['pendingRequests'], [])
            self.assertTrue(result['threads'][0]['recentRequestEvents'][-1]['staleCallback'])
            self.assertNotIn('private', json.dumps(result))
            self.assertEqual(before,path.read_bytes())
            self.assertEqual(m.snapshot(data,'different')['threads'][0]['runtime'],'absent')


if __name__ == '__main__': unittest.main()
