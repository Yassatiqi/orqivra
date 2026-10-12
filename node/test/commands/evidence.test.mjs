import assert from 'node:assert/strict';
import { readFileSync, renameSync, rmSync, symlinkSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import test from 'node:test';
import { addEvidence, checkEvidence, collectInputHashes, evidenceStaleReason } from '../../dist/commands/evidence.js';
import { createReport, markdownReport } from '../../dist/commands/report.js';
import { resumeState } from '../../dist/commands/state.js';
import { beginAttempt, diagnose, initializeState, recordVerification, transition } from '../../dist/core/state.js';
import { createScenario } from './helpers.mjs';

function acceptNode(statePath, nodeId, artifact = []) {
  const state = JSON.parse(readFileSync(statePath, 'utf8'));
  const number = state.nodes[nodeId].attempts.length + 1;
  beginAttempt(statePath, nodeId, `Verify ${nodeId} with evidence ${number}.`);
  transition(statePath, nodeId, 'verifying');
  addEvidence(statePath, nodeId, 'focused node command', 0, artifact);
  recordVerification(statePath, nodeId, number, 'pass', `Node ${nodeId} checks passed.`);
  transition(statePath, nodeId, 'accepted');
}

test('reports are read-only and separate current evidence from superseded history', () => {
  const scenario = createScenario('evidence history');
  try {
    initializeState(scenario.dagPath, scenario.statePath, scenario.project);
    for (const nodeId of ['A', 'B', 'D']) transition(scenario.statePath, nodeId, 'ready');
    acceptNode(scenario.statePath, 'A', ['output.txt']);
    transition(scenario.statePath, 'C', 'ready');
    acceptNode(scenario.statePath, 'C');
    acceptNode(scenario.statePath, 'B');
    acceptNode(scenario.statePath, 'D');

    writeFileSync(resolve(scenario.project, 'output.txt'), 'result two\n');
    const staleReport = createReport(scenario.statePath);
    assert.equal(staleReport.certified, false);
    assert.deepEqual(staleReport.stale_evidence, [{ node_id: 'A', evidence_id: 'A-evidence-1', reason: 'artifact_changed' }]);
    addEvidence(scenario.statePath, 'A', 'repeat evidence after artifact update', 0, ['output.txt']);
    const before = readFileSync(scenario.statePath);
    const report = createReport(scenario.statePath);
    const markdown = markdownReport(report);
    const after = readFileSync(scenario.statePath);

    assert.deepEqual(after, before);
    assert.equal(report.certified, true);
    assert.deepEqual(report.stale_evidence, []);
    assert.deepEqual(report.superseded_stale_evidence, [{ node_id: 'A', evidence_id: 'A-evidence-1', reason: 'artifact_changed' }]);
    assert.match(markdown, /^# ORQIVRA Report: scenario-evidence-history/m);
    assert.match(markdown, /## Superseded stale evidence/);
    assert.match(markdown, /- `A\/A-evidence-1`: artifact_changed/);

    transition(scenario.statePath, 'A', 'obsolete', 'Manual recheck requested.');
    const current = JSON.parse(readFileSync(scenario.statePath, 'utf8'));
    assert.equal(current.nodes.A.status, 'obsolete');
    assert.deepEqual(current.pending_resume, ['A', 'C']);
    const resumed = resumeState(scenario.dagPath, scenario.statePath, scenario.project);
    assert.equal(resumed.state.nodes.A.status, 'ready');
    assert.equal(resumed.state.nodes.C.status, 'planned');
    assert.deepEqual(resumed.affectedNodes, ['A', 'C']);
  } finally {
    rmSync(scenario.directory, { recursive: true, force: true });
  }
});

test('evidence check invalidates an artifact owner and dependents while keeping independent work unchanged', () => {
  const scenario = createScenario('artifact invalidation');
  try {
    initializeState(scenario.dagPath, scenario.statePath, scenario.project);
    for (const nodeId of ['A', 'B', 'D']) transition(scenario.statePath, nodeId, 'ready');
    acceptNode(scenario.statePath, 'A', ['output.txt']);
    transition(scenario.statePath, 'C', 'ready');
    acceptNode(scenario.statePath, 'C');
    acceptNode(scenario.statePath, 'B');
    acceptNode(scenario.statePath, 'D');

    writeFileSync(resolve(scenario.project, 'output.txt'), 'changed result\n');
    const checked = checkEvidence(scenario.statePath);
    assert.deepEqual(checked.staleEvidence, ['A:A-evidence-1']);
    assert.equal(checked.state.nodes.A.status, 'obsolete');
    assert.equal(checked.state.nodes.C.status, 'obsolete');
    assert.equal(checked.state.nodes.B.status, 'accepted');
    assert.equal(checked.state.nodes.D.status, 'accepted');
  } finally {
    rmSync(scenario.directory, { recursive: true, force: true });
  }
});

test('changed inputs invalidate only their dependent subtree and preserve independent accepted work', () => {
  const scenario = createScenario('scoped invalidation');
  try {
    initializeState(scenario.dagPath, scenario.statePath, scenario.project);
    for (const nodeId of ['A', 'B', 'D']) transition(scenario.statePath, nodeId, 'ready');
    acceptNode(scenario.statePath, 'A');
    transition(scenario.statePath, 'C', 'ready');
    acceptNode(scenario.statePath, 'C');
    acceptNode(scenario.statePath, 'B');
    acceptNode(scenario.statePath, 'D');

    writeFileSync(resolve(scenario.project, 'input-a.txt'), 'input changed\n');
    const report = createReport(scenario.statePath);
    assert.deepEqual(report.changed_inputs, ['input-a.txt']);
    assert.deepEqual(report.accepted_without_current_evidence, ['A', 'C']);

    const checked = checkEvidence(scenario.statePath);
    assert.equal(checked.state.nodes.A.status, 'obsolete');
    assert.equal(checked.state.nodes.C.status, 'obsolete');
    assert.equal(checked.state.nodes.B.status, 'accepted');
    assert.equal(checked.state.nodes.D.status, 'accepted');
    assert.deepEqual(checked.state.pending_resume, ['A', 'C']);

    const resumed = resumeState(scenario.dagPath, scenario.statePath, scenario.project);
    assert.equal(resumed.state.nodes.A.status, 'ready');
    assert.equal(resumed.state.nodes.C.status, 'planned');
    assert.equal(resumed.state.nodes.B.status, 'accepted');
    assert.equal(resumed.state.nodes.D.status, 'accepted');
  } finally {
    rmSync(scenario.directory, { recursive: true, force: true });
  }
});

test('resume preserves counters and requires diagnosis after an interrupted attempt', () => {
  const scenario = createScenario('interruption recovery');
  try {
    initializeState(scenario.dagPath, scenario.statePath, scenario.project);
    transition(scenario.statePath, 'A', 'ready');
    beginAttempt(scenario.statePath, 'A', 'A distinct work attempt before interruption.');

    const resumed = resumeState(scenario.dagPath, scenario.statePath, scenario.project);
    assert.equal(resumed.state.nodes.A.status, 'fix_required');
    assert.equal(resumed.state.nodes.A.attempts.length, 1);
    assert.equal(resumed.state.nodes.A.attempts[0].verification_result, 'interrupted');

    diagnose(scenario.statePath, 'A', 1, 'The prior attempt ended before its verification step.');
    transition(scenario.statePath, 'A', 'ready');
    beginAttempt(scenario.statePath, 'A', 'Retry after recording the interruption diagnosis.');
    const current = JSON.parse(readFileSync(scenario.statePath, 'utf8'));
    assert.equal(current.nodes.A.attempts.length, 2);
    assert.equal(current.nodes.A.attempts[0].verification_result, 'interrupted');
  } finally {
    rmSync(scenario.directory, { recursive: true, force: true });
  }
});

test('saved project roots replaced by a symlink or junction are rejected even with no inputs or artifacts', () => {
  const scenario = createScenario('empty-root replacement');
  const statePath = resolve(scenario.directory, 'external-state.json');
  try {
    const dag = JSON.parse(readFileSync(scenario.dagPath, 'utf8'));
    for (const node of dag.nodes) node.inputs = [];
    writeFileSync(scenario.dagPath, `${JSON.stringify(dag, null, 2)}\n`);
    initializeState(scenario.dagPath, statePath, scenario.project);
    transition(statePath, 'A', 'ready');
    transition(statePath, 'A', 'running');

    const movedRoot = `${scenario.project}-real`;
    renameSync(scenario.project, movedRoot);
    symlinkSync(movedRoot, scenario.project, process.platform === 'win32' ? 'junction' : 'dir');
    const state = JSON.parse(readFileSync(statePath, 'utf8'));

    assert.throws(() => collectInputHashes(state), /symlink|junction/i);
    assert.throws(() => evidenceStaleReason(state, 'A', { snapshot: 'stale', artifacts: [] }), /symlink|junction/i);
    assert.throws(() => checkEvidence(statePath), /symlink|junction/i);
    assert.throws(() => createReport(statePath), /symlink|junction/i);
    assert.throws(() => addEvidence(statePath, 'A', 'root guard test', 0), /symlink|junction/i);
    assert.throws(() => resumeState(scenario.dagPath, statePath), /symlink|junction/i);

    const resumed = resumeState(scenario.dagPath, statePath, movedRoot);
    assert.equal(resumed.state.project_root, resolve(movedRoot));
  } finally {
    rmSync(scenario.directory, { recursive: true, force: true });
  }
});
