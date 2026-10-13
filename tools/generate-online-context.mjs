import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const options = parseArguments(process.argv.slice(2));
const sourcePath = options.source ? path.resolve(options.source) : path.join(root, 'skills', 'orqivra-orchestrate', 'SKILL.md');
const outputPath = options.output ? path.resolve(options.output) : path.join(root, 'docs', 'online-llm-context.md');
const startMarker = '<!-- PORTABLE_METHOD_START -->';
const endMarker = '<!-- PORTABLE_METHOD_END -->';

const source = normalizeLineEndings(await readFile(sourcePath, 'utf8'));
const start = source.indexOf(startMarker);
const end = source.indexOf(endMarker);
if (start < 0 || end < 0 || end <= start || source.indexOf(startMarker, start + 1) >= 0 || source.indexOf(endMarker, end + 1) >= 0) {
  throw new Error(`Expected exactly one ordered portable-method marker pair in ${path.relative(root, sourcePath)}.`);
}

const content = `${source.slice(start + startMarker.length, end).trim()}\n`;
if (options.check) {
  const current = normalizeLineEndings(await readFile(outputPath, 'utf8'));
  if (current !== content) {
    throw new Error(`${path.relative(root, outputPath)} is stale; run node tools/generate-online-context.mjs.`);
  }
} else {
  // Write literal LF bytes on every platform; do not use platform text conversion.
  await writeFile(outputPath, content, 'utf8');
}

function normalizeLineEndings(value) {
  return value.replace(/\r\n?/g, '\n');
}

function parseArguments(args) {
  const parsed = { check: false, source: undefined, output: undefined };
  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === '--check') {
      if (parsed.check) throw new Error('Usage: node tools/generate-online-context.mjs [--check] [--source PATH] [--output PATH]');
      parsed.check = true;
      continue;
    }
    if (arg === '--source' || arg === '--output') {
      const value = args[index + 1];
      if (!value || value.startsWith('--')) throw new Error(`Usage: ${arg} requires a path.`);
      const key = arg === '--source' ? 'source' : 'output';
      if (parsed[key] !== undefined) throw new Error(`Usage: ${arg} may be specified only once.`);
      parsed[key] = value;
      index += 1;
      continue;
    }
    throw new Error('Usage: node tools/generate-online-context.mjs [--check] [--source PATH] [--output PATH]');
  }
  return parsed;
}
