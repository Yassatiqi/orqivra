import { randomBytes } from 'node:crypto';
import {
  closeSync,
  existsSync,
  fsyncSync,
  lstatSync,
  mkdirSync,
  mkdtempSync,
  openSync,
  readFileSync,
  readdirSync,
  renameSync,
  rmSync,
  rmdirSync,
  statSync,
  unlinkSync,
  writeFileSync,
} from 'node:fs';
import { basename, dirname, isAbsolute, join, relative, resolve, sep } from 'node:path';
import { assetRoot } from '../core/assets.js';
import { InputOutputError, OrqivraError, UnsafePathError } from '../core/errors.js';
import { JsonObject, JsonValue, readJson, sha256Bytes } from '../core/json.js';
import { rejectSymlinkComponents, rejectSymlinkPath, safeJoin, safeRelativePath, sha256File } from '../core/paths.js';
import { isObject, requireValid, validateData } from '../core/schema.js';

export const ORQIVRA_VERSION = '0.2.0';

export const SKILL_NAMES = ['orqivra-architecture', 'orqivra-orchestrate', 'orqivra-recover', 'orqivra-verify'];
export const EDITIONS = ['claude-code', 'codex', 'gemini-cli'];
export const MANIFEST_NAME = '.orqivra-manifest.json';

type Adapter = JsonObject & { edition: string; client_name: string; native_skills_path: string; guidance: string };
type RenderedSkill = { name: string; text: string; metadata: JsonObject; body: string; words: number };
type InstallManifest = JsonObject & { format_version: number; owner: string; edition: string; files: Record<string, string> };

export function renderEditionSkills(edition: string): { skills: RenderedSkill[]; adapter: Adapter } {
  if (!EDITIONS.includes(edition)) throw new OrqivraError(`Unknown edition: ${edition}`);
  const root = assetRoot();
  const adapterPath = resolve(root, 'editions', edition, 'adapter.json');
  const adapter = readJson(adapterPath);
  requireValid(adapter, 'edition-adapter.schema.json');
  if (!isObject(adapter) || adapter.edition !== edition) throw new OrqivraError(`Edition adapter ID does not match its directory: ${adapterPath}`);
  const expectedPaths = { codex: '.agents/skills', 'claude-code': '.claude/skills', 'gemini-cli': '.gemini/skills' };
  if (adapter.native_skills_path !== expectedPaths[edition as keyof typeof expectedPaths]) {
    throw new OrqivraError(`Edition adapter has an unexpected native skill path: ${adapterPath}`);
  }
  const marker = '<!-- ORQIVRA_CLIENT_ADAPTER -->';
  const section = `## ${String(adapter.client_name)} discovery, invocation, and permissions\n\n${String(adapter.guidance)}`;
  const rendered: RenderedSkill[] = [];
  for (const name of SKILL_NAMES) {
    const path = resolve(root, 'skills', name, 'SKILL.md');
    rejectSymlinkComponents(path);
    rejectSymlinkPath(path);
    const raw = readUtf8(path).replace(/\r\n?/g, '\n');
    if (raw.split(marker).length !== 2) throw new OrqivraError(`Canonical skill source must contain one client adapter marker: ${path}`);
    const text = raw.replace(marker, section);
    const parsed = parseSkillText(text, `${name}/SKILL.md`);
    const errors = validateData(parsed.metadata, 'skill.schema.json');
    if (errors.length) throw new OrqivraError(`Invalid metadata in ${name}/SKILL.md:\n- ${errors.join('\n- ')}`);
    if (parsed.metadata.name !== name) throw new OrqivraError(`Skill name must match its directory name: ${name}/SKILL.md`);
    const words = wordCount(parsed.body);
    if (words < 500 || words > 900) throw new OrqivraError(`Skill body must contain 500-900 words: ${name}/SKILL.md has ${words}.`);
    rendered.push({ name, text, metadata: parsed.metadata, body: parsed.body, words });
  }
  return { skills: rendered.sort((left, right) => compareText(left.name, right.name)), adapter: adapter as Adapter };
}

export function validateSkills(root: string): { skills: Array<{ name: string; words: number }>; count: number } {
  const selected = findSkillsRoot(root);
  const skills = validateSkillFiles(selected);
  return { skills: skills.map(({ name, words }) => ({ name, words })), count: skills.length };
}

export function findSkillsRoot(path: string): string {
  const base = resolve(path);
  rejectSymlinkComponents(base);
  let baseStat;
  try {
    baseStat = lstatSync(base);
  } catch (error) {
    throw new InputOutputError(`Skill directory does not exist: ${base}: ${messageOf(error)}`);
  }
  if (baseStat.isSymbolicLink() || !baseStat.isDirectory()) throw new UnsafePathError(`Skill path must be a regular directory: ${base}`);

  const candidates = new Set<string>();
  for (const file of collectFiles(base)) {
    if (basename(file) !== 'SKILL.md' || !SKILL_NAMES.includes(basename(dirname(file)))) continue;
    candidates.add(dirname(dirname(file)));
  }
  for (const candidate of [...candidates].sort(compareText)) {
    const names = readdirSync(candidate, { withFileTypes: true })
      .filter((entry) => entry.isDirectory() && SKILL_NAMES.includes(entry.name) && existsSync(resolve(candidate, entry.name, 'SKILL.md')))
      .map((entry) => entry.name)
      .sort(compareText);
    if (names.length === SKILL_NAMES.length && names.every((name, index) => name === [...SKILL_NAMES].sort(compareText)[index])) return candidate;
  }
  throw new OrqivraError(`Edition does not contain all four required skills: ${base}`);
}

function validateSkillFiles(root: string): RenderedSkill[] {
  const skills: RenderedSkill[] = [];
  for (const name of SKILL_NAMES) {
    const path = resolve(root, name, 'SKILL.md');
    rejectSymlinkComponents(path);
    rejectSymlinkPath(path);
    const parsed = parseSkillText(readUtf8(path), path);
    const errors = validateData(parsed.metadata, 'skill.schema.json');
    if (errors.length) throw new OrqivraError(`Invalid metadata in ${path}:\n- ${errors.join('\n- ')}`);
    if (parsed.metadata.name !== name) throw new OrqivraError(`Skill name must match its directory name: ${path}`);
    const words = wordCount(parsed.body);
    if (words < 500 || words > 900) throw new OrqivraError(`Skill body must contain 500-900 words: ${path} has ${words}.`);
    skills.push({ name, text: readUtf8(path), metadata: parsed.metadata, body: parsed.body, words });
  }
  return skills.sort((left, right) => compareText(left.name, right.name));
}

function collectFiles(root: string): string[] {
  const result: string[] = [];
  for (const entry of readdirSync(root, { withFileTypes: true })) {
    const path = resolve(root, entry.name);
    const info = lstatSync(path);
    if (info.isSymbolicLink()) throw new UnsafePathError(`Skill source contains a symlink or junction: ${path}`);
    if (info.isDirectory()) result.push(...collectFiles(path));
    else if (info.isFile()) result.push(path);
    else throw new UnsafePathError(`Skill source contains a non-regular file: ${path}`);
  }
  return result;
}

function parseSkillText(source: string, label: string): { metadata: JsonObject; body: string } {
  const text = source.replace(/^\uFEFF/, '').replace(/\r\n?/g, '\n');
  if (!text.startsWith('---\n')) throw new OrqivraError(`Skill frontmatter must begin with ---: ${label}`);
  const end = text.indexOf('\n---\n', 4);
  if (end < 0) throw new OrqivraError(`Skill frontmatter is not closed: ${label}`);
  const metadata = parseYamlMapping(text.slice(4, end), label);
  return { metadata, body: text.slice(end + 5) };
}

function parseYamlMapping(source: string, label: string): JsonObject {
  const lines = source.split('\n');
  const root = Object.create(null) as JsonObject;
  const stack: Array<{ indent: number; value: JsonObject }> = [{ indent: -1, value: root }];
  for (let index = 0; index < lines.length; index += 1) {
    const raw = lines[index];
    if (!raw.trim() || raw.trimStart().startsWith('#')) continue;
    if (raw.includes('\t')) throw new OrqivraError(`Tabs are not supported in skill YAML frontmatter: ${label}`);
    const indent = raw.length - raw.trimStart().length;
    const match = /^([A-Za-z0-9_-]+):(?:\s*(.*))?$/.exec(raw.trim());
    if (!match) throw new OrqivraError(`Unsupported skill YAML frontmatter syntax: ${label}`);
    const key = match[1];
    const rawValue = match[2] ?? '';
    while (stack.length > 1 && stack.at(-1)!.indent >= indent) stack.pop();
    const parent = stack.at(-1)!.value;
    if (Object.hasOwn(parent, key)) throw new OrqivraError(`Duplicate skill frontmatter key '${key}': ${label}`);
    if (rawValue === '' || rawValue === '|' || rawValue === '>' || rawValue === '|-' || rawValue === '>-') {
      const contentLines: string[] = [];
      if (rawValue.startsWith('|') || rawValue.startsWith('>')) {
        let next = index + 1;
        while (next < lines.length) {
          const candidate = lines[next];
          if (candidate.trim() && candidate.length - candidate.trimStart().length <= indent) break;
          contentLines.push(candidate.trim() ? candidate.slice(Math.min(candidate.length - candidate.trimStart().length, indent + 2)) : '');
          next += 1;
        }
        index = next - 1;
        parent[key] = rawValue.startsWith('|') ? contentLines.join('\n') : contentLines.join(' ').trim();
      } else {
        let hasChild = false;
        for (let next = index + 1; next < lines.length; next += 1) {
          if (!lines[next].trim() || lines[next].trimStart().startsWith('#')) continue;
          hasChild = lines[next].length - lines[next].trimStart().length > indent;
          break;
        }
        if (hasChild) {
          const nested = Object.create(null) as JsonObject;
          parent[key] = nested;
          stack.push({ indent, value: nested });
        } else parent[key] = null;
      }
    } else {
      parent[key] = parseYamlScalar(stripYamlComment(rawValue), label);
    }
  }
  return root;
}

function parseYamlScalar(value: string, label: string): JsonValue {
  const cleaned = value.trim();
  if (cleaned === 'null' || cleaned === 'Null' || cleaned === 'NULL' || cleaned === '~') return null;
  if (/^(?:true|false)$/i.test(cleaned)) return cleaned.toLowerCase() === 'true';
  if (/^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?$/.test(cleaned)) {
    const number = Number(cleaned);
    if (!Number.isFinite(number) || !Number.isSafeInteger(number)) return number;
    return number;
  }
  if (cleaned.startsWith('"') && cleaned.endsWith('"')) {
    try { return JSON.parse(cleaned) as string; } catch { throw new OrqivraError(`Invalid quoted skill YAML scalar: ${label}`); }
  }
  if (cleaned.startsWith("'") && cleaned.endsWith("'")) return cleaned.slice(1, -1).replaceAll("''", "'");
  if (/^[&*!]|^(?:\[|\{)/.test(cleaned)) throw new OrqivraError(`YAML tags, aliases, and flow collections are not supported: ${label}`);
  return cleaned;
}

function stripYamlComment(value: string): string {
  let quote: string | null = null;
  for (let index = 0; index < value.length; index += 1) {
    const character = value[index];
    if (quote === '"' && character === '\\') { index += 1; continue; }
    if ((character === '"' || character === "'") && (quote === null || quote === character)) { quote = quote === null ? character : null; continue; }
    if (character === '#' && quote === null && (index === 0 || /\s/.test(value[index - 1]))) return value.slice(0, index).trimEnd();
  }
  return value;
}

function wordCount(value: string): number {
  const cleaned = value.trim();
  return cleaned ? cleaned.split(/\s+/u).length : 0;
}

function readUtf8(path: string): string {
  try {
    return new TextDecoder('utf-8', { fatal: true }).decode(readFileSync(path));
  } catch (error) {
    if (isNodeError(error) && error.code === 'ENOENT') throw new InputOutputError(`Path does not exist: ${path}`);
    throw new OrqivraError(`Could not read valid UTF-8 text from ${path}: ${messageOf(error)}`);
  }
}

export function buildBundle(edition: string, outputPath: string): string[] {
  const editions = edition === 'all' ? [...EDITIONS].sort(compareText) : [edition];
  if (editions.some((name) => !EDITIONS.includes(name))) throw new OrqivraError(`Unknown edition: ${edition}`);
  const target = resolve(outputPath);
  rejectSymlinkComponents(target);
  rejectSymlinkPath(target);
  if (existsSync(target) && (!statSync(target).isDirectory() || readdirSync(target).length > 0)) {
    throw new OrqivraError(`Build output must be a new or empty directory: ${target}`);
  }
  mkdirSync(dirname(target), { recursive: true });
  const stage = mkdtempSync(join(dirname(target), `.${basename(target)}.orqivra-`));
  const results = editions.map((name) => resolve(target, name));
  try {
    for (const name of editions) {
      const editionOutput = resolve(stage, name);
      mkdirSync(editionOutput);
      const hashes = buildEdition(name, editionOutput);
      writeJsonAtomic(resolve(editionOutput, 'BUILD-MANIFEST.json'), {
        format_version: 1,
        framework_version: ORQIVRA_VERSION,
        edition: name,
        files: sortedRecord(hashes),
      });
    }
    if (existsSync(target)) rmdirSync(target);
    renameSync(stage, target);
  } catch (error) {
    throw error instanceof OrqivraError ? error : new InputOutputError(`Could not build edition bundle: ${messageOf(error)}`);
  } finally {
    if (existsSync(stage)) rmSync(stage, { recursive: true, force: true });
  }
  return results;
}

function buildEdition(edition: string, output: string): Record<string, string> {
  const root = assetRoot();
  const { skills, adapter } = renderEditionSkills(edition);
  const profilePath = resolve(root, 'profiles', `${edition}.json`);
  requireValid(readJson(profilePath), 'profile.schema.json');
  const nativePath = adapter.native_skills_path;
  const hashes = Object.create(null) as Record<string, string>;
  for (const skill of skills) {
    const relativePath = `${nativePath}/${skill.name}/SKILL.md`;
    hashes[relativePath] = writeAsset(output, relativePath, Buffer.from(skill.text, 'utf8'));
  }
  for (const [relativePath, candidates] of [
    [`profiles/${edition}.json`, [`profiles/${edition}.json`]],
    ['contracts/capabilities.md', ['contracts/capabilities.md', 'core/contracts/capabilities.md']],
    [`editions/${edition}/adapter.json`, [`editions/${edition}/adapter.json`]],
    ['LICENSE', ['LICENSE', 'ORQIVRA-LICENSE.txt']],
  ] as Array<[string, string[]]>) {
    hashes[relativePath] = copyFirstAsset(root, candidates, output, relativePath);
  }
  const schemaRoot = resolve(root, 'schemas');
  for (const entry of readdirSync(schemaRoot, { withFileTypes: true })) {
    if (!entry.isFile() || !entry.name.endsWith('.schema.json')) continue;
    hashes[`schemas/${entry.name}`] = copyFirstAsset(root, [`schemas/${entry.name}`], output, `schemas/${entry.name}`);
  }
  return hashes;
}

function copyFirstAsset(root: string, candidates: string[], output: string, relativePath: string): string {
  for (const candidate of candidates) {
    const source = resolve(root, candidate);
    if (existsSync(source)) {
      rejectSymlinkComponents(source);
      rejectSymlinkPath(source);
      if (!statSync(source).isFile()) throw new UnsafePathError(`Runtime asset must be a regular file: ${source}`);
      return writeAsset(output, relativePath, readFileSync(source));
    }
  }
  throw new InputOutputError(`Required runtime asset is missing: ${candidates[0]}`);
}

function writeAsset(root: string, relativePath: string, payload: Uint8Array): string {
  const normalized = safeRelativePath(relativePath);
  const target = resolve(root, ...normalized.split('/'));
  if (!isWithinLexical(target, root)) throw new UnsafePathError(`Bundle path escapes output directory: ${relativePath}`);
  mkdirSync(dirname(target), { recursive: true });
  writeFileSync(target, payload);
  return sha256Bytes(payload);
}

export function installSkills(edition: string, targetPath: string, selected: string[] = [], apply = false): JsonObject {
  const { skills } = renderEditionSkills(edition);
  const sources = new Map(skills.map((skill) => [skill.name, Buffer.from(skill.text, 'utf8')]));
  const selectedNames = [...new Set(selected.length ? selected : SKILL_NAMES)].sort(compareText);
  const unknown = selectedNames.filter((name) => !SKILL_NAMES.includes(name));
  if (unknown.length) throw new OrqivraError(`Unknown skill selection: ${unknown.join(', ')}`);
  const target = resolve(targetPath);
  rejectSymlinkComponents(target);
  rejectSymlinkPath(target);
  if (existsSync(target) && !statSync(target).isDirectory()) throw new OrqivraError(`Installation target must be a directory: ${target}`);
  const manifestPath = resolve(target, MANIFEST_NAME);
  rejectSymlinkPath(manifestPath);
  let current: InstallManifest | undefined;
  let oldManifestBytes: Buffer | undefined;
  if (existsSync(target) && existsSync(manifestPath)) {
    oldManifestBytes = readFileSync(manifestPath);
    current = readInstallManifest(target);
    if (current.edition !== edition) throw new OrqivraError('The target already belongs to another ORQIVRA edition.');
    for (const [relativePath, oldHash] of Object.entries(current.files)) {
      if (sha256File(safeJoin(target, relativePath)) !== oldHash) {
        throw new OrqivraError(`An installed file was modified; refusing to overwrite it: ${relativePath}`);
      }
    }
  }

  const newFiles: Record<string, string> = Object.assign(Object.create(null), current?.files ?? {});
  const planned: Array<{ path: string; digest: string; payload: Buffer }> = [];
  for (const name of selectedNames) {
    const relativePath = `${name}/SKILL.md`;
    const payload = sources.get(name)!;
    const digest = sha256Bytes(payload);
    const destination = safeDestination(target, relativePath);
    const ownedHash = newFiles[relativePath];
    if (existsSync(destination)) {
      rejectSymlinkPath(destination);
      if (!ownedHash) throw new OrqivraError(`Unowned destination already exists: ${destination}`);
      if (sha256File(destination) !== ownedHash) throw new OrqivraError(`An installed file was modified; refusing to overwrite it: ${relativePath}`);
    }
    planned.push({ path: relativePath, digest, payload });
    newFiles[relativePath] = digest;
  }
  const manifest: InstallManifest = {
    format_version: 1,
    owner: 'ORQIVRA',
    framework_version: ORQIVRA_VERSION,
    edition,
    skills: [...new Set(Object.keys(newFiles).map((path) => path.split('/')[0]))].sort(compareText),
    files: sortedRecord(newFiles),
  };

  if (apply) {
    mkdirSync(target, { recursive: true });
    rejectSymlinkComponents(target);
    const manifestTemp = `${manifestPath}.orqivra-tmp`;
    rejectSymlinkPath(manifestTemp);
    if (existsSync(manifestTemp)) throw new OrqivraError(`Temporary installation path already exists: ${manifestTemp}`);
    const temps: string[] = [];
    try {
      for (const item of planned) {
        const destination = safeDestination(target, item.path);
        const temp = `${destination}.orqivra-tmp`;
        rejectSymlinkPath(temp);
        if (existsSync(temp)) throw new OrqivraError(`Temporary installation path already exists: ${temp}`);
        if (existsSync(destination)) {
          const expected = current?.files[item.path];
          if (!expected || sha256File(destination) !== expected) throw new OrqivraError(`An installed file was modified; refusing to overwrite it: ${item.path}`);
        }
        mkdirSync(dirname(destination), { recursive: true });
        writeSyncedFile(temp, item.payload);
        temps.push(temp);
        if (existsSync(destination)) {
          const expected = current?.files[item.path];
          if (!expected || sha256File(destination) !== expected) throw new OrqivraError(`An installed file was modified; refusing to overwrite it: ${item.path}`);
        } else if (current?.files[item.path]) {
          throw new OrqivraError(`An installed file disappeared during update: ${item.path}`);
        }
        renameSync(temp, destination);
        temps.pop();
      }
      if (oldManifestBytes) {
        if (!existsSync(manifestPath) || !readFileSync(manifestPath).equals(oldManifestBytes)) {
          throw new OrqivraError(`Installation manifest changed during update: ${manifestPath}`);
        }
      } else if (existsSync(manifestPath)) {
        throw new OrqivraError(`Installation manifest appeared during update: ${manifestPath}`);
      }
      writeSyncedFile(manifestTemp, Buffer.from(`${JSON.stringify(sortObjectKeys(manifest), null, 2)}\n`, 'utf8'));
      renameSync(manifestTemp, manifestPath);
    } finally {
      for (const temp of temps) try { unlinkSync(temp); } catch { /* Keep the primary failure. */ }
      if (existsSync(manifestTemp)) try { unlinkSync(manifestTemp); } catch { /* Keep the primary failure. */ }
    }
  }
  return { edition, target, dry_run: !apply, files: planned.map((item) => item.path).sort(compareText), skill_count: skills.length };
}

export function verifyInstall(targetPath: string): JsonObject {
  const target = resolve(targetPath);
  rejectSymlinkComponents(target);
  if (!existsSync(target) || !statSync(target).isDirectory()) throw new OrqivraError(`Installation target must be a directory: ${target}`);
  const manifest = readInstallManifest(target);
  const mismatches: string[] = [];
  for (const [relativePath, expected] of Object.entries(manifest.files).sort(([left], [right]) => compareText(left, right))) {
    let actual: string | null;
    try { actual = sha256File(safeJoin(target, relativePath)); } catch { actual = null; }
    if (actual !== expected) mismatches.push(relativePath);
  }
  if (mismatches.length) throw new OrqivraError(`Installed files are missing or modified: ${mismatches.join(', ')}`);
  return { edition: manifest.edition, target, verified_files: Object.keys(manifest.files).length, valid: true };
}

export function uninstallSkills(targetPath: string, apply = false): JsonObject {
  const target = resolve(targetPath);
  rejectSymlinkComponents(target);
  if (!existsSync(target) || !statSync(target).isDirectory()) throw new OrqivraError(`Installation target must be a directory: ${target}`);
  const manifest = readInstallManifest(target);
  const verified = verifyInstall(target);
  const files = Object.keys(manifest.files).sort((left, right) => compareText(right, left));
  if (apply) {
    for (const relativePath of files) {
      const path = safeJoin(target, relativePath);
      if (sha256File(path) !== manifest.files[relativePath]) throw new OrqivraError(`Installed file changed during uninstall: ${relativePath}`);
      unlinkSync(path);
    }
    const manifestPath = resolve(target, MANIFEST_NAME);
    rejectSymlinkPath(manifestPath);
    unlinkSync(manifestPath);
    const directories = [...new Set(files.map((path) => dirname(resolve(target, ...path.split('/')))))]
      .sort((left, right) => right.length - left.length);
    for (const path of directories) try { rmdirSync(path); } catch { /* Keep directories that contain unrelated user files. */ }
  }
  return { edition: manifest.edition, target, dry_run: !apply, removed_files: files, verified_files: verified.verified_files };
}

function readInstallManifest(target: string): InstallManifest {
  const path = resolve(target, MANIFEST_NAME);
  rejectSymlinkPath(path);
  if (!existsSync(path) || !statSync(path).isFile()) throw new OrqivraError(`No ORQIVRA ownership manifest found under ${target}.`);
  const manifest = readJson(path);
  if (!isObject(manifest) || manifest.format_version !== 1 || manifest.owner !== 'ORQIVRA' || typeof manifest.edition !== 'string' || !EDITIONS.includes(manifest.edition)) {
    throw new OrqivraError('ORQIVRA ownership manifest is invalid or unsupported.');
  }
  if (!isObject(manifest.files)) throw new OrqivraError('ORQIVRA ownership manifest has no files map.');
  const files = Object.create(null) as Record<string, string>;
  for (const [rawPath, digest] of Object.entries(manifest.files)) {
    const normalized = safeRelativePath(rawPath);
    if (normalized !== rawPath || !SKILL_NAMES.includes(normalized.split('/')[0])) throw new UnsafePathError(`Manifest contains an invalid owned path: ${rawPath}`);
    if (typeof digest !== 'string' || !/^[0-9a-f]{64}$/.test(digest)) throw new OrqivraError(`Manifest contains an invalid file digest: ${rawPath}`);
    files[rawPath] = digest;
  }
  return { ...manifest, files } as InstallManifest;
}

function safeDestination(root: string, relativePath: string): string {
  const normalized = safeRelativePath(relativePath);
  rejectSymlinkComponents(root);
  const absoluteRoot = resolve(root);
  const candidate = resolve(absoluteRoot, ...normalized.split('/'));
  if (!isWithinLexical(candidate, absoluteRoot)) throw new UnsafePathError(`Path escapes selected root: ${relativePath}`);
  let current = absoluteRoot;
  for (const component of normalized.split('/')) {
    current = resolve(current, component);
    if (existsSync(current)) {
      rejectSymlinkPath(current);
      if (current !== candidate && !statSync(current).isDirectory()) throw new InputOutputError(`Path component is not a directory: ${current}`);
    }
  }
  if (existsSync(absoluteRoot)) return safeJoin(absoluteRoot, normalized, true);
  return candidate;
}

function writeSyncedFile(path: string, payload: Uint8Array): void {
  try {
    writeFileSync(path, payload, { flag: 'wx', mode: 0o600 });
    const descriptor = openSync(path, 'r+');
    try { fsyncSync(descriptor); } finally { closeSync(descriptor); }
  } catch (error) {
    if (existsSync(path)) try { unlinkSync(path); } catch { /* Preserve the primary failure. */ }
    throw error;
  }
}

function writeJsonAtomic(path: string, value: JsonObject): void {
  const temporary = `${path}.${process.pid}.${randomBytes(8).toString('hex')}.tmp`;
  try {
    writeSyncedFile(temporary, Buffer.from(`${JSON.stringify(sortObjectKeys(value), null, 2)}\n`, 'utf8'));
    renameSync(temporary, path);
  } catch (error) {
    if (existsSync(temporary)) unlinkSync(temporary);
    throw error instanceof OrqivraError ? error : new InputOutputError(`Could not write ${path}: ${messageOf(error)}`);
  }
}

function sortObjectKeys(value: JsonValue): JsonValue {
  if (Array.isArray(value)) return value.map(sortObjectKeys);
  if (value === null || typeof value !== 'object') return value;
  const result = Object.create(null) as JsonObject;
  for (const key of Object.keys(value).sort(compareText)) result[key] = sortObjectKeys(value[key]);
  return result;
}

function sortedRecord<T>(value: Record<string, T>): Record<string, T> {
  const result = Object.create(null) as Record<string, T>;
  for (const key of Object.keys(value).sort(compareText)) result[key] = value[key];
  return result;
}

function isWithinLexical(path: string, root: string): boolean {
  const rel = relative(root, path);
  return rel === '' || (rel !== '..' && !rel.startsWith(`..${sep}`) && !isAbsolute(rel));
}

function compareText(left: string, right: string): number {
  const a = Array.from(left, (character) => character.codePointAt(0)!);
  const b = Array.from(right, (character) => character.codePointAt(0)!);
  for (let index = 0; index < Math.min(a.length, b.length); index += 1) if (a[index] !== b[index]) return a[index] - b[index];
  return a.length - b.length;
}

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function isNodeError(error: unknown): error is NodeJS.ErrnoException {
  return error instanceof Error && 'code' in error;
}
