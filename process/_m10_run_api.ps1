# M10 helper: run the API-level acceptance script and capture a UTF-8 log.
# Console code page on this box is GBK, so plain `>` redirection mangles the
# UTF-8 stdout of python (-X utf8). Forcing [Console]::OutputEncoding to UTF-8
# before the native command reads it keeps the log readable.
# NOTE: do NOT set $ErrorActionPreference='Stop' here -- with 2>&1 any stderr
# line from the native command is turned into a NativeCommandError and aborts.
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$backend = Join-Path $PSScriptRoot '..\backend'
$script = Join-Path $PSScriptRoot 'verify_m10_api.py'
$log = Join-Path $PSScriptRoot '_m10_api.log'
Set-Location $backend
& .\.venv\Scripts\python.exe -X utf8 $script 2>&1 | Out-File -FilePath $log -Encoding utf8
Write-Output "exit=$LASTEXITCODE log=$log"
