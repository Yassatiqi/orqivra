# ORQIVRA v0.2.0 Delivery DAG

## Starting snapshot and compatibility contract

- Starting commit: `7208220146dd8368cb884e6e574c3c3b4c0e8824` (`Build ORQIVRA v0.1.0`).
- Starting worktree: clean; branch `main` reports its configured `origin/main` ref as gone.
- Initial source archive digest: `sha256:3fda74ae43e749c369766902340e606328e92ba5f5d5abed27cef1c623ce3e1d`, computed from the bytes emitted by `git archive HEAD`.
- Applicable project policy: root `AGENTS.md`; no nested `AGENTS.md` files exist.
- Local tools observed: Python 3.13.2, Node.js v24.20.0, Git, and `npm.cmd`. `pipx` is not installed. PowerShell blocks the `npm.ps1` shim, so npm commands use `npm.cmd`.
- The v0.1 contract in `docs/cli-contract.md` remains the behavioral baseline. It defines validation, planning, state initialization and transitions, attempts, evidence, freshness, recovery, JSON and Markdown reports, bundle builds, explicit-target skill install/verify/uninstall, exit codes, locking, and safe path handling.
- Canonical shared sources are `core/contracts/`, `schemas/`, `profiles/`, and, after node B, one provider-neutral `skills/<capability>/SKILL.md` per capability plus native-client adapter data under `editions/<client>/`. Both implementations render client skill files from those sources at build or install time. Generated skill bodies are not manually maintained copies.
- Both implementations use UTF-8 JSON canonicalization for shared hashes: recursively sort object keys by their Unicode scalar sequence, emit no insignificant whitespace, leave non-ASCII scalar values unescaped, and encode the result as UTF-8 before SHA-256. Shared hashed values use JSON null, booleans, strings, arrays, objects, and safe integers; duplicate keys, lone surrogates, non-finite numbers, and fractional numbers are rejected. File and evidence artifacts use SHA-256 over raw bytes.
- No command text stored in DAGs, profiles, skills, logs, or evidence may be executed. Installation and uninstall stay limited to an explicit target and unchanged files recorded in the ORQIVRA manifest.
- The previous v0.1 release report records review fingerprint `bb645b682b567cb9e003a73b075684ded2722a6eb1487f75d94aafd7b0732abe`; the task handoff also reports `04e3f19a7b0d02fa1136c70128403c1c0a42a7b8b9cc1fdc2cf667918023bbfd`. These are distinct values. Their review-tool hash inputs and serialization are not described in the repository, so neither is treated as a digest of the starting Git archive or as proof that the two reports refer to identical bytes. The v0.2 release report will record an exact Git commit, tree identity, archive digest, and package hashes separately.

## Execution route and recovery limits

Historical first-phase constraint: the external orchestration skill applied during the original delivery phase required the primary session to use `gpt-5.6-sol` at High before auxiliary work. The primary session used GPT-6, so no worker or independent reviewer was used in that phase. This records the condition that applied then; it does not describe the exhausted integration node as passed or erase its escalation and attempt history.

For the user-authorized corrective phase, project-owned routing is based on actual runtime capabilities, explicit authorization, task independence, and disjoint ownership. A worker or reviewer is used only when available and useful within native runtime permissions. This project guidance does not modify or override installed skills, system instructions, or runtime policy. The corrective phase keeps its own linked record and attempt budget; it does not reset prior counters or diagnoses.

See the [corrective-phase record](CORRECTIVE-PHASE.md) for its linked DAG, separate five-attempt budgets, verification evidence, review status, and release readiness states.

Each node has a five-attempt maximum. A hypothesis is recorded before an attempt begins. Failed or interrupted attempts require diagnosis before a new attempt. Integration/release corrections have a separate four-pass maximum. Counters and event history are stored in ignored local state at `.artifacts/v0.2.0/delivery-state.json`; the validated plan is `.artifacts/v0.2.0/delivery-dag.json`.

## Nodes, dependencies, ownership, and acceptance

| Node | Depends on | File scope | Acceptance |
|---|---|---|---|
| A. Inspect and freeze the contract | - | `docs/BUILD-DAG.md` | Applicable guidance, starting state, public CLI behavior, ownership boundaries, runtime availability, and release limits are recorded. The DAG validates without cycles, missing dependencies, or overlapping simultaneously ready scopes. |
| B. Canonical skills, parity fixtures, and package assets | A | `skills/**`, `editions/**`, `schemas/edition-adapter.schema.json`, `tests/parity/fixtures/**`, `tools/generate-node-assets.mjs` | Each capability has one provider-neutral source. Validated native-client adapter data supplies discovery, invocation, and permission guidance. Fixtures use canonical contracts, and the npm asset generator is repeatable. |
| C. Node core and shared JSON/state behavior | B | `node/src/core/**`, `node/test/core/**`, `src/orqivra/paths.py`, `src/orqivra/schema.py`, `src/orqivra/state.py`, `tests/test_cli_acceptance.py` | Node implements validation, planning, state transitions, attempts, diagnosis, canonical hashes, lock/conflict handling, and atomic writes without invoking Python. Python and Node reject duplicate JSON keys and share tested canonical hashes. |
| D. Node evidence, recovery, and reports | C | `node/src/commands/evidence.ts`, `node/src/commands/state.ts`, `node/src/commands/report.ts`, `node/test/commands/**` | Freshness, scoped invalidation, history, recovery, interruption diagnosis, and read-only JSON/Markdown reporting match the contract. |
| E. Node packaging and shared skill installation | B, C, D | `node/src/commands/installer.ts`, `node/src/cli.ts`, `node/scripts/**`, `node/package.json`, `node/package-lock.json`, `node/tsconfig.json`, `node/.gitignore`, `node/test/installer/**`, `src/orqivra/installer.py`, `tests/test_installer_assets.py` | Python and Node builders render skills from canonical sources plus adapters. The npm tarball contains all runtime assets and a full `orqivra` CLI; safe explicit-target manifest installation works without Python. |
| F. Python pipx distribution | E | `pyproject.toml`, `src/orqivra/__init__.py` | Version 0.2.0, MIT metadata, canonical runtime resources, wheel, sdist, and console command are verified outside the checkout; Python 3.11+ remains the declared floor. |
| G. Open-source documentation and CI | A | `README.md`, `LICENSE`, `CONTRIBUTING.md`, `CHANGELOG.md`, `docs/architecture.md`, `docs/cli-contract.md`, `docs/compatibility.md`, `docs/installation.md`, `docs/security.md`, `docs/release-notes.md`, `.github/**` | Public documentation is accurate, the authorized MIT notice and third-party findings are recorded, issue/PR templates are useful, and least-privilege Windows/Linux checks do not publish artifacts. |
| H. Integration and acceptance | C, D, E, F, G | `tests/parity/run_parity.py`, `tests/parity/expectations.json`, `node/test/parity/**` | Both CLIs pass shared fixtures, cross-runtime state and manifest interoperability, regression tests, package checks, and supported security cases. Unavailable checks are reported as unavailable. |
| I. Review and release preparation | H | `docs/release-report.md` | The report binds claims to a precise snapshot and artifacts. Publication readiness requires passing acceptance and the requested fresh read-only review. No external publication is performed. |

Graph: `A -> B -> C -> D -> E -> F -> H -> I`; `B -> E`; `A -> G -> H`.

The scopes are disjoint across concurrently runnable nodes. Generated Node.js package contents are staged under `node/dist/`; the root `.gitignore` excludes that build directory. The npm tarball includes the compiled CLI, rendered skills, profiles, schemas, contracts, README, and license from that directory. Canonical sources remain in the repository locations listed above.

## Attempt and evidence log

The first A hypothesis was diagnosed because the graph omitted canonical skill sources and shared rendering ownership; A attempt 1 is recorded as interrupted and A attempt 2 was accepted. B attempt 1 was interrupted while the scope was corrected to include the new adapter schema. B attempt 2 was diagnosed after a source test loaded the installed v0.1 wheel instead of the checkout and then failed an exact reconstruction check because one blank line was lost. B attempt 3 preserved the separator and was accepted after all twelve rendered sources matched, all eight shared fixtures validated, and two generated 23-file trees had identical hashes. The graph was then refined so E waits for the core and command handlers it packages. At state version 35, A and B are accepted and C and G are ready. State and attempts remain in ignored `.artifacts/v0.2.0/delivery-state.json`.
