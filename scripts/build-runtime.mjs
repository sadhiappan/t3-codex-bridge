import { spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const versions = JSON.parse(readFileSync(join(root, 'versions.json')));
const runtime = join(root, '.runtime');
const source = join(runtime, 't3');
const patch = join(root, 'shared-codex.patch');
const stamp = join(runtime, 'installed.json');
const productionEnvironment = { VITE_DEV_SERVER_URL: undefined, VITE_HTTP_URL: undefined, VITE_WS_URL: undefined, T3CODE_TAILSCALE_SERVE: 'false' };
function run(command, args, options = {}) {
 const result = spawnSync(command, args, { stdio: 'inherit', ...options });
 if (result.error) throw result.error;
 if (result.status !== 0) throw new Error(`${command} failed (${result.status ?? result.signal})`);
}
function main() {
 const command = process.argv[2];
 if (process.version !== `v${versions.node}`) throw new Error(`Source builds require Node ${versions.node}.`);
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
    const setupEnv = { ...process.env, ...productionEnvironment, npm_config_cache: join(runtime, 'npm-cache'),
      npm_config_store_dir: join(runtime, 'pnpm-store'), XDG_CACHE_HOME: join(runtime, 'cache') };
    run('npm', ['install', '--prefix', join(runtime, 'codex'), '--no-save', '--no-audit', '--no-fund', `@openai/codex@${versions.codex}`], { env: setupEnv });
    run('npx', ['--yes', `pnpm@${versions.pnpm}`, 'install', '--frozen-lockfile'], { cwd: source, env: setupEnv });
    run('npx', ['--yes', `pnpm@${versions.pnpm}`, 'exec', 'vp', 'run', '--filter', 't3', 'build'], { cwd: source, env: setupEnv });
    if (!existsSync(join(source, 'apps/server/dist/client/index.html'))) throw new Error('Web bundle missing.');
    writeFileSync(stamp, JSON.stringify({ patchSHA256: createHash('sha256').update(readFileSync(patch)).digest('hex'), ...versions }, null, 2) + '\n', { mode: 0o600 });
    console.log('Pinned T3 runtime build complete.');
    return;
  }
 throw new Error('This is a source-build helper. Use bridge for runtime commands.');
}
main();
