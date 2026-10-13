import { lstatSync, readFileSync, statSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { assetRoot } from './assets.js';
import { InputOutputError, OrqivraError } from './errors.js';
import { JsonObject, JsonValue, parseJson, readJson } from './json.js';
import { isObject, requireValid } from './schema.js';

export const EDITIONS = ['codex', 'claude-code', 'gemini-cli'] as const;
export type Edition = typeof EDITIONS[number];
const ROLE_NAMES = ['orchestrator', 'implementer', 'complex_implementer', 'reviewer'] as const;
type RoleName = typeof ROLE_NAMES[number];
type Reasoning = { control: string; value: string } | null;
const CLIENT_MODEL_TOKEN = /^[A-Za-z0-9][A-Za-z0-9._/-]*$/;
const CLIENT_EFFORT_TOKEN = /^[a-z][a-z0-9-]*$/;
type ModelInfo = {
  provider: string;
  edition: string | null;
  status: string;
  client_support: string;
  reasoning: { control: string; values: string[] | null; default: string | null } | null;
  qualification?: string;
  native_fallback?: string;
};

export type ConfigSource = { kind: 'file' | 'defaults'; path: string | null };
export type EffectiveConfig = {
  schema_version: 1;
  edition: Edition;
  profile_id: string;
  config_source: ConfigSource;
  catalog_version: string;
  workflow: JsonObject;
  fallback: JsonObject;
  roles: Record<RoleName, JsonObject>;
};

const PROVIDER_FOR_EDITION: Record<Edition, string> = {
  codex: 'openai',
  'claude-code': 'anthropic',
  'gemini-cli': 'google',
};

/** Resolve defaults, project configuration, and an edition profile without changing client settings. */
export function resolveConfiguration(edition: string, selectedConfigPath?: string, cwd = process.cwd()): EffectiveConfig {
  if (!isEdition(edition)) throw new OrqivraError(`Unknown edition '${edition}'. Choose codex, claude-code, or gemini-cli.`);
  if (selectedConfigPath === '') throw new OrqivraError('--config requires a non-empty file path.');
  const root = assetRoot();
  const defaults = asObject(readJson(resolve(root, 'defaults', 'config.json')), 'Default configuration');
  requireValid(defaults, 'config.schema.json');
  const profile = asObject(readJson(resolve(root, 'profiles', `${edition}.json`)), `Profile ${edition}`);
  requireValid(profile, 'profile-v2.schema.json');
  const catalog = asObject(readJson(resolve(root, 'models', 'catalog.json')), 'Model catalog');
  requireValid(catalog, 'model-catalog.schema.json');
  if (profile.edition !== edition || !isObject(profile.roles) || typeof catalog.version !== 'string' || !isObject(catalog.models)) {
    throw new OrqivraError(`The ${edition} profile or model catalog is invalid.`);
  }
  if (profile.catalog_version !== catalog.version) {
    throw new OrqivraError(`Profile '${String(profile.id)}' references catalog version '${String(profile.catalog_version)}', but the loaded model catalog is '${catalog.version}'. Rebuild the package or restore matching profile and catalog assets.`);
  }

  const chosenPath = selectedConfigPath === undefined ? resolve(cwd, 'orqivra.config.json') : resolve(selectedConfigPath);
  const loaded = readProjectConfig(chosenPath, selectedConfigPath !== undefined);
  const source: ConfigSource = loaded === null
    ? { kind: 'defaults', path: null }
    : { kind: 'file', path: selectedConfigPath === undefined ? 'orqivra.config.json' : selectedConfigPath };
  const projectConfig = loaded === null ? Object.create(null) as JsonObject : loaded;
  if (loaded !== null) requireValid(projectConfig, 'config.schema.json');
  const effective = asObject(deepMerge(defaults, projectConfig), 'Effective configuration');
  const editionConfig = getEditionConfig(effective, edition);
  const profileRoles = profile.roles;
  const roleResults = Object.create(null) as Record<RoleName, JsonObject>;

  for (const roleName of ROLE_NAMES) {
    const baseValue = profileRoles[roleName];
    if (!isObject(baseValue)) throw new OrqivraError(`Profile role '${roleName}' is invalid.`);
    const overrides = getRoleOverride(editionConfig, roleName);
    roleResults[roleName] = resolveRole(roleName, baseValue, overrides, edition, catalog.models);
  }

  const workflow = Object.assign(Object.create(null), asObject(effective.workflow, 'workflow defaults'), { preferred_parallelism_advisory: true }) as JsonObject;
  const fallback = asObject(effective.fallback, 'fallback defaults');
  return {
    schema_version: 1,
    edition,
    profile_id: String(profile.id),
    config_source: source,
    catalog_version: catalog.version as string,
    workflow,
    fallback,
    roles: roleResults,
  };
}

export function validateProjectConfig(selectedConfigPath?: string, cwd = process.cwd()): JsonObject {
  const effective = EDITIONS.map((edition) => resolveConfiguration(edition, selectedConfigPath, cwd));
  const first = effective[0];
  return {
    valid: true,
    config_source: first.config_source,
    schema_version: 1,
    workflow: first.workflow,
    fallback: first.fallback,
  };
}

export function markdownConfig(config: EffectiveConfig): string {
  const lines = [
    `# ORQIVRA configuration: ${config.edition}`,
    '',
    `- Configuration source: \`${config.config_source.path ?? 'defaults'}\``,
    `- Model catalog: \`${config.catalog_version}\``,
    `- Preferred route: \`${String(config.workflow.preferred_route)}\``,
    `- Preferred parallelism: \`${String(config.workflow.preferred_parallelism)}\` (advisory maximum)`,
    '- Fallback policy: `none` (ORQIVRA policy; client-native routing may still apply)',
    '- Provider calls: none; this output does not change client settings.',
    '',
    '## Roles',
    '',
  ];
  for (const roleName of ROLE_NAMES) {
    const role = config.roles[roleName];
    lines.push(`- \`${roleName}\`: \`${String(role.model)}\` (${String(role.provider)}); reasoning ${JSON.stringify(role.reasoning)} (${String(role.reasoning_resolution)}); documentation \`${String(role.documentation_status)}\`; runtime \`${String(role.runtime_qualification)}\`; ${String(role.client_instructions)}`);
  }
  return lines.join('\n');
}

function readProjectConfig(path: string, explicit: boolean): JsonObject | null {
  try {
    lstatSync(path);
  } catch (error) {
    if (isNodeError(error) && error.code === 'ENOENT') {
      if (explicit) throw new InputOutputError(`The explicitly selected config file does not exist: ${path}. Create it or choose an existing path with --config.`);
      try {
        if (!statSync(dirname(path)).isDirectory()) throw new Error('the parent path is not a directory');
      } catch (parentError) {
        throw new InputOutputError(`Could not inspect the discovered config location ${path}: ${messageOf(parentError)}`);
      }
      return null;
    }
    throw new InputOutputError(`Could not inspect config file ${path}: ${messageOf(error)}`);
  }
  let bytes: Buffer;
  try {
    bytes = readFileSync(path);
  } catch (error) {
    throw new InputOutputError(`Could not read config file ${path}: ${messageOf(error)}`);
  }
  let content: string;
  try { content = new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(bytes); }
  catch (error) { throw new OrqivraError(`Config file is not valid UTF-8: ${path}: ${messageOf(error)}`); }
  if (content.startsWith('\uFEFF')) content = content.slice(1);
  if (content.trim() === '') return Object.create(null) as JsonObject;
  const value = parseJson(content, path);
  if (!isObject(value)) throw new OrqivraError(`${path}: project configuration must be a JSON object.`);
  return value;
}

function resolveRole(
  roleName: RoleName,
  base: JsonObject,
  override: JsonObject,
  edition: Edition,
  rawCatalog: JsonObject,
): JsonObject {
  const expectedProvider = PROVIDER_FOR_EDITION[edition];
  const baseProvider = base.provider;
  if (baseProvider !== expectedProvider || typeof base.model !== 'string' || !isObject(base.reasoning) && base.reasoning !== null) {
    throw new OrqivraError(`The base profile role '${roleName}' is invalid.`);
  }
  const provider = override.provider === null || override.provider === undefined || override.provider === '' ? expectedProvider : override.provider;
  if (provider !== expectedProvider) {
    throw new OrqivraError(`editions.${edition}.roles.${roleName}.provider must be "${expectedProvider}" for this edition. Set provider to "${expectedProvider}" or omit it to inherit the edition provider.`);
  }
  const modelValue = override.model;
  const model = typeof modelValue === 'string' && modelValue !== '' ? modelValue : String(base.model);
  const modelChanged = model !== base.model;
  const catalogValue = rawCatalog[model];
  let modelSource: 'catalog' | 'user-supplied';
  let modelInfo: ModelInfo | undefined;
  if (isObject(catalogValue)) {
    if (override.model_source === 'user-supplied') {
      throw new OrqivraError(`editions.${edition}.roles.${roleName}.model_source cannot mark a catalog model as user-supplied.`);
    }
    modelSource = 'catalog';
    modelInfo = catalogValue as ModelInfo;
    if (modelInfo.provider !== expectedProvider || modelInfo.edition !== edition) {
      throw new OrqivraError(`editions.${edition}.roles.${roleName}.model is not available for provider ${expectedProvider} in this edition.`);
    }
  } else {
    if (override.model_source !== 'user-supplied') {
      throw new OrqivraError(`The selected model is not in the catalog at editions.${edition}.roles.${roleName}.model. Add model_source: "user-supplied" to mark it as custom; its compatibility will be UNVERIFIED.`);
    }
    modelSource = 'user-supplied';
  }

  let reasoning: Reasoning;
  let reasoningResolution: 'profile' | 'configuration' | 'client-default';
  let reasoningCompatibility: string;
  if (Object.hasOwn(override, 'reasoning')) {
    const value = override.reasoning;
    if (value === null) {
      reasoning = null;
      reasoningResolution = 'client-default';
      reasoningCompatibility = 'client-default';
    }
    else if (isObject(value) && typeof value.control === 'string' && typeof value.value === 'string') {
      reasoning = { control: value.control, value: value.value };
      validateExplicitReasoning(reasoning, modelInfo, edition, roleName, modelSource);
      reasoningResolution = 'configuration';
      reasoningCompatibility = modelSource === 'user-supplied'
        ? 'UNVERIFIED custom model'
        : knownCompatibility(reasoning, modelInfo)
          ? 'catalog-compatible'
          : 'UNVERIFIED; catalog does not enumerate compatible values';
    } else {
      throw new OrqivraError(`editions.${edition}.roles.${roleName}.reasoning must be null or an object with control and value.`);
    }
  } else {
    const baseReasoning = base.reasoning;
    if (baseReasoning === null) {
      reasoning = null;
      reasoningResolution = 'client-default';
      reasoningCompatibility = 'client-default';
    } else {
      if (!isObject(baseReasoning) || typeof baseReasoning.control !== 'string' || typeof baseReasoning.value !== 'string') {
        throw new OrqivraError(`The base profile reasoning setting for '${roleName}' is invalid.`);
      }
      reasoning = { control: baseReasoning.control, value: baseReasoning.value };
      reasoningResolution = 'profile';
      if (modelInfo?.reasoning === null) {
        throw new OrqivraError(`Inherited reasoning at editions.${edition}.roles.${roleName}.reasoning is unsupported by the selected model. Set reasoning: null to use the client default or select a model with this control.`);
      }
      if (modelInfo?.reasoning && (modelInfo.reasoning.control !== reasoning.control
        || Array.isArray(modelInfo.reasoning.values) && !modelInfo.reasoning.values.includes(reasoning.value))) {
        throw new OrqivraError(`Inherited reasoning at editions.${edition}.roles.${roleName}.reasoning is incompatible with the selected model. Set reasoning: null to use the client default or choose a documented compatible value.`);
      }
      if (modelChanged) {
        if (!modelInfo || !knownCompatibility(reasoning, modelInfo)) {
          throw new OrqivraError(`Inherited reasoning at editions.${edition}.roles.${roleName}.reasoning cannot be confirmed for the changed model. Set reasoning: null to use the client default, choose a documented compatible value, or select a supported model.`);
        }
      }
      reasoningCompatibility = modelSource === 'user-supplied'
        ? 'UNVERIFIED custom model'
        : knownCompatibility(reasoning, modelInfo)
          ? 'catalog-compatible'
          : 'UNVERIFIED; catalog does not enumerate compatible values';
    }
  }

  const qualification = typeof base.qualification === 'string' ? base.qualification : 'Runtime qualification has not been performed.';
  const runtimeQualification = modelSource === 'user-supplied' ? 'UNVERIFIED' : 'NOT_RUN';
  const clientInstructionItems: string[] = [];
  if (modelInfo?.client_support) clientInstructionItems.push(modelInfo.client_support);
  clientInstructionItems.push(clientApplicationGuidance(edition, model, reasoning, modelSource, modelInfo !== undefined));
  if (modelSource === 'user-supplied') clientInstructionItems.push('Custom model compatibility is UNVERIFIED.');
  if (reasoningCompatibility.startsWith('UNVERIFIED')) clientInstructionItems.push(reasoningCompatibility);
  if (modelInfo?.native_fallback) clientInstructionItems.push(modelInfo.native_fallback);
  if (clientInstructionItems.length === 0) clientInstructionItems.push(qualification);
  const clientInstructions = clientInstructionItems.join('; ');
  const result: JsonObject = {
    provider: expectedProvider,
    model,
    model_source: modelSource,
    reasoning,
    reasoning_resolution: reasoningResolution,
    documentation_status: modelInfo?.status ?? 'user-supplied',
    runtime_qualification: runtimeQualification,
    activatable: false,
    client_instructions: clientInstructions,
  };
  return result;
}

function clientApplicationGuidance(
  edition: Edition,
  model: string,
  reasoning: Reasoning,
  modelSource: 'catalog' | 'user-supplied',
  catalogModel: boolean,
): string {
  let selection: string;
  if (modelSource === 'user-supplied' || !catalogModel || !CLIENT_MODEL_TOKEN.test(model)) {
    selection = "Use the native client model picker or your provider's documented custom-model setup. ORQIVRA does not insert custom identifiers into executable commands; compatibility and availability are UNVERIFIED.";
  } else if (edition === 'codex') {
    let command = `codex --model ${model}`;
    if (reasoning && reasoning.control === 'codex.model_reasoning_effort' && CLIENT_EFFORT_TOKEN.test(reasoning.value)) {
      command += ` --config 'model_reasoning_effort=\"${reasoning.value}\"'`;
    }
    selection = `Main session: run \`${command}\`. Codex effort uses \`model_reasoning_effort\` when the selected model supports it. Codex subagents use separate \`[agents]\` settings; ORQIVRA does not map its role preferences into those settings. Documentation: https://developers.openai.com/codex/config-advanced.`;
  } else if (edition === 'claude-code') {
    let command = `claude --model ${model}`;
    let effortNote = 'The client default effort applies. ';
    if (reasoning && reasoning.control === 'claude-code.effort' && CLIENT_EFFORT_TOKEN.test(reasoning.value)) {
      command += ` --effort ${reasoning.value}`;
      effortNote = '';
    }
    selection = `Main session: run \`${command}\`. ${effortNote}Subagents need their own model and effort settings; ORQIVRA does not apply this role preference automatically. Documentation: https://code.claude.com/docs/en/model-config.`;
  } else {
    const selectionAction = model === 'auto'
      ? 'run `gemini --model auto` or start `gemini` and use `/model` to choose Auto'
      : `run \`gemini --model ${model}\` or start \`gemini\` and use \`/model\` to select Manual`;
    selection = `Main session: ${selectionAction}. The model selector does not set subagent models; ORQIVRA role preferences remain advisory. Gemini CLI controls routing and fallback. This edition has no ORQIVRA reasoning-effort override. Documentation: https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/model.md and https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/model-routing.md.`;
    if (model === 'gemini-3.1-pro-preview') selection += ' Preview model availability depends on account rollout and access.';
  }
  return `${selection} This instruction applies only to the main session. Multiple ORQIVRA role preferences are advisory; one launch command does not enforce every role.`;
}

function validateExplicitReasoning(reasoning: Exclude<Reasoning, null>, modelInfo: ModelInfo | undefined, edition: Edition, role: RoleName, modelSource: string): void {
  const path = `editions.${edition}.roles.${role}.reasoning`;
  const expectedControl = modelInfo?.reasoning?.control ?? (edition === 'codex' ? 'codex.model_reasoning_effort' : edition === 'claude-code' ? 'claude-code.effort' : null);
  if (expectedControl === null || reasoning.control !== expectedControl) {
    throw new OrqivraError(`${path}.control is incompatible with ${edition}; choose ${expectedControl ?? 'the client-native default'} or set reasoning: null.`);
  }
  if (modelSource === 'catalog' && modelInfo?.reasoning?.values && !modelInfo.reasoning.values.includes(reasoning.value)) {
    throw new OrqivraError(`${path}.value is unsupported by the selected model. Choose one of: ${modelInfo.reasoning.values.join(', ')}, or set reasoning: null.`);
  }
}

function knownCompatibility(reasoning: Exclude<Reasoning, null>, model: ModelInfo | undefined): boolean {
  return model !== undefined && model.reasoning !== null && model.reasoning.control === reasoning.control
    && Array.isArray(model.reasoning.values) && model.reasoning.values.includes(reasoning.value);
}

function getEditionConfig(config: JsonObject, edition: Edition): JsonObject {
  if (!isObject(config.editions)) return Object.create(null) as JsonObject;
  const value = config.editions[edition];
  return value === undefined ? Object.create(null) as JsonObject : asObject(value, `editions.${edition}`);
}

function getRoleOverride(editionConfig: JsonObject, role: RoleName): JsonObject {
  if (!isObject(editionConfig.roles)) return Object.create(null) as JsonObject;
  const value = editionConfig.roles[role];
  return value === undefined ? Object.create(null) as JsonObject : asObject(value, `roles.${role}`);
}

function deepMerge(base: JsonValue, override: JsonValue): JsonValue {
  if (!isObject(base) || !isObject(override)) return clone(override);
  const result = clone(base) as JsonObject;
  for (const [key, value] of Object.entries(override)) {
    result[key] = Object.hasOwn(base, key) ? deepMerge(base[key], value) : clone(value);
  }
  return result;
}

function clone<T extends JsonValue>(value: T): T {
  if (Array.isArray(value)) return value.map((item) => clone(item)) as T;
  if (isObject(value)) {
    const result = Object.create(null) as JsonObject;
    for (const [key, item] of Object.entries(value)) result[key] = clone(item);
    return result as T;
  }
  return value;
}

function asObject(value: JsonValue | undefined, label: string): JsonObject {
  if (!isObject(value)) throw new OrqivraError(`${label} must be a JSON object.`);
  return value;
}

function isEdition(value: string): value is Edition {
  return (EDITIONS as readonly string[]).includes(value);
}

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function isNodeError(error: unknown): error is NodeJS.ErrnoException {
  return error instanceof Error && 'code' in error;
}
