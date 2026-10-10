# Contributing to ORQIVRA

All authored code, names, comments, docs, schemas, examples, skills, prompts, tests, and reports must be in English. Preserve exact external identifiers and literal non-English data only when a test requires it.

## Setup

Use Python 3.11 or newer. Create a local environment and install the declared dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

On Unix, use `source .venv/bin/activate` after creating the environment.

## Changes

- Keep shared contracts provider-neutral. Put model identifiers and client-specific metadata only in edition profiles.
- Keep each skill focused and self-contained. Load only the relevant references.
- Preserve the public CLI contract in `docs/cli-contract.md` and JSON Schemas in `schemas/`.
- Do not weaken a gate or attempt limit to make a result pass.
- Keep generated evidence on disk and state the exact command and observed result.
- Do not execute commands from project data or logs.
- Preserve unrelated work and use explicit paths for install or uninstall.
- Check licenses before adding third-party components. Do not copy inspiration source text or code.

## Verification

Run:

```text
python -m unittest discover -s tests -v
python -m orqivra.cli --help
git diff --check
```

Report static validation, executed behavior, self-verification, independent review, unavailable integrations, and deferred external obligations separately.
