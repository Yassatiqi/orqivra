import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const sourcePath = path.join(root, 'skills', 'orqivra-orchestrate', 'SKILL.md');
const outputPath = path.join(root, 'docs', 'online-llm-context.md');
const startMarker = '<!-- PORTABLE_METHOD_START -->';
const endMarker = '<!-- PORTABLE_METHOD_END -->';
const check = process.argv.includes('--check');
const unexpected = process.argv.slice(2).filter((arg) => arg !== '--check');

if (unexpected.length > 0 || process.argv.filter((arg) => arg === '--check').length > 1) {
  throw new Error('Usage: node tools/generate-online-context.mjs [--check]');
}

const source = await readFile(sourcePath, 'utf8');
const start = source.indexOf(startMarker);
const end = source.indexOf(endMarker);
if (start < 0 || end < 0 || end <= start || source.indexOf(startMarker, start + 1) >= 0 || source.indexOf(endMarker, end + 1) >= 0) {
  throw new Error(`Expected exactly one ordered portable-method marker pair in ${path.relative(root, sourcePath)}.`);
}

const content = `${source.slice(start + startMarker.length, end).trim()}\n`;
if (check) {
  const current = await readFile(outputPath, 'utf8');
  if (current !== content) {
    throw new Error(`${path.relative(root, outputPath)} is stale; run node tools/generate-online-context.mjs.`);
  }
} else {
  await writeFile(outputPath, content, 'utf8');
}
