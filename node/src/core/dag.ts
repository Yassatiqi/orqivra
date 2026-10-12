import { lstatSync } from 'node:fs';
import { InputOutputError, OrqivraError } from './errors.js';
import { JsonObject, readJson, sha256Json } from './json.js';
import { isObject, requireValid } from './schema.js';
import { resolveSafeRoot, safeJoin, safeRelativePath, sha256File } from './paths.js';

export type DagNode = JsonObject & {
  id: string;
  inputs: string[];
  dependencies: string[];
  file_scope: string[];
  status: string;
};

export type Dag = JsonObject & { id: string; nodes: DagNode[] };

export function readDag(path: string): Dag {
  const dag = readJson(path);
  requireValid(dag, 'dag.schema.json');
  if (!isObject(dag)) throw new OrqivraError('DAG must be a JSON object.');
  validateGraph(dag);
  return dag as Dag;
}

export function validateGraph(dag: JsonObject): void {
  if (!Array.isArray(dag.nodes)) throw new OrqivraError('DAG nodes must be an array.');
  const nodes = new Map<string, DagNode>();
  for (const rawNode of dag.nodes) {
    if (!isObject(rawNode) || typeof rawNode.id !== 'string') throw new OrqivraError('Every DAG node must have a string ID.');
    const node = rawNode as DagNode;
    const nodeId = node.id;
    if (nodes.has(nodeId)) throw new OrqivraError(`Duplicate node ID: ${nodeId}`);
    nodes.set(nodeId, node);
    if (node.dependencies.includes(nodeId)) throw new OrqivraError(`Node cannot depend on itself: ${nodeId}`);
    for (const input of node.inputs) safeRelativePath(input);
    for (const scope of node.file_scope) safeRelativePath(scope, true);
  }
  for (const [nodeId, node] of nodes) {
    for (const dependency of node.dependencies) {
      if (!nodes.has(dependency)) throw new OrqivraError(`Node ${nodeId} has missing dependency: ${dependency}`);
    }
  }

  const remaining = new Map<string, Set<string>>();
  for (const [nodeId, node] of nodes) remaining.set(nodeId, new Set(node.dependencies));
  let visited = 0;
  while (remaining.size > 0) {
    const ready = [...remaining.entries()]
      .filter(([, dependencies]) => dependencies.size === 0)
      .map(([nodeId]) => nodeId)
      .sort();
    if (ready.length === 0) {
      const cyclic = [...remaining.entries()].filter(([, dependencies]) => dependencies.size > 0).map(([nodeId]) => nodeId).sort();
      throw new OrqivraError(`DAG contains a dependency cycle involving: ${cyclic.join(', ')}`);
    }
    for (const nodeId of ready) {
      remaining.delete(nodeId);
      visited += 1;
    }
    for (const dependencies of remaining.values()) for (const nodeId of ready) dependencies.delete(nodeId);
  }
  if (visited !== nodes.size) throw new OrqivraError('DAG contains a dependency cycle.');

  const reachable = dependencyReachability(nodes);
  const nodeIds = [...nodes.keys()].sort();
  for (let leftIndex = 0; leftIndex < nodeIds.length; leftIndex += 1) {
    const leftId = nodeIds[leftIndex];
    for (const rightId of nodeIds.slice(leftIndex + 1)) {
      if (reachable.get(rightId)!.has(leftId) || reachable.get(leftId)!.has(rightId)) continue;
      const left = nodes.get(leftId)!;
      const right = nodes.get(rightId)!;
      for (const leftScope of left.file_scope) {
        for (const rightScope of right.file_scope) {
          if (scopesOverlap(leftScope, rightScope)) {
            throw new OrqivraError(`Independent nodes ${leftId} and ${rightId} have overlapping file scopes: ${leftScope} and ${rightScope}`);
          }
        }
      }
    }
  }
}

export function planHashes(
  dag: Dag,
  projectRoot: string,
  allowMissingInputs = false,
): { planHash: string; headerHash: string; inputHashes: Record<string, string>; definitionHashes: Record<string, string> } {
  const root = resolveSafeRoot(projectRoot);

  const header = Object.create(null) as JsonObject;
  for (const [key, value] of Object.entries(dag)) if (key !== 'nodes') header[key] = value;
  const planHash = sha256Json(dag);
  const headerHash = sha256Json(header);
  const inputPaths = [...new Set(dag.nodes.flatMap((node) => node.inputs))].sort();
  const inputHashes: Record<string, string> = Object.create(null) as Record<string, string>;
  for (const input of inputPaths) {
    const path = safeJoin(root, input, true);
    let info;
    try {
      info = lstatSync(path);
    } catch (error) {
      if (error instanceof Error && 'code' in error && error.code === 'ENOENT') {
        if (!allowMissingInputs) throw new OrqivraError(`Required input file does not exist: ${input}`);
        continue;
      }
      throw new InputOutputError(`Could not inspect input path ${input}: ${messageOf(error)}`);
    }
    if (!info.isFile()) throw new OrqivraError(`Input path is not a regular file: ${input}`);
    inputHashes[input] = sha256File(path);
  }

  const definitionHashes: Record<string, string> = Object.create(null) as Record<string, string>;
  for (const node of dag.nodes) {
    const definition = Object.create(null) as JsonObject;
    for (const [key, value] of Object.entries(node)) {
      if (!['status', 'attempts', 'evidence', 'blocking_reason'].includes(key)) definition[key] = value;
    }
    definitionHashes[node.id] = sha256Json(definition);
  }
  return { planHash, headerHash, inputHashes, definitionHashes };
}

export function currentSnapshot(planHash: string, inputHashes: Record<string, string>): string {
  return `sha256:${sha256Json({ plan_hash: planHash, input_hashes: inputHashes })}`;
}

export function readyFrontier(dag: Dag, state?: JsonObject): string[] {
  const statuses = new Map<string, string>();
  for (const node of dag.nodes) {
    const rawNodes = state?.nodes;
    const stateNodes = isObject(rawNodes) ? rawNodes : undefined;
    const rawSaved = stateNodes?.[node.id];
    const saved = isObject(rawSaved) ? rawSaved : undefined;
    statuses.set(node.id, saved && typeof saved.status === 'string' ? saved.status : node.status);
  }
  return dag.nodes
    .filter((node) => ['planned', 'ready'].includes(statuses.get(node.id) ?? ''))
    .filter((node) => node.dependencies.every((dependency) => statuses.get(dependency) === 'accepted'))
    .map((node) => node.id)
    .sort();
}

export function nodeDefinitions(dag: Dag): Record<string, DagNode> {
  const result = Object.create(null) as Record<string, DagNode>;
  for (const node of dag.nodes) result[node.id] = node;
  return result;
}

function dependencyReachability(nodes: Map<string, DagNode>): Map<string, Set<string>> {
  const result = new Map<string, Set<string>>();
  for (const nodeId of nodes.keys()) {
    const reachable = new Set<string>();
    const pending = [...nodes.get(nodeId)!.dependencies];
    while (pending.length > 0) {
      const dependency = pending.pop()!;
      if (reachable.has(dependency)) continue;
      reachable.add(dependency);
      pending.push(...nodes.get(dependency)!.dependencies);
    }
    result.set(nodeId, reachable);
  }
  return result;
}

function scopesOverlap(left: string, right: string): boolean {
  const parts = (scope: string) => safeRelativePath(scope, true).replace(/\/\*\*$/, '').split('/');
  const a = parts(left);
  const b = parts(right);
  const limit = Math.min(a.length, b.length);
  for (let index = 0; index < limit; index += 1) if (a[index] !== b[index]) return false;
  return true;
}

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
