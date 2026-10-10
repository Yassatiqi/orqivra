# ORQIVRA v0.1.0 Construction DAG

## Initial snapshot

- Workspace: an empty Git repository at `D:\Repositories\orqivra`.
- Initial Git state: no commit exists (`HEAD` is absent); worktree has no tracked or untracked project files.
- Available local runtimes: Python 3.13.2 and Git. `codex` is installed; `claude` and `gemini` commands were not found.
- Applicable `AGENTS.md`: none before this file was created.
- External documentation was retrieved on 2026-10-10. See `docs/compatibility.md`.

## Construction graph and ownership

| Node | Depends on | Scope owner | Status |
|---|---|---|---|
| A. Discover workspace and client capabilities | — | Coordinator | accepted |
| B. Define contracts, schemas, transitions, and CLI | A | Coordinator | accepted |
| C. Implement shared Python runtime and installer | B | Coordinator | accepted |
| D. Write Codex, Claude Code, and Gemini CLI editions | B | Worker: `editions/` and `profiles/` only | accepted |
| E. Write acceptance fixtures, behavioral trials, and examples | B | Worker: `tests/` and `examples/` only | accepted |
| F. Integrate runtime, editions, fixtures, and packaging | C, D, E | Coordinator | accepted |
| G. Run behavioral trials and dogfood through the active client | F | Coordinator | accepted (`SIMULATED` client skill activation) |
| H. Fresh review, corrections, final verification, and release report | G | Coordinator and fresh reviewer | accepted (`ship`; reviewed snapshot fingerprint recorded in the release report) |

The coordinator is the only writer of this DAG. Worker results are written to separate return notes outside the project state file. The two worker scopes do not overlap. Each worker receives this document, the current public interface files, and the English-only policy. A worker's verification claims are rerun by the coordinator.

## Routing and bounded work

The route is `full`: the user explicitly requested parallel implementation and fresh review for a broad framework with persistent state, recovery, and installation safety. Two workers start after node B. The first handles the three client editions. The second handles test and example fixtures. Concurrency remains two unless an observed dependency requires a different width.

Correction loops are capped at five meaningful attempts for the same issue, with a separate four-pass integration/release correction cap. No attempt is counted as meaningful unless it starts from a distinct hypothesis or remediation. A blocker is recorded without weakening acceptance criteria.

## State transition policy

The project delivery DAG uses `planned`, `ready`, `running`, `verifying`, `fix_required`, `blocked`, `accepted`, and `obsolete`. Edges are specified in `docs/architecture.md`; final delivery requires every required node to be accepted and every external obligation either verified or explicitly reported as an unresolved blocker. The implementation's task DAG uses the same transitions and the same five-attempt per-node ceiling.

## Behavioral trial evidence

The command outputs and scenario outcomes are recorded in `docs/behavioral-trials.md`. The Codex parser dogfood and simple-work trigger judgment were manually exercised because this session did not expose a Codex skill-discovery invocation; both are explicitly `SIMULATED`. CLI planning, blocking, interruption recovery, and generated state reports were observed directly. The final independent reviewer returned `ship`; the verdict and reviewed code snapshot fingerprint are recorded in `docs/release-report.md`.
