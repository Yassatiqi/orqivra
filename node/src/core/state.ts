import { randomBytes } from 'node:crypto';
import {
  closeSync,
  existsSync,
  fsyncSync,
  lstatSync,
  mkdirSync,
  openSync,
  readFileSync,
  renameSync,
  unlinkSync,
  writeFileSync,
} from 'node:fs';
import { basename, dirname, resolve } from 'node:path';
import { currentSnapshot, planHashes, readDag } from './dag.js';
import { ConcurrentUpdateError, InputOutputError, OrqivraError } from './errors.js';
import { JsonObject, JsonValue, parseJson, sha256Json } from './json.js';
import { rejectSymlinkComponents, rejectSymlinkPath, resolveSafeRoot, safeJoin, sha256File } from './paths.js';
import { isObject, requireValid } from './schema.js';

export const MAX_ATTEMPTS = 5;

export const TRANSITIONS: Record<string, string[]> = {
  planned: ['ready', 'blocked', 'obsolete'],
  ready: ['running', 'blocked', 'obsolete'],
  running: ['verifying', 'fix_required', 'blocked', 'obsolete'],
  verifying: ['accepted', 'fix_required', 'blocked', 'obsolete'],
  fix_required: ['ready', 'blocked', 'obsolete'],
  blocked: ['ready', 'obsolete'],
  accepted: ['obsolete'],
  obsolete: ['ready'],
};

export type State = JsonObject & {
  schema_version: number;
  project_id: string;
  project_root: string;
  dag_id: string;
  plan_hash: string;
  plan_header_hash: string;
  dag_snapshot: string;
  version: number;
  input_hashes: Record<string, string>;
  pending_resume: string[];
  nodes: Record<string, NodeState>;
  events: JsonValue[];
};

export type NodeState = JsonObject & {
  status: string;
  definition_hash: string;
  dependencies: string[];
  inputs: string[];
  attempts: Attempt[];
  evidence: Evidence[];
  obligations: JsonValue[];
  blocking_reason: string | null;
};

export type Attempt = JsonObject & {
  number: number;
  hypothesis: string;
  started_at: string;
  diagnosis: string | null;
  changes: string[];
  verification_result: 'pending' | 'pass' | 'fail' | 'interrupted';
  verification_summary: string | null;
};

export type Evidence = JsonObject & {
  id: string;
  command: string;
  exit_code: number;
  snapshot: string;
  recorded_at: string;
  artifacts: Array<{ path: string; sha256: string }>;
};

export function utcNow(): string {
  return new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
}

export function readState(path: string): State {
  rejectSymlinkComponents(path);
  rejectSymlinkPath(path);
  const value = readJsonState(path);
  requireValid(value, 'state.schema.json');
  return value as State;
}

function readJsonState(path: string): JsonValue {
  let bytes: Buffer;
  try {
    bytes = readFileSync(path);
  } catch (error) {
    const failure = error as NodeJS.ErrnoException;
    if (failure.code === 'ENOENT') throw new InputOutputError(`Path does not exist: ${path}`);
    throw new InputOutputError(`Could not read state file ${path}: ${messageOf(error)}`);
  }
  let text: string;
  try {
    text = new TextDecoder('utf-8', { fatal: true }).decode(bytes);
  } catch (error) {
    throw new OrqivraError(`Could not read valid UTF-8 state JSON from ${path}: ${messageOf(error)}`);
  }
  return parseJson(text, path);
}

export function mutateState(
  path: string,
  action: string,
  nodeId: string | null,
  detail: JsonObject,
  mutation: (state: JsonObject) => void,
): State {
  const statePath = resolve(path);
  rejectSymlinkComponents(statePath);
  try {
    mkdirSync(dirname(statePath), { recursive: true });
  } catch (error) {
    throw new InputOutputError(`Could not create state directory for ${statePath}: ${messageOf(error)}`);
  }
  rejectSymlinkComponents(statePath);
  rejectSymlinkPath(statePath);

  const lockPath = `${statePath}.lock`;
  rejectSymlinkPath(lockPath);
  let lockDescriptor: number;
  try {
    lockDescriptor = openSync(lockPath, 'wx', 0o600);
  } catch (error) {
    const failure = error as NodeJS.ErrnoException;
    if (failure.code === 'EEXIST') throw new ConcurrentUpdateError(`State is locked by another writer: ${lockPath}`);
    throw new InputOutputError(`Could not acquire state lock ${lockPath}: ${messageOf(error)}`);
  }

  try {
    writeFileSync(lockDescriptor, `pid=${process.pid}\n`, { encoding: 'ascii' });
    fsyncSync(lockDescriptor);
    closeSync(lockDescriptor);
    lockDescriptor = -1;

    const existed = existsSync(statePath);
    const before = existed ? readFileSync(statePath) : undefined;
    const state: JsonObject = existed ? asObject(readJsonState(statePath), 'State must be a JSON object.') : Object.create(null) as JsonObject;
    mutation(state);
    if (existed) state.version = requireInteger(state.version, 'State version must be an integer.') + 1;
    const version = requireInteger(state.version, 'State version must be an integer.');
    const events = Array.isArray(state.events) ? state.events : [];
    events.push({
      version,
      timestamp: utcNow(),
      action,
      node_id: nodeId,
      detail,
    });
    state.events = events;
    requireValid(state, 'state.schema.json');

    if (existed) {
      let current: Buffer;
      try {
        current = readFileSync(statePath);
      } catch {
        throw new ConcurrentUpdateError(`State file changed during update: ${statePath}`);
      }
      if (!current.equals(before!)) throw new ConcurrentUpdateError(`State file changed during update: ${statePath}`);
    } else if (existsSync(statePath)) {
      throw new ConcurrentUpdateError(`State file appeared during initialization: ${statePath}`);
    }
    writeJsonAtomic(statePath, state);
    return state as State;
  } catch (error) {
    if (error instanceof OrqivraError) throw error;
    if (error instanceof Error && 'code' in error) throw new InputOutputError(`Could not update state file ${statePath}: ${messageOf(error)}`);
    throw error;
  } finally {
    try {
      if (lockDescriptor >= 0) closeSync(lockDescriptor);
    } catch {
      // The descriptor may already have been closed before an error was raised.
    }
    try {
      unlinkSync(lockPath);
    } catch {
      // Preserve the primary failure; a leftover lock is visible to the next writer.
    }
  }
}

function writeJsonAtomic(path: string, value: JsonObject): void {
  const temporary = `${path}.${process.pid}.${randomBytes(8).toString('hex')}.tmp`;
  const payload = `${JSON.stringify(sortObjectKeys(value), null, 2)}\n`;
  try {
    writeFileSync(temporary, payload, { encoding: 'utf8', flag: 'wx', mode: 0o600 });
    const descriptor = openSync(temporary, 'r+');
    try {
      fsyncSync(descriptor);
    } finally {
      closeSync(descriptor);
    }
    renameSync(temporary, path);
  } catch (error) {
    try {
      unlinkSync(temporary);
    } catch {
      // No temporary file remains, or cleanup failed.
    }
    throw new InputOutputError(`Could not atomically write state file ${path}: ${messageOf(error)}`);
  }
}

function sortObjectKeys(value: JsonValue): JsonValue {
  if (Array.isArray(value)) return value.map(sortObjectKeys);
  if (value === null || typeof value !== 'object') return value;
  const result = Object.create(null) as JsonObject;
  for (const key of Object.keys(value).sort(compareUnicodeScalars)) result[key] = sortObjectKeys(value[key]);
  return result;
}

function compareUnicodeScalars(left: string, right: string): number {
  const a = Array.from(left, (character) => character.codePointAt(0)!);
  const b = Array.from(right, (character) => character.codePointAt(0)!);
  for (let index = 0; index < Math.min(a.length, b.length); index += 1) {
    if (a[index] !== b[index]) return a[index] - b[index];
  }
  return a.length - b.length;
}

export function initializeState(dagPath: string, statePath: string, projectRoot: string): State {
  const dag = readDag(dagPath);
  const root = resolveSafeRoot(projectRoot);
  const hashes = planHashes(dag, root);
  const initial: JsonObject = {
    schema_version: 1,
    project_id: basename(root) || dag.id,
    project_root: root,
    dag_id: dag.id,
    plan_hash: hashes.planHash,
    plan_header_hash: hashes.headerHash,
    dag_snapshot: currentSnapshot(hashes.planHash, hashes.inputHashes),
    version: 1,
    input_hashes: hashes.inputHashes,
    pending_resume: [],
    nodes: Object.fromEntries(dag.nodes.map((node) => [node.id, {
      status: 'planned',
      definition_hash: hashes.definitionHashes[node.id],
      dependencies: [...node.dependencies],
      inputs: [...node.inputs],
      attempts: [],
      evidence: [],
      obligations: Array.isArray(node.obligations) ? [...node.obligations] : [],
      blocking_reason: typeof node.blocking_reason === 'string' ? node.blocking_reason : null,
    }])),
    events: [],
  };
  return mutateState(statePath, 'state_initialized', null, { dag_id: dag.id }, (state) => {
    if (Object.keys(state).length > 0) throw new ConcurrentUpdateError(`State file already exists: ${statePath}`);
    Object.assign(state, initial);
  });
}

export function nodeSnapshot(state: State, nodeId: string): string {
  const closure = dependencyClosure(state, nodeId);
  const inputNames = [...new Set([...closure].flatMap((id) => state.nodes[id].inputs))].sort();
  const inputs = Object.create(null) as Record<string, string | null>;
  for (const path of inputNames) inputs[path] = state.input_hashes[path] ?? null;
  const definitions = Object.create(null) as Record<string, string>;
  for (const id of [...closure].sort()) definitions[id] = state.nodes[id].definition_hash;
  return `sha256:${sha256Json({ header: state.plan_header_hash, definitions, inputs })}`;
}

function dependencyClosure(state: State, nodeId: string): Set<string> {
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

export function transition(path: string, nodeId: string, target: string, reason = ''): State {
  if (!(target in TRANSITIONS)) throw new OrqivraError(`Unknown state: ${target}`);
  const cleanedReason = reason.trim();
  return mutateState(path, 'state_transition', nodeId, { to: target, reason }, (rawState) => {
    const state = rawState as State;
    const node = requireNode(state, nodeId);
    const source = node.status;
    if (!TRANSITIONS[source]?.includes(target) || (source === 'obsolete' && target === 'ready')) {
      throw new OrqivraError(`Illegal state transition for ${nodeId}: ${source} -> ${target}`);
    }
    if (target === 'ready') {
      if (source === 'obsolete' && node.attempts.length >= MAX_ATTEMPTS) throw new OrqivraError(`Attempt limit reached for node ${nodeId}.`);
      const unmet = node.dependencies.filter((dependency) => state.nodes[dependency].status !== 'accepted');
      if (unmet.length) throw new OrqivraError(`Node ${nodeId} is not ready; dependencies are not accepted: ${unmet.join(', ')}`);
    }
    if (target === 'blocked' && !cleanedReason) throw new OrqivraError('A blocking reason is required when entering blocked.');
    if (target === 'accepted') validateAcceptance(state, nodeId, node);
    if (target === 'obsolete') {
      const affected = invalidateAffected(state, new Set([nodeId]));
      state.pending_resume = [...new Set([...state.pending_resume, ...affected])].sort();
      if (cleanedReason) node.blocking_reason = cleanedReason;
      return;
    }
    node.status = target;
    node.blocking_reason = target === 'blocked' ? cleanedReason : null;
  });
}

function validateAcceptance(state: State, nodeId: string, node: NodeState): void {
  const attempts = node.attempts;
  if (!attempts.length || attempts.at(-1)!.verification_result !== 'pass') {
    throw new OrqivraError(`Node ${nodeId} requires a passing verification attempt before acceptance.`);
  }
  const changed = new Set(changedInputPaths(state));
  const relevant = new Set([...dependencyClosure(state, nodeId)].flatMap((id) => state.nodes[id].inputs));
  if ([...changed].some((path) => relevant.has(path))) {
    throw new OrqivraError(`Node ${nodeId} inputs changed; run evidence check and resume before acceptance.`);
  }
  const latest = node.evidence.at(-1);
  if (!latest || latest.snapshot !== nodeSnapshot(state, nodeId) || latest.exit_code !== 0 || evidenceStaleReason(state, nodeId, latest) !== null) {
    throw new OrqivraError(`Node ${nodeId} requires current successful evidence before acceptance.`);
  }
}

export function beginAttempt(path: string, nodeId: string, hypothesis: string): State {
  const cleaned = hypothesis.replace(/^[ \t\n\r\f\v]+|[ \t\n\r\f\v]+$/g, '');
  const normalized = normalizeHypothesis(cleaned);
  if (!normalized) throw new OrqivraError('An attempt hypothesis is required.');
  return mutateState(path, 'attempt_started', nodeId, { hypothesis: cleaned }, (rawState) => {
    const state = rawState as State;
    const node = requireNode(state, nodeId);
    if (!['ready', 'running'].includes(node.status)) throw new OrqivraError(`Node ${nodeId} must be ready or running before an attempt begins.`);
    if (node.attempts.length >= MAX_ATTEMPTS) throw new OrqivraError(`Attempt limit reached for node ${nodeId}.`);
    if (node.attempts.some((attempt) => normalizeHypothesis(attempt.hypothesis) === normalized)) {
      throw new OrqivraError('A correction attempt must use a new hypothesis.');
    }
    const last = node.attempts.at(-1);
    if (last && ['fail', 'interrupted'].includes(last.verification_result) && !last.diagnosis) {
      throw new OrqivraError('Record a diagnosis before starting a correction attempt.');
    }
    if (last?.verification_result === 'pending') throw new OrqivraError('The previous attempt is unfinished; inspect state and resume before retrying.');
    node.attempts.push({
      number: node.attempts.length + 1,
      hypothesis: cleaned,
      started_at: utcNow(),
      diagnosis: null,
      changes: [],
      verification_result: 'pending',
      verification_summary: null,
    });
    node.status = 'running';
    node.blocking_reason = null;
  });
}

export function diagnose(path: string, nodeId: string, number: number, diagnosis: string): State {
  const cleaned = diagnosis.trim();
  if (!cleaned) throw new OrqivraError('A diagnosis is required.');
  return mutateState(path, 'attempt_diagnosed', nodeId, { attempt: number, diagnosis: cleaned }, (rawState) => {
    requireAttempt(rawState as State, nodeId, number).diagnosis = cleaned;
  });
}

export function recordChange(path: string, nodeId: string, number: number, summary: string): State {
  const cleaned = summary.trim();
  if (!cleaned) throw new OrqivraError('A change summary is required.');
  return mutateState(path, 'attempt_change_recorded', nodeId, { attempt: number, summary: cleaned }, (rawState) => {
    requireAttempt(rawState as State, nodeId, number).changes.push(cleaned);
  });
}

export function recordVerification(path: string, nodeId: string, number: number, result: string, summary: string): State {
  const cleaned = summary.trim();
  if (!['pass', 'fail'].includes(result) || !cleaned) throw new OrqivraError('Verification requires result pass|fail and a non-empty summary.');
  return mutateState(path, 'attempt_verified', nodeId, { attempt: number, result, summary: cleaned }, (rawState) => {
    const state = rawState as State;
    const node = requireNode(state, nodeId);
    if (node.status !== 'verifying') throw new OrqivraError(`Node ${nodeId} must be verifying before verification is recorded.`);
    const attempt = requireAttempt(state, nodeId, number);
    if (number !== node.attempts.length) throw new OrqivraError('Verification must be recorded for the latest attempt.');
    if (attempt.verification_result !== 'pending') throw new OrqivraError('Verification has already been recorded for this attempt.');
    attempt.verification_result = result as 'pass' | 'fail';
    attempt.verification_summary = cleaned;
  });
}

function requireAttempt(state: State, nodeId: string, number: number): Attempt {
  const node = requireNode(state, nodeId);
  if (!Number.isInteger(number) || number < 1 || number > node.attempts.length) throw new OrqivraError(`Attempt ${number} does not exist for node ${nodeId}.`);
  return node.attempts[number - 1];
}

function requireNode(state: State, nodeId: string): NodeState {
  const node = state.nodes[nodeId];
  if (!node) throw new OrqivraError(`Unknown node ID: ${nodeId}`);
  return node;
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
    const last = node.attempts.at(-1);
    if (['running', 'verifying'].includes(node.status) && last?.verification_result === 'pending') {
      last.verification_result = 'interrupted';
      last.verification_summary = 'The active session ended before verification; inspect current files before retrying.';
    }
    if (node.status !== 'obsolete') {
      node.status = 'obsolete';
      node.blocking_reason = 'Inputs, plan, or evidence changed; resume to recheck prerequisites.';
    }
  }
  return affected;
}

function normalizeHypothesis(value: string): string {
  return value
    .replace(/^[ \t\n\r\f\v]+|[ \t\n\r\f\v]+$/g, '')
    .normalize('NFC')
    .toLowerCase()
    .replace(/[ \t\n\r\f\v]+/g, ' ');
}

function changedInputPaths(state: State): string[] {
  const current = collectInputHashes(state);
  return [...new Set([...Object.keys(state.input_hashes), ...Object.keys(current)])]
    .filter((path) => state.input_hashes[path] !== current[path])
    .sort();
}

function collectInputHashes(state: State): Record<string, string> {
  const root = resolveSafeRoot(state.project_root);
  const paths = [...new Set(Object.values(state.nodes).flatMap((node) => node.inputs))].sort();
  const current = Object.create(null) as Record<string, string>;
  for (const path of paths) {
    const inputPath = safeJoin(root, path, true);
    let info;
    try {
      info = lstatSync(inputPath);
    } catch (error) {
      if (error instanceof Error && 'code' in error && error.code === 'ENOENT') continue;
      throw new InputOutputError(`Could not inspect input path ${path}: ${messageOf(error)}`);
    }
    if (!info.isFile()) throw new OrqivraError(`Input path is not a regular file: ${path}`);
    current[path] = sha256File(inputPath);
  }
  return current;
}

function evidenceStaleReason(state: State, nodeId: string, item: Evidence): string | null {
  const root = resolveSafeRoot(state.project_root);
  if (item.snapshot !== nodeSnapshot(state, nodeId)) return 'snapshot_changed';
  for (const artifact of item.artifacts) {
    try {
      if (sha256File(safeJoin(root, artifact.path)) !== artifact.sha256) return 'artifact_changed';
    } catch {
      return 'artifact_changed';
    }
  }
  return null;
}

function asObject(value: JsonValue, message: string): JsonObject {
  if (!isObject(value)) throw new OrqivraError(message);
  return value;
}

function requireInteger(value: JsonValue | undefined, message: string): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value)) throw new OrqivraError(message);
  return value;
}

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
