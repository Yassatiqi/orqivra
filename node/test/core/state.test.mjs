import assert from 'node:assert/strict';
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { beginAttempt, diagnose, initializeState, readState, recordVerification, transition } from '../../dist/core/state.js';

const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');
process.env.ORQIVRA_DATA_DIR ??= repositoryRoot;

function testDag() {
  return {
    schema_version: 1,
    id: 'state-test',
    objective: 'Test the Node state engine.',
    input_snapshot: `sha256:${'0'.repeat(64)}`,
    nodes: [{
      id: 'A', objective: 'Test node A.', inputs: [], dependencies: [], role: 'orchestrator', profile: 'generic',
      file_scope: ['src/test/**'], risk: 'low', acceptance_criteria: ['The test passes.'], verification: ['Run the test.'],
      status: 'planned', attempts: 0, evidence: [], blocking_reason: null,
    }],
  };
}

test('state initialization, attempts, legal transitions, and attempt ceiling match the shared contract', () => {
  const directory = mkdtempSync(resolve(tmpdir(), 'orqivra state test '));
  try {
    const project = resolve(directory, 'project');
    mkdirSync(project);
    const dagPath = resolve(directory, 'plan.json');
    const statePath = resolve(project, '.orqivra', 'state.json');
    writeFileSync(dagPath, `${JSON.stringify(testDag(), null, 2)}\n`);

    initializeState(dagPath, statePath, project);
    transition(statePath, 'A', 'ready');
    for (let number = 1; number <= 5; number += 1) {
      beginAttempt(statePath, 'A', `Distinct attempt hypothesis ${number}.`);
      transition(statePath, 'A', 'verifying');
      recordVerification(statePath, 'A', number, 'fail', `Attempt ${number} is deliberately a negative case.`);
      diagnose(statePath, 'A', number, `Attempt ${number} diagnosis recorded.`);
      transition(statePath, 'A', 'fix_required');
      transition(statePath, 'A', 'ready');
    }

    assert.throws(() => beginAttempt(statePath, 'A', 'Sixth distinct attempt.'), /Attempt limit/);
    const state = readState(statePath);
    assert.equal(state.nodes.A.attempts.length, 5);
    assert.equal(state.nodes.A.attempts[0].verification_result, 'fail');
    assert.equal(JSON.parse(readFileSync(statePath, 'utf8')).version, state.version);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test('state lock conflict does not overwrite the existing lock', () => {
  const directory = mkdtempSync(resolve(tmpdir(), 'orqivra state lock '));
  try {
    const project = resolve(directory, 'project');
    mkdirSync(project);
    const dagPath = resolve(directory, 'plan.json');
    const statePath = resolve(project, '.orqivra', 'state.json');
    writeFileSync(dagPath, `${JSON.stringify(testDag(), null, 2)}\n`);
    initializeState(dagPath, statePath, project);
    writeFileSync(`${statePath}.lock`, 'owner\n', { flag: 'wx' });
    assert.throws(() => transition(statePath, 'A', 'ready'), /locked by another writer/);
    assert.equal(readFileSync(`${statePath}.lock`, 'utf8'), 'owner\n');
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test('attempt hypotheses use ASCII whitespace, NFC, and locale-independent lowercase for duplicate checks', () => {
  const directory = mkdtempSync(resolve(tmpdir(), 'orqivra hypothesis normalization '));
  try {
    const project = resolve(directory, 'project');
    mkdirSync(project);
    const dagPath = resolve(directory, 'plan.json');
    const statePath = resolve(project, '.orqivra', 'state.json');
    writeFileSync(dagPath, `${JSON.stringify(testDag(), null, 2)}\n`);

    initializeState(dagPath, statePath, project);
    transition(statePath, 'A', 'ready');
    beginAttempt(statePath, 'A', ' \t\u00c5   focused  check \v');
    transition(statePath, 'A', 'verifying');
    recordVerification(statePath, 'A', 1, 'fail', 'First attempt failed for this duplicate check.');
    diagnose(statePath, 'A', 1, 'The first attempt used the composed form.');
    transition(statePath, 'A', 'fix_required');
    transition(statePath, 'A', 'ready');

    assert.throws(() => beginAttempt(statePath, 'A', 'A\u030A focused\tcheck'), /new hypothesis/);
    assert.equal(readState(statePath).nodes.A.attempts.length, 1);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});
