import assert from 'node:assert/strict';
import { mkdtempSync, rmSync, symlinkSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const cliPath = fileURLToPath(new URL('../../dist/cli.js', import.meta.url));

test('config show rejects a dangling discovered config through the public I/O error path', (context) => {
  const directory = mkdtempSync(resolve(tmpdir(), 'orqivra dangling config CLI '));
  try {
    const linkPath = resolve(directory, 'orqivra.config.json');
    try {
      symlinkSync(resolve(directory, 'missing target.json'), linkPath, 'file');
    } catch (error) {
      if (process.platform === 'win32' && error.code === 'EPERM') {
        context.skip(`Windows denied creation of the dangling symlink fixture: ${error.code}`);
        return;
      }
      throw error;
    }

    const env = { ...process.env };
    delete env.ORQIVRA_DATA_DIR;
    const result = spawnSync(process.execPath, [cliPath, 'config', 'show', '--edition', 'codex'], {
      cwd: directory,
      env,
      encoding: 'utf8',
    });
    assert.equal(result.error, undefined);
    assert.equal(result.status, 4);
    assert.equal(result.stdout, '');
    assert.match(result.stderr, /^orqivra: Could not read config file /);
    assert.match(result.stderr, /orqivra\.config\.json/);
    assert.doesNotMatch(result.stderr, /\n\s+at /);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});
