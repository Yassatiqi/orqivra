# ORQIVRA v0.2.0 Release Preparation Report

## Release decision

Publication readiness remains **NOT READY**. Readiness is tracked separately for the local corrective work, local commit, public repository preparation, and package publication. The first-phase delivery history and its exhausted integration attempt count remain recorded in the original ignored delivery state; this corrective phase has its own linked record and does not reset that history.

The corrective plan and attempt budget are documented in the [linked corrective-phase record](CORRECTIVE-PHASE.md); its machine-readable DAG and state remain under the ignored `.artifacts/v0.2.0/corrective-phase/` directory.

## Readiness matrix

| Readiness state | Status | Basis |
|---|---|---|
| Local implementation and verification | COMPLETE_WITH_QUALIFICATION_UNRESOLVED | Corrective source and regression changes are verified with the available Python 3.13.2 and Node.js runtimes. Python 3.11 Windows junction execution remains unavailable and explicitly unresolved. |
| Local commit readiness | READY_FOR_LOCAL_COMMIT_WITH_PYTHON_3.11_QUALIFICATION_UNRESOLVED | Relevant corrective checks pass and a fresh independent read-only review returned SHIP for the corrected 111-file source snapshot. Actual Python 3.11 Windows junction execution remains unresolved. A GitHub setting is not a prerequisite for local fixes, verification, review, or commit. |
| Public repository preparation | BLOCKED_EXTERNAL | The private vulnerability-reporting route has not been verified. Keep its verification/configuration on the external publication checklist. No repository setting was changed. |
| npm/PyPI publication readiness | NOT_READY | Requires actual Python 3.11 Windows junction qualification, completed public repository security-reporting preparation, final package inventory and hashes, and registry/package-name availability checks. npm name availability is unverified, and PyPI availability was not checked. No registry publication was performed. |

The first-phase report findings below are retained as historical evidence. They describe the earlier snapshot, not the outcome of corrective verification.

1. The first-phase fresh read-only review was unavailable. The external orchestration skill then applied required the primary session to use `gpt-5.6-sol` at High before auxiliary work; the session used GPT-6, and no independent reviewer was claimed. The corrective phase uses the project-owned capability-based routing described in [the delivery record](BUILD-DAG.md); the installed skill and system instructions were not modified.
2. The earlier path guard relied on `Path.is_junction()` when available, which did not establish Python 3.11 junction rejection. The correction now checks Windows `lstat()` file attributes for `FILE_ATTRIBUTE_REPARSE_POINT` while retaining the declared Python 3.11+ floor and existing symlink checks. Python documents `st_file_attributes` on Windows and the reparse-point constant; however, Python 3.11 was unavailable in this environment, so actual Python 3.11 execution remains unresolved. See the [Python 3.11 `os` documentation](https://docs.python.org/3.11/library/os.html), [Python 3.11 `stat` constants](https://docs.python.org/3.11/library/stat.html), and [the path guard](../src/orqivra/paths.py).
3. A private vulnerability-reporting channel was not verified in the first phase and remains an external publication checklist item. This does not block local corrective work or a local commit. See [the security policy](security.md) and the root [SECURITY.md](../SECURITY.md).

The original state remains at version 149 with H (Integration and acceptance) `accepted` after five attempts and I (Review and release preparation) `blocked` after three attempts. The corrective phase preserves both statuses, diagnoses, evidence, and histories; the blocked I node is not described as passed. These original-snapshot statuses do not establish acceptance of the corrected snapshot or publication readiness.

## Implementation summary

- Added a full TypeScript CLI for Node.js and retained the full Python CLI. Neither implementation invokes the other runtime.
- Moved capability skill bodies to canonical provider-neutral sources and added validated client adapters. Both implementations generate edition assets from those sources.
- Added shared fixtures and black-box parity checks for public commands, cross-runtime state and manifest handoff, safe paths, install ownership, locks, evidence freshness, recovery, and reporting.
- Added MIT package metadata, local distribution guides, compatibility and security guidance, contribution materials, release notes, issue/PR templates, and read-only Windows/Linux CI.
- Python metadata declares Python 3.11+. npm metadata declares Node.js 24+.

## First-phase verification results (historical baseline)

These results predate the corrective changes and must not be used as evidence that the corrected snapshot passed.

| Check | Observed result |
|---|---|
| Node unit suite: npm.cmd test --prefix node | 17 passed |
| Python regression suite: python -m unittest discover -s tests -v, using the repository virtual environment and PYTHONPATH=src | 32 run; 31 passed; 1 skipped |
| Python CLI help: python -m orqivra.cli --help, using the repository virtual environment and PYTHONPATH=src | Exit 0 |
| Shared Python/Node black-box parity harness | 18 passed; 0 skipped |
| Installed npm tarball outside the checkout | Installation, npm exec, and npx help worked with Python absent |
| pipx wheel, sdist, and local-source installations outside the checkout | Version/help and bundle/skill validation worked with Node absent, under Python 3.13.2 |
| Package inventory | Wheel: 40 entries; sdist: 66; npm tarball: 37 |
| CI workflow | YAML and job structure inspected; GitHub Actions were not run (NOT_RUN) |
| Documentation | Local-link scan checked 30 Markdown files and found no broken local links; git diff --check passed |

The Python symlink test skipped because this Windows account lacks symlink creation privilege (WinError 1314). The parity harness separately created a Windows junction and both CLIs rejected it, using Python 3.13.2. This did not establish Python 3.11 junction behavior. A bare system-Python invocation without the project environment failed because that interpreter did not have the project package and dependencies; the suite and help command passed when run with the repository virtual environment and source path.

## Corrective-phase verification

Record only commands actually executed against the corrected snapshot. Use `NOT_RUN` for configured CI or client checks that were not executed, `UNAVAILABLE` when an environment or dependency prevented execution, and `SKIPPED` only when a test runner explicitly skipped a check. Add the final source snapshot identity, package inventories, and rebuilt artifact hashes after those checks complete.

| Check | Corrective-phase result |
|---|---|
| Focused path-security regression tests | EXECUTED on Windows/Python 3.13.2: real `mklink /J` junction rejection passed; symlink-creation case was SKIPPED by unittest with WinError 1314. |
| Python 3.11 Windows junction test | UNAVAILABLE; `py -0p` listed only Python 3.13.2 and `py -3.11 --version` reported no suitable runtime. Qualification remains unresolved; the Python 3.13 test is not a substitute. |
| Full Python suite and CLI help | EXECUTED: 34 tests, 32 passed, 2 skipped; CLI help exited 0. The two skips were symlink creation cases blocked by WinError 1314. |
| Node suite | EXECUTED: 17 passed, 0 failed, 0 skipped. |
| Shared parity and affected cross-runtime interoperability | EXECUTED: 18 passed, 0 skipped, including a real Windows junction rejected by both CLIs and cross-runtime state/manifest/lock checks. |
| Rebuilt wheel, sdist, and npm tarball installation outside the checkout | EXECUTED: pipx installed the rebuilt wheel and its CLI help/version worked with Node absent; pip installed the rebuilt sdist into an outside-checkout venv and its CLI help/version worked with Node absent; npm installed the rebuilt tarball and its CLI help/version worked with Python absent. |
| Corrective package inventories and SHA-256 hashes | EXECUTED; see the local artifact table below. |
| Fresh independent read-only review of the corrected final snapshot | EXECUTED: separate worker reviewed source manifest sha256:d1c1aee0f8c20f80a5b4e6b3e69d49a4b1a617a7c87893628b44772369faee9c and returned SHIP. The first review returned FIX FIRST; its findings were corrected before this review. The reviewer made no changes and ran no tests. |
| Windows/Linux CI | NOT_RUN unless executed in GitHub Actions |
| Codex, Claude Code, and Gemini CLI runtime qualification | NOT_RUN unless each client is exercised |

## Runtime and client qualification

| Runtime/client | Declared or observed status |
|---|---|
| Python | Declared 3.11+; Python 3.13.2 on Windows exercised the corrective suites, parity, and rebuilt Python installs. Python 3.11 was unavailable, so the declared floor's Windows junction behavior remains UNAVAILABLE/UNRESOLVED pending an actual Python 3.11 Windows run. |
| Node.js | Declared 24+; Node.js 24.20.0 and npm 11.19.0 on Windows exercised the corrective suite, parity, and rebuilt npm install. Other Node versions and operating systems were not run locally. |
| Codex client | NOT_RUN; static edition validation only |
| Claude Code | NOT_RUN; static edition validation only |
| Gemini CLI | NOT_RUN; static edition validation only |
| Windows/Linux CI | NOT_RUN; workflows are configured but have not been executed in GitHub Actions |

Installing ORQIVRA or its skills does not activate a model or establish runtime compatibility with a client. The active executable should be identified with the relevant package-manager listing or command resolution; users should choose one distribution rather than install both.

## Local release artifacts

All sizes are bytes. SHA-256 values were recomputed from the files in the ignored release-artifact directory.

| Distribution | Filename | Size | SHA-256 |
|---|---|---:|---|
| Python wheel | orqivra-0.2.0-py3-none-any.whl | 50,357 | f06e0100b3a55ddd5fa7c5130cedee81e46823289fdba2fd8299ef7303f92160 |
| Python source distribution | orqivra-0.2.0.tar.gz | 47,171 | 99256988b5206f2c4ead846d51fef738bc96305bcd49f92ecf2cca359b026227 |
| npm package | orqivra-0.2.0.tgz | 38,610 | 9930ad6d21468b2027d00ce1125f1d9a7102a941762615e120beaa45ebaba17e |

The rebuilt wheel contains 40 entries, the source distribution 67, and the npm tarball 37. Each rebuilt artifact was installed outside the checkout and its CLI help/version exercised. The npm package has no production dependencies. The public npm registry lookup returned E404, so package-name availability is recorded as unverified, not available.

## Install from local artifacts

Run these from the repository root. The first two commands require pipx to be installed and available.

- Python wheel: pipx install .artifacts/v0.2.0/release/python/orqivra-0.2.0-py3-none-any.whl
- Python source distribution: pipx install .artifacts/v0.2.0/release/python/orqivra-0.2.0.tar.gz
- npm tarball: npm install --prefix ./orqivra-cli ./.artifacts/v0.2.0/release/node/orqivra-0.2.0.tgz
- Run the installed npm CLI: npm exec --prefix ./orqivra-cli -- orqivra --help
- Python local source install: pipx install .

These are local-artifact instructions. They do not imply the package is published to npm or PyPI.

## Security reporting

The private vulnerability-reporting route is not verified. Do not claim it is enabled or invent a maintainer contact. Before public repository preparation or publication, a maintainer must verify/configure an appropriate private route. This external step does not block local implementation, verification, review, or commit. See [SECURITY.md](../SECURITY.md) and the [detailed security guide](security.md).

## Snapshot identity and history

Current source snapshot manifest: sha256:d1c1aee0f8c20f80a5b4e6b3e69d49a4b1a617a7c87893628b44772369faee9c. This digest covers 111 current, non-ignored tracked or untracked project files, sorted by ordinal path and represented as UTF-8 path-NUL-file-SHA-256 entries joined with LF. It excludes docs/release-report.md to avoid self-reference, Git metadata, and Git-ignored generated/build/test artifacts. It identifies the implementation inputs but is not a Git commit. The first fresh review returned FIX FIRST for documentation consistency issues; after correction, a separate fresh reviewer returned SHIP on this exact source manifest. Review was read-only and did not execute tests; the report status update followed that review and does not alter the source manifest.

The v0.1.0 report records review fingerprint bb645b682b567cb9e003a73b075684ded2722a6eb1487f75d94aafd7b0732abe. The task handoff separately supplied 04e3f19a7b0d02fa1136c70128403c1c0a42a7b8b9cc1fdc2cf667918023bbfd. Their hashing inputs and serialization are undocumented, so they are not asserted to identify the same bytes or to match the starting source archive digest 3fda74ae43e749c369766902340e606328e92ba5f5d5abed27cef1c623ce3e1d.

The first-phase report recorded that no v0.2.0 commit had been created at that time. Current local commit readiness is determined separately in the readiness matrix after corrective checks and review. No push, pull request, package publication, external release, repository visibility change, or GitHub settings change was performed.

## External publication checklist

Complete these steps before public repository preparation or package publication:

1. Run the real Windows junction regression with Python 3.11 and record the result; the Python 3.11 qualification is unresolved until then.
2. Have a maintainer verify or configure private vulnerability reporting. Its current availability is unverified; no contact address is asserted.
3. Execute the configured Windows/Linux GitHub Actions workflows. Their status remains NOT_RUN.
4. Exercise the Codex, Claude Code, and Gemini CLI integrations individually. Their runtime qualification remains NOT_RUN.
5. Check npm and PyPI package-name and registry availability. npm returned E404 and remains unverified; PyPI availability was not checked.
6. After those obligations are complete, recheck package inventories and hashes, then decide separately whether to publish packages or create an external release.

No push, pull request, registry publication, external release, repository visibility change, or GitHub settings change was performed during this corrective phase.
