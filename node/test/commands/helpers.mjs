import { mkdirSync, mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { dirname } from 'node:path';

export const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');
process.env.ORQIVRA_DATA_DIR ??= repositoryRoot;

export function createScenario(name = 'evidence test') {
  const directory = mkdtempSync(resolve(tmpdir(), `${name} `));
  const project = resolve(directory, 'project with spaces');
  mkdirSync(project);
  for (const name of ['input-a.txt', 'input-b.txt', 'input-c.txt', 'input-d.txt']) {
    writeFileSync(resolve(project, name), `${name} initial\n`);
  }
  writeFileSync(resolve(project, 'output.txt'), 'result one\n');

  const dag = {
    schema_version: 1,
    id: `scenario-${name.replace(/[^a-z0-9-]/gi, '-')}`,
    objective: 'Exercise evidence and recovery behavior.',
    input_snapshot: `sha256:${'0'.repeat(64)}`,
    nodes: [
      makeNode('A', ['input-a.txt'], []),
      makeNode('B', ['input-b.txt'], []),
      makeNode('C', ['input-c.txt'], ['A']),
      makeNode('D', ['input-d.txt'], []),
    ],
  };
  const dagPath = resolve(directory, 'plan.json');
  writeFileSync(dagPath, `${JSON.stringify(dag, null, 2)}\n`);
  return { directory, project, dagPath, statePath: resolve(project, '.orqivra', 'state.json') };
}

function makeNode(id, inputs, dependencies) {
  return {
    id,
    objective: `Complete node ${id}.`,
    inputs,
    dependencies,
    role: 'implementer',
    profile: 'generic',
    file_scope: [`src/${id.toLowerCase()}/**`],
    risk: 'low',
    acceptance_criteria: [`Node ${id} is accepted.`],
    verification: ['Run the focused test.'],
    status: 'planned',
    attempts: 0,
    evidence: [],
    blocking_reason: null,
  };
}
