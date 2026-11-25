Set-Location (Join-Path (Split-Path $PSScriptRoot -Parent) 'backend')
$py = @'
import sqlite3
con = sqlite3.connect("fault_tracker.db")
cur = con.cursor()
print("--- alembic_version ---")
for r in cur.execute("SELECT version_num FROM alembic_version"):
    print(r[0])
print("--- tables ---")
for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
    print(r[0])
print("--- users DDL ---")
for r in cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='users'"):
    print(r[0])
print("--- users row count ---")
try:
    print(cur.execute("SELECT COUNT(*) FROM users").fetchone()[0])
except Exception as e:
    print("ERR:", e)
print("--- pipeline_faults columns ---")
for r in cur.execute("PRAGMA table_info(pipeline_faults)"):
    print(r[1])
print("--- fault_timelines DDL ---")
for r in cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='fault_timelines'"):
    print(r[0])
print("--- fault_timelines row count ---")
print(cur.execute("SELECT COUNT(*) FROM fault_timelines").fetchone()[0])
print("--- indexes on fault_timelines ---")
for r in cur.execute("PRAGMA index_list(fault_timelines)"):
    print(r)
print("--- all indexes in db ---")
for r in cur.execute("SELECT name, tbl_name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'"):
    print(r)
'@
$tmpPy = Join-Path (Get-Location) 'check_db_state_tmp.py'
$py | Out-File -FilePath $tmpPy -Encoding utf8
.\.venv\Scripts\python.exe $tmpPy
Remove-Item $tmpPy
Get-ChildItem (Join-Path $PSScriptRoot 'fault_tracker.db.bak*') | Select-Object Name, Length, LastWriteTime | Format-Table -AutoSize
Get-ChildItem (Join-Path (Split-Path $PSScriptRoot -Parent) 'backend\fault_tracker.db') | Select-Object Name, Length, LastWriteTime | Format-Table -AutoSize
