# One-shot probe (M10 planning): inspect the P2 backup DB without touching it.
import sqlite3
from pathlib import Path

BAK = Path(__file__).resolve().parents[1] / "process" / "fault_tracker.db.bak-p2-20261102"

con = sqlite3.connect(BAK.as_posix())
tables = [r[0] for r in con.execute(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
print("tables:", tables)
if "alembic_version" in tables:
    print("alembic_version:", con.execute("SELECT version_num FROM alembic_version").fetchall())
print("faults:", con.execute("SELECT COUNT(*) FROM pipeline_faults").fetchone()[0])
print("pipelines:", con.execute("SELECT COUNT(*) FROM pipelines").fetchone()[0])
cols = [r[1] for r in con.execute("PRAGMA table_info(pipeline_faults)")]
print("pipeline_faults cols:", cols)
print("sample row:", con.execute(
    "SELECT id, status, location, occurred_at, closed_at, handling_note "
    "FROM pipeline_faults ORDER BY id LIMIT 3").fetchall())
con.close()
