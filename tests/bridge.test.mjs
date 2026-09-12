import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createServer } from 'node:net';
import { spawnSync } from 'node:child_process';
import { configuration, socketReady, root } from '../scripts/bridge.mjs';

test('dedicated T3 state and opt-in registration override ambient discovery settings', () => {
  const result = configuration({ PATH: '/custom/bin', T3CODE_HOME: '/existing-t3', T3_CODEX_SHARED_PROJECTS: '["/all"]', VITE_DEV_SERVER_URL: 'http://localhost:9999', T3CODE_TAILSCALE_SERVE: 'true' }, '/tester');
  assert.equal(result.env.CODEX_HOME, '/tester/.codex');
  assert.equal(result.env.T3CODE_HOME, '/tester/.local/share/t3-codex-bridge/t3');
  assert.equal(result.env.T3_CODEX_SHARED_PROJECTS, '[]');
  assert.equal(result.env.T3_CODEX_START_DAEMON, '0');
  assert.equal(result.env.VITE_DEV_SERVER_URL, undefined);
  assert.equal(result.env.T3CODE_TAILSCALE_SERVE, 'false');
  assert.ok(result.env.PATH.endsWith(':/custom/bin'));
});
test('custom isolated Codex home controls socket and preserves arguments with spaces', () => {
  const result = configuration({ CODEX_HOME: '/tmp/codex test', T3_BRIDGE_HOME: '/tmp/t3 test', T3_BRIDGE_PORT: '18774' });
  assert.equal(result.env.T3_CODEX_SHARED_SOCKET, '/tmp/codex test/app-server-control/app-server-control.sock');
  assert.equal(result.env.T3CODE_HOME, '/tmp/t3 test/t3');
  assert.equal(result.port, 18774);
});
test('invalid ports fail before starting a process', () => {
  for (const value of ['0', '80', '65536', 'bad', '18773.5'])
    assert.throws(() => configuration({ T3_BRIDGE_PORT: value }), /1024/);
});
test('socket preflight distinguishes listening and missing socket and releases its connection', async () => {
  const dir = mkdtempSync(join(tmpdir(), 'bridge-test-'));
  const socket = join(dir, 'daemon.sock');
  const server = createServer((client) => client.end());
  try {
    assert.equal(await socketReady(socket), false);
    await new Promise((resolve) => server.listen(socket, resolve));
    assert.equal(await socketReady(socket), true);
    await new Promise((resolve) => server.close(resolve));
    assert.equal(await socketReady(socket), false);
  } finally { server.close(); rmSync(dir, { recursive: true, force: true }); }
});
test('help runs without an installation and lists opt-in commands', () => {
  const result = spawnSync(process.execPath, [join(root, 'scripts/bridge.mjs'), '--help'], { encoding: 'utf8' });
  assert.equal(result.status, 0);
  assert.match(result.stdout, /codex unshare/);
});
test('public patch contains no hardware bridge or personal host paths', () => {
  const patch = readFileSync(join(root, 'shared-codex.patch'), 'utf8');
  assert.doesNotMatch(patch, /microRequest|codex-micro|sharedCodexMicroClient|\/Users\/|\.ts\.net/);
});
