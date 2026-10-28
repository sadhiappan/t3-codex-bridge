import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('toggle_observation', Path(__file__).resolve().parents[1] / 'skills/t3/scripts/t3.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class ObservabilityTests(unittest.TestCase):
    def test_failed_attempt_has_correlated_start_and_failure_without_exception_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            class Client:
                def request(self, *args):
                    raise ValueError('secret-value-should-never-appear')
            with self.assertRaises(ValueError):
                m.run('on', data, 'native-id', Client())
            rows = [json.loads(line) for line in (data/'diagnostics/lifecycle.jsonl').read_text().splitlines()]
            self.assertEqual([r['event'] for r in rows], ['toggle.started', 'toggle.failed'])
            self.assertEqual(rows[0]['operationId'], rows[1]['operationId'])
            self.assertNotIn('secret-value', json.dumps(rows))
            self.assertEqual(rows[1]['errorType'], 'ValueError')

    def test_timeout_records_intent_and_observed_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            class Client:
                def request(self, *args): pass
            with patch.object(m, 'record', return_value=None), patch.object(m, 'require_shared_owner'), self.assertRaises(m.T3Error):
                m.run('on', data, 'native-id', Client(), timeout=0)
            rows = [json.loads(line) for line in (data/'diagnostics/lifecycle.jsonl').read_text().splitlines()]
            self.assertIn('toggle.intent', [r['event'] for r in rows])
            self.assertEqual(rows[-1]['event'], 'toggle.failed')
            self.assertEqual(rows[-2]['state']['attached'], False)
            self.assertEqual((data/'diagnostics/lifecycle.jsonl').stat().st_mode & 0o777, 0o600)

    def test_repeated_enable_refreshes_explicit_attach_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            m.marker(data, 'native-id', True)
            path = data/'registrations/native-id.thread'
            import os
            os.utime(path, (1, 1))
            m.marker(data, 'native-id', True)
            self.assertGreater(path.stat().st_mtime, 1)

    def test_rotation_is_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            with patch.object(m, 'AUDIT_MAX_BYTES', 1):
                for _ in range(8): m.audit(data, 'op', 'native-id', 'test')
            self.assertEqual(len(list((data/'diagnostics').glob('lifecycle.jsonl*'))), 4)


if __name__ == '__main__': unittest.main()
