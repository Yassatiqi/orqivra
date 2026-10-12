# Quickstart

ORQIVRA provides two independent implementations. Choose the one matching the runtime already available in your environment.

## Use the Python CLI

Python 3.11 or newer is required. From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\orqivra.exe --help
```

On POSIX, activate `.venv` with `source .venv/bin/activate`, then run `python -m pip install -e .` and `orqivra --help`.

## Use the Node CLI

Node.js 24 or newer is required. From the repository root:

```powershell
npm.cmd ci --prefix node
npm.cmd run build --prefix node
node node/dist/cli.js --help
```

On POSIX, use `npm ci --prefix node`, `npm run build --prefix node`, then `node node/dist/cli.js --help`. This path does not require Python.

## Run a disposable workflow

After either `orqivra` command is available in PATH, run one of:

```powershell
powershell -ExecutionPolicy Bypass -File examples/quickstart.ps1
```

```sh
sh examples/quickstart.sh
```

Each script creates a uniquely named disposable project under the operating system's temporary directory, validates `examples/solo-change.json`, initializes state, and prints a report. It does not edit this checkout. Remove the printed temporary directory when you no longer need it.

See [the examples guide](../examples/README.md) for a recovery workflow and [the CLI contract](cli-contract.md) for all commands.
