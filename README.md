# ORQIVRA

ORQIVRA is a local, provider-independent engineering framework for AI agents. It packages shared contracts, JSON Schemas, a deterministic Python CLI, and separate skills for Codex, Claude Code, and Gemini CLI. Its four capabilities are `orqivra-orchestrate`, `orqivra-architecture`, `orqivra-verify`, and `orqivra-recover`.

The CLI tracks a project DAG, READY frontier, state transitions, bounded attempts, evidence hashes, recovery, reports, and selective skill installation. It supports work during a session; it is not an autonomous scheduler. A hash identifies bytes and does not establish that a result is correct.

## Quick start

Requires Python 3.11 or newer.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
orqivra --help
```

On Unix, activate with `source .venv/bin/activate`. The runtime uses `jsonschema` for JSON Schema validation and PyYAML's safe loader for skill frontmatter. Both are declared project dependencies.

Validate a fixture and inspect its deterministic READY frontier:

```text
orqivra validate dag examples/solo-change.json
orqivra plan examples/independent-branches.json
```

See [examples/README.md](examples/README.md) for disposable state workflows.

## Install an edition

The installation target is the exact client skills directory. Install defaults to a dry run; inspect the listed files, then pass `--apply` to write them.

```text
orqivra install --edition codex --target .agents/skills --skill orqivra-orchestrate
orqivra install --edition codex --target .agents/skills --skill orqivra-orchestrate --apply
orqivra verify-install --target .agents/skills
orqivra uninstall --target .agents/skills
orqivra uninstall --target .agents/skills --apply
```

Use `.claude/skills` for Claude Code and `.gemini/skills` for Gemini CLI. The Codex edition follows the documented `.agents/skills` path. The installer writes only selected skill files and its ownership manifest. It does not edit global client instructions or infer a home directory. Installation, verification, and uninstall refuse unsafe paths and modified owned files.

Create a deterministic bundle containing the selected edition's self-contained skills, profile, shared contract, and schemas:

```text
orqivra build --edition all --output dist/orqivra-v0.1.0
```

The CLI package is independently installable with pip. Client skills carry their own complete instructions and do not load the source repository at use time.

## Editions and qualification

The editions share acceptance contracts and adapt discovery, invocation, and permission guidance to each client. Codex discovers repository skills under `.agents/skills`; Claude Code uses `.claude/skills`; Gemini CLI supports `.gemini/skills` and the interoperable `.agents/skills` alias. See [compatibility notes](docs/compatibility.md).

The Codex profile is the requested Astra Advisor configuration: `gpt-6-astra`/high, `gpt-6-luna`/max, and `gpt-6-sol`/xhigh and high. These values are recorded as unvalidated and non-activatable until verified in the target runtime. Claude and Gemini profiles are unresolved, user-supplied examples and are not activatable. A profile documents a logical role; it cannot change the active parent model or grant permissions.

This environment exposed Codex but not Claude Code or Gemini CLI. Static format checks do not establish runtime compatibility. See the release report for actual checks.

## Security and scope

The CLI never executes command text from a DAG, skill, or evidence record. It refuses path traversal and symlink or junction traversal under explicit project and installation roots. State writes use an exclusive lock, versioned events, and atomic replacement. Install and uninstall are scoped to a manifest of ORQIVRA-owned files.

The generic adapter does not inherit MIP-only rules. The optional MIP adapter keeps external applications and infrastructure as `DEFERRED_EXTERNAL` until observed in the final validation sprint. A mock does not close such an obligation.

ORQIVRA v0.1 excludes autonomous scheduling, UI/dashboard, cloud orchestration, cross-provider account routing, issue tracker integration, API billing, model downloads, and production deployment.

## Development

```text
python -m unittest discover -s tests -v
python -m orqivra.cli --help
```

See [CONTRIBUTING.md](CONTRIBUTING.md), [the change log](CHANGELOG.md), and the [release report](docs/release-report.md). Original framework code is licensed under MIT. Check third-party licenses before adding components.
