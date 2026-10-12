import { existsSync, realpathSync, statSync } from 'node:fs';
import { isAbsolute, relative, sep } from 'node:path';
import { currentSnapshot } from '../core/dag.js';
import { OrqivraError, UnsafePathError } from '../core/errors.js';
import { isWithin, rejectSymlinkComponents, safeJoin, safeRelativePath, sha256File } from '../core/paths.js';
import { Evidence, NodeState, State, mutateState, nodeSnapshot, utcNow } from '../core/state.js';

export function addEvidence(statePath: string, nodeId: string, command: string, exitCode: number, artifacts: string[] = []): State {
  const cleaned = command.trim();
  if (!cleaned) throw new OrqivraError('Evidence command text is required.');
  if (!Number.isSafeInteger(exitCode)) throw new OrqivraError('Evidence exit code must be an integer.');
  return mutateState(statePath, 'evidence_recorded', nodeId, { command: cleaned, exit_code: exitCode }, (rawState) => {
    const state = rawState as State;
    const node = requireNode(state, nodeId);
    if (!['running', 'verifying', 'accepted'].includes(node.status)) {
      throw new OrqivraError(`Evidence for ${nodeId} can be recorded only while it is active or accepted.`);
    }
    const records = artifacts.map((rawPath) => {
      const artifactPath = relativeArtifactPath(state.project_root, rawPath);
      const absolutePath = safeJoin(state.project_root, artifactPath);
      return { path: artifactPath, sha256: sha256File(absolutePath) };
    });
    const evidence: Evidence = {
      id: `${nodeId}-evidence-${node.evidence.length + 1}`,
      command: cleaned,
      exit_code: exitCode,
      snapshot: nodeSnapshot(state, nodeId),
      recorded_at: utcNow(),
      artifacts: records,
    };
    node.evidence.push(evidence);
  });
}

export function checkEvidence(statePath: string): { state: State; staleEvidence: string[] } {
  const stale: string[] = [];
  const state = mutateState(statePath, 'evidence_checked', null, {}, (rawState) => {
    const current = rawState as State;
    const oldInputs = current.input_hashes;
    const currentInputs = collectInputHashes(current);
    const changedInputs = new Set([...Object.keys(oldInputs), ...Object.keys(currentInputs)]
      .filter((path) => oldInputs[path] !== currentInputs[path]));
    const affected = new Set(Object.entries(current.nodes)
      .filter(([, node]) => node.inputs.some((input) => changedInputs.has(input)))
      .map(([nodeId]) => nodeId));

    current.input_hashes = currentInputs;
    current.dag_snapshot = currentSnapshot(current.plan_hash, currentInputs);
    for (const [nodeId, node] of Object.entries(current.nodes)) {
      const latest = node.evidence.at(-1);
      if (latest && evidenceStaleReason(current, nodeId, latest)) {
        stale.push(`${nodeId}:${latest.id}`);
        affected.add(nodeId);
      }
    }
    if (affected.size > 0) {
      const invalidated = invalidateAffected(current, affected);
      current.pending_resume = [...new Set([...current.pending_resume, ...invalidated])].sort();
      for (const nodeId of invalidated) {
        const node = current.nodes[nodeId];
        for (const evidence of node.evidence) {
          if (evidence.snapshot !== nodeSnapshot(current, nodeId)) stale.push(`${nodeId}:${evidence.id}`);
        }
      }
    }
  });
  return { state, staleEvidence: [...new Set(stale)].sort() };
}

export function collectInputHashes(state: State): Record<string, string> {
  const result = Object.create(null) as Record<string, string>;
  const inputs = [...new Set(Object.values(state.nodes).flatMap((node) => node.inputs))].sort();
  for (const input of inputs) {
    const path = safeJoin(state.project_root, input, true);
    if (existsSync(path) && statSync(path).isFile()) result[input] = sha256File(path);
  }
  return result;
}

export function changedInputPaths(state: State): string[] {
  const current = collectInputHashes(state);
  return [...new Set([...Object.keys(state.input_hashes), ...Object.keys(current)])]
    .filter((path) => state.input_hashes[path] !== current[path])
    .sort();
}

export function evidenceStaleReason(state: State, nodeId: string, item: Evidence): string | null {
  if (item.snapshot !== nodeSnapshot(state, nodeId)) return 'snapshot_changed';
  for (const artifact of item.artifacts) {
    try {
      if (sha256File(safeJoin(state.project_root, artifact.path)) !== artifact.sha256) return 'artifact_changed';
    } catch {
      return 'artifact_changed';
    }
  }
  return null;
}

export function dependencyClosure(state: State, nodeId: string): Set<string> {
  requireNode(state, nodeId);
  const closure = new Set<string>();
  const pending = [nodeId];
  while (pending.length > 0) {
    const current = pending.pop()!;
    if (closure.has(current)) continue;
    closure.add(current);
    pending.push(...state.nodes[current].dependencies);
  }
  return closure;
}

function relativeArtifactPath(root: string, rawPath: string): string {
  if (!isAbsolute(rawPath)) return safeRelativePath(rawPath);
  rejectSymlinkComponents(rawPath);
  let resolved: string;
  try {
    resolved = realpathSync(rawPath);
  } catch (error) {
    throw new UnsafePathError(`Artifact must be an existing file inside the project root: ${rawPath}`);
  }
  const absoluteRoot = realpathSync(root);
  if (!isWithin(resolved, absoluteRoot)) throw new UnsafePathError(`Artifact must be inside the project root: ${rawPath}`);
  const local = relative(absoluteRoot, resolved);
  if (!local || local === '..' || local.startsWith(`..${sep}`)) throw new UnsafePathError(`Artifact must be inside the project root: ${rawPath}`);
  return local.split(sep).join('/');
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
    const lastAttempt = node.attempts.at(-1);
    if (['running', 'verifying'].includes(node.status) && lastAttempt?.verification_result === 'pending') {
      lastAttempt.verification_result = 'interrupted';
      lastAttempt.verification_summary = 'The active session ended before verification; inspect current files before retrying.';
    }
    if (node.status !== 'obsolete') {
      node.status = 'obsolete';
      node.blocking_reason = 'Inputs, plan, or evidence changed; resume to recheck prerequisites.';
    }
  }
  return affected;
}

function requireNode(state: State, nodeId: string): NodeState {
  const node = state.nodes[nodeId];
  if (!node) throw new OrqivraError(`Unknown node ID: ${nodeId}`);
  return node;
}
