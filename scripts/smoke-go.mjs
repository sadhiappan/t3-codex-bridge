import { spawn } from 'node:child_process';
import { mkdtempSync, mkdirSync, rmSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { createServer } from 'node:net';
import { createRequire } from 'node:module';
import { once } from 'node:events';
import assert from 'node:assert/strict';
import { configuration, root, socketReady } from './bridge.mjs';

if (!process.argv[2]) throw new Error('Pass the prebuilt bundle directory.');
const bundle = resolve(process.argv[2]);
// A raw, isolated app-server process: never the user's managed daemon.
const directory = mkdtempSync('/tmp/t3b-smoke-');
const require = createRequire(join(root, '.runtime/t3/apps/server/package.json'));
const { NodeWS } = await import(require.resolve('@effect/platform-node/NodeSocket'));
const portServer = createServer();
await new Promise((resolve) => portServer.listen(0, '127.0.0.1', resolve));
const port = portServer.address().port;
await new Promise((resolve) => portServer.close(resolve));
const config = configuration({ ...process.env, CODEX_HOME: join(directory, 'codex'), T3_BRIDGE_HOME: join(directory, 'data'), T3_BRIDGE_PORT: String(port), T3_BRIDGE_HOST: '127.0.0.1' });
config.env.T3_CODEX_BINARY = join(bundle, 'runtime/codex/bin/codex');
config.env.PATH = '/usr/bin:/bin:/usr/sbin:/sbin';
mkdirSync(join(config.codexHome, 'app-server-control'), { recursive: true, mode: 0o700 });
const children = [];
function launch(command, args) {
  const child = spawn(command, args, { env: config.env, cwd: directory, stdio: ['ignore', 'pipe', 'pipe'] });
  // Drain privately; pairing credentials and diagnostics are not printed to CI.
  let output = '';
  child.stdout.on('data', (chunk) => { output = (output + chunk).slice(-100000); });
  child.stderr.on('data', (chunk) => { output = (output + chunk).slice(-100000); });
  child.on('error', () => {});
  children.push(child);
  return { child, output: () => output };
}
async function until(check, label) {
  const deadline = Date.now() + 30000;
  while (Date.now() < deadline) {
    if (await check()) return;
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error(`Timed out waiting for ${label}.`);
}
let native;
try {
  launch(config.env.T3_CODEX_BINARY, ['app-server', '--listen', `unix://${config.env.T3_CODEX_SHARED_SOCKET}`]);
  await until(() => socketReady(config.env.T3_CODEX_SHARED_SOCKET), 'isolated native socket');
  native = new NodeWS.WebSocket(`ws+unix://${config.env.T3_CODEX_SHARED_SOCKET}:/`, { handshakeTimeout: 5000, perMessageDeflate: false });
  native.on('error', () => {});
  await once(native, 'open');
  native.send(JSON.stringify({ id: 1, method: 'initialize', params: { clientInfo: { name: 'bridge-smoke', version: '1' }, capabilities: { experimentalApi: true } } }));
  const initialize = await Promise.race([
    once(native, 'message').then(([frame]) => JSON.parse(frame.toString())),
    new Promise((_, reject) => { const timer = setTimeout(() => reject(new Error('Native initialize timed out')), 5000); timer.unref(); }),
  ]);
  assert.equal(initialize.id, 1);
  assert.ok(initialize.result);
  native.send(JSON.stringify({ method: 'initialized' }));
  const doctor = launch(join(bundle, 'bin/bridge'), ['doctor', '--json']);
  const [doctorCode] = await once(doctor.child, 'exit');
  assert.equal(doctorCode, 0);
  const health = JSON.parse(doctor.output());
  assert.equal(health.protocol, 'connected');
  assert.equal(health.mcp, 'unknown');
  console.log('PASS: Go doctor verifies native RPC without claiming MCP health.');
  console.log('PASS: bundled native Codex initializes over an isolated Unix WebSocket.');
  launch(join(bundle, 'bin/bridge'), ['serve']);
  const origin = `http://127.0.0.1:${port}`;
  await until(async () => {
    try { return (await fetch(origin, { signal: AbortSignal.timeout(1000) })).status === 200; }
    catch { return false; }
  }, 'built web server');
  const html = await (await fetch(origin)).text();
  assert.match(html, /<html/);
  const asset = html.match(/src="([^"]+\.js)"/);
  assert.ok(asset, 'built JavaScript asset');
  assert.equal((await fetch(new URL(asset[1], origin))).status, 200);
  console.log('PASS: production server serves HTML and its built JavaScript asset.');
  const status = await new Promise((resolve, reject) => {
    const ws = new NodeWS.WebSocket(origin.replace('http:', 'ws:') + '/ws', { handshakeTimeout: 5000, perMessageDeflate: false });
    ws.on('unexpected-response', (_, response) => { response.resume(); resolve(response.statusCode); ws.terminate(); });
    ws.on('open', () => { ws.close(); reject(new Error('Unauthenticated WebSocket accepted')); });
    ws.on('error', () => {});
    const timer = setTimeout(() => reject(new Error('Auth rejection timed out')), 6000); timer.unref();
  });
  assert.equal(status, 401);
  console.log('PASS: unauthenticated T3 WebSocket is rejected with HTTP 401.');
  const pair = launch(join(bundle, 'bin/bridge'), ['pair']);
  const [code] = await once(pair.child, 'exit');
  assert.equal(code, 0, 'pair command exits successfully');
  assert.match(pair.output(), /Pairing URL: http:\/\/127\.0\.0\.1:/);
  assert.match(pair.output(), /token=/);
  console.log('PASS: pairing command issues a private link for the isolated server.');
} finally {
  native?.terminate();
  for (const child of children.reverse()) {
    if (child.exitCode !== null || child.signalCode !== null) continue;
    const exited = once(child, 'exit');
    child.kill('SIGTERM');
    const timer = setTimeout(() => child.kill('SIGKILL'), 8000);
    await exited;
    clearTimeout(timer);
  }
  rmSync(directory, { recursive: true, force: true, maxRetries: 10, retryDelay: 100 });
}
