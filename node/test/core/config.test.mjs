import assert from 'node:assert/strict';
import { cpSync, mkdirSync, mkdtempSync, readFileSync, rmSync, symlinkSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { markdownConfig, resolveConfiguration, validateProjectConfig } from '../../dist/core/config.js';
import { InputOutputError } from '../../dist/core/errors.js';

const scratch = () => mkdtempSync(resolve(tmpdir(), 'orqivra config test '));
const save = (directory, text) => {
  const path = resolve(directory, 'orqivra.config.json');
  writeFileSync(path, text);
  return path;
};

test('missing auto-discovered configuration uses defaults and reports that source', () => {
  const directory = scratch();
  try {
    const result = resolveConfiguration('codex', undefined, directory);
    assert.deepEqual(result.config_source, { kind: 'defaults', path: null });
    assert.equal(result.workflow.preferred_route, 'recommend');
    assert.equal(result.workflow.preferred_parallelism, 2);
  } finally { rmSync(directory, { recursive: true, force: true }); }
});

test('explicitly selected missing config is an actionable I/O error', () => {
  const directory = scratch();
  try {
    assert.throws(
      () => resolveConfiguration('codex', resolve(directory, 'missing.json')),
      /explicitly selected config file does not exist.*Create it or choose an existing path with --config/,
    );
  } finally { rmSync(directory, { recursive: true, force: true }); }
});

test('a missing discovery parent is an inspection error rather than a defaults fallback', () => {
  const directory = scratch();
  try {
    assert.throws(
      () => resolveConfiguration('codex', undefined, resolve(directory, 'missing working directory')),
      /Could not inspect the discovered config location/,
    );
  } finally { rmSync(directory, { recursive: true, force: true }); }
});

test('dangling discovered config symlinks never fall back to defaults', (context) => {
  const directory = scratch();
  try {
    const linkPath = resolve(directory, 'orqivra.config.json');
    try {
      symlinkSync(resolve(directory, 'missing target.json'), linkPath, 'file');
    } catch (error) {
      if (process.platform === 'win32' && error.code === 'EPERM') {
        context.skip(`The platform does not allow creating a dangling symlink for this test: ${error.code}`);
        return;
      }
      throw error;
    }
    assert.throws(() => resolveConfiguration('codex', undefined, directory), (error) => {
      assert.ok(error instanceof InputOutputError);
      assert.equal(error.exitCode, 4);
      assert.match(error.message, /Could not read config file/);
      assert.match(error.message, /orqivra\.config\.json/);
      return true;
    });
  } finally { rmSync(directory, { recursive: true, force: true }); }
});

test('empty, whitespace-only, and empty-object config inherit all defaults', () => {
  const directory = scratch();
  try {
    for (const text of ['', ' \r\n\t', '{}']) {
      const path = save(directory, text);
      const result = resolveConfiguration('claude-code', path);
      assert.equal(result.workflow.preferred_parallelism, 2);
      assert.equal(result.fallback.policy, 'none');
      assert.equal(result.roles.implementer.model, 'claude-sonnet-5-5');
    }

    const emptyOverrides = save(directory, JSON.stringify({
      editions: { 'claude-code': { roles: { implementer: { provider: '', model: '' } } } },
    }));
    const inherited = resolveConfiguration('claude-code', emptyOverrides).roles.implementer;
    assert.equal(inherited.provider, 'anthropic');
    assert.equal(inherited.model, 'claude-sonnet-5-5');
    assert.equal(inherited.model_source, 'catalog');
  } finally { rmSync(directory, { recursive: true, force: true }); }
});

test('partial config recursively inherits defaults and rejects malformed or duplicate JSON', () => {
  const directory = scratch();
  try {
    const path = save(directory, JSON.stringify({ workflow: { preferred_parallelism: 3 } }));
    const valid = validateProjectConfig(path);
    assert.equal(valid.workflow.preferred_route, 'recommend');
    assert.equal(valid.workflow.preferred_parallelism, 3);
    assert.throws(() => resolveConfiguration('codex', save(directory, '{"workflow":{},"workflow":{}}')), /Duplicate object key/);
    assert.throws(() => resolveConfiguration('codex', save(directory, '{broken')), /Object keys must be strings/);
    const invalidUtf8 = resolve(directory, 'invalid-utf8.json');
    writeFileSync(invalidUtf8, Buffer.from([0xff, 0xfe]));
    assert.throws(() => resolveConfiguration('codex', invalidUtf8), /Config file is not valid UTF-8/);
    assert.throws(() => resolveConfiguration('codex', save(directory, JSON.stringify({ unexpected: true }))), /additional property is not allowed/);
  } finally { rmSync(directory, { recursive: true, force: true }); }
});

test('reasoning inheritance is retained only for a proven compatible model change', () => {
  const directory = scratch();
  try {
    const sameModelPath = save(directory, JSON.stringify({
      editions: { codex: { roles: { implementer: { model: 'gpt-6-luna' } } } },
    }));
    assert.deepEqual(resolveConfiguration('codex', sameModelPath).roles.implementer.reasoning, {
      control: 'codex.model_reasoning_effort', value: 'max',
    });
    assert.equal(resolveConfiguration('codex', sameModelPath).roles.implementer.runtime_qualification, 'NOT_RUN');
    assert.match(resolveConfiguration('codex', sameModelPath).roles.implementer.client_instructions, /UNVERIFIED; catalog does not enumerate compatible values/);

    const unknownCompatibilityPath = save(directory, JSON.stringify({
      editions: { codex: { roles: { implementer: { model: 'gpt-6-sol' } } } },
    }));
    assert.throws(() => resolveConfiguration('codex', unknownCompatibilityPath), /cannot be confirmed.*Set reasoning: null/);

    const clearedPath = save(directory, JSON.stringify({
      editions: { codex: { roles: { implementer: { model: 'gpt-6-sol', reasoning: null } } } },
    }));
    const cleared = resolveConfiguration('codex', clearedPath).roles.implementer;
    assert.equal(cleared.reasoning, null);
    assert.equal(cleared.reasoning_resolution, 'client-default');

    const assetCopy = resolve(directory, 'assets');
    for (const name of ['defaults', 'models', 'profiles', 'schemas', 'skills', 'editions']) mkdirSync(resolve(assetCopy, name), { recursive: true });
    const repoRoot = fileURLToPath(new URL('../../..', import.meta.url));
    for (const [source, target] of [
      ['defaults/config.json', 'defaults/config.json'],
      ['models/catalog.json', 'models/catalog.json'],
      ['schemas/config.schema.json', 'schemas/config.schema.json'],
      ['schemas/model-catalog.schema.json', 'schemas/model-catalog.schema.json'],
      ['schemas/profile-v2.schema.json', 'schemas/profile-v2.schema.json'],
      ['profiles/claude-code.json', 'profiles/claude-code.json'],
    ]) {
      writeFileSync(resolve(assetCopy, target), readFileSync(resolve(repoRoot, source)));
    }
    const catalogVersion = JSON.parse(readFileSync(resolve(assetCopy, 'models/catalog.json'), 'utf8')).version;
    const profilePath = resolve(assetCopy, 'profiles/claude-code.json');
    const profile = JSON.parse(readFileSync(profilePath, 'utf8'));
    profile.roles.implementer.reasoning = { control: 'claude-code.effort', value: 'high' };
    writeFileSync(profilePath, `${JSON.stringify(profile)}\n`);
    const priorAssetDir = process.env.ORQIVRA_DATA_DIR;
    try {
      process.env.ORQIVRA_DATA_DIR = assetCopy;
      profile.catalog_version = 'stale-catalog';
      writeFileSync(profilePath, `${JSON.stringify(profile)}\n`);
      assert.throws(() => resolveConfiguration('claude-code'), /references catalog version 'stale-catalog'.*loaded model catalog/);
      profile.catalog_version = catalogVersion;
      writeFileSync(profilePath, `${JSON.stringify(profile)}\n`);
      const compatiblePath = save(directory, JSON.stringify({
        editions: { 'claude-code': { roles: { implementer: { model: 'claude-opus-5-5' } } } },
      }));
      const compatible = resolveConfiguration('claude-code', compatiblePath).roles.implementer;
      assert.deepEqual(compatible.reasoning, { control: 'claude-code.effort', value: 'high' });
      assert.equal(compatible.reasoning_resolution, 'profile');
    } finally {
      if (priorAssetDir === undefined) delete process.env.ORQIVRA_DATA_DIR;
      else process.env.ORQIVRA_DATA_DIR = priorAssetDir;
    }
  } finally { rmSync(directory, { recursive: true, force: true }); }
});

test('explicit reasoning is checked against known model controls and values with an actionable error', () => {
  const directory = scratch();
  try {
    const incompatible = save(directory, JSON.stringify({
      editions: { 'claude-code': { roles: { implementer: { reasoning: { control: 'claude-code.effort', value: 'ultra' } } } } },
    }));
    assert.throws(() => resolveConfiguration('claude-code', incompatible), (error) => {
      assert.match(error.message, /editions\.claude-code\.roles\.implementer\.reasoning\.value is unsupported/);
      assert.match(error.message, /Choose one of: low, medium, high, xhigh, max/);
      assert.match(error.message, /set reasoning: null/);
      assert.doesNotMatch(error.message, /ultra/);
      return true;
    });

    const valid = save(directory, JSON.stringify({
      editions: { 'claude-code': { roles: { implementer: { reasoning: { control: 'claude-code.effort', value: 'high' } } } } },
    }));
    const role = resolveConfiguration('claude-code', valid).roles.implementer;
    assert.deepEqual(role.reasoning, { control: 'claude-code.effort', value: 'high' });
    assert.equal(role.reasoning_resolution, 'configuration');
    assert.equal(role.documentation_status, 'documented');
  } finally { rmSync(directory, { recursive: true, force: true }); }
});

test('custom models require explicit user-supplied provenance and remain unqualified', () => {
  const directory = scratch();
  try {
    const missingSource = save(directory, JSON.stringify({
      editions: { codex: { roles: { implementer: { model: 'local-codex-model' } } } },
    }));
    assert.throws(() => resolveConfiguration('codex', missingSource), /model_source: "user-supplied"/);

    const custom = save(directory, JSON.stringify({
      editions: { codex: { roles: { implementer: {
        model: 'local-codex-model', model_source: 'user-supplied',
        reasoning: { control: 'codex.model_reasoning_effort', value: 'custom-level' },
      } } } },
    }));
    const result = resolveConfiguration('codex', custom);
    assert.equal(result.roles.implementer.model_source, 'user-supplied');
    assert.match(result.roles.implementer.client_instructions, /UNVERIFIED/);
    assert.equal(result.roles.implementer.runtime_qualification, 'UNVERIFIED');
    assert.equal(result.roles.implementer.documentation_status, 'user-supplied');

    const mislabeled = save(directory, JSON.stringify({
      editions: { codex: { roles: { implementer: { model: 'gpt-6-luna', model_source: 'user-supplied' } } } },
    }));
    assert.throws(() => resolveConfiguration('codex', mislabeled), (error) => {
      assert.match(error.message, /editions\.codex\.roles\.implementer\.model_source/);
      assert.match(error.message, /cannot mark a catalog model as user-supplied/);
      assert.doesNotMatch(error.message, /gpt-6-luna/);
      return true;
    });
  } finally { rmSync(directory, { recursive: true, force: true }); }
});

test('Gemini models reject reasoning controls and config output is advisory', () => {
  const directory = scratch();
  try {
    const invalid = save(directory, JSON.stringify({
      editions: { 'gemini-cli': { roles: { implementer: { reasoning: { control: 'codex.model_reasoning_effort', value: 'high' } } } } },
    }));
    assert.throws(() => resolveConfiguration('gemini-cli', invalid), /control is incompatible with gemini-cli/);
    const report = resolveConfiguration('gemini-cli');
    assert.match(markdownConfig(report), /advisory maximum/);
    assert.equal(report.roles.complex_implementer.model, 'gemini-3.1-pro-preview');
    assert.match(report.roles.complex_implementer.client_instructions, /fallback/);
  } finally { rmSync(directory, { recursive: true, force: true }); }
});
