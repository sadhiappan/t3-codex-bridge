import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync, readFileSync, symlinkSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');

test('public patch contains no hardware bridge or personal host paths', () => {
  const patch = readFileSync(join(root, 'shared-codex.patch'), 'utf8');
  assert.doesNotMatch(patch, /microRequest|codex-micro|sharedCodexMicroClient|\/Users\/|\.ts\.net/);
});
test('shell launcher resolves absolute and relative symlinks from another directory', () => {
  const directory = mkdtempSync(join(tmpdir(), 'bridge links '));
  try {
    const absoluteLink = join(directory, 'absolute bridge');
    const relativeLink = join(directory, 'relative bridge');
    symlinkSync(join(root, 'bridge'), absoluteLink);
    symlinkSync('absolute bridge', relativeLink);
    for (const launcher of [absoluteLink, relativeLink]) {
      const result = spawnSync(launcher, ['--help'], { cwd: directory, encoding: 'utf8' });
      assert.equal(result.status, 0, result.stderr);
      assert.match(result.stdout, /codex resume/);
    }
  } finally { rmSync(directory, { recursive: true, force: true }); }
});
