import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const cliPath = fileURLToPath(new URL('../../dist/cli.js', import.meta.url));
function run(args, cwd) {
  const env = { ...process.env };
  delete env.ORQIVRA_DATA_DIR;
  return spawnSync(process.execPath, [cliPath, ...args], { cwd, env, encoding: 'utf8' });
}

test('config CLI validates defaults and renders JSON or Markdown without modifying the config file', () => {
  const directory = mkdtempSync(resolve(tmpdir(), 'orqivra config CLI '));
  try {
    const missing = run(['config', 'validate'], directory);
    assert.equal(missing.status, 0, missing.stderr);
    const validation = JSON.parse(missing.stdout);
    assert.equal(validation.valid, true);
    assert.deepEqual(Object.keys(validation).sort(), ['config_source', 'fallback', 'schema_version', 'valid', 'workflow']);
    assert.equal(validation.workflow.preferred_parallelism_advisory, true);

    const discoveredPath = resolve(directory, 'orqivra.config.json');
    writeFileSync(discoveredPath, '{"workflow":{"preferred_parallelism":3}}\n');
    const discovered = run(['config', 'show', '--edition', 'codex'], directory);
    assert.equal(discovered.status, 0, discovered.stderr);
    assert.deepEqual(JSON.parse(discovered.stdout).config_source, { kind: 'file', path: 'orqivra.config.json' });
    assert.equal(JSON.parse(discovered.stdout).workflow.preferred_parallelism, 3);

    const configPath = resolve(directory, 'project config.json');
    const original = '{"workflow":{"preferred_parallelism":4}}\n';
    writeFileSync(configPath, original);
    const json = run(['config', 'show', '--edition', 'claude-code', '--config', configPath], directory);
    assert.equal(json.status, 0, json.stderr);
    assert.equal(JSON.parse(json.stdout).workflow.preferred_parallelism, 4);
    assert.equal(JSON.parse(json.stdout).roles.complex_implementer.model, 'claude-opus-5-5');

    const markdown = run(['config', 'show', '--edition', 'claude-code', '--config', configPath, '--format', 'markdown'], directory);
    assert.equal(markdown.status, 0, markdown.stderr);
    assert.match(markdown.stdout, /## Roles/);
    assert.equal(readFileSync(configPath, 'utf8'), original);

    const absent = run(['config', 'show', '--edition', 'codex', '--config', resolve(directory, 'absent.json')], directory);
    assert.equal(absent.status, 4);
    assert.match(absent.stderr, /explicitly selected config file does not exist/);
  } finally { rmSync(directory, { recursive: true, force: true }); }
});
