#!/usr/bin/env python3
"""Manual gate for T3_HANDOFF_AUTO_END: how does an idle Codex TUI react to a signal?

Usage: manual_idle_exit_probe.py <codex-binary> [SIGTERM|SIGINT|SIGHUP|ctrld]

Runs the real binary in a pty with an empty throwaway HOME/CODEX_HOME (no credentials), outbound network
denied by sandbox-exec except loopback, and a loopback mock model. It completes one turn, waits for
task_complete, delivers the signal (or Ctrl+D), and prints what happened as JSON. A clean result needs
exit_code set, term_signal null, termios_restored true, and no BADJSON rollout lines.
Not part of the automated suite: it needs the real binary and about 20 seconds.
"""
import fcntl
import glob
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import pty
import select
import signal
import struct
import sys
import tempfile
import termios
import threading
import time

PROFILE = '(version 1)(allow default)(deny network-outbound)(allow network-outbound (remote ip "localhost:*"))(allow network-outbound (remote unix-socket))'
USAGE = {'input_tokens': 1, 'input_tokens_details': None, 'output_tokens': 1, 'output_tokens_details': None, 'total_tokens': 2}


class Mock(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        self.rfile.read(int(self.headers.get('Content-Length') or 0))
        if not self.path.endswith('/responses'):
            return self.do_GET()
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.end_headers()
        item = {'type': 'message', 'role': 'assistant', 'id': 'msg_1', 'content': [{'type': 'output_text', 'text': 'MOCK_OK'}]}
        for event in ({'type': 'response.created', 'response': {'id': 'resp_1'}}, {'type': 'response.output_item.done', 'item': item},
                      {'type': 'response.completed', 'response': {'id': 'resp_1', 'usage': USAGE}}):
            self.wfile.write(('event: %s\ndata: %s\n\n' % (event['type'], json.dumps(event))).encode())
        self.wfile.flush()


def main():
    binary, how = sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else 'SIGTERM'
    server = ThreadingHTTPServer(('127.0.0.1', 0), Mock)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    root = os.path.realpath(tempfile.mkdtemp(prefix='t3-idle-exit-'))
    home, work = root + '/home', root + '/work'
    os.makedirs(home)
    os.makedirs(work)
    with open(home + '/config.toml', 'w') as config:
        config.write('model = "mock-model"\nmodel_provider = "mock"\ncheck_for_update_on_startup = false\n'
                     '[model_providers.mock]\nname = "mock"\nbase_url = "http://127.0.0.1:%d/v1"\nwire_api = "responses"\n'
                     '[projects."%s"]\ntrust_level = "trusted"\n' % (server.server_address[1], work))
    env = {'HOME': root, 'CODEX_HOME': home, 'PATH': '/usr/bin:/bin:/usr/sbin:/sbin', 'TERM': 'xterm-256color'}
    pid, fd = pty.fork()
    if pid == 0:
        os.chdir(work)
        os.execve('/usr/bin/sandbox-exec', ['sandbox-exec', '-p', PROFILE, binary], env)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack('HHHH', 40, 120, 0, 0))
    before = termios.tcgetattr(fd)

    def events():
        found = []
        for path in glob.glob(home + '/sessions/*/*/*/rollout-*.jsonl'):
            for line in open(path):
                try:
                    payload = json.loads(line).get('payload') or {}
                except ValueError:
                    found.append('BADJSON')
                    continue
                if payload.get('type') in ('task_started', 'task_complete', 'turn_aborted'):
                    found.append(payload['type'])
        return found

    def pump(seconds, until=None):
        end = time.monotonic() + seconds
        while time.monotonic() < end and not (until and until()):
            if select.select([fd], [], [], 0.1)[0]:
                try:
                    chunk = os.read(fd, 65536)
                except OSError:
                    return
                # Answer the terminal queries the TUI waits on.
                if b'\x1b[6n' in chunk:
                    os.write(fd, b'\x1b[1;1R')
                if b'\x1b[c' in chunk:
                    os.write(fd, b'\x1b[?1;2c')

    pump(6)
    os.write(fd, b'say hi')
    pump(0.5)
    os.write(fd, b'\r')
    pump(30, lambda: 'task_complete' in events())
    pump(2)
    idle = events()
    started = time.monotonic()
    if how == 'ctrld':
        os.write(fd, b'\x04')
    else:
        os.kill(pid, getattr(signal, how))
    status = None
    while status is None and time.monotonic() - started < 10:
        pump(0.1)
        done, value = os.waitpid(pid, os.WNOHANG)
        status = value if done else None
    seconds = round(time.monotonic() - started, 2)
    if status is None:
        os.kill(pid, signal.SIGKILL)
        os.waitpid(pid, 0)
    print(json.dumps(dict(how=how, reached_idle=idle[-1:] == ['task_complete'], exited=status is not None, seconds=seconds,
                          exit_code=os.WEXITSTATUS(status) if status is not None and os.WIFEXITED(status) else None,
                          term_signal=os.WTERMSIG(status) if status is not None and os.WIFSIGNALED(status) else None,
                          termios_restored=termios.tcgetattr(fd) == before, rollout_events=events(), runtime=root)))


if __name__ == '__main__':
    main()
