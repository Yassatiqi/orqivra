# Quickstart

ORQIVRA has independent Python and Node implementations. Choose one route. Each installs an `orqivra` command for the workflow scripts, and neither route needs the other runtime.

## Python source setup

Prerequisites: a checkout or extracted source archive with this directory as its root, Python 3.11 or newer with its `venv` and `pip` modules, and network or package-index access to install the project and its Python dependencies. The commands below select an installed Python 3 interpreter and check that it meets the minimum version before creating an environment. From the repository root, create an isolated environment, install the checkout, and add its scripts directory to this PowerShell session's PATH:

```powershell
py -3 --version
py -3 -c "import sys; assert sys.version_info >= (3, 11), 'Python 3.11 or newer is required'"
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
$env:Path = "$PWD\.venv\Scripts;$env:Path"
orqivra --help
```

If the launcher selects a Python older than 3.11, select an installed supported version explicitly, for example with `py -3.13`, and replace each `py -3` above with that selector. If the launcher is unavailable, use the full path to an installed Python 3.11 or newer executable for those commands. The selected interpreter must include `venv` and `pip`.

On POSIX, use Python 3.11 or newer and run:

```sh
python3 --version
python3 -c "import sys; assert sys.version_info >= (3, 11), 'Python 3.11 or newer is required'"
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
orqivra --help
```

If `python3` selects a version older than 3.11, use an installed supported interpreter such as `python3.12` or its full path, and replace each `python3` above with that command. The selected interpreter must include `venv` and `pip`.

The editable install and PATH update apply to this checkout and shell session. This route requires no Node.js or npm.

The Python venv keeps the `orqivra` command on `PATH` for the workflow scripts. In a different shell, activate `.venv` again or prepend its `Scripts` (Windows) or `bin` (POSIX) directory to `PATH`. You can also run the Python CLI directly as `python -m orqivra.cli`; the Node route below has its own installed command and does not use Python.

## Node source setup

Prerequisites: Node.js 24 or newer, npm, and network or package-cache access for the locked development dependencies. The npm implementation has no production dependencies. From the repository root, install its build tools, build the CLI, pack the built package, and install that package into a temporary prefix so npm exposes its `orqivra` command:

```powershell
node --version
npm.cmd --version
npm.cmd ci --prefix node
npm.cmd run build --prefix node
$nodeCliRoot = Join-Path ([IO.Path]::GetTempPath()) ("orqivra-node-cli-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $nodeCliRoot | Out-Null
Push-Location node
npm.cmd pack --pack-destination $nodeCliRoot
if ($LASTEXITCODE -ne 0) { throw "npm pack failed with exit code $LASTEXITCODE." }
Pop-Location
$nodeTarball = Get-ChildItem $nodeCliRoot -Filter 'orqivra-*.tgz' | Select-Object -First 1
if (-not $nodeTarball) { throw 'npm pack did not create the ORQIVRA package archive.' }
npm.cmd install --prefix $nodeCliRoot --no-save $nodeTarball.FullName
if ($LASTEXITCODE -ne 0) { throw "npm install failed with exit code $LASTEXITCODE." }
$nodeCliBin = "$nodeCliRoot\node_modules\.bin"
$env:Path = "$nodeCliBin;$env:Path"
function orqivra {
    & "$nodeCliBin\orqivra.cmd" @args
    if ($LASTEXITCODE -ne 0) { throw "ORQIVRA exited with code $LASTEXITCODE." }
}
orqivra --help
```

The PowerShell function calls npm's `.cmd` shim directly, so PowerShell does not try to load npm's generated `.ps1` shim. It does not change or bypass the current execution policy.

For POSIX, use:

```sh
node --version
npm --version
npm ci --prefix node
npm run build --prefix node
node_cli_root=$(mktemp -d "${TMPDIR:-/tmp}/orqivra-node-cli.XXXXXXXX")
(cd node && npm pack --pack-destination "$node_cli_root")
node_tarball=$(find "$node_cli_root" -maxdepth 1 -type f -name 'orqivra-*.tgz' -print -quit)
test -n "$node_tarball"
npm install --prefix "$node_cli_root" --no-save "$node_tarball"
PATH="$node_cli_root/node_modules/.bin:$PATH"
export PATH
orqivra --help
```

The temporary npm prefix and PATH update apply to this shell session. This route requires no Python. Remove the temporary prefix after use if desired.

## Inspect an edition and configure a project

Configuration is optional. With no `--config` argument, ORQIVRA looks for `orqivra.config.json` in the current directory. If that automatically discovered file is absent, built-in defaults apply. If you pass `--config PATH`, ORQIVRA reads that exact path and reports an actionable error if it is missing. An existing empty or whitespace-only file and `{}` both inherit the defaults.

From either installed route, inspect the profile without changing client settings or making a provider request:

```text
orqivra config show --edition codex
orqivra config show --edition claude-code --format markdown
orqivra config validate
```

For a project-specific preference, create `orqivra.config.json` at the project root. A partial file inherits every omitted value:

```json
{
  "schema_version": 1,
  "workflow": {
    "preferred_parallelism": 2
  }
}
```

Validate a selected file explicitly with `orqivra config validate --config ./orqivra.config.json`. Preferred parallelism is an advisory maximum, not a promise of that many workers. Actual concurrency depends on available runtime capabilities and resources, dependency readiness, authorization, task independence, and disjoint ownership. The default route is `recommend`; the current task may still need to run solo.

An omitted, null, or empty-string provider/model setting inherits the edition provider and base profile model. If reasoning is omitted and the model is unchanged, the profile value remains. For Codex, the catalog does not enumerate supported reasoning values, so the setting is shown as `UNVERIFIED`, not documented compatibility. After a model change, inherited reasoning carries only when compatibility is known; otherwise validation explains how to select a compatible value or defer to the client with `"reasoning": null`. Explicit values are checked against catalog lists when available; an unenumerated value is accepted structurally and marked `UNVERIFIED`. Null clears the inherited preference and uses the selected model's documented client default where known, otherwise the client's own default. Unknown custom model IDs require `"model_source": "user-supplied"` and remain unqualified; ORQIVRA does not infer their supported reasoning controls.

## Edit, inspect, apply, and run a workflow

This example uses Codex. Before applying it, install the Codex CLI, sign in through its normal client flow, and confirm your account can use the selected model. ORQIVRA does not sign in or test account access. In the project root, create or edit `orqivra.config.json` with a model preference for one role:

```json
{
  "schema_version": 1,
  "editions": {
    "codex": {
      "roles": {
        "orchestrator": {
          "model": "gpt-6-luna",
          "reasoning": {
            "control": "codex.model_reasoning_effort",
            "value": "max"
          }
        }
      }
    }
  }
}
```

Validate and inspect the resolved configuration from the shell where the Python venv or installed npm command is on `PATH`:

```text
orqivra config validate --config ./orqivra.config.json
orqivra config show --edition codex --config ./orqivra.config.json --format markdown
```

Read the generated `client_instructions`, then start a new Codex main session using its command. For this example, the command is:

```text
codex --model gpt-6-luna --config 'model_reasoning_effort="max"'
```

This launch applies the model and effort to that main Codex session, subject to model support and account access. It does not configure Codex subagents or enforce the other ORQIVRA role preferences. Editing the ORQIVRA file alone does not switch a running client. To try ORQIVRA's disposable workflow after returning to a shell, run `examples\quickstart.ps1` in PowerShell or `sh examples/quickstart.sh` on POSIX. The `orqivra` command must remain on `PATH` in that shell; the workflow script uses the installed CLI and does not require the client to be active.

For example, when replacing a role's model but letting the client choose reasoning, use a null preference rather than keeping the old model's setting:

```json
{
  "schema_version": 1,
  "editions": {
    "claude-code": {
      "roles": {
        "complex_implementer": {
          "model": "claude-sonnet-5-5",
          "reasoning": null
        }
      }
    }
  }
}
```

The configuration is advisory. It does not switch the active model, alter account access, grant tools, change client permissions, or prevent provider/client-native routing or fallback. See [compatibility and qualification](compatibility.md#configuration-and-model-profiles).

## Run a disposable workflow

After either route makes `orqivra` available in PATH, run the matching example:

```powershell
.\examples\quickstart.ps1
```

PowerShell applies the current execution policy and any organizational restrictions. Run this local script only when that policy authorizes it. Do not lower policy scope or use an execution-policy bypass to run it. If execution is restricted, use an approved shell or ask the administrator responsible for the policy. You can also enter the equivalent CLI commands directly, using real disposable paths:

```powershell
$tempRoot = Join-Path ([IO.Path]::GetTempPath()) ("orqivra-quickstart-" + [guid]::NewGuid().ToString('N'))
$projectRoot = Join-Path $tempRoot 'project'
New-Item -ItemType Directory -Path $projectRoot | Out-Null
$dagPath = Join-Path $PWD 'examples\solo-change.json'
$statePath = Join-Path $tempRoot 'state.json'
orqivra validate dag $dagPath
orqivra state init $dagPath --state $statePath --project-root $projectRoot
orqivra report --state $statePath
```

On POSIX, run:

```sh
sh examples/quickstart.sh
```

Each script creates a uniquely named disposable project under the operating system's temporary directory, validates `examples/solo-change.json`, initializes state, and prints a report. It does not edit this checkout. Remove the printed temporary directory when you no longer need it.

See [the examples guide](../examples/README.md) for a recovery workflow and [the CLI contract](cli-contract.md) for all commands.
