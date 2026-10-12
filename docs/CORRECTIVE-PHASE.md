# ORQIVRA v0.2.0 Corrective Phase

## Authorization and linkage

This corrective phase follows escalation of the original v0.2.0 integration node. The user explicitly authorized a new corrective budget of at most five attempts for each corrective task after that escalation. This creates a new linked phase; it does not reset, rewrite, or reinterpret any prior attempt, diagnosis, evidence, or blocker, and the original integration node is not recorded as passed by this phase.

The prior plan and event history remain at `.artifacts/v0.2.0/delivery-dag.json` and `.artifacts/v0.2.0/delivery-state.json`. At phase start, the prior plan ID was `orqivra-v0.2.0-delivery` and its event state was at version 149. The corrective plan and its state are separate files under `.artifacts/v0.2.0/corrective-phase/` and link back to these originals.

## Corrective tasks and ownership

Each row starts with zero attempts and has a separate maximum of five. An attempt is counted when its distinct, testable hypothesis is started. Diagnoses and evidence remain in the corrective state; prior history remains in the original state.

| Node | Objective | Owned scope | Depends on |
|---|---|---|---|
| J | Add Python 3.11-compatible Windows junction detection and focused security regression coverage. | `src/orqivra/paths.py`, `src/orqivra/installer.py`, `tests/test_path_security.py` | - |
| K | Correct project-owned orchestration guidance and add discoverable security policy documentation. | `docs/BUILD-DAG.md`, `docs/security.md`, root `SECURITY.md`, plus the release-report readiness structure | - |
| L | Integrate the correction, run requested suites and interoperability, rebuild and inspect distributions, and refresh the release report, hashes, and readiness evidence. | `docs/release-report.md`, `.artifacts/v0.2.0/corrective-phase/` | J, K |
| M | Fresh read-only review of the final corrective source and documentation snapshot. | `.artifacts/v0.2.0/corrective-phase/review.md` | L |
| N | Inspect the complete final diff and create a local commit if the corrected work is coherent and relevant checks pass. | Local Git commit; corrective state and final report evidence | M |

J and K have disjoint write scopes and can proceed independently. One coordinator owns integration, acceptance, evidence freshness, review dispatch, and commit decisions. Reviewer output is independent only if a separate, fresh read-only worker actually performs it; coordinator self-review is recorded separately.

## Routing and external workflow constraint

The installed Sol Advisor orchestration skill contains a prerequisite requiring the primary session to use `gpt-5.6-sol` at High before auxiliary work. This project does not edit that installed skill. The user explicitly authorized correction of project-owned workflow instructions and requested another workflow when the external skill blocks the available native runtime. This phase therefore uses the native worker facility only where a task is independent, explicitly authorized, and has a disjoint scope; the coordinator retains shared-state ownership and final acceptance. This records the reason for the route and does not claim the external prerequisite was satisfied.

The first J attempt began from a plan that named `tests/test_cli_acceptance.py`, but the worker added a dedicated `tests/test_path_security.py`. The scope was reconciled in the corrective DAG before J attempt 2, and J was accepted after that parent-run re-verification. The first attempt remains in the corrective state; any further re-verification uses the same five-attempt corrective budget.

## Readiness states

Local implementation and verification, local commit readiness, public repository preparation, and npm/PyPI publication readiness are separate states. A repository setting or private reporting channel that cannot be verified is an external publication checklist item; it does not block local corrections, tests, review, or a local commit. Private vulnerability reporting is not claimed to be enabled. No repository visibility or settings changes, push, package publication, or external release are authorized in this phase.

## Attempt and evidence log

The original delivery DAG/state were not edited; the original state remains at version 149 with H retaining its five recorded attempts and I retaining its three-attempt blocked status. These historical state labels and evidence are not replaced by this phase.

| Node | Attempt | Observed work and result |
|---|---:|---|
| J | 1 | Implemented Windows `lstat()` reparse-point detection and a real `mklink /J` test. The test passed on Python 3.13.2; symlink creation skipped with WinError 1314. The first plan named the wrong test file, so the DAG scope was corrected and this evidence was preserved as history. |
| J | 2 | Coordinator reran the focused test against the corrected scope: real junction rejection passed for explicit-root, path-component, install-target, and state-path boundaries; symlink test skipped with WinError 1314. Python 3.11 was not installed (`py -3.11 --version` returned no suitable runtime), so qualification remains unresolved. |
| K | 1 | Reframed the project-owned model gate as historical and added the security/readiness structure. A plan/input refresh reopened the task for current-snapshot verification; the first attempt remains recorded. |
| K | 2 | Coordinator checked local security/corrective links, active capability-based routing, four readiness states, `NOT_RUN` client/CI labels, and the private-reporting boundary. Verified. |
| L | 1 | Ran focused path-security tests (real junction rejection passed; symlink creation skipped with WinError 1314), the full Python suite (34 run, 32 passed, 2 skipped), CLI help (exit 0), Node suite (17 passed), and shared parity/interoperability (18 passed). Python 3.11 was unavailable, so the real-junction qualification was not run on 3.11 and remains unresolved. Rebuilt wheel, sdist, and npm tarball; installed each outside the checkout and exercised help/version. npm worked with Python absent; pipx wheel and sdist worked with Node absent. Default npm/pip cache writes failed with access denied, so the caches were redirected to ignored project artifacts. An initial sdist attempt also lacked setuptools in pip's temporary build environment, then a dependency-only test path lacked `attr`; both were corrected and the rebuilt sdist install passed. Package inventories and SHA-256 values are in the release report. |

The corrective state file retains the full event and evidence history under `.artifacts/v0.2.0/corrective-phase/delivery-state.json`. L's verification qualifies only the available runtimes; it does not establish Python 3.11 behavior. The first independent reviewer returned `FIX FIRST` for two history statements and a stray literal in the report; the findings and diagnosis are preserved in M attempt 1. Review findings and the final independent-review verdict are recorded in the ignored review artifact and release report, separately from executed tests. The original state and its H/I statuses remain intact.
