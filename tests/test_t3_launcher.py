import json
import os
from pathlib import Path
import pty
import select
import signal
import subprocess
import sys
import tempfile
import time
import unittest

LAUNCHER = Path(__file__).resolve().parents[1]/'scripts/everyday-codex.zsh'


class LauncherTests(unittest.TestCase):
    def launch(self, args, tty=True):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for kind in ('native', 'node'):
                p = root/kind
                p.write_text('#!'+sys.executable+'\nimport json,os,sys\nprint(json.dumps(dict(kind='+repr(kind)+',args=sys.argv[1:],sharing=os.environ.get("T3_CODEX_AUTO_SHARE"))))\n')
                p.chmod(0o700)
            env = dict(os.environ, T3_CODEX_BINARY=str(root/'native'), T3_NODE_BINARY=str(root/'node'))
            if not tty:
                r = subprocess.run(['/bin/zsh', str(LAUNCHER), *args], env=env, capture_output=True, text=True, timeout=5)
                self.assertEqual(r.returncode,0)
                return json.loads(r.stdout)
            pid, fd = pty.fork()
            if pid == 0: os.execve('/bin/zsh',['zsh',str(LAUNCHER),*args],env)
            output=b''
            deadline=time.monotonic()+5
            try:
                while time.monotonic()<deadline:
                    if select.select([fd],[],[],0.1)[0]:
                        try: output+=os.read(fd,4096)
                        except OSError: pass
                    done,status=os.waitpid(pid,os.WNOHANG)
                    if done:
                        self.assertEqual(os.waitstatus_to_exitcode(status),0)
                        return json.loads(output)
                os.kill(pid,signal.SIGKILL);os.waitpid(pid,0)
                self.fail('launcher timeout')
            finally: os.close(fd)

    def test_new_interactive_launch_is_shared_runtime_with_sharing_off(self):
        r=self.launch(['resume','session-id'])
        self.assertEqual((r['kind'],r['sharing']),('node','0'))
        self.assertEqual(r['args'][1:],['resume','session-id'])

    def test_explicit_share_and_standalone_escape(self):
        r=self.launch(['--t3','resume','session-id'])
        self.assertEqual(r['sharing'],'1')
        self.assertEqual(r['args'][1:],['resume','session-id'])
        r=self.launch(['--standalone','-p','custom'])
        self.assertEqual((r['kind'],r['args']),('native',['-p','custom']))

    def test_non_terminal_stays_native(self):
        r=self.launch(['exec','a prompt with spaces'],tty=False)
        self.assertEqual((r['kind'],r['args']),('native',['exec','a prompt with spaces']))


if __name__=='__main__': unittest.main()
