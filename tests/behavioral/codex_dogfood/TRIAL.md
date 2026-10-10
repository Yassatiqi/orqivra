# Codex dogfood trial

## Fault observed

The first focused test run used a deliberately incorrect `line == ""` skip check. `python -m unittest discover -s tests/behavioral/codex_dogfood -v` exited 1: the fixture test errored when the whitespace-only second line reached `json.loads`, producing `ValueError: Malformed JSON on line 2`. The empty-input, malformed-JSON, and non-object checks passed.

## Diagnosis and correction

Hypothesis: the skip guard recognizes only an empty string, so a line containing spaces or tabs is treated as a JSON record. The observed line-2 decoding error confirmed the hypothesis. One correction changed the guard to `line.strip() == ""`; no assertions or acceptance criteria changed.

## Final check

The same focused command exited 0 after the correction. All four tests passed, covering empty input, blank and whitespace-only fixture lines, malformed JSON rejection, and non-object rejection with source line numbers. This is self-verification of the focused fixture only; the CLI acceptance suite was not part of this trial.

## ORQIVRA state workflow

The coordinator validated and initialized `dogfood-dag.json`, then recorded contract review, the failing implementation attempt, its diagnosis, one distinct correction attempt, and final verification in `.artifacts/codex-dogfood-state.json`. The coordinator deliberately reintroduced the exact-empty-line guard to reproduce the controlled failure, observed the whitespace-only fixture error, restored the whitespace-aware guard, and reran the unchanged four tests successfully. After removing an unnecessary final blank record from the fixture, the coordinator refreshed its saved evidence through `evidence check`, `resume`, and new verification attempts. All three task nodes ended `accepted`; the current report is certified with no active stale evidence or unresolved gates. Superseded evidence from the prior fixture snapshot remains visible as history. The state file is local, ignored build evidence and contains this workspace's absolute fixture root.

This trial is `SIMULATED`: the Codex runtime did not expose a skill-activation mechanism for the newly installed edition. The worker and coordinator applied the installed Codex skill contracts manually. No client skill invocation or runtime qualification is claimed.
