import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');
const fixtureRoot = resolve(repositoryRoot, 'tests/parity/fixtures');
const cases = JSON.parse(readFileSync(resolve(fixtureRoot, 'cases.json'), 'utf8'));
const cli = resolve(repositoryRoot, 'node/dist/cli.js');

test('Node CLI matches every shared schema and planning fixture', () => {
  for (const item of [...cases.validation_cases, ...cases.planning_cases]) {
    const source = item.source.startsWith('profiles/') || item.source.startsWith('examples/')
      ? resolve(repositoryRoot, item.source)
      : resolve(fixtureRoot, item.source);
    const args = item.operation === 'plan'
      ? ['plan', source]
      : ['validate', item.operation.replace('validate_', ''), source];
    const result = spawnSync(process.execPath, [cli, ...args], { cwd: repositoryRoot, encoding: 'utf8' });
    assert.equal(result.status, item.exit_code, `${item.id}: ${result.stderr}`);
    if (Object.hasOwn(item, 'json')) assert.deepEqual(JSON.parse(result.stdout), item.json, item.id);
  }
});
