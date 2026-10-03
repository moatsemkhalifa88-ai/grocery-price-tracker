# One-time setup on Windows (run from the project folder):
#   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

# Prefer Python 3.12 via the py launcher; fall back to whatever "python" is.
$made = $false
if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3.12 --version *> $null
    if ($LASTEXITCODE -eq 0) { & py -3.12 -m venv .venv; $made = ($LASTEXITCODE -eq 0) }
}
if (-not $made) { & python -m venv .venv }
if (-not (Test-Path ".venv\Scripts\python.exe")) { throw "Could not create .venv - is Python 3.10+ installed and on PATH?" }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\python.exe -m pip install -e . --no-deps
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env"; Write-Host "Created .env - open it and paste your DATABASE_URL." }
Write-Host "Setup done. Next: .\.venv\Scripts\python.exe -m pricetracker migrate"
