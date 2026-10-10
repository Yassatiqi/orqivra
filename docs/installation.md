# Installation

## Install the CLI

Use Python 3.11 or newer. Create and activate a virtual environment, then install the package. On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install .
```

On Unix:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
```

For development, install with `python -m pip install -e .`.

## Install selected client skills

The `--target` path is required and is the exact skills directory. Dry-run is the default. Review the selected file paths before using `--apply`.

```powershell
orqivra install --edition codex --target .agents/skills --skill orqivra-orchestrate
orqivra install --edition codex --target .agents/skills --skill orqivra-orchestrate --apply
```

Targets by client:

| Edition | Repository discovery path |
|---|---|
| Codex | `.agents/skills` |
| Claude Code | `.claude/skills` |
| Gemini CLI | `.gemini/skills` or `.agents/skills` |

To install all four skills, omit `--skill`. Repeat `--skill` to select multiple skills. Each installed skill includes its full instructions. The installer creates an ORQIVRA manifest in the explicit target, refuses unowned collisions, and never edits `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, global configuration, or user profile files.

## Verify and uninstall

```text
orqivra verify-install --target .agents/skills
orqivra uninstall --target .agents/skills
orqivra uninstall --target .agents/skills --apply
```

Uninstall is dry-run by default. It removes only files recorded in the manifest whose content still matches the recorded hash. It leaves modified files and unrelated user files untouched and reports a refusal before deleting anything.

## Build an offline edition bundle

```text
orqivra build --edition codex --output dist/codex
orqivra build --edition all --output dist/orqivra-v0.1.0
```

Each bundle includes the selected native skill layout, its profile, shared contracts, and schemas. Files are produced from the canonical edition sources; the three editions do not maintain divergent copies of shared tools.
