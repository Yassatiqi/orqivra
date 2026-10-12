import assert from 'node:assert/strict';
import { mkdirSync, mkdtempSync, rmSync } from 'node:fs';
import { resolve } from 'node:path';
import { tmpdir } from 'node:os';
import test from 'node:test';
import { planHashes, validateGraph } from '../../dist/core/dag.js';

function node(id, dependencies = [], fileScope = [`src/${id}/**`]) {
  return { id, inputs: [], dependencies, file_scope: fileScope };
}

test('DAG graph validation rejects missing dependencies, cycles, and independent scope overlap', () => {
  assert.throws(() => validateGraph({ nodes: [node('A', ['missing'])] }), /missing dependency/);
  assert.throws(() => validateGraph({ nodes: [node('A', ['B']), node('B', ['A'])] }), /cycle/);
  assert.throws(() => validateGraph({ nodes: [node('A', [], ['src/shared/**']), node('B', [], ['src/shared/file.ts'])] }), /overlapping file scopes/);
});

test('input hashing rejects existing directories in normal and recovery modes', () => {
  const directory = mkdtempSync(resolve(tmpdir(), 'orqivra dag input type '));
  try {
    const project = resolve(directory, 'project');
    mkdirSync(project);
    mkdirSync(resolve(project, 'input-directory'));
    const dag = { id: 'input-type-test', nodes: [node('A')] };
    dag.nodes[0].inputs = ['input-directory'];

    assert.throws(() => planHashes(dag, project), /not a regular file/);
    assert.throws(() => planHashes(dag, project, true), /not a regular file/);

    dag.nodes[0].inputs = ['missing-input.txt'];
    assert.throws(() => planHashes(dag, project), /Required input file does not exist/);
    assert.deepEqual(Object.keys(planHashes(dag, project, true).inputHashes), []);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});
