#!/usr/bin/env pwsh
# Thin wrapper so you can type `.\radar.ps1 run` instead of the full venv path.
$ErrorActionPreference = "Stop"
$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }
& $py -m radar @args
exit $LASTEXITCODE
