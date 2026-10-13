import assert from 'node:assert/strict';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const cliPath = fileURLToPath(new URL('../../dist/cli.js', import.meta.url));

test('config CLI diagnostics redact values, arbitrary keys, and semantic overrides', () => {
  const directory = mkdtempSync(resolve(tmpdir(), 'orqivra config safe '));
  try {
    const cases = [
      ['object', { workflow: { preferred_parallelism: { api_key: 'AUDIT_SECRET_SENTINEL_OBJECT' } } }, ['config', 'validate']],
      ['scalar', { workflow: { preferred_parallelism: 'AUDIT_SECRET_SENTINEL_SCALAR' } }, ['config', 'validate']],
      ['array', { workflow: { preferred_parallelism: ['AUDIT_SECRET_SENTINEL_ARRAY'] } }, ['config', 'validate']],
      ['unknown', { AUDIT_SECRET_SENTINEL_KEY: { api_key: 'AUDIT_SECRET_SENTINEL_UNKNOWN' } }, ['config', 'validate']],
      ['nested-unknown', { workflow: { AUDIT_SECRET_SENTINEL_NESTED_KEY: 'AUDIT_SECRET_SENTINEL_NESTED_VALUE' } }, ['config', 'validate']],
      ['provider', { editions: { codex: { roles: { implementer: { provider: 'AUDIT_SECRET_SENTINEL_PROVIDER' } } } } }, ['config', 'show', '--edition', 'codex']],
      ['model', { editions: { codex: { roles: { implementer: { model: 'AUDIT_SECRET_SENTINEL_MODEL' } } } } }, ['config', 'show', '--edition', 'codex']],
      ['reasoning-value', { editions: { 'claude-code': { roles: { implementer: { reasoning: { control: 'claude-code.effort', value: 'AUDIT_SECRET_SENTINEL_REASONING' } } } } } }, ['config', 'show', '--edition', 'claude-code']],
      ['reasoning-control', { editions: { 'claude-code': { roles: { implementer: { reasoning: { control: 'AUDIT_SECRET_SENTINEL_CONTROL', value: 'high' } } } } } }, ['config', 'validate']],
    ];
    for (const [name, config, command] of cases) {
      const configPath = resolve(directory, `${name}.json`);
      writeFileSync(configPath, JSON.stringify(config));
      const result = spawnSync(process.execPath, [cliPath, ...command, '--config', configPath], { cwd: directory, encoding: 'utf8' });
      assert.equal(result.status, 2, `${name}: ${result.stderr}`);
      assert.doesNotMatch(`${result.stdout}\n${result.stderr}`, /AUDIT_SECRET_SENTINEL/);
      assert.doesNotMatch(result.stderr, /Traceback/);
      assert.match(result.stderr, /^orqivra:/);
    }

    const duplicatePath = resolve(directory, 'duplicate.json');
    writeFileSync(duplicatePath, '{"AUDIT_SECRET_SENTINEL_DUPLICATE":1,"AUDIT_SECRET_SENTINEL_DUPLICATE":2}');
    const duplicate = spawnSync(process.execPath, [cliPath, 'config', 'validate', '--config', duplicatePath], { cwd: directory, encoding: 'utf8' });
    assert.equal(duplicate.status, 2, duplicate.stderr);
    assert.doesNotMatch(`${duplicate.stdout}\n${duplicate.stderr}`, /AUDIT_SECRET_SENTINEL/);
    assert.match(duplicate.stderr, /Duplicate object key/);
  } finally { rmSync(directory, { recursive: true, force: true }); }
});

test('config CLI diagnostics show trusted schema constraints and corrective actions', () => {
  const directory = mkdtempSync(resolve(tmpdir(), 'orqivra config constraints '));
  const reasoningControlConfig = {
    editions: {
      codex: {
        roles: {
          implementer: {
            reasoning: { control: 'AUDIT_SECRET_SENTINEL_CONTROL', value: 'high' },
          },
        },
      },
    },
  };
  const providerConfig = {
    editions: {
      codex: {
        roles: {
          implementer: { provider: 'AUDIT_SECRET_SENTINEL_PROVIDER' },
        },
      },
    },
  };
  const cases = [
    ['schema-version', { schema_version: 'AUDIT_SECRET_SENTINEL_SCHEMA' }, ['config', 'validate'], 'schema_version: must use the schema-defined value 1. Restore this documented value.'],
    ['fallback-policy', { fallback: { policy: 'AUDIT_SECRET_SENTINEL_FALLBACK' } }, ['config', 'validate'], 'fallback.policy: must use the schema-defined value "none". Restore this documented value.'],
    ['preferred-route', { workflow: { preferred_route: 'AUDIT_SECRET_SENTINEL_ROUTE' } }, ['config', 'validate'], 'workflow.preferred_route: must be one of the documented values: "recommend", "solo", "delegate", "audit", "full". Choose one of these values.'],
    ['parallelism-type', { workflow: { preferred_parallelism: { api_key: 'AUDIT_SECRET_SENTINEL_PARALLELISM' } } }, ['config', 'validate'], 'workflow.preferred_parallelism: expected integer. Set this field to a whole number.'],
    ['parallelism-minimum', { workflow: { preferred_parallelism: 0 } }, ['config', 'validate'], 'workflow.preferred_parallelism: must be at least 1. Increase this value to at least 1.'],
    ['parallelism-maximum', { workflow: { preferred_parallelism: 9 } }, ['config', 'validate'], 'workflow.preferred_parallelism: must be at most 8. Reduce this value to no more than 8.'],
    [
      'reasoning-control',
      reasoningControlConfig,
      ['config', 'validate'],
      'reasoning.control: must be one of the documented values: "codex.model_reasoning_effort", "claude-code.effort". Choose one of these values.',
    ],
    [
      'provider',
      providerConfig,
      ['config', 'show', '--edition', 'codex'],
      'provider must be "openai" for this edition. Set provider to "openai" or omit it to inherit the edition provider.',
    ],
  ];
  try {
    for (const [name, config, command, expected] of cases) {
      const configPath = resolve(directory, `${name}.json`);
      writeFileSync(configPath, JSON.stringify(config));
      const result = spawnSync(process.execPath, [cliPath, ...command, '--config', configPath], { cwd: directory, encoding: 'utf8' });
      const diagnostic = `${result.stdout}\n${result.stderr}`;
      assert.equal(result.status, 2, `${name}: ${result.stderr}`);
      assert.ok(diagnostic.includes(expected), `${name}: missing safe constraint/remediation: ${diagnostic}`);
      assert.doesNotMatch(diagnostic, /AUDIT_SECRET_SENTINEL/);
      assert.doesNotMatch(result.stderr, /Traceback/);
    }
  } finally { rmSync(directory, { recursive: true, force: true }); }
});
