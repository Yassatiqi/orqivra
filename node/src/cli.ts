#!/usr/bin/env node
import { dirname, isAbsolute, resolve } from 'node:path';
import { parseArgs } from 'node:util';
import { fileURLToPath } from 'node:url';
import { readDag, planHashes, readyFrontier } from './core/dag.js';
import { OrqivraError } from './core/errors.js';
import { JsonObject, JsonValue, readJson } from './core/json.js';
import { safeJoin, safeRelativePath } from './core/paths.js';
import { isObject, requireValid } from './core/schema.js';
import { addEvidence, checkEvidence } from './commands/evidence.js';
import { buildBundle, installSkills, validateSkills, verifyInstall, uninstallSkills, EDITIONS, ORQIVRA_VERSION } from './commands/installer.js';
import { createReport, markdownReport } from './commands/report.js';
import { resumeState } from './commands/state.js';
import { beginAttempt, diagnose, initializeState, readState, recordChange, recordVerification, transition } from './core/state.js';

const USAGE = `Usage: orqivra <command> [options]

Commands:
  validate project|dag|profile|skills PATH
  plan DAG [--state PATH]
  state init DAG --state PATH [--project-root DIR]
  state transition --state PATH NODE --to STATUS --reason TEXT
  attempt begin|diagnose|record-change|verify --state PATH NODE [options]
  evidence add|check --state PATH [NODE] [options]
  resume --dag DAG --state PATH [--project-root DIR]
  report --state PATH [--format json|markdown]
  build --edition codex|claude-code|gemini-cli|all --output DIR
  install --edition codex|claude-code|gemini-cli --target DIR [--skill NAME ...] [--apply]
  verify-install --target DIR
  uninstall --target DIR [--apply]

Mutations require explicit paths. Install and uninstall are dry-run by default.
Use --help with a command for its options.\n`;

type Parsed = { positionals: string[]; values: Record<string, string | boolean | string[] | undefined> };

export function main(argv = process.argv.slice(2)): number {
  try {
    if (argv.length === 0 || argv[0] === '--help' || argv[0] === '-h' || argv[0] === 'help') {
      process.stdout.write(USAGE);
      return 0;
    }
    if (argv[0] === '--version' || argv[0] === '-V') {
      process.stdout.write(`orqivra ${ORQIVRA_VERSION}\n`);
      return 0;
    }
    if (argv.includes('--help') || argv.includes('-h')) {
      process.stdout.write(commandHelp(argv[0], argv[1]));
      return 0;
    }
    const result = execute(argv);
    if (typeof result === 'string') process.stdout.write(result);
    else emitJson(result);
    return 0;
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    const code = error instanceof OrqivraError ? error.exitCode : isNodeError(error) ? 4 : 2;
    process.stderr.write(`orqivra: ${message}\n`);
    return code;
  }
}

function execute(argv: string[]): JsonValue | string {
  const [command, action, ...remaining] = argv;
  if (command === 'validate') return validateCommand(action, remaining);
  if (command === 'plan') {
    const parsed = parse(argv.slice(1), { state: 'string' }, 1);
    const dag = readDag(parsed.positionals[0]);
    const statePath = stringValue(parsed.values.state);
    const state = statePath ? readState(statePath) : undefined;
    if (state && state.dag_id !== dag.id) throw new OrqivraError('DAG ID differs from state file.');
    return { dag_id: dag.id, ready_frontier: readyFrontier(dag, state) };
  }
  if (command === 'state') {
    if (action === 'init') {
      const parsed = parse(remaining, { state: 'string', 'project-root': 'string' }, 1);
      return initializeState(requiredPosition(parsed, 0), requiredOption(parsed, 'state'), stringValue(parsed.values['project-root']) ?? process.cwd());
    }
    if (action === 'transition') {
      const parsed = parse(remaining, { state: 'string', to: 'string', reason: 'string' }, 1);
      return transition(requiredOption(parsed, 'state'), requiredPosition(parsed, 0), requiredOption(parsed, 'to'), requiredOption(parsed, 'reason'));
    }
    throw new OrqivraError('Expected state action init or transition.');
  }
  if (command === 'attempt') {
    const parsed = parse(remaining, {
      state: 'string', hypothesis: 'string', attempt: 'string', diagnosis: 'string', summary: 'string', result: 'string',
    }, 1);
    const statePath = requiredOption(parsed, 'state');
    const nodeId = requiredPosition(parsed, 0);
    if (action === 'begin') return beginAttempt(statePath, nodeId, requiredOption(parsed, 'hypothesis'));
    const number = integerOption(parsed, 'attempt');
    if (action === 'diagnose') return diagnose(statePath, nodeId, number, requiredOption(parsed, 'diagnosis'));
    if (action === 'record-change') return recordChange(statePath, nodeId, number, requiredOption(parsed, 'summary'));
    if (action === 'verify') {
      const result = requiredOption(parsed, 'result');
      if (!['pass', 'fail'].includes(result)) throw new OrqivraError('--result must be pass or fail.');
      return recordVerification(statePath, nodeId, number, result, requiredOption(parsed, 'summary'));
    }
    throw new OrqivraError('Expected attempt action begin, diagnose, record-change, or verify.');
  }
  if (command === 'evidence') {
    if (action === 'add') {
      const parsed = parse(remaining, { state: 'string', command: 'string', 'exit-code': 'string', artifact: 'string[]' }, 1);
      return addEvidence(requiredOption(parsed, 'state'), requiredPosition(parsed, 0), requiredOption(parsed, 'command'), integerOption(parsed, 'exit-code'), arrayValue(parsed.values.artifact));
    }
    if (action === 'check') {
      const parsed = parse(remaining, { state: 'string' }, 0);
      const result = checkEvidence(requiredOption(parsed, 'state'));
      return { version: result.state.version, stale_evidence: result.staleEvidence, snapshot: result.state.dag_snapshot };
    }
    throw new OrqivraError('Expected evidence action add or check.');
  }
  if (command === 'resume') {
    const parsed = parse(argv.slice(1), { dag: 'string', state: 'string', 'project-root': 'string' }, 0);
    const result = resumeState(requiredOption(parsed, 'dag'), requiredOption(parsed, 'state'), stringValue(parsed.values['project-root']));
    return { version: result.state.version, snapshot: result.state.dag_snapshot, affected_nodes: result.affectedNodes };
  }
  if (command === 'report') {
    const parsed = parse(argv.slice(1), { state: 'string', format: 'string' }, 0);
    const format = stringValue(parsed.values.format) ?? 'json';
    if (!['json', 'markdown'].includes(format)) throw new OrqivraError('--format must be json or markdown.');
    const report = createReport(requiredOption(parsed, 'state'));
    return format === 'markdown' ? markdownReport(report) : report;
  }
  if (command === 'build') {
    const parsed = parse(argv.slice(1), { edition: 'string', output: 'string' }, 0);
    const edition = requiredOption(parsed, 'edition');
    if (![...EDITIONS, 'all'].includes(edition)) throw new OrqivraError(`Unknown edition: ${edition}`);
    return { built: buildBundle(edition, requiredOption(parsed, 'output')) };
  }
  if (command === 'install') {
    const parsed = parse(argv.slice(1), { edition: 'string', target: 'string', skill: 'string[]', apply: 'boolean', 'dry-run': 'boolean' }, 0);
    if (parsed.values.apply === true && parsed.values['dry-run'] === true) throw new OrqivraError('Choose only one of --apply or --dry-run.');
    return installSkills(requiredOption(parsed, 'edition'), requiredOption(parsed, 'target'), arrayValue(parsed.values.skill), parsed.values.apply === true);
  }
  if (command === 'verify-install') {
    const parsed = parse(argv.slice(1), { target: 'string' }, 0);
    return verifyInstall(requiredOption(parsed, 'target'));
  }
  if (command === 'uninstall') {
    const parsed = parse(argv.slice(1), { target: 'string', apply: 'boolean', 'dry-run': 'boolean' }, 0);
    if (parsed.values.apply === true && parsed.values['dry-run'] === true) throw new OrqivraError('Choose only one of --apply or --dry-run.');
    return uninstallSkills(requiredOption(parsed, 'target'), parsed.values.apply === true);
  }
  throw new OrqivraError(`Unknown command: ${command}`);
}

function validateCommand(kind: string | undefined, args: string[]): JsonObject {
  if (!kind) throw new OrqivraError('Expected validation kind project, dag, profile, or skills.');
  const parsed = parse(args, kind === 'dag' ? { project: 'string' } : {}, 1);
  const path = requiredPosition(parsed, 0);
  if (kind === 'project') {
    const project = loadProject(path);
    return { valid: true, kind, id: project.id };
  }
  if (kind === 'profile') {
    const profile = readJson(path);
    requireValid(profile, 'profile.schema.json');
    if (!isObject(profile)) throw new OrqivraError('Profile must be a JSON object.');
    return { valid: true, kind, id: profile.id, edition: profile.edition };
  }
  if (kind === 'skills') return { valid: true, kind, ...validateSkills(path) };
  if (kind === 'dag') {
    const dag = readDag(path);
    const projectPath = stringValue(parsed.values.project);
    let snapshot: JsonObject | null = null;
    if (projectPath) {
      const project = loadProject(projectPath);
      const rawRoot = project.root as string;
      const root = isAbsolute(rawRoot) ? rawRoot : resolve(dirname(resolve(projectPath)), rawRoot);
      for (const node of dag.nodes) {
        for (const scope of node.file_scope) {
          const relative = scope.endsWith('/**') ? scope.slice(0, -3) : scope;
          safeJoin(root, relative, true);
        }
      }
      const hashes = planHashes(dag, root);
      snapshot = { plan_hash: hashes.planHash, input_hashes: hashes.inputHashes };
    }
    return { valid: true, kind, id: dag.id, node_count: dag.nodes.length, snapshot_inputs: snapshot };
  }
  throw new OrqivraError(`Unknown validation kind: ${kind}`);
}

function loadProject(path: string): JsonObject {
  const project = readJson(path);
  requireValid(project, 'project.schema.json');
  if (!isObject(project) || !Array.isArray(project.inputs)) throw new OrqivraError('Project configuration is invalid.');
  for (const input of project.inputs) {
    if (typeof input !== 'string') throw new OrqivraError('Project inputs must be relative paths.');
    safeRelativePath(input);
  }
  return project;
}

function parse(args: string[], optionTypes: Record<string, 'string' | 'string[]' | 'boolean'>, positionalCount: number): Parsed {
  const options: Record<string, { type: 'string' | 'boolean'; multiple?: boolean }> = {};
  for (const [name, type] of Object.entries(optionTypes)) options[name] = type === 'string[]' ? { type: 'string', multiple: true } : { type };
  try {
    const result = parseArgs({ args, options, allowPositionals: true, strict: true });
    if (result.positionals.length !== positionalCount) throw new OrqivraError(`Expected ${positionalCount} positional argument(s), received ${result.positionals.length}.`);
    return { positionals: result.positionals, values: result.values as Parsed['values'] };
  } catch (error) {
    if (error instanceof OrqivraError) throw error;
    throw new OrqivraError(messageOf(error));
  }
}

function requiredPosition(parsed: Parsed, index: number): string {
  const value = parsed.positionals[index];
  if (!value) throw new OrqivraError(`Missing positional argument ${index + 1}.`);
  return value;
}

function requiredOption(parsed: Parsed, name: string): string {
  const value = stringValue(parsed.values[name]);
  if (value === undefined || value.length === 0) throw new OrqivraError(`--${name} is required.`);
  return value;
}

function integerOption(parsed: Parsed, name: string): number {
  const value = requiredOption(parsed, name);
  if (!/^-?(?:0|[1-9][0-9]*)$/.test(value)) throw new OrqivraError(`--${name} must be an integer.`);
  const number = Number(value);
  if (!Number.isSafeInteger(number)) throw new OrqivraError(`--${name} must be a safe integer.`);
  return number;
}

function stringValue(value: string | boolean | string[] | undefined): string | undefined {
  return typeof value === 'string' ? value : undefined;
}

function arrayValue(value: string | boolean | string[] | undefined): string[] {
  return Array.isArray(value) ? value : [];
}

function emitJson(value: JsonValue): void {
  process.stdout.write(`${JSON.stringify(sortObjectKeys(value), null, 2)}\n`);
}

function sortObjectKeys(value: JsonValue): JsonValue {
  if (Array.isArray(value)) return value.map(sortObjectKeys);
  if (value === null || typeof value !== 'object') return value;
  const result = Object.create(null) as JsonObject;
  for (const key of Object.keys(value).sort(compareText)) result[key] = sortObjectKeys(value[key]);
  return result;
}

function compareText(left: string, right: string): number {
  const a = Array.from(left, (character) => character.codePointAt(0)!);
  const b = Array.from(right, (character) => character.codePointAt(0)!);
  for (let index = 0; index < Math.min(a.length, b.length); index += 1) if (a[index] !== b[index]) return a[index] - b[index];
  return a.length - b.length;
}

function commandHelp(command?: string, action?: string): string {
  if (command === 'validate') return 'Usage: orqivra validate project|dag|profile|skills PATH [--project PROJECT]\n';
  if (command === 'state' && action === 'init') return 'Usage: orqivra state init DAG --state PATH [--project-root DIR]\n';
  if (command === 'state' && action === 'transition') return 'Usage: orqivra state transition --state PATH NODE --to STATUS --reason TEXT\n';
  if (command === 'attempt') return 'Usage: orqivra attempt begin|diagnose|record-change|verify --state PATH NODE [options]\n';
  if (command === 'evidence') return 'Usage: orqivra evidence add|check --state PATH [NODE] [options]\n';
  if (command === 'report') return 'Usage: orqivra report --state PATH [--format json|markdown]\n';
  return USAGE;
}

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function isNodeError(error: unknown): error is NodeJS.ErrnoException {
  return error instanceof Error && 'code' in error;
}

if (process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url))) {
  process.exitCode = main();
}
