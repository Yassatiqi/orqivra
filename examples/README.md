# Workflow examples

The JSON examples use all required DAG node fields. The solo plan illustrates a one-node change. The independent-branches plan has two nodes with disjoint file scopes and an integration node that waits for both. The correction-and-recovery plan records a failed verification, requires a diagnosis before another attempt, and demonstrates resume with counters preserved.

Run `examples/quickstart.ps1` on Windows or `examples/quickstart.sh` on POSIX to validate `solo-change.json`, initialize a state file, and print a report in a uniquely named temporary directory. Each script requires an installed `orqivra` executable on PATH. The [quickstart setup guide](../docs/quickstart.md) gives complete Python and Node source setup commands that expose this executable without requiring the other runtime. On Windows, run the PowerShell script only when the current execution policy and organizational rules authorize it; do not bypass a restriction. Review the printed path and remove that disposable directory when finished. The scripts never write into this checkout.

For manual commands, use absolute paths for the disposable project and state file:

```text
orqivra plan examples/solo-change.json
orqivra state init examples/solo-change.json --state PATH/state.json --project-root PATH/project
```

The solo example declares no input files, so it needs no fixture files. The recovery example includes a sample correction sequence; use a fresh state file for it and do not copy recorded command text into a shell without reviewing it. ORQIVRA records commands as evidence and does not execute them.
