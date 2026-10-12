import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { InputOutputError, OrqivraError } from './errors.js';

export type JsonValue = null | boolean | number | string | JsonValue[] | { [key: string]: JsonValue };
export type JsonObject = { [key: string]: JsonValue };

class JsonReader {
  private position = 0;

  constructor(private readonly text: string, private readonly source: string) {}

  parse(): JsonValue {
    this.skipWhitespace();
    const result = this.parseValue();
    this.skipWhitespace();
    if (this.position !== this.text.length) this.fail('Unexpected trailing content');
    return result;
  }

  private parseValue(): JsonValue {
    this.skipWhitespace();
    const character = this.text[this.position];
    if (character === '{') return this.parseObject();
    if (character === '[') return this.parseArray();
    if (character === '"') return this.parseString();
    if (character === 't') return this.parseLiteral('true', true);
    if (character === 'f') return this.parseLiteral('false', false);
    if (character === 'n') return this.parseLiteral('null', null);
    return this.parseInteger();
  }

  private parseObject(): JsonObject {
    this.position += 1;
    this.skipWhitespace();
    const result = Object.create(null) as JsonObject;
    if (this.text[this.position] === '}') {
      this.position += 1;
      return result;
    }
    while (this.position < this.text.length) {
      this.skipWhitespace();
      if (this.text[this.position] !== '"') this.fail('Object keys must be strings');
      const key = this.parseString();
      if (Object.hasOwn(result, key)) this.fail(`Duplicate object key: ${key}`);
      this.skipWhitespace();
      if (this.text[this.position] !== ':') this.fail('Expected colon after object key');
      this.position += 1;
      result[key] = this.parseValue();
      this.skipWhitespace();
      const separator = this.text[this.position];
      if (separator === '}') {
        this.position += 1;
        return result;
      }
      if (separator !== ',') this.fail('Expected comma or closing brace');
      this.position += 1;
    }
    this.fail('Unterminated object');
  }

  private parseArray(): JsonValue[] {
    this.position += 1;
    this.skipWhitespace();
    const result: JsonValue[] = [];
    if (this.text[this.position] === ']') {
      this.position += 1;
      return result;
    }
    while (this.position < this.text.length) {
      result.push(this.parseValue());
      this.skipWhitespace();
      const separator = this.text[this.position];
      if (separator === ']') {
        this.position += 1;
        return result;
      }
      if (separator !== ',') this.fail('Expected comma or closing bracket');
      this.position += 1;
    }
    this.fail('Unterminated array');
  }

  private parseString(): string {
    const start = this.position;
    this.position += 1;
    while (this.position < this.text.length) {
      const code = this.text.charCodeAt(this.position);
      if (code === 0x22) {
        this.position += 1;
        let value: string;
        try {
          value = JSON.parse(this.text.slice(start, this.position)) as string;
        } catch (error) {
          this.fail(error instanceof Error ? error.message : 'Invalid string escape');
        }
        if (containsLoneSurrogate(value!)) this.fail('Strings cannot contain lone surrogates');
        return value!;
      }
      if (code < 0x20) this.fail('Unescaped control character in string');
      if (code === 0x5c) {
        this.position += 1;
        const escape = this.text[this.position];
        if (escape === 'u') {
          const digits = this.text.slice(this.position + 1, this.position + 5);
          if (!/^[0-9a-fA-F]{4}$/.test(digits)) this.fail('Invalid Unicode escape');
          this.position += 5;
        } else if ('"\\/bfnrt'.includes(escape ?? '')) {
          this.position += 1;
        } else {
          this.fail('Invalid string escape');
        }
      } else {
        this.position += 1;
      }
    }
    this.fail('Unterminated string');
  }

  private parseInteger(): number {
    const start = this.position;
    const match = /^-?(?:0|[1-9][0-9]*)/.exec(this.text.slice(start));
    if (!match) this.fail('Expected a JSON value');
    const raw = match[0];
    this.position += raw.length;
    if (this.text[this.position] === '.' || this.text[this.position] === 'e' || this.text[this.position] === 'E') {
      this.fail('Only integer JSON numbers are supported by the shared contract');
    }
    const value = Number(raw);
    if (!Number.isSafeInteger(value)) this.fail('JSON integers must be within the interoperable safe range');
    return value;
  }

  private parseLiteral<T extends null | boolean>(literal: string, value: T): T {
    if (this.text.slice(this.position, this.position + literal.length) !== literal) this.fail(`Invalid literal`);
    this.position += literal.length;
    return value;
  }

  private skipWhitespace(): void {
    while (this.position < this.text.length && /[\u0020\u0009\u000a\u000d]/.test(this.text[this.position])) {
      this.position += 1;
    }
  }

  private fail(message: string): never {
    throw new OrqivraError(`${this.source}: ${message} at character ${this.position}.`);
  }
}

function containsLoneSurrogate(value: string): boolean {
  for (let index = 0; index < value.length; index += 1) {
    const unit = value.charCodeAt(index);
    if (unit >= 0xd800 && unit <= 0xdbff) {
      const next = value.charCodeAt(index + 1);
      if (!(next >= 0xdc00 && next <= 0xdfff)) return true;
      index += 1;
    } else if (unit >= 0xdc00 && unit <= 0xdfff) {
      return true;
    }
  }
  return false;
}

export function parseJson(text: string, source = '<input>'): JsonValue {
  return new JsonReader(text, source).parse();
}

export function readJson(path: string): JsonValue {
  let text: string;
  try {
    const bytes = readFileSync(path);
    text = new TextDecoder('utf-8', { fatal: true }).decode(bytes);
  } catch (error) {
    if (isNodeError(error) && error.code === 'ENOENT') throw new InputOutputError(`Path does not exist: ${path}`);
    if (isNodeError(error) && error.code && error.code !== 'ERR_ENCODING_INVALID_ENCODED_DATA') {
      throw new InputOutputError(`Could not read file ${path}: ${error.message}`);
    }
    throw new OrqivraError(`Could not read valid UTF-8 JSON from ${path}: ${messageOf(error)}`);
  }
  return parseJson(text, path);
}

export function canonicalJson(value: unknown): string {
  return canonicalValue(value, '$', new Set());
}

function canonicalValue(value: unknown, location: string, ancestors: Set<object>): string {
  if (value === null) return 'null';
  if (value === true) return 'true';
  if (value === false) return 'false';
  if (typeof value === 'string') {
    if (containsLoneSurrogate(value)) throw new TypeError(`Canonical JSON strings cannot contain lone surrogates at ${location}.`);
    return JSON.stringify(value);
  }
  if (typeof value === 'number') {
    if (!Number.isSafeInteger(value)) throw new TypeError(`Canonical JSON numbers must be safe integers at ${location}.`);
    return Object.is(value, -0) ? '0' : String(value);
  }
  if (typeof value !== 'object') throw new TypeError(`Unsupported canonical JSON value at ${location}.`);
  if (ancestors.has(value)) throw new TypeError(`Canonical JSON values cannot contain cycles at ${location}.`);
  ancestors.add(value);
  try {
    if (Array.isArray(value)) {
      return `[${value.map((item, index) => canonicalValue(item, `${location}/${index}`, ancestors)).join(',')}]`;
    }
    const record = value as Record<string, unknown>;
    const keys = Object.keys(record);
    for (const key of keys) {
      if (containsLoneSurrogate(key)) throw new TypeError(`Canonical JSON object keys cannot contain lone surrogates at ${location}.`);
    }
    keys.sort(compareUnicodeScalars);
    return `{${keys.map((key) => `${JSON.stringify(key)}:${canonicalValue(record[key], `${location}/${key}`, ancestors)}`).join(',')}}`;
  } finally {
    ancestors.delete(value);
  }
}

function compareUnicodeScalars(left: string, right: string): number {
  const a = Array.from(left, (character) => character.codePointAt(0)!);
  const b = Array.from(right, (character) => character.codePointAt(0)!);
  const limit = Math.min(a.length, b.length);
  for (let index = 0; index < limit; index += 1) {
    if (a[index] !== b[index]) return a[index] - b[index];
  }
  return a.length - b.length;
}

export function sha256Bytes(bytes: Uint8Array): string {
  return createHash('sha256').update(bytes).digest('hex');
}

export function sha256Json(value: unknown): string {
  return sha256Bytes(Buffer.from(canonicalJson(value), 'utf8'));
}

export function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function isNodeError(error: unknown): error is NodeJS.ErrnoException {
  return error instanceof Error && 'code' in error;
}
