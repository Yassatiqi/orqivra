# Compatibility and Qualification

## Declared support

| Component | Declared minimum | Independent runtime |
|---|---:|---|
| Python CLI | Python 3.11 | Does not require Node.js |
| npm CLI | Node.js 24 | Does not require Python |
| Codex edition | `.agents/skills/` | Client discovery and activation must be tested in Codex |
| Claude Code edition | `.claude/skills/` | Client discovery and activation must be tested in Claude Code |
| Gemini CLI edition | `.gemini/skills/` or `.agents/skills/` | Client discovery and activation must be tested in Gemini CLI |

## Configuration and model profiles

The default profile mapping is advisory and does not activate a model or configure a client:

| Edition | Routine roles | Complex-work role | Qualification note |
|---|---|---|---|
| Codex | `gpt-6-astra`, `gpt-6-luna` | `gpt-6-sol` | Existing four Codex profile model/reasoning pairs are preserved. Model effort availability can vary by model and client; activation is unqualified. |
| Claude Code | `claude-sonnet-5-5` | `claude-opus-5-5` | Models require a recent Claude Code client and account access. The profile defers effort to the client; current Sonnet 5.5 documentation differs on its default effort. |
| Gemini CLI | `auto` | `gemini-3.1-pro-preview` | `auto` lets Gemini CLI choose the backend. The preview model is conditional on client rollout and account access. |

The preserved Codex role settings are `orchestrator: gpt-6-astra/high`, `implementer: gpt-6-luna/max`, `complex_implementer: gpt-6-sol/xhigh`, and `reviewer: gpt-6-sol/high` (`codex.model_reasoning_effort`). The Codex catalog currently does not enumerate supported reasoning values. These settings and explicit non-empty Codex values using the native control are structurally accepted and displayed as `UNVERIFIED`; they are not claimed as documented model compatibility. Actual model/client compatibility remains unqualified until exercised in the intended Codex client.

The versioned catalog at `models/catalog.json` records its source documents and qualification notes. Current documentation lists Claude Sonnet 5.5 for Claude Code 2.1.284+ and Opus 5.5 for 2.1.280+; Fable 5.1 is an explicit opt-in for 2.1.257+ and is not a default. Account eligibility and actual activation remain unqualified. Claude Code may invoke its own fallback for some flagged safety or availability cases. ORQIVRA cannot disable that client behavior. Gemini CLI owns dynamic model routing and may silently fall back for internal utility requests. Those client-owned behaviors can occur with ORQIVRA's `fallback.policy` set to `none`.

`gemini-3.8-flash` is documented as a stable Gemini API model. Gemini CLI support is unresolved; do not treat API documentation as evidence of CLI support or select it as a CLI default. The Gemini complex-work candidate is `gemini-3.1-pro-preview`, whose direct invocation and Manual selector are documented for eligible accounts, but preview access is conditional and activation has not been observed.

The catalog links to the [Codex model documentation](https://developers.openai.com/codex/models) and [Codex configuration reference](https://developers.openai.com/codex/config-reference), [Claude Code model configuration](https://code.claude.com/docs/en/model-config) and [Claude model overview](https://platform.claude.com/docs/en/models/overview), [Gemini CLI's Gemini 3 guide](https://github.com/google-gemini/gemini-cli/blob/main/docs/get-started/gemini-3.md), [Gemini CLI model routing](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/model-routing.md), and the [Gemini API model catalog](https://ai.google.dev/gemini-api/docs/models). These source links establish documentation status, not local client qualification.

Project configuration changes are validated against the selected model. Omitted, `null`, or empty-string provider/model values inherit the edition provider and base profile model. If reasoning is omitted and the model is unchanged, its base profile value remains; when the catalog does not enumerate values, the result is `UNVERIFIED`. After a model change, reasoning is inherited only when catalog data establishes compatibility; an incompatible or unknown inherited value must be corrected explicitly. Set `reasoning` to `null` to clear a prior preference and defer to the client's documented default where known, otherwise its native default. Explicit reasoning uses the provider control; enumerated catalog values are checked, while values absent from the catalog are accepted structurally and shown as unverified. A custom model ID requires `model_source: "user-supplied"` and cannot be assumed to support catalog-specific reasoning controls. See [the configuration contract](cli-contract.md#project-configuration-and-effective-profiles) for merge and file-discovery rules.

## v0.3.0 pre-release qualification gates

The v0.3.0 source is a pre-release candidate. Documentation, schemas, or local artifacts do not substitute for execution in the named environment. At this stage, keep these states unresolved until the corresponding evidence exists:

| Gate | Current state | Evidence needed |
|---|---|---|
| Python 3.11 Windows junction protection | `UNRESOLVED` | Execute the required real junction regressions on Python 3.11 for Windows; Python 3.13 or mocked paths do not qualify it. |
| Codex client activation | `NOT_RUN` | Observe discovery and activation in the supported Codex client. |
| Claude Code client activation | `NOT_RUN` | Observe discovery and activation in a supported client version/account. |
| Gemini CLI activation and preview access | `NOT_RUN` | Observe discovery plus model access in an eligible client/account; preview access can vary. |
| Gemini CLI support for `gemini-3.8-flash` | `UNRESOLVED` | Supported CLI documentation or actual CLI execution must establish support. |
| GitHub Actions | `NOT_RUN` | Observe a real workflow run and its result; checked-in CI configuration is not a pass. |
| npm/PyPI name ownership and publisher access | `NOT_RUN` | Verify the exact package names and publishing account eligibility on each registry. |
| Private vulnerability reporting | `UNRESOLVED` external checklist item | Verify the repository's private reporting route or provide an approved, verified private contact. No maintainer address or enabled setting is assumed. |

Local test, package, and artifact results for this candidate must be recorded separately in its ignored `scratch/` report. Do not describe this pre-release as fully qualified or publication-ready.

## Historical local qualification for v0.2.0

The results below are preserved historical evidence for the named v0.2.0 runtime versions and artifacts; they do not qualify v0.3.0. Full commands, inventories, and SHA-256 values remain in ignored `scratch/prepublication-audit/reports/`. A configured CI workflow is `NOT_RUN` until GitHub Actions actually runs it. Static adapter validation and generated skill files do not qualify a client runtime.

| Check | Result | Limit |
|---|---|---|
| Python suite | `PASS`: 48 tests on Python 3.13.2; 46 passed and 2 symlink tests skipped because Windows denied symlink creation | Real Windows junction tests executed, including explicit-root relocation. Python 3.11 qualification remains `UNRESOLVED`; Python 3.13 does not qualify 3.11. |
| Node suite | `PASS`: 23 tests on Node.js 24.20.0 | Applies to this Node version and package snapshot. |
| Shared Python/Node parity | `PASS`: 22 checks, 0 skipped | Includes state handoff, install/uninstall interoperability, Unicode, directory inputs, and real Windows junction root replacement. |
| npm artifact install | `PASS` outside the checkout with Python absent from `PATH` | Rebuilt local tarball smoke check; registry ownership and publication eligibility were not tested. |
| Python wheel install | `PASS` outside the checkout in a fresh venv with Node absent from `PATH` | Rebuilt local wheel smoke check. `pipx` is unavailable in this environment; this does not qualify Python 3.11. |
| Codex skill activation | `NOT_RUN` | Presence of the Codex app or CLI is not evidence that these skills activated. |
| Claude Code skill activation | `NOT_RUN` | An unavailable command is not a pass. |
| Gemini CLI skill activation | `NOT_RUN` | An unavailable command is not a pass. |
| GitHub Actions | `NOT_OBSERVED` | The source push succeeded, but the Actions run status was not accessible through the available GitHub interfaces. A configured or queued workflow is not a pass. |
| GitHub private vulnerability reporting | External checklist item | No setting change or private-reporting claim is made. |
| npm and PyPI live registry access | `UNAVAILABLE` | Read-only requests could not connect from this environment; account eligibility remains unchecked. |

See [client qualification](client-qualification.md) for the repeatable procedure and [release checklist](releasing.md) for external publication gates.
