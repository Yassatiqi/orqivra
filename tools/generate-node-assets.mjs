import { copyFile, lstat, mkdir, readdir, stat } from 'node:fs/promises';
import { dirname, join, relative, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');

function readOutputArgument(args) {
  const index = args.indexOf('--output');
  if (index < 0 || !args[index + 1] || args[index + 1].startsWith('--')) {
    throw new Error('Usage: node tools/generate-node-assets.mjs --output DIRECTORY');
  }
  if (args.indexOf('--output', index + 1) >= 0) {
    throw new Error('Specify --output only once.');
  }
  return resolve(args[index + 1]);
}

async function ensureEmptyDirectory(path) {
  try {
    const info = await lstat(path);
    if (info.isSymbolicLink() || !info.isDirectory()) {
      throw new Error(`Output must be a regular directory: ${path}`);
    }
    if ((await readdir(path)).length > 0) {
      throw new Error(`Output directory must be empty: ${path}`);
    }
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
    await mkdir(path, { recursive: true });
  }
}

async function copyRegularFile(sourceRelative, targetRelative) {
  const source = join(root, sourceRelative);
  const target = join(output, targetRelative);
  const sourceInfo = await lstat(source);
  if (!sourceInfo.isFile() || sourceInfo.isSymbolicLink()) {
    throw new Error(`Canonical asset must be a regular file: ${sourceRelative}`);
  }
  const normalized = relative(output, target);
  if (normalized.startsWith(`..${sep}`) || normalized === '..' || resolve(target) !== target) {
    throw new Error(`Generated asset path escapes the output directory: ${targetRelative}`);
  }
  await mkdir(dirname(target), { recursive: true });
  await copyFile(source, target);
}

const output = readOutputArgument(process.argv.slice(2));
await ensureEmptyDirectory(output);

const copies = [
  ['core/contracts/capabilities.md', 'contracts/capabilities.md'],
  ['LICENSE', 'ORQIVRA-LICENSE.txt'],
  ['README.md', 'README.md'],
  ['defaults/config.json', 'defaults/config.json'],
  ['models/catalog.json', 'models/catalog.json'],
];

for (const entry of await readdir(join(root, 'schemas'), { withFileTypes: true })) {
  if (entry.isFile() && entry.name.endsWith('.schema.json')) {
    copies.push([`schemas/${entry.name}`, `schemas/${entry.name}`]);
  }
}
for (const entry of await readdir(join(root, 'profiles'), { withFileTypes: true })) {
  if (entry.isFile() && entry.name.endsWith('.json')) {
    copies.push([`profiles/${entry.name}`, `profiles/${entry.name}`]);
  }
}
for (const entry of await readdir(join(root, 'skills'), { withFileTypes: true })) {
  if (!entry.isDirectory()) continue;
  copies.push([`skills/${entry.name}/SKILL.md`, `skills/${entry.name}/SKILL.md`]);
}
for (const edition of ['codex', 'claude-code', 'gemini-cli']) {
  copies.push([`editions/${edition}/adapter.json`, `editions/${edition}/adapter.json`]);
}

copies.sort((left, right) => (left[1] < right[1] ? -1 : left[1] > right[1] ? 1 : 0));
for (const [source, target] of copies) await copyRegularFile(source, target);

console.log(JSON.stringify({ output, files: copies.map(([, target]) => target) }, null, 2));
