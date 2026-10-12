# Quickstart

ORQIVRA has independent Python and Node implementations. Choose one route. Each installs an `orqivra` command for the workflow scripts, and neither route needs the other runtime.

## Python source setup

Prerequisites: a checkout or extracted source archive with this directory as its root, Python 3.11 or newer with its `venv` and `pip` modules, and network or package-index access to install the project and its Python dependencies. On Windows, the Python launcher (`py`) is convenient; if it is unavailable, substitute the full path to a Python 3.11 executable for `py` below. From the repository root, create an isolated environment, install the checkout, and add its scripts directory to this PowerShell session's PATH:

```powershell
py -3.11 --version
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
$env:Path = "$PWD\.venv\Scripts;$env:Path"
orqivra --help
```

For POSIX, use Python 3.11 or newer and run:

```sh
python3.11 --version
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
orqivra --help
```

The editable install and PATH update apply to this checkout and shell session. This route requires no Node.js or npm.

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
