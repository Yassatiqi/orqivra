import assert from 'node:assert/strict';
import test from 'node:test';
import { validateGraph } from '../../dist/core/dag.js';

function node(id, dependencies = [], fileScope = [`src/${id}/**`]) {
  return { id, inputs: [], dependencies, file_scope: fileScope };
}

test('DAG graph validation rejects missing dependencies, cycles, and independent scope overlap', () => {
  assert.throws(() => validateGraph({ nodes: [node('A', ['missing'])] }), /missing dependency/);
  assert.throws(() => validateGraph({ nodes: [node('A', ['B']), node('B', ['A'])] }), /cycle/);
  assert.throws(() => validateGraph({ nodes: [node('A', [], ['src/shared/**']), node('B', [], ['src/shared/file.ts'])] }), /overlapping file scopes/);
});
