#!/usr/bin/env python3
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pty
import re
import select
import sqlite3
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid


class T3Error(Exception):
    pass


def identity():
    first = os.environ.get('CODEX_THREAD_ID')
    second = os.environ.get('CODEX_SESSION_ID')
    if first and second and first != second:
        raise T3Error('Session identity is ambiguous; no sharing changed.')
    value = first or second
    if not value or not re.fullmatch(r'[A-Za-z0-9_-]+', value):
        raise T3Error('No valid current Codex session ID; no sharing changed.')
    return value


def require_shared_owner():
    socket = str(Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))) / 'app-server-control/app-server-control.sock')
    pid = os.getppid()
    for _ in range(32):
        if pid <= 1:
            break
        result = subprocess.run(['/bin/ps', '-p', str(pid), '-o', 'ppid=', '-o', 'command='], capture_output=True, text=True, timeout=2)
        fields = result.stdout.strip().split(None, 1)
        if len(fields) != 2:
            break
        parent, command = fields
        if 'app-server' in command and '--listen unix://' in command:
            result = subprocess.run(['/usr/sbin/lsof', '-a', '-p', str(pid), '-U', '-Fn'], capture_output=True, text=True, timeout=3)
            if 'n' + socket in result.stdout.splitlines():
                return
        pid = int(parent)
    raise T3Error('This session is not owned by the shared daemon. Resume its native ID with codex --t3 resume first; no duplicate session was created.')


def record(data, sid):
    path = data / 't3/userdata/state.sqlite'
    if not path.is_file():
        raise T3Error('T3 database is unavailable.')
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=2) as db:
        rows = db.execute('SELECT t.thread_id,t.archived_at,t.deleted_at,r.status,r.resume_cursor_json FROM projection_threads t LEFT JOIN provider_session_runtime r ON t.thread_id=r.thread_id').fetchall()
    matches = []
    for tid, archived, deleted, status, cursor in rows:
        native = (json.loads(cursor) if cursor else {}).get('threadId')
        if tid == sid or native == sid:
            matches.append(dict(threadId=tid, archived=archived is not None, deleted=deleted is not None, status=status))
    if len(matches) > 1:
        raise T3Error('Multiple T3 records match this session; no automatic choice made.')
    return matches[0] if matches else None


def state(data, sid, row):
    directory = data / 'registrations'
    enabled = (directory / (sid + '.thread')).exists() and not (directory / (sid + '.unshared')).exists()
    attached = bool(row and not row['archived'] and not row['deleted'] and row['status'] == 'running')
    return dict(enabled=enabled and not bool(row and (row['archived'] or row['deleted'])), attached=attached,
                archived=bool(row and row['archived']), runtime=row['status'] if row else 'absent')


def marker(data, sid, enable):
    directory = data / 'registrations'
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (directory / '.lock').open('a') as lock:
        os.chmod(lock.name, 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX)
        suffix, other = ('.thread', '.unshared') if enable else ('.unshared', '.thread')
        fd = os.open(directory / (sid + suffix), os.O_CREAT | os.O_WRONLY, 0o600)
        os.close(fd)
        (directory / (sid + other)).unlink(missing_ok=True)


class Client:
    def __init__(self, origin, bridge, keychain):
        self.origin, self.bridge, self.keychain = origin, bridge, keychain
        self.service = 't3-toggle-' + hashlib.sha256(origin.encode()).hexdigest()[:12]

    def request(self, path, payload=None, token=None, form=False):
        headers = {}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        body = None
        if payload is not None:
            body = (urllib.parse.urlencode(payload) if form else json.dumps(payload)).encode()
            headers['Content-Type'] = 'application/x-www-form-urlencoded' if form else 'application/json'
        req = urllib.request.Request(self.origin + path, data=body, headers=headers)
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        with urllib.request.build_opener(NoRedirect).open(req, timeout=5) as response:
            return json.load(response)

    def token(self):
        result = subprocess.run([self.keychain, 'get', self.service], capture_output=True, text=True, timeout=10)
        token = result.stdout.strip()
        if token and not token.startswith('Not found:'):
            try:
                session = self.request('/api/auth/session', token=token)
                if session.get('authenticated') is True:
                    return token
            except urllib.error.HTTPError as error:
                if error.code not in (401, 403):
                    raise
        result = subprocess.run([self.bridge, 'pair'], capture_output=True, text=True, timeout=20)
        if result.returncode:
            raise T3Error('T3 pairing failed; credentials were not printed.')
        urls = re.findall(r'https?://[^\s]+', result.stdout)
        credentials = [urllib.parse.parse_qs((urllib.parse.urlsplit(url).fragment or urllib.parse.urlsplit(url).query)).get('token', [None])[0] for url in urls]
        credential = next((value for value in credentials if value), None)
        if not credential:
            raise T3Error('No pairing credential returned.')
        response = self.request('/oauth/token', {
            'grant_type': 'urn:ietf:params:oauth:grant-type:token-exchange',
            'subject_token': credential,
            'subject_token_type': 'urn:t3:params:oauth:token-type:environment-bootstrap',
            'requested_token_type': 'urn:ietf:params:oauth:token-type:access_token',
            'scope': 'orchestration:read orchestration:operate',
            'client_label': 'Local Codex T3 toggle',
        }, form=True)
        token = response['access_token']
        self.store(token)
        return token

    def store(self, token):
        pid, master = pty.fork()
        if pid == 0:
            os.execv(self.keychain, [self.keychain, 'set', self.service])
        deadline, output, sent = time.monotonic() + 15, b'', False
        try:
            while time.monotonic() < deadline:
                if select.select([master], [], [], 0.2)[0]:
                    try:
                        chunk = os.read(master, 4096)
                    except OSError:
                        break
                    if not chunk:
                        break
                    output = (output + chunk)[-4096:]
                    if b'Password:' in output and not sent:
                        os.write(master, token.encode() + b'\n')
                        sent = True
                done, status = os.waitpid(pid, os.WNOHANG)
                if done:
                    if status != 0:
                        raise T3Error('Keychain helper failed.')
                    return
            done, status = os.waitpid(pid, os.WNOHANG)
            if not done:
                os.kill(pid, 15)
                os.waitpid(pid, 0)
                raise T3Error('Keychain helper timed out.')
            if status != 0 or not sent:
                raise T3Error('Keychain helper failed.')
        finally:
            os.close(master)

    def unarchive(self, tid):
        return self.request('/api/orchestration/dispatch', {
            'type': 'thread.unarchive', 'commandId': str(uuid.uuid4()), 'threadId': tid,
        }, token=self.token())


def run(action, data, sid, client, timeout=35):
    client.request('/.well-known/t3/environment')
    row = record(data, sid)
    before = state(data, sid, row)
    if action == 'status':
        return before
    if row and row['deleted']:
        raise T3Error('T3 entry was deleted; refusing to recreate it automatically.')
    enable = not before['enabled'] if action == 'toggle' else action == 'on'
    # Unarchive through T3's event pipeline before changing discovery intent.
    if enable:
        require_shared_owner()
    if enable and row and row['archived']:
        client.unarchive(row['threadId'])
    marker(data, sid, enable)
    deadline = time.monotonic() + timeout
    while True:
        current = state(data, sid, record(data, sid))
        if enable and current['enabled'] and current['attached']:
            return current
        if not enable and not current['enabled'] and current['runtime'] in ('stopped', 'absent', None):
            return current
        if time.monotonic() >= deadline:
            raise T3Error('Sharing intent saved, but T3 did not confirm attachment/detachment within 35 seconds. Run status; do not repeat toggle blindly.')
        time.sleep(0.5)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['on', 'off', 'status', 'toggle'], nargs='?', default='toggle')
    args = parser.parse_args()
    data = Path(os.environ.get('T3_BRIDGE_HOME', str(Path.home() / '.local/share/t3-codex-bridge'))).resolve()
    sid = identity()
    port = int(os.environ.get('T3_BRIDGE_PORT', '18773'))
    if not 1024 <= port <= 65535:
        raise T3Error('Invalid local T3 port.')
    client = Client('http://127.0.0.1:' + str(port), os.environ.get('T3_TOGGLE_BRIDGE', str(Path.home() / '.local/bin/bridge')), str(Path.home() / 'bin/keychain-secret'))
    data.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (data / 'toggle.lock').open('a') as lock:
        os.chmod(lock.name, 0o600)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise T3Error('Another toggle is running; retry status after it finishes.')
        print(json.dumps(run(args.action, data, sid, client)))


if __name__ == '__main__':
    try:
        main()
    except (T3Error, OSError, ValueError, sqlite3.Error, subprocess.SubprocessError) as error:
        # Never include HTTP bodies, CLI output, or credentials in diagnostics.
        message = str(error) if isinstance(error, T3Error) else type(error).__name__
        raise SystemExit('T3 toggle: ' + message)
