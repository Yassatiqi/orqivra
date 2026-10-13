# Installation

## Choose one CLI distribution

Both distributions expose the full `orqivra` CLI. Use one distribution in a shell environment to avoid PATH ambiguity.

| Distribution | Runtime | Declared minimum |
|---|---|---:|
| npm | Node.js | 24 |
| pipx | Python | 3.11 |

The npm implementation does not need Python. The Python implementation does not need Node.js.

## Install a local artifact

Install the local npm pre-release tarball:

```powershell
npm.cmd install --global C:\path\to\orqivra-0.3.0.tgz
orqivra --help
```

Install the Python wheel with pipx:

```powershell
pipx install C:\path\to\orqivra-0.3.0-py3-none-any.whl
orqivra --help
```

The Python source archive and a local source checkout can also be installed with pipx. ORQIVRA 0.3.0 is a pre-release candidate, not a fully qualified package release. These are local artifact commands; they do not publish packages or verify publisher account eligibility.

## Build local release artifacts

From a source checkout, build npm using Node and npm only:

```powershell
Push-Location node
npm.cmd ci
npm.cmd run build
npm.cmd pack --pack-destination ..\scratch\packages
Pop-Location
```

Build the Python wheel and source distribution using Python only:

```powershell
python -m pip install build
python -m build --outdir scratch/packages
```

The generated Node `dist/` directory is excluded from Git but is required in the npm tarball. Python schemas, defaults, model catalog, skills, profiles, adapters, and contracts are included in Python distributions. Always inspect both inventories and test installation outside the checkout, with the other runtime unavailable.

## Install client skills

CLI installation and skill installation are separate. The `--target` path is mandatory and must be the exact skills directory. Dry-run is the default. Review the listed paths before using `--apply`.

```text
orqivra install --edition codex --target .agents/skills --skill orqivra-orchestrate
orqivra install --edition codex --target .agents/skills --skill orqivra-orchestrate --apply
```

| Edition | Repository skills path |
|---|---|
| Codex | `.agents/skills` |
| Claude Code | `.claude/skills` |
| Gemini CLI | `.gemini/skills` or `.agents/skills` |

The canonical source tree contains shared skill bodies, not pre-created native directories. `orqivra build` or `orqivra install` generates the selected client layout. The installer writes only selected skills and its ORQIVRA ownership manifest. It refuses unowned collisions and modified owned files. It does not edit global client instructions or infer a home directory.

## Troubleshooting

- **PowerShell blocks `npm.ps1`:** use `npm.cmd` as shown above; do not change the execution policy for this project.
- **The wrong `orqivra` runs:** use `Get-Command orqivra -All` in PowerShell or `type -a orqivra` in POSIX shells, then remove PATH ambiguity or use the intended environment's executable directly.
- **The pipx command is missing from PATH:** run `pipx ensurepath` in the appropriate shell and open a new shell, or invoke the executable by its reported full path.
- **A skill is not discovered:** verify the exact target and manifest with `orqivra verify-install`, then follow the client's documented workspace trust and skill reload steps. Installing a skill does not activate a model or grant permissions.
- **Configuration is missing:** when `--config` is omitted, only a missing automatically discovered `orqivra.config.json` uses defaults. If you named a missing file with `--config PATH`, correct the path or create the file. An existing empty file or `{}` inherits defaults.

## After a public registry release

Use `npm install --global orqivra@0.3.0` or `pipx install orqivra==0.3.0` only after the version is actually published and visible. Publication is a separate authorized action. Registry 404 responses do not reserve a package name.
