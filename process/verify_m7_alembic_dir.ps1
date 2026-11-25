# M7-4 verification: alembic upgrade head with DATABASE_URL pointing at a
# nested directory that does not exist yet (requirement 5.4 scenario).
# ASCII-only body; scratch dir is removed by cleanup step in the repo.
param(
    [string]$BackendDir = (Split-Path -Parent $PSScriptRoot) + "\backend"
)

Set-Location $BackendDir
$scratch = ".\m7_scratch_check"
if (Test-Path $scratch) { Remove-Item -Recurse -Force $scratch }

$env:DATABASE_URL = "sqlite:///$scratch/nested/fault_tracker.db"
Write-Output ("parent dir before: " + (Test-Path "$scratch\nested"))

& .venv\Scripts\python.exe -m alembic upgrade head
Write-Output ("alembic exit code: " + $LASTEXITCODE)

Write-Output ("parent dir after : " + (Test-Path "$scratch\nested"))
Write-Output ("db file after    : " + (Test-Path "$scratch\nested\fault_tracker.db"))
Write-Output ("tables (alembic current): " + (& .venv\Scripts\python.exe -m alembic current 2>&1 | Out-String))
