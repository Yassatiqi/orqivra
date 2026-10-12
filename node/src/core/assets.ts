import { existsSync, statSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { InputOutputError } from './errors.js';

export function assetRoot(): string {
  const configured = process.env.ORQIVRA_DATA_DIR;
  if (configured) {
    const candidate = resolve(configured);
    if (isAssetRoot(candidate)) return candidate;
    throw new InputOutputError(`ORQIVRA_DATA_DIR does not contain runtime assets: ${candidate}`);
  }

  let current = dirname(fileURLToPath(import.meta.url));
  while (true) {
    if (isAssetRoot(resolve(current, 'assets'))) return resolve(current, 'assets');
    if (isAssetRoot(current)) return current;
    const parent = dirname(current);
    if (parent === current) break;
    current = parent;
  }
  throw new InputOutputError('ORQIVRA runtime assets were not found in this installation.');
}

function isAssetRoot(path: string): boolean {
  try {
    return ['schemas', 'profiles', 'skills', 'editions'].every((name) => {
      const candidate = resolve(path, name);
      return existsSync(candidate) && statSync(candidate).isDirectory();
    });
  } catch {
    return false;
  }
}
