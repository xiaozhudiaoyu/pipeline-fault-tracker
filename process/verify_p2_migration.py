# 第二阶段迁移验证脚本（临时演练用，process/ 目录不入库）。
#
# 覆盖需求三 / 五的迁移验收点：
#   1. 空库 alembic upgrade head -> 最新结构（含 priority 列）        [需求三.1]
#   2. 旧库（v1 结构 + 模拟数据，未 stamp）-> stamp 基线 -> upgrade head
#      -> 记录数/编号/状态/说明不变，已有故障统一为 normal            [需求三.2/三.3]
#   3. downgrade -1 -> priority 列消失；再 upgrade head -> 列回来     [回退手段演练]
#
# 用法（在 backend/ 或任意目录）: .venv/Scripts/python.exe -X utf8 ../process/verify_p2_migration.py
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
DB_NAME = "p2_verify.db"

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}{'  ' + detail if detail else ''}")
    if not ok:
        failures.append(name)


def alembic(workdir: Path, *args: str) -> subprocess.CompletedProcess:
    """在 workdir（backend/）下跑 alembic，DATABASE_URL 经环境变量指向目标库。

    走 subprocess + env 字典而非 shell 内联设变量：规避 PowerShell 引号坑
    与沙箱对含 DATABASE_URL 赋值命令的拦截（用户级规则 6.1 / 长期记忆坑点）。
    """
    env = dict(os.environ, DATABASE_URL=f"sqlite:///{(workdir / DB_NAME).as_posix()}")
    r = subprocess.run(
        [sys.executable, "-X", "utf8", "-m", "alembic", *args],
        cwd=BACKEND, env=env, capture_output=True, text=True, encoding="utf-8",
    )
    if r.returncode != 0 and args[0] != "check":
        print(r.stdout)
        print(r.stderr, file=sys.stderr)
        raise SystemExit(f"alembic {' '.join(args)} 执行失败（rc={r.returncode}）")
    return r


def cols(db: Path) -> list[str]:
    con = sqlite3.connect(db)
    try:
        return [r[1] for r in con.execute("PRAGMA table_info(pipeline_faults)")]
    finally:
        con.close()


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="p2_mig_"))
    db = tmp / DB_NAME

    # ── 1. 空库初始化 ──────────────────────────────────────────────
    alembic(tmp, "upgrade", "head")
    c = cols(db)
    check("空库 upgrade head 后 pipeline_faults 存在 priority 列", "priority" in c, str(c))

    # ── 2. 旧库（v1 结构 + 数据，无 alembic_version）接入迁移 ──────
    tmp2 = tmp / "legacy"
    tmp2.mkdir(exist_ok=True)
    db2 = tmp2 / DB_NAME
    con = sqlite3.connect(db2)
    con.executescript(
        """
        CREATE TABLE pipelines (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            code VARCHAR(50) NOT NULL UNIQUE,
            name VARCHAR(100) NOT NULL,
            description TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
        );
        CREATE TABLE pipeline_faults (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            pipeline_id INTEGER NOT NULL REFERENCES pipelines(id) ON DELETE CASCADE,
            location VARCHAR(200) NOT NULL,
            occurred_at DATETIME NOT NULL,
            symptom TEXT NOT NULL,
            status VARCHAR(10) NOT NULL,
            handling_note TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            closed_at DATETIME
        );
        INSERT INTO pipelines (id, code, name) VALUES (1, 'LINE-A', '总装线A'), (2, 'LINE-B', '总装线B');
        INSERT INTO pipeline_faults (id, pipeline_id, location, occurred_at, symptom, status, handling_note)
        VALUES (1, 1, '3号工位', '2026-09-01 08:00:00', '传送带卡死', 'done', '更换轴承后恢复'),
               (2, 1, '5号工位', '2026-09-02 09:30:00', '异响', 'pending', NULL),
               (3, 2, '1号工位', '2026-09-03 10:00:00', '传感器失灵', 'processing', NULL);
        """
    )
    con.commit()
    con.close()

    # 旧库接入点：先 stamp 当前所在版本（只写版本号，不动数据），再 upgrade
    alembic(tmp2, "stamp", "a74bf448a946")
    alembic(tmp2, "upgrade", "head")

    con = sqlite3.connect(db2)
    c2 = [r[1] for r in con.execute("PRAGMA table_info(pipeline_faults)")]
    check("旧库升级后 priority 列存在", "priority" in c2, str(c2))
    rows = con.execute("SELECT id, status, handling_note, priority FROM pipeline_faults ORDER BY id").fetchall()
    expected = [
        (1, "done", "更换轴承后恢复", "normal"),
        (2, "pending", None, "normal"),
        (3, "processing", None, "normal"),
    ]
    check("旧数据保留且已有故障统一为 normal（编号/状态/说明不变）", rows == expected, repr(rows))
    ver = con.execute("SELECT version_num FROM alembic_version").fetchall()
    check("版本推进到 head（b3e19c4d7a52）", ver == [("b3e19c4d7a52",)], repr(ver))
    con.close()

    # ── 3. 回退与重升 ──────────────────────────────────────────────
    # 注意：SQLite 的 ALTER COLUMN ... DROP DEFAULT 是无效语法（离线 --sql 生成的那行
    # 在 SQLite 上实测是否会报错，正是本段要回答的）。
    alembic(tmp2, "downgrade", "-1")
    check("downgrade 后 priority 列消失", "priority" not in cols(db2))
    alembic(tmp2, "upgrade", "head")
    check("重升后 priority 列恢复", "priority" in cols(db2))
    con = sqlite3.connect(db2)
    n = con.execute("SELECT count(*), sum(priority='normal') FROM pipeline_faults").fetchone()
    check("重升后数据仍完整且全为 normal", n == (3, 3), repr(n))
    con.close()

    # ── 4. 空库初始化产物与模型无新增漂移（autogenerate 体检）──────
    # 用 db（纯 alembic 链产物）而非 db2：手工拼的 legacy fixture 无 ix 索引/表级约束，
    # batch 重建也会丢命名 FK —— 那些 drift 属 fixture 伪影，拿来体检会误报。
    r = alembic(tmp, "check")
    check("alembic check 无 drift（alembic 产物库与 models.py 一致）", r.returncode == 0,
          (r.stdout + r.stderr).strip().splitlines()[-1] if (r.stdout + r.stderr).strip() else "")

    print()
    if failures:
        print(f"共 {len(failures)} 项失败：{failures}")
        raise SystemExit(1)
    print(f"全部通过（临时目录：{tmp}）")


if __name__ == "__main__":
    main()
