# CLI Contract

The public command is `orqivra`. It is available from the npm distribution and the Python distribution; Python also supports `python -m orqivra.cli`. Node.js 24 or newer is required for npm. Python 3.11 or newer is required for pipx. Each implementation provides the commands below without invoking the other runtime. JSON is used for machine-readable project, DAG, profile, state, and evidence files.

Shared JSON is strict: duplicate keys, fractions, non-finite values, integers outside the safe interoperable range, and lone surrogates are rejected. Configuration files may begin with exactly one UTF-8 BOM; a second or misplaced BOM remains invalid JSON. Configuration diagnostics identify the schema path, safe constraint, and recovery action without echoing supplied values or arbitrary property names. Canonical serialization recursively sorts object keys by Unicode scalar value, preserves array order, emits compact UTF-8 JSON without a BOM, and hashes those bytes with SHA-256. The Python and Node implementations share golden serialization and hash fixtures.

## Commands

```text
orqivra validate project PATH
orqivra validate dag PATH [--project PATH]
orqivra validate profile PATH
orqivra validate skills PATH
orqivra config validate [--config PATH]
orqivra config show --edition codex|claude-code|gemini-cli [--config PATH] [--format json|markdown]
orqivra plan DAG [--state PATH]
orqivra state init DAG --state PATH [--project-root DIR]
orqivra state transition --state PATH NODE --to STATUS --reason TEXT
orqivra attempt begin --state PATH NODE --hypothesis TEXT
orqivra attempt diagnose --state PATH NODE --attempt N --diagnosis TEXT
orqivra attempt record-change --state PATH NODE --attempt N --summary TEXT
orqivra attempt verify --state PATH NODE --attempt N --result pass|fail --summary TEXT
orqivra evidence add --state PATH NODE --command TEXT --exit-code INTEGER [--artifact PATH ...]
orqivra evidence check --state PATH
orqivra resume --dag PATH --state PATH [--project-root DIR]
orqivra report --state PATH [--format json|markdown]
orqivra build --edition codex|claude-code|gemini-cli|all --output DIR
orqivra install --edition EDITION --target DIR [--skill NAME ...] [--dry-run|--apply]
orqivra verify-install --target DIR
orqivra uninstall --target DIR [--dry-run|--apply]
```

Both implementations accept the same command names, JSON formats, installation manifests, and documented exit codes. Python validates against Draft 2020-12 through `jsonschema`; Node deliberately supports a smaller subset and rejects unknown schema keywords rather than silently ignoring them. Node supports `$defs`, `$id`, `$ref`, `$schema`, `additionalProperties`, `const`, `description`, `enum`, `format`, `items`, `maxItems`, `maxLength`, `maximum`, `minItems`, `minLength`, `minProperties`, `minimum`, `not`, `pattern`, `properties`, `required`, `title`, `type`, and `uniqueItems`. `format` supports only `date-time`; `items` requires an object schema. This is not full Draft 2020-12 validation. A profile describes a logical role; it does not select the parent model or grant permissions.

## Project configuration and effective profiles

Configuration is optional. When `--config` is omitted, the CLI discovers `orqivra.config.json` only in the current working directory. If that automatically discovered path does not exist, built-in defaults apply. When `--config PATH` is explicitly supplied, that exact file is required; a missing file produces an actionable I/O error and does not fall back to defaults. An existing empty or whitespace-only file and `{}` both inherit defaults. Invalid JSON, duplicate keys, unreadable paths, or invalid values are errors; they are never treated as an absent configuration.

Configuration is schema version 1. Objects merge recursively over the selected edition profile and shared defaults; arrays replace as a whole. Omitted values inherit. The default workflow route is `recommend`, and the default `preferred_parallelism` is 2. This is only an advisory maximum: actual concurrency is bounded by available runtime capability, dependency readiness, authorization, task independence, resources, and non-overlapping ownership. `fallback.policy` is `none` for ORQIVRA-level fallback; client-native routing behavior may still apply.

The `config show` command resolves these inputs without contacting a provider, switching a running client, editing client settings, granting permissions, or starting workers. JSON and Markdown output identify the edition/profile and catalog version, whether configuration came from defaults or a file, workflow preferences, each role's effective model and reasoning, documentation and runtime qualification, activatability, and client instructions. Invalid configuration errors expose stable JSON paths and safe constraints; they do not include supplied scalar, object, array, or unknown-key values. `config validate` checks the discovered or explicitly selected configuration against the schema and edition profile.

Client instructions apply the resolved model and reasoning to a new main client session only. Codex guidance uses `codex --model MODEL` and, when a role has a safe supported effort value, `--config 'model_reasoning_effort="VALUE"'`; Codex agent settings are separate. Claude Code guidance uses `claude --model MODEL` and adds `--effort VALUE` only for an explicit role setting; otherwise the client default applies. Subagents need their own model and effort preferences. Gemini CLI guidance uses `gemini --model auto` or `gemini --model MODEL`, or directs users to `/model`; model selection does not set Gemini subagent models, and its native routing and fallback remain client-controlled. The current Gemini edition does not define an ORQIVRA effort override. These command forms are grounded in the [Codex configuration guide](https://developers.openai.com/codex/config-advanced), [Claude Code CLI reference](https://code.claude.com/docs/en/cli-usage) and [model configuration guide](https://code.claude.com/docs/en/model-config), and [Gemini CLI model selection](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/model.md) and [routing documentation](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/model-routing.md). A preview model may require eligible account access. ORQIVRA role preferences are advisory: one launch command does not enforce every role, and editing ORQIVRA configuration does not change an existing client session. Custom model identifiers remain `UNVERIFIED`; ORQIVRA directs users to the native picker or provider's documented setup and never interpolates those identifiers into executable guidance.

For a role, omitted, `null`, or empty-string `provider` and `model` values inherit the edition's expected provider and base profile model. A non-empty value is an explicit override. An omitted `reasoning` keeps the base profile preference when the model is unchanged; if the catalog does not enumerate compatible values, the setting is returned as `UNVERIFIED`. After a model change, inherited reasoning carries only when catalog data establishes compatibility. An incompatible or unverified inherited value then produces an actionable error instead of silently carrying over; select a documented compatible value or set `reasoning` to `null`.

An explicit reasoning object must have a non-empty string value and use the provider's native control. When the catalog enumerates the selected model's supported values, values outside that list are rejected. When values are not enumerated, the setting is accepted structurally and reported as `UNVERIFIED`; acceptance does not mean that the model or client supports it. The current Codex catalog entries do not enumerate values, so explicit Codex reasoning values are not described as catalog-compatible. An explicit incompatible value is an actionable error.

`reasoning: null` clears the inherited role-level preference and defers to the selected model's documented client default when known, otherwise to the client-native default. It does not promise a particular effective effort. A custom model identifier must be accompanied by `model_source: "user-supplied"`. Its compatibility and activation are reported as unverified. Validate its provider control and value structurally, but do not infer that the client supports that control for the custom model. Catalog model changes require `model_source: "catalog"` or the matching source declared by the catalog.

The model catalog is advisory and records vendor documentation, access qualifications, and client-native behavior. Claude Code may use a client-owned fallback for certain flagged safety or availability cases. Gemini CLI owns dynamic routing and can silently fall back for some internal utility calls. These behaviors can occur even when ORQIVRA's fallback policy is `none`; ORQIVRA does not control or disable them.

`plan` validates missing dependencies, cycles, and ownership conflicts and returns a stable lexical READY frontier. `state transition` rejects illegal edges and unmet prerequisites. Transitioning a node to `obsolete` invalidates its dependent subtree and queues it for `resume`; active attempts are marked interrupted and require diagnosis after resume. Acceptance also rechecks the relevant input and active evidence artifact hashes; changed inputs or artifacts require `evidence check` and recovery before acceptance. `attempt begin` increments once before work starts and enforces the five-attempt ceiling. `evidence add` hashes artifacts but never runs the recorded command. Evidence records are append-ordered; the latest record is active, and earlier records remain historical. `evidence check` finds changed inputs or active artifacts and invalidates dependent acceptance. `resume` recalculates only affected nodes and preserves counters. `report` is read-only: it checks current input and active artifact hashes, lists changed inputs, stale active evidence, superseded stale history, and accepted nodes without current successful evidence. It never certifies changed inputs, stale active evidence, or accepted nodes without current successful evidence.

Mutations require an existing state path or an explicit `state init`. Every mutation uses a state version check and atomic replacement under an exclusive lock. On conflict, the command fails without overwriting. The `--target` argument to install or uninstall is mandatory and is the exact installation root; commands never infer a home directory or edit global client instructions. Both commands default to dry-run. Pass `--apply` to perform the reviewed operation. A manifest records every owned relative path and SHA-256 digest. Verification and uninstall refuse missing, modified, or unsafe entries.

The CLI uses exit code 0 for success, 2 for invalid data or illegal state, 3 for a concurrent version conflict, and 4 for I/O or unsafe-path errors. Diagnostics are English. No command accepts a shell command to execute. Both distributions are local release artifacts until a public package version has actually been published.
