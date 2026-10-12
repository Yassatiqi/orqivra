# ORQIVRA

ORQIVRA makes engineering work easier to scope, resume, and verify. Its local CLI records a user-authored task DAG, file ownership, bounded attempts, evidence, and recovery state. It does not schedule work outside the current session.

The four capabilities are:

- **Orchestrate** (`orqivra-orchestrate`) work as solo, delegated, audit, or full-review tasks, with explicit ownership and integration.
- **Architecture** (`orqivra-architecture`) define concise boundaries, inputs, outputs, and invariants before implementation.
- **Verify** (`orqivra-verify`) check behavior and artifacts against acceptance criteria and current evidence.
- **Recover** (`orqivra-recover`) diagnose a failed or interrupted attempt and reopen only affected dependent work.

The same full CLI is available as a Node.js package and a Python package. Neither implementation invokes the other runtime.

## Choose a CLI

Use one distribution so the `orqivra` command resolves to one installation.

| Distribution | Runtime | Local v0.2.0 artifact |
|---|---|---|
| npm | Node.js 24 or newer | `npm install --global /path/to/orqivra-0.2.0.tgz` |
| pipx | Python 3.11 or newer | `pipx install /path/to/orqivra-0.2.0-py3-none-any.whl` |

These commands install a local release artifact. The v0.2.0 task does not publish to npm or PyPI. See [installation](docs/installation.md) for building local artifacts, installing from a source checkout, and commands to use only after publication.

If both distributions are present, check which executable your shell will run:

```powershell
Get-Command orqivra -All
```

```sh
command -v orqivra
```

## Try a workflow

From a source checkout, validate a sample DAG and inspect its deterministic READY frontier:

```text
orqivra validate dag examples/solo-change.json
orqivra plan examples/independent-branches.json
```

For a real task, copy a sample DAG, replace its inputs and file scopes with the files in your project, initialize state with an explicit project root, and record each observed check as evidence. Do not accept a node while its active evidence is stale. The [correction and interruption example](examples/README.md) shows a failed attempt being diagnosed before a new hypothesis, followed by resume with counters preserved. A changed input reopens its dependent subtree while an independent branch can remain accepted.

## Install client skills

Installing the CLI and installing skills are separate operations. Skill installation always takes the exact target directory and defaults to a dry run:

```text
orqivra install --edition codex --target .agents/skills --skill orqivra-orchestrate
orqivra install --edition codex --target .agents/skills --skill orqivra-orchestrate --apply
orqivra verify-install --target .agents/skills
```

Use `.claude/skills` for Claude Code and `.gemini/skills` for Gemini CLI. The installer writes only selected skills and an ORQIVRA ownership manifest. It refuses unowned collisions and modified owned files. It does not edit global client instructions or infer a home directory.

Installing a skill does not activate a model, grant tools, or qualify the client runtime. Profiles describe logical roles and remain subject to the client’s controls. See [client compatibility](docs/compatibility.md).

## Build an offline bundle

```text
orqivra build --edition all --output dist/orqivra-v0.2.0
```

Each edition bundle contains rendered skills, the edition adapter and profile, shared contracts, schemas, and the license. Skills are rendered from canonical sources rather than maintained as duplicated client copies.

## Development and limits

The CLI tracks task state; it does not run commands read from DAGs, profiles, skills, logs, or evidence. SHA-256 records identify bytes and do not prove semantic correctness. Current runtime and client qualification results are in the [release report](docs/release-report.md).

```text
python -m unittest discover -s tests -v
python -m orqivra.cli --help
npm ci --prefix node
npm test --prefix node
```

Read the [architecture](docs/architecture.md), [CLI contract](docs/cli-contract.md), [security model](docs/security.md), [contribution guide](CONTRIBUTING.md), and [change log](CHANGELOG.md). ORQIVRA’s original project content is licensed under MIT. The documented third-party dependency inventory is scoped in the security guide.
