$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("orqivra-quickstart-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tempRoot | Out-Null
$projectRoot = Join-Path $tempRoot 'project'
New-Item -ItemType Directory -Path $projectRoot | Out-Null
$statePath = Join-Path $tempRoot 'state.json'
$dagPath = Join-Path $repoRoot 'examples\solo-change.json'

orqivra validate dag $dagPath
if ($LASTEXITCODE -ne 0) { throw 'DAG validation failed.' }
orqivra state init $dagPath --state $statePath --project-root $projectRoot
if ($LASTEXITCODE -ne 0) { throw 'State initialization failed.' }
orqivra report --state $statePath
if ($LASTEXITCODE -ne 0) { throw 'Report generation failed.' }
Write-Output "Disposable quickstart directory: $tempRoot"
