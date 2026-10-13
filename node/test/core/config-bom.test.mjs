import assert from 'node:assert/strict';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { resolve } from 'node:path';
import test from 'node:test';
import { resolveConfiguration, validateProjectConfig } from '../../dist/core/config.js';

test('config accepts exactly one leading UTF-8 BOM for empty and nonempty files', () => {
  const directory = mkdtempSync(resolve(tmpdir(), 'orqivra config BOM '));
  try {
    const empty = resolve(directory, 'empty.json');
    writeFileSync(empty, Buffer.from([0xef, 0xbb, 0xbf, 0x7b, 0x7d]));
    assert.equal(validateProjectConfig(empty).workflow.preferred_parallelism, 2);

    const configured = resolve(directory, 'configured.json');
    writeFileSync(configured, Buffer.concat([
      Buffer.from([0xef, 0xbb, 0xbf]),
      Buffer.from('{"workflow":{"preferred_parallelism":3}}'),
    ]));
    assert.equal(resolveConfiguration('codex', configured).workflow.preferred_parallelism, 3);
  } finally { rmSync(directory, { recursive: true, force: true }); }
});

test('config rejects multiple or misplaced BOMs and malformed UTF-8', () => {
  const directory = mkdtempSync(resolve(tmpdir(), 'orqivra config BOM invalid '));
  try {
    const cases = [
      ['multiple', Buffer.from([0xef, 0xbb, 0xbf, 0xef, 0xbb, 0xbf, 0x7b, 0x7d])],
      ['misplaced', Buffer.concat([Buffer.from('{"workflow":'), Buffer.from([0xef, 0xbb, 0xbf]), Buffer.from('{"preferred_parallelism":3}}')])],
      ['invalid-utf8', Buffer.from([0x7b, 0xff, 0x7d])],
    ];
    for (const [name, bytes] of cases) {
      const configPath = resolve(directory, `${name}.json`);
      writeFileSync(configPath, bytes);
      assert.throws(() => resolveConfiguration('codex', configPath));
    }
  } finally { rmSync(directory, { recursive: true, force: true }); }
});
