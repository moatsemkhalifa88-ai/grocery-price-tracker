# Daily run on Windows: ingestion -> dbt -> analytics.
# Called by the scheduled task (see register_task.ps1). Logs go to logs\daily-YYYY-MM-DD.log
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "Virtual environment not found. Run setup first (see docs\RUN_GUIDE_HE.md)." }

New-Item -ItemType Directory -Force -Path (Join-Path $root "logs") | Out-Null
$log = Join-Path $root ("logs\daily-{0}.log" -f (Get-Date -Format "yyyy-MM-dd"))

# dbt.exe lives next to python.exe inside the venv
$env:PATH = (Join-Path $root ".venv\Scripts") + ";" + $env:PATH
$env:PYTHONIOENCODING = "utf-8"

& $python -m pricetracker daily *>&1 | Tee-Object -FilePath $log -Append
exit $LASTEXITCODE
