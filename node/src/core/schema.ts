import { basename, resolve } from 'node:path';
import { assetRoot } from './assets.js';
import { OrqivraError } from './errors.js';
import { JsonObject, JsonValue, readJson } from './json.js';

type Schema = JsonObject;

export function validateData(data: JsonValue, schemaName: string): string[] {
  const schemaPath = resolve(assetRoot(), 'schemas', schemaName);
  const schema = asObject(readJson(schemaPath), `Schema ${schemaName}`);
  const errors: string[] = [];
  validateAt(data, schema, schemaPath, '$', errors, new Set());
  return errors.sort();
}

export function requireValid(data: JsonValue, schemaName: string): void {
  const errors = validateData(data, schemaName);
  if (errors.length > 0) {
    throw new OrqivraError(`${schemaName} validation failed:\n- ${errors.join('\n- ')}`);
  }
}

function validateAt(
  value: JsonValue,
  schema: Schema,
  schemaPath: string,
  location: string,
  errors: string[],
  refStack: Set<string>,
): void {
  if (typeof schema.$ref === 'string') {
    const resolved = resolveRef(schema.$ref, schemaPath);
    const refKey = `${resolved.path}#${resolved.pointer}`;
    if (refStack.has(refKey)) {
      errors.push(`${location}: cyclic $ref is not supported.`);
      return;
    }
    refStack.add(refKey);
    validateAt(value, resolved.schema, resolved.path, location, errors, refStack);
    refStack.delete(refKey);
    return;
  }

  if (schema.type !== undefined && !matchesType(value, schema.type)) {
    errors.push(`${location}: expected ${displayType(schema.type)}.`);
    return;
  }
  if (schema.const !== undefined && !sameJson(value, schema.const)) errors.push(`${location}: does not equal its required constant.`);
  if (Array.isArray(schema.enum) && !schema.enum.some((candidate) => sameJson(value, candidate))) {
    errors.push(`${location}: value is not in the allowed set.`);
  }

  if (typeof value === 'string') {
    const length = Array.from(value).length;
    if (typeof schema.minLength === 'number' && length < schema.minLength) errors.push(`${location}: string is too short.`);
    if (typeof schema.maxLength === 'number' && length > schema.maxLength) errors.push(`${location}: string is too long.`);
    if (typeof schema.pattern === 'string') {
      try {
        if (!new RegExp(schema.pattern).test(value)) errors.push(`${location}: string does not match the required pattern.`);
      } catch {
        errors.push(`${location}: schema has an invalid regular expression.`);
      }
    }
    if (schema.format === 'date-time' && !isDateTime(value)) errors.push(`${location}: string is not a valid date-time.`);
  }

  if (typeof value === 'number') {
    if (typeof schema.minimum === 'number' && value < schema.minimum) errors.push(`${location}: number is below the minimum.`);
    if (typeof schema.maximum === 'number' && value > schema.maximum) errors.push(`${location}: number is above the maximum.`);
  }

  if (Array.isArray(value)) {
    if (typeof schema.minItems === 'number' && value.length < schema.minItems) errors.push(`${location}: array has too few items.`);
    if (typeof schema.maxItems === 'number' && value.length > schema.maxItems) errors.push(`${location}: array has too many items.`);
    if (schema.uniqueItems === true) {
      for (let index = 0; index < value.length; index += 1) {
        if (value.slice(0, index).some((prior) => sameJson(prior, value[index]))) {
          errors.push(`${location}: array items must be unique.`);
          break;
        }
      }
    }
    if (isObject(schema.items)) {
      value.forEach((item, index) => validateAt(item, schema.items as Schema, schemaPath, `${location}[${index}]`, errors, refStack));
    }
  }

  if (isObject(value)) validateObject(value, schema, schemaPath, location, errors, refStack);

  if (isObject(schema.not)) {
    const nestedErrors: string[] = [];
    validateAt(value, schema.not, schemaPath, location, nestedErrors, refStack);
    if (nestedErrors.length === 0) errors.push(`${location}: value matches a forbidden schema.`);
  }
}

function validateObject(
  value: JsonObject,
  schema: Schema,
  schemaPath: string,
  location: string,
  errors: string[],
  refStack: Set<string>,
): void {
  if (typeof schema.minProperties === 'number' && Object.keys(value).length < schema.minProperties) {
    errors.push(`${location}: object has too few properties.`);
  }
  const properties = isObject(schema.properties) ? schema.properties : Object.create(null) as JsonObject;
  if (Array.isArray(schema.required)) {
    for (const name of schema.required) {
      if (typeof name === 'string' && !Object.hasOwn(value, name)) errors.push(`${location}: missing required property '${name}'.`);
    }
  }
  for (const [name, propertySchema] of Object.entries(properties)) {
    if (Object.hasOwn(value, name) && isObject(propertySchema)) {
      validateAt(value[name], propertySchema, schemaPath, childLocation(location, name), errors, refStack);
    }
  }
  for (const [name, propertyValue] of Object.entries(value)) {
    if (Object.hasOwn(properties, name)) continue;
    if (schema.additionalProperties === false) {
      errors.push(`${childLocation(location, name)}: additional property is not allowed.`);
    } else if (isObject(schema.additionalProperties)) {
      validateAt(propertyValue, schema.additionalProperties, schemaPath, childLocation(location, name), errors, refStack);
    }
  }
}

function resolveRef(ref: string, currentPath: string): { path: string; pointer: string; schema: Schema } {
  const [filePart, rawPointer = ''] = ref.split('#', 2);
  const path = filePart ? resolve(resolve(assetRoot(), 'schemas'), basename(filePart)) : currentPath;
  const document = asObject(readJson(path), `Schema ${path}`);
  let schemaValue: JsonValue = document;
  if (rawPointer) {
    if (!rawPointer.startsWith('/')) throw new Error(`Unsupported schema reference: ${ref}`);
    for (const component of rawPointer.slice(1).split('/')) {
      const key = component.replaceAll('~1', '/').replaceAll('~0', '~');
      if (!isObject(schemaValue) || !Object.hasOwn(schemaValue, key)) throw new Error(`Unresolved schema reference: ${ref}`);
      schemaValue = schemaValue[key];
    }
  }
  return { path, pointer: rawPointer, schema: asObject(schemaValue, `Reference ${ref}`) };
}

function matchesType(value: JsonValue, expected: JsonValue): boolean {
  const types = Array.isArray(expected) ? expected : [expected];
  return types.some((type) => {
    if (type === 'null') return value === null;
    if (type === 'object') return isObject(value);
    if (type === 'array') return Array.isArray(value);
    if (type === 'integer') return typeof value === 'number' && Number.isInteger(value);
    if (type === 'number') return typeof value === 'number';
    if (type === 'string') return typeof value === 'string';
    if (type === 'boolean') return typeof value === 'boolean';
    return false;
  });
}

function displayType(expected: JsonValue): string {
  return Array.isArray(expected) ? expected.map(String).join(' or ') : String(expected);
}

function isDateTime(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(value)) return false;
  const time = Date.parse(value);
  if (!Number.isFinite(time)) return false;
  const [datePart, timePart] = value.split('T');
  const [year, month, day] = datePart.split('-').map(Number);
  const [hour, minute, second] = timePart.slice(0, 8).split(':').map(Number);
  const days = new Date(Date.UTC(year, month, 0)).getUTCDate();
  return month >= 1 && month <= 12 && day >= 1 && day <= days && hour <= 23 && minute <= 59 && second <= 59;
}

function sameJson(left: unknown, right: unknown): boolean {
  if (left === right) return true;
  if (typeof left !== 'object' || left === null || typeof right !== 'object' || right === null) return false;
  if (Array.isArray(left) || Array.isArray(right)) {
    return Array.isArray(left) && Array.isArray(right) && left.length === right.length && left.every((item, index) => sameJson(item, right[index]));
  }
  const a = left as Record<string, unknown>;
  const b = right as Record<string, unknown>;
  const keys = Object.keys(a);
  return keys.length === Object.keys(b).length && keys.every((key) => Object.hasOwn(b, key) && sameJson(a[key], b[key]));
}

export function isObject(value: unknown): value is JsonObject {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function asObject(value: JsonValue, label: string): JsonObject {
  if (!isObject(value)) throw new Error(`${label} must be a JSON object.`);
  return value;
}

function childLocation(parent: string, key: string): string {
  return /^[A-Za-z_][A-Za-z0-9_-]*$/.test(key) ? `${parent}.${key}` : `${parent}[${JSON.stringify(key)}]`;
}
