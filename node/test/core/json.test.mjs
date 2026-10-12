import assert from 'node:assert/strict';
import test from 'node:test';
import { canonicalJson, parseJson, sha256Json } from '../../dist/core/json.js';

test('strict JSON rejects duplicate keys and fractional or unsafe integers', () => {
  assert.throws(() => parseJson('{"value":1,"value":2}'), /Duplicate object key/);
  assert.throws(() => parseJson('{"value":1.5}'), /Only integer JSON numbers/);
  assert.throws(() => parseJson('{"value":9007199254740992}'), /safe range/);
  assert.throws(() => parseJson('{"value":"\\ud800"}'), /lone surrogates/);
});

test('canonical JSON sorts keys and hashes UTF-8 bytes deterministically', () => {
  assert.equal(canonicalJson({ z: 1, a: 'é', list: [true, null] }), '{"a":"é","list":[true,null],"z":1}');
  assert.equal(sha256Json({ z: 1, a: 'é' }), sha256Json({ a: 'é', z: 1 }));
});
