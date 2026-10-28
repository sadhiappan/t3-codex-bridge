#!/usr/bin/env python3
"""Supervise an ordinary interactive Codex launch so its session can be handed to the shared T3 route.

The launcher runs `supervisor.py <codex-binary> [args...]`. Codex runs as a child in the same process
group with the terminal untouched. `t3.py on` inside that session arms a handoff request bound to this
launch; once the child has exited the supervisor confirms nothing still holds the session and execs
the launcher's existing `--t3 resume <id>` route in the same terminal.
"""
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import signal
import stat
import subprocess
import sys
import termios
import time

# Mirrors localCommands/valueOptions in t3code apps/server/src/provider/sharedCodexLaunch.ts.
LOCAL_COMMANDS = {
    'exec', 'e', 'review', 'login', 'logout', 'mcp', 'plugin', 'app-server', 'remote-control', 'app', 'completion',
    'update', 'doctor', 'sandbox', 'debug', 'apply', 'a', 'queue', 'archive', 'delete', 'migrate-rollouts',
    'unarchive', 'cloud', 'exec-server', 'features', 'help', 'agents',
}
VALUE_OPTIONS = {
    '-c', '--config', '--enable', '--disable', '-i', '--image', '-m', '--model', '--local-provider', '-p', '--profile',
    '-s', '--sandbox', '-C', '--cd', '--add-dir', '-a', '--ask-for-approval', '--remote-auth-token-env',
}
SESSION = re.compile(r'[A-Za-z0-9_-]+')
BOUNDARIES = ('task_started', 'task_complete', 'turn_aborted')
REFUSED = 3


class HandoffError(Exception):
    pass


def interactive(args):
    command, index = None, 0
    while index < len(args):
        arg = args[index]
        if arg == '--':
            break
        if arg in ('--help', '-h', '--version', '-V', '--remote') or arg.startswith('--remote='):
            return False
        if arg in VALUE_OPTIONS:
            index += 2
            continue
        if not arg.startswith('-') and command is None:
            command = arg
        index += 1
    return command not in LOCAL_COMMANDS


def handoff_dir():
    return Path(os.environ.get('T3_HANDOFF_DIR', str(Path.home() / '.local/state/codex-shared-t3/handoff')))


def process_field(pid, field):
    result = subprocess.run(['/bin/ps', '-p', str(pid), '-o', field + '='], capture_output=True, text=True, timeout=3)
    return result.stdout.strip()


def held_rollout(pid, sid):
    result = subprocess.run(['/usr/sbin/lsof', '-a', '-p', str(pid), '-Fn'], capture_output=True, text=True, timeout=5)
    name = re.compile(r'rollout-.*-' + re.escape(sid) + r'\.jsonl')
    paths = {line[1:] for line in result.stdout.splitlines() if line.startswith('n/') and name.fullmatch(os.path.basename(line))}
    return paths.pop() if len(paths) == 1 else None


def holders(path):
    result = subprocess.run(['/usr/sbin/lsof', '-t', '--', path], capture_output=True, text=True, timeout=5)
    pids = result.stdout.split()
    if result.returncode and (pids or result.returncode != 1):
        raise HandoffError('could not check whether the session is still open')
    return pids


def boundaries(path):
    events = []
    with open(path, 'rb') as rollout:
        for line in rollout:
            if not line.endswith(b'\n') or not any(kind.encode() in line for kind in BOUNDARIES):
                continue
            try:
                payload = json.loads(line).get('payload')
            except (ValueError, AttributeError):
                continue
            if isinstance(payload, dict) and payload.get('type') in BOUNDARIES:
                events.append((payload['type'], payload.get('turn_id')))
    return events


def open_turn(events):
    return events[-1][1] if events and events[-1][0] == 'task_started' else None


def turn_finished(path, turn_id):
    events = boundaries(path)
    ended = any(kind != 'task_started' and turn == turn_id for kind, turn in events)
    return ended and events[-1][0] != 'task_started'


def request_path(directory, child):
    return Path(directory) / (str(child) + '.request')


def read_request(directory, child, start, nonce, sessions):
    path = request_path(directory, child)
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError:
        return None
    with os.fdopen(fd, 'rb') as handle:
        info = os.fstat(handle.fileno())
        raw = handle.read(65536) if info.st_uid == os.getuid() and info.st_size < 65536 else b''
    try:
        request = json.loads(raw)
        valid = (hmac.compare_digest(str(request['nonce']), nonce) and request['child_pid'] == child
                 and request['child_start'] == start and bool(SESSION.fullmatch(request['sid']))
                 and (request['turn_id'] is None or isinstance(request['turn_id'], str))
                 and bool(re.fullmatch(r'rollout-.*-' + re.escape(request['sid']) + r'\.jsonl', os.path.basename(request['rollout'])))
                 and Path(os.path.realpath(request['rollout'])).is_relative_to(Path(os.path.realpath(sessions))))
    except (ValueError, KeyError, TypeError):
        valid = False
    if not valid:
        # Stale or foreign: addressed to our child's PID but not minted by this launch.
        path.unlink(missing_ok=True)
        return None
    return request


# --- session side (called by t3.py inside the supervised Codex) ---

def supervised():
    try:
        return os.environ['T3_HANDOFF_NONCE'], int(os.environ['T3_HANDOFF_CHILD']), int(os.environ['T3_HANDOFF_SUPERVISOR'])
    except (KeyError, ValueError):
        return None


def arm(sid):
    launch = supervised()
    if not launch:
        raise HandoffError('unsupervised')
    nonce, child, supervisor = launch
    pid = os.getppid()
    for _ in range(32):
        if pid == child or pid <= 1:
            break
        pid = int(process_field(pid, 'ppid') or 0)
    if pid != child or process_field(child, 'ppid') != str(supervisor):
        raise HandoffError('unsupervised')
    rollout = held_rollout(child, sid)
    if not rollout:
        raise HandoffError('The supervised Codex process does not hold this session (nested or switched session); no handoff armed.')
    request = dict(nonce=nonce, sid=sid, child_pid=child, child_start=process_field(child, 'lstart'), rollout=rollout,
                   turn_id=open_turn(boundaries(rollout)), requested_at=time.time())
    directory = handoff_dir()
    temporary = directory / ('.%d.%s' % (child, secrets.token_hex(8)))
    fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as handle:
        json.dump(request, handle)
    os.replace(temporary, request_path(directory, child))


def armed(sid):
    launch = supervised()
    if not launch:
        return None
    try:
        request = json.loads(request_path(handoff_dir(), launch[1]).read_text())
        return hmac.compare_digest(str(request['nonce']), launch[0]) and request['sid'] == sid
    except (OSError, ValueError, KeyError, TypeError):
        return False


def cancel(sid):
    if armed(sid):
        request_path(handoff_dir(), supervised()[1]).unlink(missing_ok=True)
        return True
    return False


# --- launcher side ---

def safe_to_end(child, start, request, reread, settle, sleep=time.sleep):
    """Decide whether the idle child may be signalled. Any doubt returns False and nothing is sent."""
    if not request or not request['turn_id'] or not turn_finished(request['rollout'], request['turn_id']):
        return False
    if held_rollout(child, request['sid']) != request['rollout']:
        return False
    before = os.stat(request['rollout'])
    sleep(settle)
    after = os.stat(request['rollout'])
    return (process_field(child, 'lstart') == start and reread() == request
            and (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
            and turn_finished(request['rollout'], request['turn_id']))


def restore_signals(inherited):
    for number in (signal.SIGPIPE, signal.SIGXFSZ, signal.SIGTERM, signal.SIGHUP):
        signal.signal(number, signal.SIG_DFL)
    for number, handler in inherited.items():
        signal.signal(number, signal.SIG_IGN if handler == signal.SIG_IGN else signal.SIG_DFL)


def mirror(status, inherited):
    if os.WIFSIGNALED(status):
        restore_signals(inherited)
        try:
            signal.signal(os.WTERMSIG(status), signal.SIG_DFL)
        except (OSError, ValueError):
            pass
        os.kill(os.getpid(), os.WTERMSIG(status))
        time.sleep(1)
        return 128 + os.WTERMSIG(status)
    return os.WEXITSTATUS(status)


def note(message):
    try:
        sys.stderr.write('\nT3 handoff: ' + message + '\n')
        sys.stderr.flush()
    except OSError:
        pass


def hand_off(request, inherited):
    sid = request['sid']
    manual = 'Resume manually when ready: codex --t3 resume ' + sid
    launcher, helper = os.environ.get('T3_HANDOFF_LAUNCHER'), os.environ.get('T3_HANDOFF_HELPER')
    if not launcher or not helper or not (os.isatty(0) and os.isatty(1)):
        return note('skipped, this terminal cannot host the shared session. ' + manual)
    try:
        if holders(request['rollout']):
            return note('skipped, another process still has this session open. ' + manual)
        environment = {key: value for key, value in os.environ.items() if not key.startswith('T3_HANDOFF_')}
        identity = dict(environment, CODEX_THREAD_ID=sid)
        identity.pop('CODEX_SESSION_ID', None)
        prepared = subprocess.run([helper, 'prepare-resume'], env=identity,
                                  stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60)
    except (HandoffError, OSError, subprocess.SubprocessError) as error:
        return note('skipped, %s. %s' % (error if isinstance(error, HandoffError) else type(error).__name__, manual))
    if prepared.returncode == REFUSED:
        return note('skipped, %s %s' % (prepared.stderr.strip(), manual))
    if prepared.returncode:
        note('T3 did not confirm its entry for this session; run $t3 status after it reopens.')
    note('reopening %s through the shared daemon.' % sid)
    restore_signals(inherited)
    try:
        os.execve(launcher, [launcher, '--t3', 'resume', sid], environment)
    except OSError:
        note('could not start the shared route. ' + manual)


def supervise(binary, args):
    state = dict(child=None, pending=[])

    def forward(number, _frame):
        if state['child'] is None:
            state['pending'].append(number)
        else:
            try:
                os.kill(state['child'], number)
            except ProcessLookupError:
                pass

    inherited = {number: signal.getsignal(number) for number in (signal.SIGINT, signal.SIGQUIT)}
    try:
        directory = handoff_dir()
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        info = os.lstat(directory)
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise HandoffError('handoff directory is not private')
        nonce = secrets.token_hex(32)
        sessions = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))) / 'sessions'
        auto_end = os.environ.get('T3_HANDOFF_AUTO_END') == '1'
        terminal = termios.tcgetattr(0)
        # Terminal-generated INT/QUIT reach the child directly through the shared process group.
        for number in inherited:
            signal.signal(number, lambda *_: None)
        for number in (signal.SIGTERM, signal.SIGHUP):
            signal.signal(number, forward)
    except Exception:
        # Supervision is optional; the launch is not.
        restore_signals(inherited)
        os.execv(binary, [binary] + args)

    child = os.fork()
    if child == 0:
        try:
            restore_signals(inherited)
            environment = dict(os.environ, T3_HANDOFF_NONCE=nonce, T3_HANDOFF_CHILD=str(os.getpid()),
                               T3_HANDOFF_SUPERVISOR=str(os.getppid()), T3_HANDOFF_DIR=str(directory))
            environment.pop('T3_HANDOFF_AUTO_END', None)
            os.execve(binary, [binary] + args, environment)
        except OSError as error:
            os.write(2, ('codex: %s: %s\n' % (binary, error.strerror)).encode())
        finally:
            os._exit(127)
    state['child'] = child
    for number in state['pending']:
        forward(number, None)

    status, ended_by_us, signalled_at = None, False, None
    try:
        start = process_field(child, 'lstart')
        request_path(directory, child).unlink(missing_ok=True)
        reread = lambda: read_request(directory, child, start, nonce, sessions)
        while True:
            done, status = os.waitpid(child, os.WUNTRACED | (os.WNOHANG if auto_end else 0))
            if done and os.WIFSTOPPED(status):
                # Mirror the stop so the shell's job control sees it; fg continues both.
                if process_field(child, 'stat').startswith('T'):
                    os.kill(os.getpid(), signal.SIGSTOP)
                    os.kill(child, signal.SIGCONT)
                continue
            if done:
                break
            if signalled_at is None and safe_to_end(child, start, reread(), reread, settle=2.0):
                os.kill(child, signal.SIGTERM)
                ended_by_us, signalled_at = True, time.monotonic()
            elif signalled_at is not None and ended_by_us and time.monotonic() - signalled_at > 5:
                # Never escalate. The child ignored the request, so the handoff waits for a normal exit.
                ended_by_us = False
            time.sleep(0.5)
        request = reread()
        request_path(directory, child).unlink(missing_ok=True)
    except Exception:
        # Supervision must never take the session down with it.
        request = None
        while status is None or os.WIFSTOPPED(status):
            _, status = os.waitpid(child, 0)
    try:
        if ended_by_us:
            termios.tcsetattr(0, termios.TCSADRAIN, terminal)
            os.write(1, b'\x1b[<u\x1b[?2004l\x1b[?1004l\x1b[?25h\r\n')
        clean = os.WIFEXITED(status) and os.WEXITSTATUS(status) == 0
        if request and (clean or ended_by_us):
            hand_off(request, inherited)
        elif request:
            note('skipped because Codex did not exit normally. Resume manually when ready: codex --t3 resume ' + request['sid'])
    except Exception as error:
        note('skipped, %s.' % type(error).__name__)
    return mirror(status, inherited)


def main():
    binary, args = sys.argv[1], sys.argv[2:]
    if not (interactive(args) and os.isatty(0) and os.isatty(1)) or os.environ.get('T3_HANDOFF_SUPERVISE') == '0':
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
        signal.signal(signal.SIGXFSZ, signal.SIG_DFL)
        os.execv(binary, [binary] + args)
    sys.exit(supervise(binary, args))


if __name__ == '__main__':
    main()
