# Compatibility and Qualification

## Declared support

| Component | Declared minimum | Independent runtime |
|---|---:|---|
| Python CLI | Python 3.11 | Does not require Node.js |
| npm CLI | Node.js 24 | Does not require Python |
| Codex edition | `.agents/skills/` | Client discovery and activation must be tested in Codex |
| Claude Code edition | `.claude/skills/` | Client discovery and activation must be tested in Claude Code |
| Gemini CLI edition | `.gemini/skills/` or `.agents/skills/` | Client discovery and activation must be tested in Gemini CLI |

## Local qualification for v0.2.0

The local results below apply only to the named runtime versions and artifacts. Full commands, inventories, and SHA-256 values are preserved in ignored `scratch/prepublication-audit/reports/`. A configured CI workflow is `NOT_RUN` until GitHub Actions actually runs it. Static adapter validation and generated skill files do not qualify a client runtime.

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
