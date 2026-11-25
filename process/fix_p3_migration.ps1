# Repair P3 migration conflict: create_all() pre-created users/fault_timelines
# (both 0 rows, verified) while alembic_version stuck at b3e19c4d7a52.
# Plan A: backup -> drop the 3 pre-created objects -> alembic upgrade head -> verify.
# Rollback: copy the backup file below back over backend/fault_tracker.db.

$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$backend = Join-Path $root 'backend'
$db = Join-Path $backend 'fault_tracker.db'
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$bak = Join-Path $PSScriptRoot ("fault_tracker.db.bak-p3fix-" + $stamp)

Write-Output "[1] backup -> $bak"
Copy-Item $db $bak
Write-Output ("    backup size: " + (Get-Item $bak).Length)

Set-Location $backend

$dropPy = Join-Path $backend 'drop_precreated_tmp.py'
@'
import sqlite3
con = sqlite3.connect("fault_tracker.db")
cur = con.cursor()
# drop child table index/table first, then the referenced users table
cur.execute("DROP INDEX IF EXISTS ix_fault_timelines_fault_id")
cur.execute("DROP TABLE IF EXISTS fault_timelines")
cur.execute("DROP TABLE IF EXISTS users")
con.commit()
print("[2] dropped. remaining tables:")
for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
    print("   ", r[0])
'@ | Out-File -FilePath $dropPy -Encoding utf8
.\.venv\Scripts\python.exe $dropPy
Remove-Item $dropPy

Write-Output "[3] alembic upgrade head"
.\.venv\Scripts\alembic.exe upgrade head

$verifyPy = Join-Path $backend 'verify_tmp.py'
@'
import sqlite3
con = sqlite3.connect("fault_tracker.db")
cur = con.cursor()
print("[4] verify:")
print("  alembic_version:", [r[0] for r in cur.execute("SELECT version_num FROM alembic_version")])
print("  tables:", [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")])
cols = [r[1] for r in cur.execute("PRAGMA table_info(pipeline_faults)")]
print("  pipeline_faults has created_by_id/assignee_id:",
      "created_by_id" in cols and "assignee_id" in cols)
print("  fault data intact:", cur.execute("SELECT COUNT(*) FROM pipeline_faults").fetchone()[0], "faults,",
      cur.execute("SELECT COUNT(*) FROM pipelines").fetchone()[0], "pipelines")
'@ | Out-File -FilePath $verifyPy -Encoding utf8
.\.venv\Scripts\python.exe $verifyPy
Remove-Item $verifyPy
