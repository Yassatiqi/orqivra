import { createHash, randomBytes } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import {
  existsSync,
  lstatSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  renameSync,
  rmSync,
  writeFileSync,
} from 'node:fs';
import { dirname, relative, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const packageRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const repositoryRoot = resolve(packageRoot, '..');
const output = resolve(packageRoot, 'dist');
const markerName = '.orqivra-build-manifest.json';
const markerPath = resolve(output, markerName);
const stage = resolve(packageRoot, `.orqivra-build-${process.pid}-${randomBytes(6).toString('hex')}`);

if (Number(process.versions.node.split('.')[0]) < 24) {
  throw new Error(`ORQIVRA Node package build requires Node.js 24 or newer; found ${process.versions.node}.`);
}

verifyPreviousBuild(output, markerPath, markerName);
mkdirSync(stage);
try {
  const compiler = resolve(packageRoot, 'node_modules', 'typescript', 'bin', 'tsc');
  run(process.execPath, [compiler, '-p', resolve(packageRoot, 'tsconfig.json'), '--outDir', stage], packageRoot);
  run(process.execPath, [resolve(repositoryRoot, 'tools', 'generate-node-assets.mjs'), '--output', resolve(stage, 'assets')], repositoryRoot);
  const inventory = inventorySync(stage, markerName);
  writeFileSync(resolve(stage, markerName), `${JSON.stringify({ format_version: 2, ...inventory }, null, 2)}\n`, 'utf8');
  if (existsSync(output)) rmSync(output, { recursive: true });
  renameSync(stage, output);
  process.stdout.write(`Built ORQIVRA ${JSON.parse(readFileSync(resolve(packageRoot, 'package.json'), 'utf8')).version} for Node.js ${process.versions.node}.\n`);
} catch (error) {
  if (existsSync(stage)) rmSync(stage, { recursive: true, force: true });
  throw error;
}

function run(program, args, cwd) {
  const result = spawnSync(program, args, { cwd, stdio: 'inherit' });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`Build command failed with exit code ${result.status}: ${program}`);
}

function verifyPreviousBuild(directory, marker, markerName) {
  if (!existsSync(directory)) return;
  const directoryInfo = lstatSync(directory);
  if (directoryInfo.isSymbolicLink() || !directoryInfo.isDirectory()) throw new Error(`Build output must be a regular directory: ${directory}`);
  if (!existsSync(marker)) throw new Error(`Build output exists without an ORQIVRA build manifest; refusing to replace it: ${directory}`);
  const previous = JSON.parse(readFileSync(marker, 'utf8'));
  if (![1, 2].includes(previous.format_version) || !previous.files || typeof previous.files !== 'object' || Array.isArray(previous.files) || (previous.format_version === 2 && !Array.isArray(previous.directories))) {
    throw new Error(`ORQIVRA build manifest is invalid: ${marker}`);
  }
  const actual = inventorySync(directory, markerName);
  const expectedPaths = Object.keys(previous.files).sort();
  const actualPaths = Object.keys(actual.files).sort();
  if (expectedPaths.length !== actualPaths.length || expectedPaths.some((path, index) => path !== actualPaths[index])) {
    throw new Error(`Build output has missing or unowned files; refusing to replace it: ${directory}`);
  }
  for (const path of expectedPaths) {
    if (previous.files[path] !== actual.files[path]) throw new Error(`Build output was modified; refusing to replace ${path}`);
  }
  const expectedDirectories = previous.format_version === 2
    ? [...previous.directories].sort()
    : directoriesFromFiles(expectedPaths);
  const actualDirectories = [...actual.directories].sort();
  if (expectedDirectories.length !== actualDirectories.length || expectedDirectories.some((path, index) => path !== actualDirectories[index])) {
    throw new Error(`Build output has missing or unowned directories; refusing to replace it: ${directory}`);
  }
}

function directoriesFromFiles(files) {
  const directories = new Set();
  for (const file of files) {
    const components = file.split('/');
    components.pop();
    for (let index = 1; index <= components.length; index += 1) {
      directories.add(components.slice(0, index).join('/'));
    }
  }
  return [...directories].sort();
}

function inventorySync(directory, markerName) {
  const files = Object.create(null);
  const directories = [];
  for (const entry of listEntries(directory)) {
    const path = entry.path;
    const relativePath = relative(directory, path).split(sep).join('/');
    if (relativePath === markerName) continue;
    if (entry.type === 'directory') directories.push(relativePath);
    else files[relativePath] = createHash('sha256').update(readFileSync(path)).digest('hex');
  }
  return {
    files: Object.fromEntries(Object.entries(files).sort(([left], [right]) => left < right ? -1 : left > right ? 1 : 0)),
    directories: directories.sort(),
  };
}

function listEntries(directory) {
  const entries = [];
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const path = resolve(directory, entry.name);
    const info = lstatSync(path);
    if (info.isSymbolicLink()) throw new Error(`Build output contains a symlink or junction: ${path}`);
    if (info.isDirectory()) entries.push({ path, type: 'directory' }, ...listEntries(path));
    else if (info.isFile()) entries.push({ path, type: 'file' });
    else throw new Error(`Build output contains a non-regular entry: ${path}`);
  }
  return entries;
}
