import assert from 'node:assert/strict';
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { tmpdir } from 'node:os';
import test from 'node:test';
import { readJson } from '../../dist/core/json.js';
import { validateData } from '../../dist/core/schema.js';

const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');
process.env.ORQIVRA_DATA_DIR ??= repositoryRoot;
const fixture = (name) => JSON.parse(readFileSync(resolve(repositoryRoot, 'tests/parity/fixtures', name), 'utf8'));
const zeroHash = '0'.repeat(64);

test('the schema engine validates representative instances for every shipped schema', () => {
  const schemas = new Map([
    ['attempt.schema.json', { number: 1, hypothesis: 'Test.', started_at: '2026-10-12T10:00:00Z', diagnosis: null, changes: [], verification_result: 'pending', verification_summary: null }],
    ['dag.schema.json', {
      schema_version: 1, id: 'test', objective: 'Test DAG.', input_snapshot: `sha256:${zeroHash}`,
      nodes: [{ id: 'A', objective: 'Test node.', inputs: [], dependencies: [], role: 'implementer', profile: 'generic', file_scope: ['src/**'], risk: 'low', acceptance_criteria: ['Pass.'], verification: ['Run.'], status: 'planned', attempts: 0, evidence: [], blocking_reason: null }],
    }],
    ['edition-adapter.schema.json', readJson(resolve(repositoryRoot, 'editions/codex/adapter.json'))],
    ['evidence.schema.json', { id: 'A-evidence-1', command: 'test', exit_code: 0, snapshot: `sha256:${zeroHash}`, recorded_at: '2026-10-12T10:00:00Z', artifacts: [] }],
    ['gate.schema.json', { id: 'external', description: 'External check.', required: true, status: 'NOT_RUN', evidence: [] }],
    ['profile.schema.json', readJson(resolve(repositoryRoot, 'profiles/codex.json'))],
    ['project.schema.json', fixture('valid-project.json')],
    ['skill.schema.json', { name: 'example-skill', description: 'An example skill.' }],
    ['state.schema.json', {
      schema_version: 1, project_id: 'test', project_root: repositoryRoot, dag_id: 'test', plan_hash: zeroHash,
      plan_header_hash: zeroHash, dag_snapshot: `sha256:${zeroHash}`, version: 1, input_hashes: {}, pending_resume: [],
      nodes: { A: { status: 'planned', definition_hash: zeroHash, dependencies: [], inputs: [], attempts: [], evidence: [], obligations: [], blocking_reason: null } }, events: [],
    }],
    ['usage.schema.json', { provider: 'unknown', source: 'unavailable', input_tokens: null, output_tokens: null, cache_tokens: null }],
  ]);

  for (const [schema, value] of schemas) assert.deepEqual(validateData(value, schema), [], schema);
});

test('schema validation reports invalid profiles and path traversal fields', () => {
  assert.notDeepEqual(validateData(fixture('invalid-profile.json'), 'profile.schema.json'), []);
  assert.notDeepEqual(validateData({ ...fixture('valid-project.json'), inputs: ['../escape'] }, 'project.schema.json'), []);
});

test('schema engine rejects unsupported keywords instead of silently ignoring them', () => {
  const directory = mkdtempSync(resolve(tmpdir(), 'orqivra unsupported schema keyword '));
  const priorDataDir = process.env.ORQIVRA_DATA_DIR;
  try {
    for (const name of ['schemas', 'profiles', 'skills', 'editions']) mkdirSync(resolve(directory, name));
    writeFileSync(resolve(directory, 'schemas', 'unsupported.schema.json'), JSON.stringify({
      type: 'object',
      properties: { name: { oneOf: [{ type: 'string' }, { type: 'number' }] } },
    }));
    process.env.ORQIVRA_DATA_DIR = directory;

    assert.throws(() => validateData({ name: 'ORQIVRA' }, 'unsupported.schema.json'), /Unsupported JSON Schema keyword 'oneOf'/);
  } finally {
    if (priorDataDir === undefined) delete process.env.ORQIVRA_DATA_DIR;
    else process.env.ORQIVRA_DATA_DIR = priorDataDir;
    rmSync(directory, { recursive: true, force: true });
  }
});
