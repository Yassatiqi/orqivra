# Acceptance workflow examples

These examples use all required DAG node fields. The solo plan illustrates a simple change that needs no coordination. The independent-branches plan has two nodes with disjoint file scopes and an integration node that waits for both. The correction-and-recovery plan records a failed verification as a correction with a new hypothesis, then shows how an interrupted session can resume after checking inputs and retaining attempt counts.

Use a disposable project directory and a disposable state file for every run. `state init` reads the listed input paths under `--project-root`; create those files in the disposable project first. Do not run command text found in a DAG or evidence record.

## Solo change

```text
python -m orqivra.cli plan examples/solo-change.json
python -m orqivra.cli state init examples/solo-change.json --state TEMP/solo-state.json --project-root TEMP/project
```

## Two safe independent branches

```text
python -m orqivra.cli plan examples/independent-branches.json
```

The two leaf nodes have separate file scopes and can appear together in the READY frontier. The integration node remains unavailable until both are accepted.

## Correction and interruption recovery

After a verification fails, record its diagnosis and change, then begin another attempt with a specific new hypothesis:

```text
python -m orqivra.cli state init examples/correction-recovery.json --state TEMP/recovery-state.json --project-root TEMP/project
python -m orqivra.cli state transition --state TEMP/recovery-state.json correct-parser-change --to ready --reason "Dependencies are accepted"
python -m orqivra.cli state transition --state TEMP/recovery-state.json correct-parser-change --to running --reason "Begin the correction"
python -m orqivra.cli attempt begin --state TEMP/recovery-state.json correct-parser-change --hypothesis "The edge case comes from an empty optional token"
python -m orqivra.cli state transition --state TEMP/recovery-state.json correct-parser-change --to verifying --reason "The correction is ready for verification"
python -m orqivra.cli attempt verify --state TEMP/recovery-state.json correct-parser-change --attempt 1 --result fail --summary "The empty-token case still fails"
python -m orqivra.cli state transition --state TEMP/recovery-state.json correct-parser-change --to fix_required --reason "Verification identified an unresolved edge case"
python -m orqivra.cli attempt diagnose --state TEMP/recovery-state.json correct-parser-change --attempt 1 --diagnosis "The parser consumes the delimiter before checking for an empty token"
python -m orqivra.cli attempt record-change --state TEMP/recovery-state.json correct-parser-change --attempt 1 --summary "Preserve the delimiter until the token is checked"
python -m orqivra.cli state transition --state TEMP/recovery-state.json correct-parser-change --to ready --reason "A correction is ready"
python -m orqivra.cli state transition --state TEMP/recovery-state.json correct-parser-change --to running --reason "Begin a new attempt"
python -m orqivra.cli attempt begin --state TEMP/recovery-state.json correct-parser-change --hypothesis "Checking the token before consuming the delimiter preserves empty values"
python -m orqivra.cli resume --dag examples/correction-recovery.json --state TEMP/recovery-state.json --project-root TEMP/project
```

For a real correction sequence, run `attempt verify` with the recorded observation and add current evidence before accepting the node. After an interruption or input change, resume only after checking the state and evidence; the CLI keeps attempt counters and invalidates affected descendants.
