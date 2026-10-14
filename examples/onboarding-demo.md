# Operator-driven onboarding demo

This short demonstration uses the Python CLI to validate a one-node plan, run a real check that fails, record the diagnosis and correction, refresh evidence after an input change, rerun the check, and generate a final report. The operator runs each step; the demo does not launch agents, contact a model, or activate a client.

## Prerequisites

- A source checkout of ORQIVRA.
- Python 3.11 or newer with `venv` and `pip`.
- The Python CLI and its dependencies installed using the [Python source setup](../docs/quickstart.md#python-source-setup).

Node.js, a client installation, model credentials, and external services are not used. The demo invokes the installed Python package with the active interpreter. It requires no change to PowerShell execution policy.

## Run from a clean working directory

The script creates a new output directory under the checkout's ignored `scratch/` folder. Its `--output` path must not already exist. On Windows, after completing the Python source setup, run:

```powershell
$repo = (Get-Location).Path
$run = Join-Path $repo ("scratch\onboarding-demo\run-" + [guid]::NewGuid().ToString('N'))
$clean = Join-Path ([IO.Path]::GetTempPath()) ("orqivra-demo-cwd-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $clean | Out-Null
Push-Location $clean
try {
    & "$repo\.venv\Scripts\python.exe" "$repo\examples\onboarding_demo.py" --output $run
    if ($LASTEXITCODE -ne 0) { throw "Demo failed with exit code $LASTEXITCODE." }
} finally {
    Pop-Location
    Remove-Item -LiteralPath $clean -Recurse -Force
}
```

On POSIX:

```sh
set -eu
repo=$PWD
run="$repo/scratch/onboarding-demo/run-$(date +%Y%m%d%H%M%S)-$$"
clean=$(mktemp -d "${TMPDIR:-/tmp}/orqivra-demo-cwd.XXXXXXXX")
trap 'rmdir "$clean"' EXIT
(
  cd "$clean"
  "$repo/.venv/bin/python" "$repo/examples/onboarding_demo.py" --output "$run"
)
```

Both commands launch the example from a fresh working directory outside the checkout. The run output remains under ignored `scratch/`, not under `examples/`. The transcript records every command and result; the final state and report preserve the failed first attempt.

## Expected result

- The first project-name check prints `FAIL: project_name must be a non-empty string` and exits `1` intentionally.
- After the input changes, evidence checking marks the earlier result stale and resume retains attempt one.
- The corrected check prints `PASS: project_name is non-empty` and exits `0`.
- The final report shows the node accepted with attempts `fail`, `pass` and evidence exit codes `1`, `0`.

The generated directory includes `demo-dag.json`, a disposable project, `state.json`, and `transcript.txt`. Review it before deleting that exact run directory under `scratch/onboarding-demo/`.
