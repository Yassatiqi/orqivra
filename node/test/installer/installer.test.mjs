import assert from 'node:assert/strict';
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { basename, resolve } from 'node:path';
import test from 'node:test';
import { buildBundle, installSkills, renderEditionSkills, uninstallSkills, validateSkills, verifyInstall } from '../../dist/commands/installer.js';

test('canonical skills render into all three validated client editions', () => {
  const expected = new Map([
    ['claude-code', [828, 890, 876, 857]],
    ['codex', [835, 897, 883, 864]],
    ['gemini-cli', [825, 887, 873, 854]],
  ]);
  for (const [edition, words] of expected) {
    const { skills, adapter } = renderEditionSkills(edition);
    assert.equal(skills.length, 4);
    assert.equal(adapter.edition, edition);
    assert.deepEqual(skills.map((skill) => skill.words), words);
    assert.ok(skills.every((skill) => !skill.text.includes('ORQIVRA_CLIENT_ADAPTER')));
  }
});

test('bundle generation includes native skill paths, schemas, adapter data, and the MIT license', () => {
  const directory = mkdtempSync(resolve(tmpdir(), 'orqivra bundle test '));
  try {
    const output = resolve(directory, 'bundle output');
    const built = buildBundle('all', output);
    assert.equal(built.length, 3);
    const nativePaths = { codex: '.agents/skills', 'claude-code': '.claude/skills', 'gemini-cli': '.gemini/skills' };
    for (const path of built) {
      const edition = basename(path);
      assert.ok(readFileSync(resolve(path, 'BUILD-MANIFEST.json'), 'utf8').includes('"framework_version": "0.2.0"'));
      assert.ok(readFileSync(resolve(path, 'LICENSE'), 'utf8').includes('Permission is hereby granted'));
      assert.ok(readFileSync(resolve(path, 'schemas', 'state.schema.json'), 'utf8').includes('ORQIVRA Session State'));
      assert.ok(readFileSync(resolve(path, 'editions', edition, 'adapter.json'), 'utf8').includes('native_skills_path'));
      assert.equal(validateSkills(resolve(path, nativePaths[edition])).count, 4);
    }
    assert.throws(() => buildBundle('codex', output), /new or empty directory/);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test('manifest-scoped install, verification, dry-run, and uninstall preserve unrelated or modified files', () => {
  const directory = mkdtempSync(resolve(tmpdir(), 'orqivra install test '));
  try {
    const target = resolve(directory, 'explicit client skills target');
    const dryRun = installSkills('codex', target, ['orqivra-orchestrate']);
    assert.equal(dryRun.dry_run, true);
    assert.deepEqual(dryRun.files, ['orqivra-orchestrate/SKILL.md']);

    const applied = installSkills('codex', target, ['orqivra-orchestrate'], true);
    assert.equal(applied.dry_run, false);
    assert.equal(verifyInstall(target).verified_files, 1);
    const installed = resolve(target, 'orqivra-orchestrate', 'SKILL.md');
    const original = readFileSync(installed);
    writeFileSync(installed, Buffer.concat([original, Buffer.from('\nUser change.\n')]));
    assert.throws(() => verifyInstall(target), /missing or modified/);
    assert.throws(() => installSkills('codex', target, ['orqivra-orchestrate'], true), /modified/);
    assert.throws(() => uninstallSkills(target, true), /missing or modified/);
    assert.ok(readFileSync(installed).toString('utf8').endsWith('User change.\n'));

    writeFileSync(installed, original);
    const unrelated = resolve(target, 'unrelated-user-file.txt');
    writeFileSync(unrelated, 'Keep this file.\n');
    const removed = uninstallSkills(target, true);
    assert.equal(removed.verified_files, 1);
    assert.equal(readFileSync(unrelated, 'utf8'), 'Keep this file.\n');
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test('installer refuses unowned collisions and modified destinations', () => {
  const directory = mkdtempSync(resolve(tmpdir(), 'orqivra collision test '));
  try {
    const target = resolve(directory, 'skills');
    const collision = resolve(target, 'orqivra-recover', 'SKILL.md');
    const original = 'Preserve this unowned file.\n';
    mkdirSync(resolve(collision, '..'), { recursive: true });
    writeFileSync(collision, original);
    assert.throws(() => installSkills('codex', target, ['orqivra-recover'], true), /Unowned destination/);
    assert.equal(readFileSync(collision, 'utf8'), original);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});
