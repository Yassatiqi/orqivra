# CLI Contract

The public command is `orqivra` (also available as `python -m orqivra.cli`). JSON is used for machine-readable project, DAG, profile, state, and evidence files. The CLI validates skill YAML frontmatter with its declared PyYAML dependency.

## Commands

```text
orqivra validate project PATH
orqivra validate dag PATH [--project PATH]
orqivra validate profile PATH
orqivra validate skills PATH
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

`plan` validates missing dependencies, cycles, and ownership conflicts and returns a stable lexical READY frontier. `state transition` rejects illegal edges and unmet prerequisites. Transitioning a node to `obsolete` invalidates its dependent subtree and queues it for `resume`; active attempts are marked interrupted and require diagnosis after resume. Acceptance also rechecks the relevant input and active evidence artifact hashes; changed inputs or artifacts require `evidence check` and recovery before acceptance. `attempt begin` increments once before work starts and enforces the five-attempt ceiling. `evidence add` hashes artifacts but never runs the recorded command. Evidence records are append-ordered; the latest record is active, and earlier records remain historical. `evidence check` finds changed inputs or active artifacts and invalidates dependent acceptance. `resume` recalculates only affected nodes and preserves counters. `report` is read-only: it checks current input and active artifact hashes, lists changed inputs, stale active evidence, superseded stale history, and accepted nodes without current successful evidence. It never certifies changed inputs, stale active evidence, or accepted nodes without current successful evidence.

Mutations require an existing state path or an explicit `state init`. Every mutation uses a state version check and atomic replacement under an exclusive lock. On conflict, the command fails without overwriting. The `--target` argument to install or uninstall is mandatory and is the exact installation root; commands never infer a home directory or edit global client instructions. Both commands default to dry-run. Pass `--apply` to perform the reviewed operation. A manifest records every owned relative path and SHA-256 digest. Verification and uninstall refuse missing, modified, or unsafe entries.

The CLI uses exit code 0 for success, 2 for invalid data or illegal state, 3 for a concurrent version conflict, and 4 for I/O or unsafe-path errors. Diagnostics are English. No command accepts a shell command to execute.
