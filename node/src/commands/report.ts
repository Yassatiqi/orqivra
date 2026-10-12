import { dependencyClosure, changedInputPaths, evidenceStaleReason } from './evidence.js';
import { JsonObject, JsonValue } from '../core/json.js';
import { isObject } from '../core/schema.js';
import { State, readState } from '../core/state.js';

export function reportState(state: State): JsonObject {
  const unresolvedGates: JsonObject[] = [];
  for (const [nodeId, node] of Object.entries(state.nodes).sort(([left], [right]) => compareText(left, right))) {
    for (const obligation of node.obligations) {
      if (!isObject(obligation)) continue;
      if (obligation.required === true && (obligation.status !== 'VERIFIED' || !Array.isArray(obligation.evidence) || obligation.evidence.length === 0)) {
        unresolvedGates.push({ node_id: nodeId, ...obligation });
      }
    }
  }

  const changedInputs = changedInputPaths(state);
  const changedSet = new Set(changedInputs);
  const staleEvidence: JsonObject[] = [];
  const supersededStaleEvidence: JsonObject[] = [];
  const acceptedWithoutCurrentEvidence: string[] = [];
  for (const [nodeId, node] of Object.entries(state.nodes).sort(([left], [right]) => compareText(left, right))) {
    const relevantInputs = new Set([...dependencyClosure(state, nodeId)].flatMap((id) => state.nodes[id].inputs));
    const inputsChanged = [...changedSet].some((path) => relevantInputs.has(path));
    const latest = node.evidence.at(-1);
    for (const evidence of node.evidence) {
      const reason = inputsChanged ? 'input_changed' : evidenceStaleReason(state, nodeId, evidence);
      if (!reason) continue;
      const record: JsonObject = { node_id: nodeId, evidence_id: evidence.id, reason };
      if (evidence === latest) staleEvidence.push(record);
      else supersededStaleEvidence.push(record);
    }
    if (node.status === 'accepted' && (
      inputsChanged
      || !latest
      || latest.exit_code !== 0
      || evidenceStaleReason(state, nodeId, latest) !== null
    )) acceptedWithoutCurrentEvidence.push(nodeId);
  }

  const allAccepted = Object.values(state.nodes).every((node) => node.status === 'accepted');
  const nodes = Object.create(null) as Record<string, JsonValue>;
  for (const [nodeId, node] of Object.entries(state.nodes).sort(([left], [right]) => compareText(left, right))) nodes[nodeId] = node.status;
  const readyFrontier = Object.entries(state.nodes)
    .filter(([, node]) => ['planned', 'ready'].includes(node.status)
      && node.dependencies.every((dependency) => state.nodes[dependency].status === 'accepted'))
    .map(([nodeId]) => nodeId)
    .sort();

  return {
    schema_version: 1,
    project_id: state.project_id,
    dag_id: state.dag_id,
    version: state.version,
    snapshot: state.dag_snapshot,
    nodes,
    ready_frontier: readyFrontier,
    changed_inputs: changedInputs,
    stale_evidence: staleEvidence,
    superseded_stale_evidence: supersededStaleEvidence,
    accepted_without_current_evidence: acceptedWithoutCurrentEvidence,
    unresolved_required_gates: unresolvedGates,
    certified: allAccepted
      && acceptedWithoutCurrentEvidence.length === 0
      && changedInputs.length === 0
      && staleEvidence.length === 0
      && unresolvedGates.length === 0,
  };
}

export function createReport(statePath: string): JsonObject {
  return reportState(readState(statePath));
}

export function markdownReport(report: JsonObject): string {
  const lines = [
    `# ORQIVRA Report: ${String(report.dag_id)}`,
    '',
    `- Project: \`${String(report.project_id)}\``,
    `- State version: ${String(report.version)}`,
    `- Snapshot: \`${String(report.snapshot)}\``,
    `- Certified: ${report.certified === true ? 'yes' : 'no'}`,
    '',
    '## Nodes',
    '',
  ];
  const nodes = isObject(report.nodes) ? report.nodes : {};
  lines.push(...Object.entries(nodes).sort(([left], [right]) => compareText(left, right)).map(([nodeId, status]) => `- \`${nodeId}\`: \`${String(status)}\``));
  lines.push('', '## Ready frontier', '');
  appendArray(lines, report.ready_frontier, (item) => `- \`${String(item)}\``);
  lines.push('', '## Unresolved required gates', '');
  appendArray(lines, report.unresolved_required_gates, (item) => {
    const gate = isObject(item) ? item : {};
    return `- \`${String(gate.node_id)}/${String(gate.id)}\`: \`${String(gate.status)}\` — ${String(gate.description)}`;
  });
  lines.push('', '## Changed inputs', '');
  appendArray(lines, report.changed_inputs, (item) => `- \`${String(item)}\``);
  lines.push('', '## Stale evidence', '');
  appendArray(lines, report.stale_evidence, (item) => formatEvidenceLine(item));
  lines.push('', '## Superseded stale evidence', '');
  appendArray(lines, report.superseded_stale_evidence, (item) => formatEvidenceLine(item));
  lines.push('', '## Accepted nodes without current evidence', '');
  appendArray(lines, report.accepted_without_current_evidence, (item) => `- \`${String(item)}\``);
  return `${lines.join('\n')}\n`;
}

function appendArray(lines: string[], value: JsonValue | undefined, format: (item: JsonValue) => string): void {
  const items = Array.isArray(value) ? value : [];
  lines.push(...items.map(format));
  if (items.length === 0) lines.push('- None');
}

function formatEvidenceLine(value: JsonValue): string {
  const item = isObject(value) ? value : {};
  return `- \`${String(item.node_id)}/${String(item.evidence_id)}\`: ${String(item.reason)}`;
}

function compareText(left: string, right: string): number {
  const a = Array.from(left, (character) => character.codePointAt(0)!);
  const b = Array.from(right, (character) => character.codePointAt(0)!);
  for (let index = 0; index < Math.min(a.length, b.length); index += 1) {
    if (a[index] !== b[index]) return a[index] - b[index];
  }
  return a.length - b.length;
}
