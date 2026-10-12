import { existsSync, lstatSync, readFileSync, realpathSync, statSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { isAbsolute, parse, relative, resolve, sep } from 'node:path';
import { InputOutputError, UnsafePathError } from './errors.js';

export function safeRelativePath(value: string, allowSubtree = false): string {
  if (typeof value !== 'string' || value.length === 0 || value.includes('\0')) {
    throw new UnsafePathError('Path must be a non-empty relative string.');
  }
  let normalized = value.replaceAll('\\', '/');
  if (normalized.startsWith('/') || /^[A-Za-z]:/.test(value) || isAbsolute(value)) {
    throw new UnsafePathError(`Absolute paths are not allowed: ${value}`);
  }
  const subtree = allowSubtree && normalized.endsWith('/**');
  if (subtree) normalized = normalized.slice(0, -3);
  const components = normalized.split('/');
  if (components.some((part) => part.length === 0 || part === '.' || part === '..')) {
    throw new UnsafePathError(`Path traversal or empty path components are not allowed: ${value}`);
  }
  if (components.some((part) => /[*?:]/.test(part))) {
    throw new UnsafePathError(`Only a trailing /** directory scope is supported: ${value}`);
  }
  return components.join('/') + (subtree ? '/**' : '');
}

export function isLinkLike(path: string): boolean {
  try {
    return lstatSync(path).isSymbolicLink();
  } catch (error) {
    if (isNodeError(error) && (error.code === 'ENOENT' || error.code === 'ENOTDIR')) return false;
    throw new InputOutputError(`Could not inspect path: ${path}: ${messageOf(error)}`);
  }
}

export function rejectSymlinkPath(path: string): void {
  if (isLinkLike(path)) throw new UnsafePathError(`Selected path is a symlink or junction: ${path}`);
}

export function rejectSymlinkComponents(path: string): void {
  const absolute = resolve(path);
  const root = parse(absolute).root;
  let current = root;
  const components = relative(root, absolute).split(sep).filter(Boolean);
  for (const component of components) {
    current = resolve(current, component);
    if (isLinkLike(current)) throw new UnsafePathError(`Path crosses a symlink or junction: ${current}`);
  }
}

export function resolveSafeRoot(root: string): string {
  rejectSymlinkComponents(root);
  try {
    const resolved = realpathSync(root);
    if (!statSync(resolved).isDirectory()) throw new UnsafePathError(`Selected root is not a directory: ${root}`);
    return resolved;
  } catch (error) {
    if (error instanceof UnsafePathError) throw error;
    if (isNodeError(error) && error.code === 'ENOENT') throw new InputOutputError(`Selected root does not exist: ${root}`);
    throw new InputOutputError(`Could not inspect selected root ${root}: ${messageOf(error)}`);
  }
}

export function safeJoin(root: string, relativePath: string, allowMissing = false): string {
  const normalized = safeRelativePath(relativePath);
  const base = resolveSafeRoot(root);
  const candidate = resolve(base, ...normalized.split('/'));
  if (!within(candidate, base)) throw new UnsafePathError(`Path escapes selected root: ${relativePath}`);
  let current = base;
  const components = normalized.split('/');
  for (let index = 0; index < components.length; index += 1) {
    current = resolve(current, components[index]);
    if (isLinkLike(current)) throw new UnsafePathError(`Symlinks or junctions are not allowed under the selected root: ${current}`);
    if (!existsSync(current)) {
      if (!allowMissing) throw new InputOutputError(`Path does not exist: ${current}`);
      continue;
    }
    if (index < components.length - 1 && !statSync(current).isDirectory()) {
      throw new InputOutputError(`Path component is not a directory: ${current}`);
    }
  }
  if (existsSync(candidate)) {
    let resolved: string;
    try {
      resolved = realpathSync(candidate);
    } catch (error) {
      throw new InputOutputError(`Could not resolve path ${candidate}: ${messageOf(error)}`);
    }
    if (!within(resolved, base)) throw new UnsafePathError(`Path escapes selected root: ${relativePath}`);
  }
  return candidate;
}

export function sha256File(path: string): string {
  rejectSymlinkPath(path);
  try {
    if (!statSync(path).isFile()) throw new UnsafePathError(`Expected a regular non-symlink file: ${path}`);
    return createHash('sha256').update(readFileSync(path)).digest('hex');
  } catch (error) {
    if (error instanceof UnsafePathError) throw error;
    if (isNodeError(error) && error.code === 'ENOENT') throw new InputOutputError(`Path does not exist: ${path}`);
    throw new InputOutputError(`Could not read file ${path}: ${messageOf(error)}`);
  }
}

export function isWithin(path: string, root: string): boolean {
  try {
    return within(realpathSync(path), realpathSync(root));
  } catch {
    return false;
  }
}

function within(path: string, root: string): boolean {
  const relativePath = relative(root, path);
  return relativePath === '' || (!relativePath.startsWith(`..${sep}`) && relativePath !== '..' && !isAbsolute(relativePath));
}

function isNodeError(error: unknown): error is NodeJS.ErrnoException {
  return error instanceof Error && 'code' in error;
}

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
