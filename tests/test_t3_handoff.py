import importlib.util
import json
import os
from pathlib import Path
import pty
import select
import signal
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/t3/scripts'
SUPERVISOR = SCRIPTS / 'supervisor.py'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


m = load('toggle_handoff', SCRIPTS / 't3.py')
s = m.supervisor

# Stands in for the native binary: holds a rollout open like Codex does and plays one scripted scenario.
FAKE_CODEX = r'''#!%s
import json, os, signal, subprocess, sys, time
root, mode, sid = os.environ['FAKE_ROOT'], os.environ['FAKE_MODE'], 'sid-1'
record = lambda name, value: open(os.path.join(root, name), 'w').write(json.dumps(value))
record('launch', dict(argv=sys.argv[1:], pid=os.getpid(), ppid=os.getppid(), keep=os.environ.get('KEEP_ME'),
                      handoff={k: v for k, v in os.environ.items() if k.startswith('T3_HANDOFF_')}))
signal.signal(signal.SIGTERM, lambda *_: (record('sigterm', True), os._exit(143)) if 'trap' in mode else None)
if 'trap' not in mode: signal.signal(signal.SIGTERM, signal.SIG_DFL)
directory = os.path.join(root, 'home/sessions/2026/01/01'); os.makedirs(directory, exist_ok=True)
rollout = open(os.path.join(directory, 'rollout-2026-01-01T00-00-00-' + sid + '.jsonl'), 'a')
def event(kind, turn): rollout.write(json.dumps(dict(type='event_msg', payload=dict(type=kind, turn_id=turn))) + '\n'); rollout.flush()
def arm(session=sid):
    code = 'import sys; sys.path.insert(0, %%r); import supervisor; supervisor.arm(%%r)' %% (os.environ['FAKE_SCRIPTS'], session)
    result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True)
    record('arm', dict(code=result.returncode, error=result.stderr[-300:]))
event('task_started', 'turn-1')
if mode == 'exit5': sys.exit(5)
if mode == 'sigself': os.kill(os.getpid(), signal.SIGTERM); time.sleep(5)
if mode == 'killself': os.kill(os.getpid(), signal.SIGKILL)
if mode == 'stop': os.kill(os.getpid(), signal.SIGSTOP); sys.exit(0)
if mode == 'wait-term': time.sleep(20); sys.exit(0)
if mode == 'forged':
    forged = dict(nonce='0' * 64, sid=sid, child_pid=os.getpid(), child_start='x', rollout=rollout.name, turn_id='turn-1', requested_at=0)
    open(os.path.join(os.environ['T3_HANDOFF_DIR'], str(os.getpid()) + '.request'), 'w').write(json.dumps(forged)); sys.exit(0)
if mode == 'arm-foreign-session': arm('other-sid'); sys.exit(0)
arm()
if mode == 'arm-exit7': sys.exit(7)
if mode == 'arm-holder':
    subprocess.Popen(['/bin/sleep', '8'], stdout=rollout, stdin=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
event('task_complete', 'turn-1')
if mode == 'trap-new-turn': event('task_started', 'turn-2'); time.sleep(4.5)
if mode in ('trap-idle', 'trap-short-idle'): time.sleep(4.5 if mode == 'trap-short-idle' else 20)
sys.exit(0)
''' % sys.executable

STUB = '#!/bin/sh\nprintf "%s\\n" "$@" > "$FAKE_ROOT/{name}.args"\nenv > "$FAKE_ROOT/{name}.env"\n{body}\n'


class Harness(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(os.path.realpath(self.tmp.name))
        self.addCleanup(self.tmp.cleanup)
        self.script('codex', FAKE_CODEX)
        self.script('launcher', STUB.format(name='launcher', body='exit 42'))
        # The helper stub proves ordering: the native child must already be gone when it runs.
        self.script('helper', STUB.format(name='helper', body='kill -0 $(sed -E \'s/.*"pid": ([0-9]+).*/\\1/\' "$FAKE_ROOT/launch") 2>/dev/null && echo alive > "$FAKE_ROOT/helper.child"\nexit ${HELPER_EXIT:-0}'))

    def script(self, name, text):
        path = self.root / name
        path.write_text(text)
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
        return path

    def environment(self, mode, **extra):
        return dict({'PATH': '/usr/bin:/bin:/usr/sbin:/sbin', 'HOME': str(self.root), 'CODEX_HOME': str(self.root / 'home'),
                     'FAKE_ROOT': str(self.root), 'FAKE_MODE': mode, 'FAKE_SCRIPTS': str(SCRIPTS), 'KEEP_ME': 'kept value',
                     'T3_HANDOFF_DIR': str(self.root / 'handoff'), 'T3_HANDOFF_LAUNCHER': str(self.root / 'launcher'),
                     'T3_HANDOFF_HELPER': str(self.root / 'helper')}, **extra)

    def spawn(self, argv, env):
        pid, fd = pty.fork()
        if pid == 0:
            os.execve(argv[0], argv, env)
        return pid, fd

    def finish(self, pid, fd, timeout=25):
        deadline, output = time.monotonic() + timeout, b''
        while time.monotonic() < deadline:
            if select.select([fd], [], [], 0.1)[0]:
                try:
                    output += os.read(fd, 65536)
                except OSError:
                    pass
            done, status = os.waitpid(pid, os.WNOHANG)
            if done:
                os.close(fd)
                return status, output.decode(errors='replace')
        os.kill(pid, signal.SIGKILL)
        os.waitpid(pid, 0)
        self.fail('supervised launch did not finish in time')

    def supervise(self, mode, args=(), **extra):
        return self.finish(*self.spawn([sys.executable, str(SUPERVISOR), str(self.root / 'codex'), *args], self.environment(mode, **extra)))

    def read(self, name):
        path = self.root / name
        return path.read_text() if path.exists() else None

    def launch(self):
        return json.loads(self.read('launch'))


class SupervisorProcessTests(Harness):
    def test_ordinary_launch_preserves_argv_env_and_exit_code(self):
        status, _ = self.supervise('exit5', args=['--profile', 'yolo', 'two words'])
        launch = self.launch()
        self.assertEqual((os.WIFEXITED(status), os.WEXITSTATUS(status)), (True, 5))
        self.assertEqual(launch['argv'], ['--profile', 'yolo', 'two words'])
        self.assertEqual(launch['keep'], 'kept value')
        self.assertEqual(launch['handoff']['T3_HANDOFF_CHILD'], str(launch['pid']))
        self.assertEqual(len(launch['handoff']['T3_HANDOFF_NONCE']), 64)
        self.assertIsNone(self.read('launcher.args'))
        self.assertIsNone(self.read('helper.args'))

    def test_non_interactive_commands_are_not_supervised(self):
        pid, fd = self.spawn([sys.executable, str(SUPERVISOR), str(self.root / 'codex'), 'exec', 'hi'], self.environment('exit5'))
        status, _ = self.finish(pid, fd)
        launch = self.launch()
        self.assertEqual(os.WEXITSTATUS(status), 5)
        self.assertEqual(launch['pid'], pid)
        self.assertNotIn('T3_HANDOFF_NONCE', launch['handoff'])

    def test_child_signal_death_is_mirrored_without_handoff(self):
        status, _ = self.supervise('sigself')
        self.assertTrue(os.WIFSIGNALED(status))
        self.assertEqual(os.WTERMSIG(status), signal.SIGTERM)
        self.assertIsNone(self.read('launcher.args'))

    def test_sigkill_death_is_mirrored(self):
        status, _ = self.supervise('killself')
        self.assertEqual((os.WIFSIGNALED(status), os.WTERMSIG(status)), (True, signal.SIGKILL))

    def test_non_private_handoff_directory_falls_back_to_plain_launch(self):
        shared = self.root / 'shared'
        shared.mkdir(mode=0o755)
        pid, fd = self.spawn([sys.executable, str(SUPERVISOR), str(self.root / 'codex')], self.environment('exit5', T3_HANDOFF_DIR=str(shared)))
        status, _ = self.finish(pid, fd)
        self.assertEqual(os.WEXITSTATUS(status), 5)
        self.assertEqual(self.launch()['pid'], pid)
        self.assertEqual(stat.S_IMODE(shared.stat().st_mode), 0o755)

    def test_sigterm_to_supervisor_reaches_child(self):
        pid, fd = self.spawn([sys.executable, str(SUPERVISOR), str(self.root / 'codex')], self.environment('wait-term'))
        while self.read('launch') is None:
            time.sleep(0.05)
        time.sleep(0.3)
        os.kill(pid, signal.SIGTERM)
        status, _ = self.finish(pid, fd, timeout=10)
        self.assertEqual(os.WTERMSIG(status), signal.SIGTERM)

    def test_child_stop_suspends_the_job_and_continue_resumes_it(self):
        pid, fd = self.spawn([sys.executable, str(SUPERVISOR), str(self.root / 'codex')], self.environment('stop'))
        deadline = time.monotonic() + 10
        while not s.process_field(pid, 'stat').startswith('T'):
            self.assertLess(time.monotonic(), deadline, 'supervisor never mirrored the stop')
            time.sleep(0.1)
        os.kill(pid, signal.SIGCONT)
        status, _ = self.finish(pid, fd, timeout=10)
        self.assertEqual((os.WIFEXITED(status), os.WEXITSTATUS(status)), (True, 0))

    def test_armed_handoff_execs_shared_resume_only_after_child_is_gone(self):
        status, output = self.supervise('arm-exit0')
        self.assertEqual(json.loads(self.read('arm'))['code'], 0, self.read('arm'))
        self.assertEqual(os.WEXITSTATUS(status), 42)
        self.assertEqual(self.read('launcher.args').split(), ['--t3', 'resume', 'sid-1'])
        self.assertEqual(self.read('helper.args').split(), ['prepare-resume'])
        self.assertIn('CODEX_THREAD_ID=sid-1', self.read('helper.env'))
        self.assertIsNone(self.read('helper.child'), 'helper ran while the native child was still alive')
        self.assertNotIn('T3_HANDOFF_', self.read('launcher.env'))
        self.assertIn('KEEP_ME=kept value', self.read('launcher.env'))
        self.assertEqual(list((self.root / 'handoff').iterdir()), [])
        self.assertIn('reopening sid-1', output)

    def test_default_mode_never_signals_an_idle_armed_child(self):
        status, _ = self.supervise('trap-short-idle')
        self.assertIsNone(self.read('sigterm'))
        self.assertEqual(os.WEXITSTATUS(status), 42)

    def test_abnormal_exit_cancels_handoff_and_keeps_exit_code(self):
        status, output = self.supervise('arm-exit7')
        self.assertEqual(os.WEXITSTATUS(status), 7)
        self.assertIsNone(self.read('launcher.args'))
        self.assertIsNone(self.read('helper.args'))
        self.assertIn('codex --t3 resume sid-1', output)
        self.assertEqual(list((self.root / 'handoff').iterdir()), [])

    def test_forged_request_is_discarded(self):
        status, _ = self.supervise('forged')
        self.assertEqual(os.WEXITSTATUS(status), 0)
        self.assertIsNone(self.read('launcher.args'))
        self.assertEqual(list((self.root / 'handoff').iterdir()), [])

    def test_session_not_held_by_supervised_child_cannot_arm(self):
        status, _ = self.supervise('arm-foreign-session')
        self.assertNotEqual(json.loads(self.read('arm'))['code'], 0)
        self.assertIn('does not hold this session', json.loads(self.read('arm'))['error'])
        self.assertIsNone(self.read('launcher.args'))

    def test_remaining_writer_blocks_handoff(self):
        status, output = self.supervise('arm-holder')
        self.assertEqual(os.WEXITSTATUS(status), 0)
        self.assertIsNone(self.read('launcher.args'))
        self.assertIsNone(self.read('helper.args'))
        self.assertIn('still has this session open', output)

    def test_helper_refusal_blocks_handoff(self):
        status, _ = self.supervise('arm-exit0', HELPER_EXIT='3')
        self.assertEqual(os.WEXITSTATUS(status), 0)
        self.assertIsNone(self.read('launcher.args'))

    def test_opt_in_auto_end_signals_only_a_quiescent_child(self):
        status, _ = self.supervise('trap-idle', T3_HANDOFF_AUTO_END='1')
        self.assertEqual(self.read('sigterm'), 'true')
        self.assertEqual(os.WEXITSTATUS(status), 42)
        self.assertIsNone(self.read('helper.child'))
        self.assertNotIn('T3_HANDOFF_AUTO_END', self.launch()['handoff'])

    def test_opt_in_auto_end_holds_fire_when_a_new_turn_started(self):
        status, _ = self.supervise('trap-new-turn', T3_HANDOFF_AUTO_END='1')
        self.assertIsNone(self.read('sigterm'))
        self.assertEqual(os.WEXITSTATUS(status), 42)


class SafetyDecisionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(os.path.realpath(self.tmp.name))
        self.sessions = self.root / 'sessions'
        self.sessions.mkdir()
        self.rollout = self.sessions / 'rollout-2026-01-01T00-00-00-sid-1.jsonl'
        self.events(('task_started', 'turn-1'), ('task_complete', 'turn-1'))
        self.request = dict(nonce='n' * 64, sid='sid-1', child_pid=4242, child_start='START', rollout=str(self.rollout),
                            turn_id='turn-1', requested_at=1)

    def events(self, *events, mode='a'):
        with self.rollout.open(mode) as handle:
            for kind, turn in events:
                handle.write(json.dumps(dict(type='event_msg', payload=dict(type=kind, turn_id=turn))) + '\n')

    def decide(self, request=None, reread=None, sleep=lambda _: None, start='START', held=None):
        request = self.request if request is None else request
        with patch.object(s, 'held_rollout', return_value=str(self.rollout) if held is None else held), \
                patch.object(s, 'process_field', return_value=start):
            return s.safe_to_end(4242, 'START', request, reread or (lambda: request), 0, sleep=sleep)

    def test_quiescent_requesting_turn_is_safe(self):
        self.assertTrue(self.decide())

    def test_requesting_turn_still_running_or_unknown(self):
        self.events(('task_started', 'turn-1'), mode='w')
        self.assertFalse(self.decide())
        self.assertFalse(self.decide(request=dict(self.request, turn_id=None)))

    def test_aborted_turn_counts_as_finished_but_partial_lines_do_not(self):
        self.events(('task_started', 'turn-1'), ('turn_aborted', 'turn-1'), mode='w')
        self.assertTrue(self.decide())
        self.events(('task_started', 'turn-1'), mode='w')
        with self.rollout.open('a') as handle:
            handle.write(json.dumps(dict(type='event_msg', payload=dict(type='task_complete', turn_id='turn-1'))))
        self.assertFalse(self.decide())

    def test_new_turn_before_or_during_settle_rolls_back(self):
        self.assertFalse(self.decide(sleep=lambda _: self.events(('task_started', 'turn-2'))))
        self.assertFalse(self.decide())

    def test_any_write_during_settle_rolls_back(self):
        self.assertFalse(self.decide(sleep=lambda _: self.rollout.write_text(self.rollout.read_text() + '{"type":"response_item"}\n')))

    def test_cancel_during_settle_rolls_back(self):
        self.assertFalse(self.decide(reread=lambda: None))

    def test_process_identity_or_session_mismatch_rolls_back(self):
        self.assertFalse(self.decide(start='OTHER'))
        self.assertFalse(self.decide(held='/elsewhere/rollout-x-sid-1.jsonl'))

    def read(self, request, start='START', nonce='n' * 64):
        directory = self.root / 'handoff'
        directory.mkdir(exist_ok=True)
        s.request_path(directory, 4242).write_text(json.dumps(request))
        result = s.read_request(directory, 4242, start, nonce, self.sessions)
        return result, s.request_path(directory, 4242).exists()

    def test_request_validation(self):
        self.assertEqual(self.read(self.request), (self.request, True))
        outside = self.root / 'rollout-2026-01-01T00-00-00-sid-1.jsonl'
        outside.write_text('')
        for bad in (dict(self.request, nonce='stale'), dict(self.request, child_pid=1), dict(self.request, sid='../x'),
                    dict(self.request, rollout=str(outside)), dict(self.request, rollout=str(self.sessions / 'rollout-x-other.jsonl')),
                    dict(self.request, turn_id=5), ['not', 'a', 'dict']):
            self.assertEqual(self.read(bad), (None, False), bad)
        self.assertEqual(self.read(self.request, start='REUSED PID'), (None, False))

    def test_symlinked_request_is_rejected(self):
        directory = self.root / 'handoff'
        directory.mkdir()
        real = self.root / 'real.json'
        real.write_text(json.dumps(self.request))
        s.request_path(directory, 4242).symlink_to(real)
        self.assertIsNone(s.read_request(directory, 4242, 'START', 'n' * 64, self.sessions))

    def test_interactive_detection_matches_shared_launcher(self):
        for args in ([], ['--profile', 'yolo'], ['resume', 'id'], ['fork'], ['-m', 'exec'], ['fix the bug']):
            self.assertTrue(s.interactive(args), args)
        for args in (['exec', 'x'], ['-m', 'o3', 'mcp'], ['--version'], ['-h'], ['--remote', 'unix://x'], ['--remote=ws://x'], ['app-server']):
            self.assertFalse(s.interactive(args), args)


class HelperTests(unittest.TestCase):
    class Client:
        def __init__(self):
            self.unarchived = []

        def request(self, *args):
            pass

        def unarchive(self, tid):
            self.unarchived.append(tid)

    def run_helper(self, action, row, env, owner=False):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        data, client = Path(self.tmp.name), self.Client()
        owned = patch.object(m, 'require_shared_owner', side_effect=None if owner else m.T3Error('not owned'))
        with patch.object(m, 'record', return_value=row), owned, patch.dict(os.environ, env, clear=True):
            try:
                result = m.run(action, data, 'sid-1', client, timeout=0)
            except m.T3Error as error:
                result = error
        return result, client, sorted(p.name for p in (data / 'registrations').glob('*')) if (data / 'registrations').exists() else []

    ARCHIVED = dict(threadId='t3-id', archived=True, deleted=False, status='stopped')

    def test_unsupervised_session_gets_limitation_and_no_side_effects(self):
        result, client, markers = self.run_helper('on', self.ARCHIVED, {})
        self.assertIsInstance(result, m.T3Error)
        self.assertIn('codex --t3 resume sid-1', str(result))
        self.assertIn('Nothing was signalled', str(result))
        self.assertEqual((client.unarchived, markers), ([], []))

    def test_env_without_matching_ancestry_is_unsupervised(self):
        env = dict(T3_HANDOFF_NONCE='n' * 64, T3_HANDOFF_CHILD='999999', T3_HANDOFF_SUPERVISOR='999998', T3_HANDOFF_DIR='/nonexistent')
        result, client, markers = self.run_helper('on', None, env)
        self.assertIsInstance(result, m.T3Error)
        self.assertIn('codex --t3 resume sid-1', str(result))
        self.assertEqual(markers, [])

    def test_arming_writes_no_marker_and_does_not_unarchive(self):
        with patch.object(m.supervisor, 'arm') as arm:
            result, client, markers = self.run_helper('on', self.ARCHIVED, {})
        arm.assert_called_once_with('sid-1')
        self.assertEqual(result['handoff'], 'armed')
        self.assertFalse(result['attached'])
        self.assertEqual((client.unarchived, markers), ([], []))

    def test_off_cancels_armed_handoff_and_toggle_treats_armed_as_on(self):
        for action in ('off', 'toggle'):
            with patch.object(m.supervisor, 'armed', return_value=True), patch.object(m.supervisor, 'cancel') as cancel, \
                    patch.object(m.supervisor, 'arm') as arm:
                result, _, markers = self.run_helper(action, None, {})
            cancel.assert_called_once_with('sid-1')
            arm.assert_not_called()
            self.assertEqual(markers, ['.lock', 'sid-1.unshared'])
            self.assertFalse(result['enabled'])

    def test_status_is_unchanged_outside_supervision_and_reports_armed_inside(self):
        result, _, _ = self.run_helper('status', None, {})
        self.assertEqual(result, dict(enabled=False, attached=False, archived=False, runtime='absent'))
        with patch.object(m.supervisor, 'armed', return_value=True):
            result, _, _ = self.run_helper('status', None, {})
        self.assertEqual(result['handoff'], 'armed')

    def test_prepare_resume_unarchives_without_marker_and_refuses_deleted(self):
        result, client, markers = self.run_helper('prepare-resume', self.ARCHIVED, {})
        self.assertEqual((result, client.unarchived, markers), (dict(prepared=True), ['t3-id'], []))
        result, client, _ = self.run_helper('prepare-resume', dict(self.ARCHIVED, deleted=True), {})
        self.assertIsInstance(result, m.Refused)
        self.assertEqual(client.unarchived, [])


if __name__ == '__main__':
    unittest.main()
