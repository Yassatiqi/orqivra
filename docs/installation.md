# Installation

## Choose one CLI distribution

Both packages expose the same `orqivra` command and full CLI. Use one distribution in a shell environment to avoid PATH ambiguity.

| Distribution | Runtime | Declared minimum |
|---|---|---|
| npm | Node.js | 24 |
| pipx | Python | 3.11 |

### Install a local npm artifact

Install the v0.2.0 tarball you received or built:

```powershell
npm install --global C:\path\to\orqivra-0.2.0.tgz
orqivra --help
```

On Unix, use the path to the same tarball, for example `/path/to/orqivra-0.2.0.tgz`. You can also run the installed package from a project with `npm exec -- orqivra --help` or `npx --no-install orqivra --help` when that project has the package installed.

### Install a local Python artifact

Install the built wheel with pipx:

```powershell
pipx install C:\path\to\orqivra-0.2.0-py3-none-any.whl
orqivra --help
```

The source archive and a local source checkout are also supported:

```powershell
pipx install C:\path\to\orqivra-0.2.0.tar.gz
pipx install C:\path\to\orqivra-source
```

### Build local release artifacts

From a source checkout, build the npm tarball:

```text
cd node
npm ci
npm run build
node -e "require('node:fs').mkdirSync('../dist',{recursive:true})"
npm pack --pack-destination ../dist
```

In Windows PowerShell, use `npm.cmd` if your execution policy blocks the `npm.ps1` shim.

Build the Python wheel and sdist:

```text
python -m pip install build
python -m build --outdir dist
```

The commands above create local artifacts. They do not publish packages.

### After a public registry release

Use registry commands only after the requested version is visible in the registry:

```text
npm install --global orqivra@0.2.0
pipx install orqivra==0.2.0
```

These commands are conditional examples, not currently available installation routes for this local release. Package publication is outside the v0.2.0 preparation task.

## Identify the active executable

Both distributions install an executable named `orqivra`. On Windows PowerShell, inspect all matches and their source paths:

```powershell
Get-Command orqivra -All
```

On Unix-like shells:

```sh
command -v orqivra
type -a orqivra
```

Prefer installing only one distribution in a given environment. For Python, `python -m orqivra.cli --help` explicitly runs the package associated with that interpreter.

## Install selected client skills

CLI installation and skill installation are separate. The `--target` path is mandatory and must be the exact skills directory. Dry-run is the default. Review the listed paths before using `--apply`.

```text
orqivra install --edition codex --target .agents/skills --skill orqivra-orchestrate
orqivra install --edition codex --target .agents/skills --skill orqivra-orchestrate --apply
```

Targets by client:

| Edition | Repository skills path |
|---|---|
| Codex | `.agents/skills` |
| Claude Code | `.claude/skills` |
| Gemini CLI | `.gemini/skills` or `.agents/skills` |

To install all four skills, omit `--skill`. Repeat `--skill` to select multiple skills. Each skill contains its full instructions. The installer writes an ORQIVRA manifest in the explicit target, refuses unowned collisions, and does not edit global client instructions or user-profile files.

## Verify, remove, and build bundles

```text
orqivra verify-install --target .agents/skills
orqivra uninstall --target .agents/skills
orqivra uninstall --target .agents/skills --apply
orqivra build --edition codex --output dist/codex
orqivra build --edition all --output dist/orqivra-v0.2.0
```

Uninstall is dry-run by default. It removes only files listed in the ORQIVRA manifest whose content still matches the recorded hash. Modified and unrelated files are preserved. Each bundle includes the selected native skill layout, profile, adapter, shared contracts, schemas, and license.

Installing a skill does not activate a model or establish compatibility with the client runtime. See the [qualification matrix](compatibility.md).
