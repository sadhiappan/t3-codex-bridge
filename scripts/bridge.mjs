import { spawnSync, spawn } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, writeFileSync, realpathSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { homedir } from 'node:os';
import { createHash } from 'node:crypto';
import { connect } from 'node:net';

export const root = dirname(dirname(fileURLToPath(import.meta.url)));
const versions = JSON.parse(readFileSync(join(root, 'versions.json'), 'utf8'));
const runtime = join(root, '.runtime');
const source = join(runtime, 't3');
const binary = join(runtime, 'codex', 'node_modules', '.bin', 'codex');
const patch = join(root, 'shared-codex.patch');
const stamp = join(runtime, 'installed.json');

export function configuration(env = process.env, home = homedir()) {
  const codexHome = resolve(env.CODEX_HOME || join(home, '.codex'));
  const data = resolve(env.T3_BRIDGE_HOME || join(home, '.local', 'share', 't3-codex-bridge'));
  const port = Number(env.T3_BRIDGE_PORT || 18773);
  if (!Number.isInteger(port) || port < 1024 || port > 65535) throw new Error('T3_BRIDGE_PORT must be 1024–65535.');
  return {
    data, port, codexHome,
    env: { ...env, CODEX_HOME: codexHome, T3CODE_HOME: join(data, 't3'),
      T3_CODEX_BINARY: binary,
      T3_CODEX_SHARED_SOCKET: join(codexHome, 'app-server-control', 'app-server-control.sock'),
      T3_CODEX_SHARED_PROJECTS: '[]', T3_CODEX_SHARED_REGISTRATIONS: join(data, 'registrations'),
      PATH: `${dirname(realpathSync(process.execPath))}:${dirname(binary)}:${env.PATH || ''}`,
      T3_CODEX_START_DAEMON: '0', T3_CODEX_MICRO_SOCKET: '',
    },
  };
}

function run(command, args, options = {}) {
  const result = spawnSync(command, args, { stdio: 'inherit', ...options });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`${command} failed (${result.status ?? result.signal}).`);
  return result;
}
function checkNode() {
  const [major, minor, patch] = process.versions.node.split('.').map(Number);
  if (major !== 24 || minor < 13 || (minor === 13 && patch < 1))
    throw new Error('Use Node.js 24.13.1 or newer within Node 24.');
  if (process.platform !== 'darwin' && process.platform !== 'linux')
    throw new Error('This alpha supports macOS and experimental Linux. Windows requires further work.');
}
function fingerprint() {
  return createHash('sha256').update(readFileSync(patch)).update(JSON.stringify(versions)).digest('hex');
}
function installed() {
  if (!existsSync(stamp) || JSON.parse(readFileSync(stamp)).fingerprint !== fingerprint())
    throw new Error('Run ./bridge setup for this release first.');
  if (!existsSync(binary) || !existsSync(join(source, 'apps/server/dist/client/index.html')))
    throw new Error('Installation is incomplete. Run ./bridge setup again.');
}
export function socketReady(socket) {
  return new Promise((resolveReady) => {
    const client = connect(socket);
    const finish = (ready) => { client.destroy(); resolveReady(ready); };
    client.setTimeout(1500, () => finish(false));
    client.once('connect', () => finish(true));
    client.once('error', () => finish(false));
  });
}
async function forward(command, args, env, cwd) {
  const child = spawn(command, args, { stdio: 'inherit', env, cwd });
  const terminate = () => child.kill('SIGTERM');
  process.on('SIGTERM', terminate);
  try {
    process.exitCode = await new Promise((resolveExit, reject) => {
      child.once('error', reject);
      child.once('exit', (code) => resolveExit(code ?? 1));
    });
  } finally { process.off('SIGTERM', terminate); }
}

export async function main(args = process.argv.slice(2)) {
  const [command = 'help', ...rest] = args;
  if (command === 'help' || command === '--help') {
    console.log(`T3 Codex Bridge — tester alpha
  ./bridge setup                   Fetch pinned T3/Codex, apply patch, build
  ./bridge login                   Authenticate bundled Codex (existing login is reused)
  ./bridge daemon-start            Explicitly start native daemon if no socket exists
  ./bridge serve                   Serve T3 locally in foreground
  ./bridge pair [--tailscale]       Issue private pairing link for this T3 server
  ./bridge codex [args...]          Opt this terminal session into T3
  ./bridge codex resume <id>        Continue the same native session
  ./bridge codex unshare <id>       Detach it from T3; preserve history
  ./bridge doctor                  Check installation and socket reachability

No command restarts/stops your daemon or edits shell/Codex configuration.`);
    return;
  }
  checkNode();
  const config = configuration();
  if (command === 'setup') {
    run('git', ['--version']);
    mkdirSync(runtime, { recursive: true, mode: 0o700 });
    if (!existsSync(join(source, '.git'))) {
      run('git', ['init', source]);
      run('git', ['remote', 'add', 'origin', versions.upstream], { cwd: source });
      run('git', ['fetch', '--depth=1', 'origin', versions.commit], { cwd: source });
      run('git', ['checkout', '--detach', 'FETCH_HEAD'], { cwd: source });
    }
    const head = spawnSync('git', ['rev-parse', 'HEAD'], { cwd: source, encoding: 'utf8' });
    if (head.status !== 0 || head.stdout.trim() !== versions.commit)
      throw new Error('Runtime checkout is not the pinned version. Keep your changes and use a fresh clone.');
    const applied = spawnSync('git', ['apply', '--reverse', '--check', patch], { cwd: source, stdio: 'ignore' });
    if (applied.status !== 0) {
      run('git', ['apply', '--check', patch], { cwd: source });
      run('git', ['apply', patch], { cwd: source });
    }
    const setupEnv = { ...process.env, npm_config_cache: join(runtime, 'npm-cache'),
      npm_config_store_dir: join(runtime, 'pnpm-store'), XDG_CACHE_HOME: join(runtime, 'cache') };
    run('npm', ['install', '--prefix', join(runtime, 'codex'), '--no-save', '--no-audit', '--no-fund', `@openai/codex@${versions.codex}`], { env: setupEnv });
    run('npx', ['--yes', `pnpm@${versions.pnpm}`, 'install', '--frozen-lockfile'], { cwd: source, env: setupEnv });
    run('npx', ['--yes', `pnpm@${versions.pnpm}`, 'exec', 'vp', 'run', '--filter', 't3', 'build'], { cwd: source, env: setupEnv });
    if (!existsSync(join(source, 'apps/server/dist/client/index.html'))) throw new Error('Web bundle missing.');
    writeFileSync(stamp, JSON.stringify({ fingerprint: fingerprint(), ...versions }, null, 2) + '\n', { mode: 0o600 });
    console.log('Build complete. Next: ./bridge login, ./bridge daemon-start, then ./bridge serve.');
    return;
  }
  installed();
  if (command === 'login') { run(binary, ['login', ...rest], { env: config.env }); return; }
  if (command === 'doctor') {
    run(binary, ['--version'], { env: config.env });
    console.log(`Node: ${process.versions.node}\nFile limit: ${process.env.T3_BRIDGE_FILE_LIMIT || 'unknown'}\nT3 data: ${config.data}\nCodex home: ${config.codexHome}`);
    const reachable = await socketReady(config.env.T3_CODEX_SHARED_SOCKET);
    console.log(`Daemon socket reachable: ${reachable}. This is not an MCP or conversation health check.`);
    if (!reachable) process.exitCode = 1;
    return;
  }
  if (command === 'daemon-start') {
    if (existsSync(config.env.T3_CODEX_SHARED_SOCKET)) {
      if (await socketReady(config.env.T3_CODEX_SHARED_SOCKET)) {
        console.log('Existing daemon socket is reachable; leaving it unchanged. Verify its CLI version and MCP health in a real session.');
        return;
      }
      throw new Error('Existing daemon socket is unreachable. No restart attempted. See troubleshooting.');
    }
    run(binary, ['app-server', 'daemon', 'start'], { env: config.env });
    return;
  }
  if (!['serve', 'pair', 'codex'].includes(command)) throw new Error(`Unknown command: ${command}`);
  mkdirSync(config.env.T3_CODEX_SHARED_REGISTRATIONS, { recursive: true, mode: 0o700 });
  if (command === 'codex') {
    await forward(process.execPath, [join(source, 'apps/server/src/sharedCodexTerminal.ts'), ...rest], config.env);
    return;
  }
  const server = join(source, 'apps/server/dist/bin.mjs');
  if (command === 'pair') {
    await forward(process.execPath, [server, 'pair', '--base-dir', config.env.T3CODE_HOME,
      ...(rest.includes('--tailscale') && !rest.some((arg) => arg.startsWith('--tailscale-serve-port')) ? ['--tailscale-serve-port', '8243'] : []), ...rest], config.env);
    return;
  }
  if (rest.length) throw new Error('serve takes no arguments. Set T3_BRIDGE_PORT to choose a local port.');
  if (!await socketReady(config.env.T3_CODEX_SHARED_SOCKET)) throw new Error('Daemon is not reachable. Start it explicitly with ./bridge daemon-start.');
  await forward(process.execPath, [server, 'serve', '--base-dir', config.env.T3CODE_HOME,
    '--host', '127.0.0.1', '--port', String(config.port), '--no-browser'], config.env);
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((error) => { console.error(`Bridge: ${error.message}`); process.exitCode = 1; });
}
