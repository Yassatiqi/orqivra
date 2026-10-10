# Behavioral Trials

These trials exercise user-facing behavior and saved workflow state. `OBSERVED` means the command or local outcome was executed in this session. `SIMULATED` means a capability contract was applied manually because the client did not expose skill discovery; it is not runtime qualification.

## Positive skill trigger: coordinated parser correction

**Status: `SIMULATED`.** The controlled JSON Lines parser fixture had a whitespace-only-line defect. This is a positive orchestration case because it required checking the input contract, changing the parser, verifying behavior, and recovering from a deliberately injected failure. The Codex edition was installed locally for the trial, but the session exposed no supported skill activation mechanism. The coordinator manually applied the architecture, orchestration, verification, and recovery skill contracts. No Codex skill invocation is claimed.

The first focused test run used the wrong empty-line guard and failed on the whitespace-only second line. Replacing the guard with `line.strip() == ""` made the unchanged four-test suite pass. The parent then reintroduced the same controlled defect, observed the expected test error, restored the correction, and observed the focused suite pass again. Full details are in `tests/behavioral/codex_dogfood/TRIAL.md`.

## Negative skill trigger: simple local edit

**Status: `SIMULATED` contract decision; local edit `OBSERVED`.** A one-line fixture at `.artifacts/simple-work/status.txt` was changed from `status=draft` to `status=complete` and read back. It had no dependencies, shared files, review requirement, or coordination need. The route remained solo; no agent or task DAG was created. This demonstrates the intended negative trigger without claiming that Codex loaded the edition's skill metadata.

## Two safe independent branches

**Status: `OBSERVED` CLI behavior.** Running `orqivra plan examples/independent-branches.json` returned the deterministic READY frontier:

```json
["update-architecture-contract", "update-cli-reference"]
```

The two nodes have disjoint file scopes and no dependency edge between them. The integration node depends on both.

## Independent branch remains available after a local block

**Status: `OBSERVED` CLI behavior.** The saved example state blocked `update-architecture-contract` with reason `A local fixture dependency is unavailable`. Planning against that state returned:

```json
["update-cli-reference"]
```

The block remained local; the independent CLI-reference node stayed in the frontier.

## Recovery after interruption

**Status: `OBSERVED` CLI and test behavior.** In `.artifacts/interrupt-recovery-state.json`, `resume` marked unfinished attempt 1 as interrupted and preserved the attempt count. The coordinator inspected the current fixture, recorded a distinct second hypothesis, and reran the focused parser tests. Attempt 2 passed; the dependent state-check node also passed. `orqivra report --state .artifacts/interrupt-recovery-state.json --format markdown` reported both nodes accepted, certification `yes`, no unresolved required gates, and no stale evidence.

## Independent review

The fresh read-only reviewer returned `ship` for the corrected implementation snapshot with fingerprint `bb645b682b567cb9e003a73b075684ded2722a6eb1487f75d94aafd7b0732abe` (71 project files). The review confirmed the corrected evidence freshness, Markdown diagnostics, manual-obsoletion recovery, regression coverage, and wheel contents. The release report records the verdict and verification evidence; the reviewer did not rerun the full suite.
