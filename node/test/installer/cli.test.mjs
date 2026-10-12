import assert from 'node:assert/strict';
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const cliPath = fileURLToPath(new URL('../../dist/cli.js', import.meta.url));
const assetsRoot = resolve(dirname(cliPath), 'assets');

function runCli(args) {
  const env = { ...process.env };
  delete env.ORQIVRA_DATA_DIR;
  return spawnSync(process.execPath, [cliPath, ...args], { cwd: tmpdir(), env, encoding: 'utf8' });
}

function jsonCommand(args) {
  const result = runCli(args);
  assert.equal(result.status, 0, `${args.join(' ')} failed: ${result.stderr}`);
  return JSON.parse(result.stdout);
}

test('standalone Node CLI implements the public validation, state, evidence, reporting, bundle, and install commands', () => {
  const directory = mkdtempSync(resolve(tmpdir(), 'orqivra Node CLI acceptance '));
  try {
    const project = resolve(directory, 'project with spaces');
    mkdirSync(project);
    writeFileSync(resolve(project, 'input.txt'), 'initial input\n');
    writeFileSync(resolve(project, 'output.txt'), 'verified output\n');
    const projectPath = resolve(directory, 'project config.json');
    writeFileSync(projectPath, `${JSON.stringify({ schema_version: 1, id: 'cli-project', name: 'CLI Project', root: project, inputs: ['input.txt'], profile: 'codex' }, null, 2)}\n`);
    const dagPath = resolve(directory, 'plan with spaces.json');
    writeFileSync(dagPath, `${JSON.stringify({
      schema_version: 1,
      id: 'cli-acceptance',
      objective: 'Exercise the standalone Node CLI.',
      input_snapshot: `sha256:${'0'.repeat(64)}`,
      nodes: [{
        id: 'A', objective: 'Verify Node CLI parity.', inputs: ['input.txt'], dependencies: [], role: 'implementer', profile: 'generic',
        file_scope: ['src/a/**'], risk: 'low', acceptance_criteria: ['All commands work.'], verification: ['Run the CLI tests.'],
        status: 'planned', attempts: 0, evidence: [], blocking_reason: null,
      }],
    }, null, 2)}\n`);

    const help = runCli(['--help']);
    assert.equal(help.status, 0);
    assert.match(help.stdout, /Usage: orqivra/);
    assert.equal(runCli(['--version']).stdout.trim(), 'orqivra 0.2.0');
    assert.equal(jsonCommand(['validate', 'project', projectPath]).id, 'cli-project');
    assert.equal(jsonCommand(['validate', 'profile', resolve(assetsRoot, 'profiles', 'codex.json')]).edition, 'codex');
    assert.equal(jsonCommand(['validate', 'skills', resolve(assetsRoot, 'skills')]).count, 4);
    assert.equal(jsonCommand(['validate', 'dag', dagPath, '--project', projectPath]).node_count, 1);
    assert.deepEqual(jsonCommand(['plan', dagPath]).ready_frontier, ['A']);

    const statePath = resolve(project, '.orqivra', 'state.json');
    jsonCommand(['state', 'init', dagPath, '--state', statePath, '--project-root', project]);
    jsonCommand(['state', 'transition', '--state', statePath, 'A', '--to', 'ready', '--reason', 'Dependencies are satisfied.']);
    jsonCommand(['attempt', 'begin', '--state', statePath, 'A', '--hypothesis', 'Initial command verification hypothesis.']);
    jsonCommand(['attempt', 'record-change', '--state', statePath, 'A', '--attempt', '1', '--summary', 'Recorded the initial CLI setup.']);
    jsonCommand(['state', 'transition', '--state', statePath, 'A', '--to', 'verifying', '--reason', 'Begin the first verification.']);
    jsonCommand(['attempt', 'verify', '--state', statePath, 'A', '--attempt', '1', '--result', 'fail', '--summary', 'The first verification exposed a retry path.']);
    jsonCommand(['attempt', 'diagnose', '--state', statePath, 'A', '--attempt', '1', '--diagnosis', 'The first check must be corrected before retry.']);
    jsonCommand(['state', 'transition', '--state', statePath, 'A', '--to', 'fix_required', '--reason', 'The first verification failed.']);
    jsonCommand(['state', 'transition', '--state', statePath, 'A', '--to', 'ready', '--reason', 'The correction is ready.']);
    jsonCommand(['attempt', 'begin', '--state', statePath, 'A', '--hypothesis', 'The second CLI verification will pass with recorded evidence.']);
    jsonCommand(['state', 'transition', '--state', statePath, 'A', '--to', 'verifying', '--reason', 'Begin the corrected verification.']);
    jsonCommand(['evidence', 'add', '--state', statePath, 'A', '--command', 'recorded test result', '--exit-code', '0', '--artifact', 'output.txt']);
    jsonCommand(['attempt', 'verify', '--state', statePath, 'A', '--attempt', '2', '--result', 'pass', '--summary', 'The corrected verification passed.']);
    jsonCommand(['state', 'transition', '--state', statePath, 'A', '--to', 'accepted', '--reason', 'Current successful evidence is recorded.']);

    const stateBytes = readFileSync(statePath);
    assert.equal(jsonCommand(['report', '--state', statePath]).certified, true);
    assert.match(runCli(['report', '--state', statePath, '--format', 'markdown']).stdout, /Certified: yes/);
    assert.deepEqual(readFileSync(statePath), stateBytes);

    writeFileSync(resolve(project, 'output.txt'), 'changed artifact\n');
    const checked = jsonCommand(['evidence', 'check', '--state', statePath]);
    assert.deepEqual(checked.stale_evidence, ['A:A-evidence-1']);
    assert.equal(jsonCommand(['resume', '--dag', dagPath, '--state', statePath, '--project-root', project]).affected_nodes[0], 'A');
    assert.equal(jsonCommand(['plan', dagPath, '--state', statePath]).ready_frontier[0], 'A');

    const bundle = resolve(directory, 'offline bundle');
    assert.equal(jsonCommand(['build', '--edition', 'all', '--output', bundle]).built.length, 3);
    const installTarget = resolve(directory, 'explicit client skills target');
    const dryRun = jsonCommand(['install', '--edition', 'codex', '--target', installTarget, '--skill', 'orqivra-orchestrate']);
    assert.equal(dryRun.dry_run, true);
    assert.equal(jsonCommand(['install', '--edition', 'codex', '--target', installTarget, '--skill', 'orqivra-orchestrate', '--apply']).dry_run, false);
    assert.equal(jsonCommand(['verify-install', '--target', installTarget]).valid, true);
    assert.equal(jsonCommand(['uninstall', '--target', installTarget]).dry_run, true);
    assert.equal(jsonCommand(['uninstall', '--target', installTarget, '--apply']).dry_run, false);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});
