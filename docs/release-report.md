# ORQIVRA v0.1.0 Release Report

## Outcome

The v0.1.0 implementation and release artifact are complete. The shared Python CLI, nine schemas, provider-neutral contracts, generic and MIP adapters, three static client editions, twelve skills, three profiles, examples, and installation workflow are present. Fresh reviews found and drove corrections for stale acceptance/reporting, missing Markdown integrity diagnostics, and unrecoverable manual obsoletion. Each correction has regression coverage. The final fresh reviewer returned `ship` for the corrected implementation snapshot with fingerprint `bb645b682b567cb9e003a73b075684ded2722a6eb1487f75d94aafd7b0732abe`.

## Verification evidence

- `python -m compileall -q src tests` completed successfully.
- `.venv\Scripts\python.exe -m unittest discover -s tests -v` ran 27 tests: 26 passed and one skipped. Coverage includes changed inputs or artifacts before acceptance, JSON and Markdown reporting without `evidence check`, visibility of superseded stale history, recovery using new active evidence, descendant invalidation on manual obsoletion, and interrupted active attempts requiring diagnosis. The symlink-scope test was skipped because this Windows account could not create a symlink (`WinError 1314`); it is not counted as passed.
- All nine JSON Schemas passed `Draft202012Validator.check_schema`.
- CLI validation passed for the dogfood project, all three profiles, all three example DAGs, and all twelve source-edition skills. Building all editions from the installed wheel also succeeded; all twelve packaged skills and three packaged profiles validated.
- The disposable Codex installation path contained spaces. Dry-run, apply, manifest verification, uninstall dry-run, and uninstall apply succeeded. An unrelated sentinel file survived uninstall.
- The controlled parser dogfood passed its focused four-test suite after one correction. The parent re-injected and observed the same intentional defect, restored the correction, and reran the unchanged tests successfully. The trial and saved state report are in `tests/behavioral/codex_dogfood/TRIAL.md` and local ignored evidence.
- Interruption recovery preserved interrupted attempt 1, accepted a distinct second attempt, and produced a certified report with no stale evidence or unresolved gates. CLI frontier and local-block observations are recorded in `docs/behavioral-trials.md`.
- MIP adapter tests verify that obligations remain `DEFERRED_EXTERNAL` unless final-sprint observation and evidence are both present. The framework test suite also verifies that an unresolved required external gate blocks certification. No MIP-specific external obligation was declared for this ORQIVRA repository build, and no external MIP runtime validation is claimed.
- A scan of 68 text files (`.md`, `.py`, `.json`, `.toml`, `.txt`, `.yaml`, and `.yml`) found no Unicode replacement characters. The scan excluded `.git`, `.venv`, `build`, `dist`, `.artifacts`, and `__pycache__`; generated `src/orqivra.egg-info` was removed before counting. The repository snapshot contains 71 non-generated files. This is a corruption check, not a perfect language detector; authored deliverables were also inspected for English compliance.

## Distribution

The release wheel is `dist/orqivra-0.1.0-py3-none-any.whl`, 70,752 bytes, SHA-256 `8d06e761fe2f23d1a0f3a90eb08fc689ca5ed0913dde8c04f257595981292871`. It contains 43 entries, including all twelve skill resources, nine schemas, and three profiles. The installed-wheel fallback built standalone bundles for Codex, Claude Code, and Gemini CLI under the ignored `.artifacts/final-obsoletion-wheel-bundle/` directory.

Build command:

```text
.venv\Scripts\python.exe -m pip wheel --no-deps --no-build-isolation --no-cache-dir --wheel-dir dist .
```

## Edition qualification

| Edition | Static validation | Runtime qualification | Profile |
|---|---|---|---|
| Codex | Four skills and packaged bundle valid | `SIMULATED`: the session exposed no skill-discovery invocation; manual contract application only | Requested model and effort values preserved; unvalidated and non-activatable |
| Claude Code | Four skills and packaged bundle valid | `NOT_RUN`: `claude` was unavailable | User-supplied sample values unresolved and non-activatable |
| Gemini CLI | Four skills and packaged bundle valid | `NOT_RUN`: `gemini` was unavailable | User-supplied sample values unresolved and non-activatable |

The current Codex profile preserves `gpt-6-astra/high`, `gpt-6-luna/max`, `gpt-6-sol/xhigh` for complex implementation, and `gpt-6-sol/high` for review. It does not claim those identifiers or efforts are supported by the target runtime.

## Resource metrics and limitations

No account-wide token, billing, provider quota, or model-usage metrics were available. No token or cost values are inferred from word counts or file sizes. The four skill bodies in each edition passed the 500-900 word format bound.

The symlink test remains unexecuted on this Windows account. Claude Code and Gemini CLI runtime checks remain `NOT_RUN`; Codex skill activation remains `SIMULATED`. These qualifications do not hide static edition validation or local CLI execution. No external publication or deployment was performed.

## Git and review

The repository began without a commit or project files. Local delivery commit `Build ORQIVRA v0.1.0` was created using the configured Git identity and amended to include the final release report. No push or pull request was made.

Fresh read-only reviews found three concrete defects, all now addressed: acceptance/reporting stale-evidence checks, omitted Markdown integrity diagnostics, and explicit obsoletion that could not be resumed. The final reviewer inspected the 71-file implementation snapshot read-only and returned `ship`; the review did not rerun the full test suite. The independent test, schema, packaging, and installer verification evidence is listed above.
