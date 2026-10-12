import { currentSnapshot, nodeDefinitions, planHashes, readDag } from '../core/dag.js';
import { OrqivraError } from '../core/errors.js';
import { resolveSafeRoot } from '../core/paths.js';
import { MAX_ATTEMPTS, State, mutateState, readState } from '../core/state.js';

export function resumeState(dagPath: string, statePath: string, projectRoot?: string): { state: State; affectedNodes: string[] } {
  const dag = readDag(dagPath);
  const stored = projectRoot ? undefined : readState(statePath);
  const selectedRoot = projectRoot ?? stored!.project_root;
  const root = resolveSafeRoot(selectedRoot);
  const hashes = planHashes(dag, root, true);
  const changed: string[] = [];

  const state = mutateState(statePath, 'state_resumed', null, { plan_hash: hashes.planHash }, (rawState) => {
    const current = rawState as State;
    if (current.dag_id !== dag.id) throw new OrqivraError('DAG ID differs from stored state; initialize a new state for a new DAG.');
    if (Object.keys(current.nodes).sort().join('\0') !== Object.keys(hashes.definitionHashes).sort().join('\0')) {
      throw new OrqivraError('DAG node IDs changed; use a new DAG ID to preserve attempt history.');
    }

    current.project_root = root;
    const affected = new Set(current.pending_resume);
    if (current.plan_header_hash !== hashes.headerHash) for (const nodeId of Object.keys(current.nodes)) affected.add(nodeId);
    for (const [nodeId, definitionHash] of Object.entries(hashes.definitionHashes)) {
      if (current.nodes[nodeId].definition_hash !== definitionHash) affected.add(nodeId);
    }
    for (const [nodeId, node] of Object.entries(current.nodes)) {
      if (node.inputs.some((input) => current.input_hashes[input] !== hashes.inputHashes[input])) affected.add(nodeId);
    }

    current.plan_hash = hashes.planHash;
    current.plan_header_hash = hashes.headerHash;
    current.input_hashes = hashes.inputHashes;
    current.dag_snapshot = currentSnapshot(hashes.planHash, hashes.inputHashes);
    for (const [nodeId, source] of Object.entries(nodeDefinitions(dag))) {
      const node = current.nodes[nodeId];
      node.definition_hash = hashes.definitionHashes[nodeId];
      node.dependencies = [...source.dependencies];
      node.inputs = [...source.inputs];
      node.obligations = Array.isArray(source.obligations) ? [...source.obligations] : [];
    }
    if (affected.size > 0) {
      const reopened = reopenAffected(current, affected);
      changed.push(...reopened);
    }
    for (const [nodeId, node] of Object.entries(current.nodes)) {
      if (!['running', 'verifying'].includes(node.status)) continue;
      const attempt = node.attempts.at(-1);
      if (attempt?.verification_result === 'pending') {
        attempt.verification_result = 'interrupted';
        attempt.verification_summary = 'The prior session ended before verification; inspect current files before retrying.';
        node.status = 'fix_required';
        node.blocking_reason = 'An interrupted attempt requires diagnosis before retry.';
        changed.push(nodeId);
      } else if (node.attempts.length === 0) {
        node.status = 'blocked';
        node.blocking_reason = 'The prior session ended before an attempt was recorded; inspect the work before resuming.';
        changed.push(nodeId);
      }
    }
    current.pending_resume = [];
  });
  return { state, affectedNodes: [...new Set(changed)].sort() };
}

function reopenAffected(state: State, seeds: Set<string>): Set<string> {
  const affected = invalidateAffected(state, seeds);
  for (const nodeId of topologicalIds(state)) {
    if (!affected.has(nodeId)) continue;
    const node = state.nodes[nodeId];
    const attempt = node.attempts.at(-1);
    if (attempt?.verification_result === 'interrupted') {
      node.status = 'fix_required';
      node.blocking_reason = 'An interrupted attempt requires diagnosis before retry.';
      continue;
    }
    if (node.attempts.length >= MAX_ATTEMPTS) {
      node.blocking_reason = 'Attempt limit reached; node cannot be retried.';
      continue;
    }
    if (node.dependencies.every((dependency) => state.nodes[dependency].status === 'accepted')) {
      node.status = 'ready';
      node.blocking_reason = null;
    } else {
      node.status = 'planned';
      node.blocking_reason = null;
    }
  }
  return affected;
}

function invalidateAffected(state: State, seeds: Set<string>): Set<string> {
  const affected = new Set(seeds);
  let changed = true;
  while (changed) {
    changed = false;
    for (const [nodeId, node] of Object.entries(state.nodes)) {
      if (!affected.has(nodeId) && node.dependencies.some((dependency) => affected.has(dependency))) {
        affected.add(nodeId);
        changed = true;
      }
    }
  }
  for (const nodeId of affected) {
    const node = state.nodes[nodeId];
    const attempt = node.attempts.at(-1);
    if (['running', 'verifying'].includes(node.status) && attempt?.verification_result === 'pending') {
      attempt.verification_result = 'interrupted';
      attempt.verification_summary = 'The active session ended before verification; inspect current files before retrying.';
    }
    if (node.status !== 'obsolete') {
      node.status = 'obsolete';
      node.blocking_reason = 'Inputs, plan, or evidence changed; resume to recheck prerequisites.';
    }
  }
  return affected;
}

function topologicalIds(state: State): string[] {
  const remaining = new Map(Object.entries(state.nodes).map(([nodeId, node]) => [nodeId, new Set(node.dependencies)]));
  const result: string[] = [];
  while (remaining.size > 0) {
    const ready = [...remaining.entries()].filter(([, dependencies]) => dependencies.size === 0).map(([nodeId]) => nodeId).sort();
    if (ready.length === 0) throw new OrqivraError('Stored state contains a dependency cycle.');
    for (const nodeId of ready) {
      result.push(nodeId);
      remaining.delete(nodeId);
    }
    for (const dependencies of remaining.values()) for (const nodeId of ready) dependencies.delete(nodeId);
  }
  return result;
}
