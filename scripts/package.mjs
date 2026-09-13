import { cpSync, mkdirSync, readFileSync, writeFileSync, existsSync, readdirSync, statSync, realpathSync, mkdtempSync, renameSync } from 'node:fs';
import { join, dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const versions = JSON.parse(readFileSync(join(root, 'versions.json')));
if (process.platform !== 'darwin') throw new Error('Build Mac packages on their target Mac architecture.');
if (process.version !== `v${versions.node}`) throw new Error(`Packaging requires Node ${versions.node}.`);
const source = join(root, '.runtime/t3');
const { selectCliRuntimeExternalDependencies } = await import(join(source, 'scripts/lib/cli-external-packages.ts'));
const name = `t3-codex-bridge-darwin-${process.arch}`;
const destination = join(root, 'dist', name);
if (existsSync(destination)) throw new Error('Completed output exists; preserve it before rebuilding.');
mkdirSync(join(root, 'dist'), { recursive: true });
const output = mkdtempSync(join(root, 'dist', name + '.build-'));
const copy = (from, to) => { mkdirSync(dirname(to), { recursive: true }); cpSync(from, to, { recursive: true, dereference: true }); };
for (const file of ['versions.json', 'package.json', 'README.md', 'LICENSE', 'NOTICE']) copy(join(root, file), join(output, file));
copy(join(root, 'bin/bridge'), join(output, 'bin/bridge'));
copy(realpathSync(process.execPath), join(output, 'runtime/node/bin/node'));
copy(join(dirname(dirname(realpathSync(process.execPath))), 'LICENSE'), join(output, 'runtime/node/LICENSE'));
copy(join(root, 'go.mod'), join(output, 'runtime/go/go.mod'));
copy(join(root, 'go.sum'), join(output, 'runtime/go/go.sum'));
const codexLicense = await fetch(`https://raw.githubusercontent.com/openai/codex/rust-v${versions.codex}/LICENSE`, { signal: AbortSignal.timeout(15000) });
if (!codexLicense.ok) throw new Error('Pinned Codex license is unavailable');
mkdirSync(join(output, 'runtime/codex'), { recursive: true });
writeFileSync(join(output, 'runtime/codex/LICENSE'), await codexLicense.text());
const server = join(output, 'runtime/t3/apps/server');
copy(join(source, 'apps/server/dist'), join(server, 'dist'));
const manifest = JSON.parse(readFileSync(join(source, 'apps/server/package.json')));
const roots = selectCliRuntimeExternalDependencies(manifest.dependencies);
for (const name of Object.keys(roots)) roots[name] = JSON.parse(readFileSync(join(source, 'apps/server/node_modules', name, 'package.json'))).version;
writeFileSync(join(server, 'package.json'), JSON.stringify({ name: 't3-bridge-runtime', version: '0.2.0-alpha.1', private: true, type: 'module', dependencies: roots }, null, 2));
const env = { ...process.env, PATH: `${dirname(process.execPath)}:${process.env.PATH}` };
const npm = spawnSync('npm', ['install', '--prefix', server, '--omit=dev', '--no-audit', '--no-fund', '--cache', join(root, '.runtime/npm-package-cache')], { env, stdio: 'inherit' });
if (npm.error || npm.status !== 0) throw npm.error || new Error('Native runtime dependency installation failed');
const arch = process.arch === 'arm64' ? 'aarch64' : 'x86_64';
const vendor = join(root, '.runtime/codex/node_modules/@openai', `codex-darwin-${process.arch}`, 'vendor', `${arch}-apple-darwin`);
copy(join(vendor, 'bin'), join(output, 'runtime/codex/bin'));
if (existsSync(join(vendor, 'path'))) copy(join(vendor, 'path'), join(output, 'runtime/codex/bin'));
copy(join(root, '.runtime/codex/node_modules/@openai/codex/package.json'), join(output, 'runtime/codex/package.json'));
const sbom = spawnSync('npm', ['sbom', '--prefix', server, '--sbom-format=cyclonedx', '--omit=dev', '--cache', join(root, '.runtime/npm-package-cache')], { env, encoding: 'utf8' });
if (sbom.error || sbom.status !== 0) throw new Error('Runtime dependency SBOM generation failed');
writeFileSync(join(output, 'runtime-sbom.json'), sbom.stdout);
const inventory = [];
function walk(dir) {
 for (const entry of readdirSync(dir, { withFileTypes: true })) {
  const path = join(dir, entry.name);
  if (entry.isDirectory()) walk(path);
  else if (entry.isFile()) inventory.push({ path: path.slice(output.length + 1), sha256: createHash('sha256').update(readFileSync(path)).digest('hex'), bytes: statSync(path).size });
  else if (entry.isSymbolicLink()) { if (!realpathSync(path).startsWith(output + '/')) throw new Error('External package symlink'); }
 }
}
walk(output);
writeFileSync(join(output, 'manifest.json'), JSON.stringify({ schemaVersion: 1, platform: process.platform, architecture: process.arch, versions, files: inventory }, null, 2));
renameSync(output, destination);
const zip = spawnSync('/usr/bin/ditto', ['-c', '-k', '--keepParent', destination, destination + '.zip'], { stdio: 'inherit' });
if (zip.error || zip.status !== 0) throw new Error('Archive creation failed');
writeFileSync(destination + '.zip.sha256', createHash('sha256').update(readFileSync(destination + '.zip')).digest('hex') + '  ' + name + '.zip\n');
console.log(`Unsigned preview staged: ${destination}`);
