# 第二阶段：真实开发库副本升级演练（临时脚本，process/ 不入库）。
# 与 verify_p2_migration.py 的区别：数据源不是手拼 fixture，而是当前 fault_tracker.db
# 的逐字节副本（17 条模拟故障），验证"文档步骤"对真实旧库成立。
# 步骤 = README 旧库升级章节：备份副本 -> alembic stamp a74bf448a946 -> upgrade head -> 核对数据。
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
SRC = BACKEND / "fault_tracker.db"

tmp = Path(tempfile.mkdtemp(prefix="p2_drill_"))
db = tmp / "fault_tracker.db"
shutil.copy2(SRC, db)

con = sqlite3.connect(db)
before = con.execute(
    "SELECT id, pipeline_id, location, occurred_at, symptom, status, handling_note, closed_at "
    "FROM pipeline_faults ORDER BY id"
).fetchall()
con.close()
print(f"副本就绪：{len(before)} 条故障")


def alembic(*args: str) -> None:
    env = dict(subprocess.os.environ, DATABASE_URL=f"sqlite:///{db.as_posix()}")
    r = subprocess.run(
        [sys.executable, "-X", "utf8", "-m", "alembic", *args],
        cwd=BACKEND, env=env, capture_output=True, text=True, encoding="utf-8",
    )
    if r.returncode != 0:
        print(r.stdout, r.stderr, file=sys.stderr)
        raise SystemExit(f"alembic {' '.join(args)} 失败")


alembic("stamp", "a74bf448a946")
alembic("upgrade", "head")

con = sqlite3.connect(db)
cols = [r[1] for r in con.execute("PRAGMA table_info(pipeline_faults)")]
after = con.execute(
    "SELECT id, pipeline_id, location, occurred_at, symptom, status, handling_note, closed_at "
    "FROM pipeline_faults ORDER BY id"
).fetchall()
prio = con.execute("SELECT DISTINCT priority FROM pipeline_faults").fetchall()
ver = con.execute("SELECT version_num FROM alembic_version").fetchone()
pipelines = con.execute("SELECT count(*) FROM pipelines").fetchone()[0]
con.close()

ok = True
def check(name: str, passed: bool, detail: str = "") -> None:
    global ok
    print(f"[{'PASS' if passed else 'FAIL'}] {name}{'  ' + detail if detail else ''}")
    ok = ok and passed

check("priority 列已加入", "priority" in cols, str(cols))
check("原 17 条记录逐字段不变（除新列外）", before == after, f"before={len(before)} after={len(after)}")
check("已有故障统一为 normal", prio == [("normal",)], str(prio))
check("版本 = head (b3e19c4d7a52)", ver == ("b3e19c4d7a52",), str(ver))
check("pipelines 主数据完好", pipelines == 2, str(pipelines))
print(f"临时演练库：{db}")
raise SystemExit(0 if ok else 1)
