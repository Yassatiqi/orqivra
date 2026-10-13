# ORQIVRA

ORQIVRA is a local workflow CLI for planning engineering tasks, recording bounded attempts and verification evidence, and recovering from changed inputs or interruptions. It provides the same public contract through independent Python and Node.js implementations. The Python CLI requires Python 3.11 or newer; the npm CLI requires Node.js 24 or newer. Neither CLI invokes the other runtime.

## Choose a CLI

Install one distribution so `orqivra` resolves to one installation:

| Distribution | Runtime | Local artifact installation |
|---|---|---|
| npm | Node.js 24+ | `npm install --global ./orqivra-0.3.0.tgz` |
| pipx | Python 3.11+ | `pipx install ./orqivra-0.3.0-py3-none-any.whl` |

These are local pre-release artifact examples. Version 0.3.0 is not published to npm or PyPI and is not fully qualified for publication. See [installation](docs/installation.md) for building artifacts, installing from a checkout, and troubleshooting.

## Try a workflow

From an installed CLI, validate a sample DAG and inspect its READY frontier:

```text
orqivra validate dag examples/solo-change.json
orqivra plan examples/independent-branches.json
```

The [quickstart](docs/quickstart.md) creates a disposable project and initializes a state report. It also shows how to inspect edition profiles and validate optional project configuration. A missing discovered `orqivra.config.json` uses defaults; a missing file explicitly selected with `--config` is an error. The [examples guide](examples/README.md) shows correction and interruption recovery. Do not accept a node while its active evidence is stale; input changes require checks and recovery while preserving attempt counters.

## Client skills

Installing the CLI and installing client skills are separate operations. Provide an explicit target directory; installation defaults to a dry run:

```text
orqivra install --edition codex --target .agents/skills --skill orqivra-orchestrate
orqivra install --edition codex --target .agents/skills --skill orqivra-orchestrate --apply
orqivra verify-install --target .agents/skills
```

Canonical skills are rendered into native client directories by `install` or `build`; those generated copies are not maintained in the source tree. Installation refuses unowned collisions and modified owned files. It does not edit global client instructions or infer a home directory. Installed skills and profiles do not grant tools, change the active model, or qualify client activation. See [client qualification](docs/client-qualification.md).

## Development

```text
python -m unittest discover -s tests -v
python -m orqivra.cli --help
npm.cmd test --prefix node
```

Use [documentation](docs/README.md) for architecture, CLI details, security boundaries, and the release checklist. Python 3.11 Windows junction qualification, client activation, GitHub Actions, registry ownership, and private vulnerability reporting remain unresolved until observed. Current per-runtime and client qualification evidence is maintained locally under ignored `scratch/`, not presented as a public release claim. ORQIVRA is MIT-licensed; third-party components and package boundaries are described in [the security model](docs/security.md).
