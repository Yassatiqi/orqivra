import assert from 'node:assert/strict';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import { resolveConfiguration } from '../../dist/core/config.js';

function resolveWithConfig(edition, config, context) {
  const directory = mkdtempSync(join(tmpdir(), 'orqivra-config-guidance-'));
  context.after(() => rmSync(directory, { recursive: true, force: true }));
  const path = join(directory, 'orqivra.config.json');
  writeFileSync(path, JSON.stringify(config), 'utf8');
  return resolveConfiguration(edition, path);
}

test('Codex guidance names the main-session model and supported effort option', () => {
  const instructions = resolveConfiguration('codex').roles.implementer.client_instructions;
  assert.match(instructions, /codex --model gpt-6-luna/);
  assert.match(instructions, /model_reasoning_effort="max"/);
  assert.match(instructions, /main session/i);
  assert.match(instructions, /separate `\[agents\]` settings/);
  assert.match(instructions, /Multiple ORQIVRA role preferences are advisory/);
});

test('Claude guidance names the main-session model and explicit effort option', (context) => {
  const config = {
    editions: {
      'claude-code': {
        roles: {
          implementer: { reasoning: { control: 'claude-code.effort', value: 'high' } },
        },
      },
    },
  };
  const instructions = resolveWithConfig('claude-code', config, context).roles.implementer.client_instructions;
  assert.match(instructions, /claude --model claude-sonnet-5-5 --effort high/);
  assert.match(instructions, /Subagents need their own model and effort settings/);
  assert.match(instructions, /Multiple ORQIVRA role preferences are advisory/);
});

test('Gemini guidance covers Auto, preview access, subagents, and native routing', () => {
  const roles = resolveConfiguration('gemini-cli').roles;
  assert.match(roles.implementer.client_instructions, /gemini --model auto/);
  assert.match(roles.implementer.client_instructions, /choose Auto/);
  assert.match(roles.implementer.client_instructions, /does not set subagent models/);
  assert.match(roles.implementer.client_instructions, /advisory/);
  assert.match(roles.complex_implementer.client_instructions, /gemini --model gemini-3\.1-pro-preview/);
  assert.match(roles.complex_implementer.client_instructions, /Preview model availability depends on account rollout and access/);
  assert.match(roles.complex_implementer.client_instructions, /model-routing\.md/);
  assert.match(roles.complex_implementer.client_instructions, /no ORQIVRA reasoning-effort override/);
});

test('custom model identifiers are not inserted into executable commands', (context) => {
  const identifier = 'custom-model;$(echo AUDIT_SENTINEL)';
  const config = {
    editions: {
      'claude-code': {
        roles: { implementer: { model: identifier, model_source: 'user-supplied' } },
      },
    },
  };
  const role = resolveWithConfig('claude-code', config, context).roles.implementer;
  assert.equal(role.runtime_qualification, 'UNVERIFIED');
  assert.match(role.client_instructions, /compatibility and availability are UNVERIFIED/);
  assert.equal(role.client_instructions.includes(identifier), false);
  assert.doesNotMatch(role.client_instructions, /claude --model/);
});
