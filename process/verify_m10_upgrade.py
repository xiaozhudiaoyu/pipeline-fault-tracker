# M10 验收脚本（一）：需求九.1 数据库双路径回归 —— 空库初始化 / 第二阶段旧库升级。
#
# 对应计划（process/_p3_implementation_plan.md · M10）口径：
#   「按需求九.1~9.6 逐场景执行：空库初始化 + 旧库升级双路径……」
# 覆盖需求条目：
#   九.1  「分别验证空库初始化和第二阶段数据库升级」
#   六.1  「原故障编号、优先级、处理说明、状态及其他数据都应保留，
#          不能靠删除数据库或重新录入解决」
#   七.3  「多次启动不能清空数据或重复添加演示记录」（迁移幂等 + create_admin 幂等）
#   七.4  「初始管理员账号密码可配置；再次执行不重复创建、不擅自重置密码」
#   八.2  「交付前自行解压检查……启动步骤」（本脚本即按 README 10.1 / 10.2 命令序列照抄）
#
# 三条路径，全部在 process/_m10_scratch/ 下的临时库副本上跑，
# 【不碰】backend/fault_tracker.db 真实开发库，也【不改动】process 下的备份文件
# （规则 2.6：迁移属不可逆操作，只在副本上演练，真实库执行由人工）：
#   A 空库路径：不存在的库文件 → alembic upgrade head → 五表齐、版本=head、
#              故障表含 priority/created_by_id/assignee_id → 重跑 upgrade head 幂等
#              → create_admin ×2（密码走环境变量）幂等且不重置哈希、明文不入库
#   B 旧库路径：复制 P2 备份（停在 a74bf448a946，2 流水线 / 17 故障）→ 全字段快照
#              → upgrade head → 逐行逐字段比对不变，新增列留 NULL，新表为空
#   C 无标记历史卷路径（README 10.2 告警与接管步骤）：副本上 DROP alembic_version
#              → 直接 upgrade head 【应当失败】（基线 CREATE TABLE 撞已存在表）
#              → 按 README stamp a74bf448a946 → upgrade head 成功 → 数据仍逐字段不变
#
# 用法（在 backend/ 目录）：.venv\Scripts\python.exe -X utf8 ..\process\verify_m10_upgrade.py [--keep]
#   --keep：保留临时库目录便于手工复核（默认跑完删除）
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
SCRATCH = ROOT / "process" / "_m10_scratch"
P2_BACKUP = ROOT / "process" / "fault_tracker.db.bak-p2-20261102"

HEAD_REV = "105a10b2f697"      # 迁移链最新版本（README 十节）
PRE_P3_REV = "a74bf448a946"    # P2 备份库停留的版本，也是 README 10.2 的 stamp 目标
ADMIN_PASSWORD = "m10-admin-passw0rd"  # 仅本次演练的一次性口令，不代表任何真实账号

EXPECTED_TABLES = {"pipelines", "pipeline_faults", "users", "fault_timelines", "alembic_version"}
FAULT_COLUMNS = [
    "id", "pipeline_id", "location", "occurred_at", "symptom", "status",
    "handling_note", "created_at", "updated_at", "closed_at",
]

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}{'  ' + detail if detail else ''}")
    if not ok:
        failures.append(name)


def db_url(db: Path) -> str:
    return f"sqlite:///{db.as_posix()}"


def _run(cmd: list[str], cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess:
    """子进程执行：统一按 utf-8 解码并容错。

    坑：alembic / create_admin 在中文 Windows 上会向 stderr 输出 GBK 字节（如
    “（coming from ...）”路径告警），text=True + encoding=utf-8 不加 errors 会在
    读线程里直接 UnicodeDecodeError（脚本结论没错，但日志满屏堆栈）。取错误文本
    只用于人工看，errors="replace" 不影响的判定（判定看 rc）。
    """
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def alembic(db: Path, *args: str, expect_fail: bool = False) -> subprocess.CompletedProcess:
    """对指定库文件跑 alembic（DATABASE_URL 经 env 注入，不走 shell 内联变量）。

    expect_fail=True 时反过来：rc 非 0 才算通过，rc=0 记一条 FAIL（防"该失败却成功"被当成好消息）。
    """
    env = dict(os.environ, DATABASE_URL=db_url(db))
    r = _run([sys.executable, "-X", "utf8", "-m", "alembic", *args], BACKEND, env)
    if expect_fail:
        if r.returncode == 0:
            check(f"alembic {' '.join(args)} 应失败却成功", False, str(db.name))
        return r
    if r.returncode != 0:
        print(r.stdout)
        print(r.stderr, file=sys.stderr)
        raise SystemExit(f"alembic {' '.join(args)} 失败（rc={r.returncode}）：{db.name}")
    return r


def run_create_admin(db: Path, *, with_password: bool = True,
                     username: str | None = None) -> subprocess.CompletedProcess:
    """跑一次 create_admin.py：DATABASE_URL / ADMIN_PASSWORD 均经 env 注入，不落盘。"""
    env = dict(os.environ, DATABASE_URL=db_url(db))
    if with_password:
        env["ADMIN_PASSWORD"] = ADMIN_PASSWORD
    else:
        env.pop("ADMIN_PASSWORD", None)
    if username is not None:
        env["ADMIN_USERNAME"] = username
    return _run([sys.executable, "-X", "utf8", "create_admin.py"], BACKEND, env)


def query(db: Path, sql: str, params: tuple = ()) -> list[tuple]:
    """只读直查（规则 4.3：不信工具返回，信磁盘现状）。"""
    con = sqlite3.connect(db.as_posix())
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


def execute(db: Path, sql: str) -> None:
    """对临时库副本执行写操作（仅 C 路径造「无版本标记的历史卷」用，绝不作用于备份库）。"""
    con = sqlite3.connect(db.as_posix())
    try:
        con.execute(sql)
        con.commit()
    finally:
        con.close()


def scalar(db: Path, sql: str, params: tuple = ()):
    rows = query(db, sql, params)
    return rows[0][0] if rows else None


def table_names(db: Path) -> set[str]:
    return {r[0] for r in query(db, "SELECT name FROM sqlite_master WHERE type='table'")}


def column_names(db: Path, table: str) -> list[str]:
    return [r[1] for r in query(db, f"PRAGMA table_info({table})")]


def version_num(db: Path) -> str | None:
    if "alembic_version" not in table_names(db):
        return None
    rows = query(db, "SELECT version_num FROM alembic_version")
    return rows[0][0] if rows else None


def fault_snapshot(db: Path) -> list[tuple]:
    """P2 旧库全部业务字段快照（升级前后逐行比对用，不含新增列）。"""
    cols = ", ".join(FAULT_COLUMNS)
    return query(db, f"SELECT {cols} FROM pipeline_faults ORDER BY id")


# ── 路径 A：空库初始化（需求九.1 前半 + 七.4）────────────────────────
def path_a_empty() -> None:
    print("\n===== A 空库初始化（README 10.1）=====")
    db = SCRATCH / "a_empty.db"
    if db.exists():
        db.unlink()

    alembic(db, "upgrade", "head")
    tables = table_names(db)
    check("A1 空库一次 upgrade head 建全五表", EXPECTED_TABLES <= tables, str(sorted(tables)))
    check("A2 库内版本=head（105a10b2f697）", version_num(db) == HEAD_REV, str(version_num(db)))
    fault_cols = column_names(db, "pipeline_faults")
    check(
        "A3 pipeline_faults 含第三/二阶段新列",
        {"priority", "created_by_id", "assignee_id"} <= set(fault_cols),
        str([c for c in fault_cols if c in ("priority", "created_by_id", "assignee_id")]),
    )
    user_cols = set(column_names(db, "users"))
    check(
        "A4 users 表含认证列",
        {"username", "password_hash", "role", "is_active", "token_version"} <= user_cols,
    )
    tl_cols = set(column_names(db, "fault_timelines"))
    check(
        "A5 fault_timelines 含前后值与导入标记列",
        {"action", "operator_id", "from_status", "to_status",
         "from_assignee_id", "to_assignee_id", "note", "is_imported"} <= tl_cols,
    )

    # 幂等：反复 upgrade head 不清库、不报错（容器 entrypoint 每次启动都跑）
    alembic(db, "upgrade", "head")
    check("A6 重复 upgrade head 幂等（版本不变、表不减）",
          version_num(db) == HEAD_REV and EXPECTED_TABLES <= table_names(db))

    # 初始管理员：密码走环境变量；重复执行不重建、不重置
    r = run_create_admin(db)
    check("A7 create_admin 首次执行成功（rc=0）", r.returncode == 0, f"rc={r.returncode}")
    rows = query(db, "SELECT username, password_hash FROM users")
    check("A8 建出 1 个 admin 账号", len(rows) == 1 and rows[0][0] == "admin", str(rows))
    hashed = rows[0][1]
    check("A9 密码入库为 bcrypt 哈希（$2b$）", hashed.startswith("$2b$"), hashed[:7])
    check("A10 明文口令不在库内任何字段",
          ADMIN_PASSWORD not in " ".join(str(c) for row in rows for c in row))

    r = run_create_admin(db)  # 第二次：已存在即跳过
    rows2 = query(db, "SELECT username, password_hash FROM users")
    check("A11 重跑 create_admin 不重复建号", len(rows2) == 1, str(len(rows2)))
    check("A12 重跑 create_admin 不擅自重置密码（哈希不变）", rows2[0][1] == hashed)

    # 空库 + 不给口令：应中止而不是用默认密码建号（需求七.4「不写死密码」反证）
    db2 = SCRATCH / "a_empty_guard.db"
    if db2.exists():
        db2.unlink()
    alembic(db2, "upgrade", "head")
    r = run_create_admin(db2, with_password=False)
    check("A13 缺 ADMIN_PASSWORD 时中止（rc!=0）", r.returncode != 0, f"rc={r.returncode}")
    check("A14 中止时零账号写入",
          (scalar(db2, "SELECT COUNT(*) FROM users") or 0) == 0)


# ── 路径 B：第二阶段旧库升级（需求九.1 后半 + 六.1）───────────────────
def path_b_upgrade() -> None:
    print("\n===== B P2 旧库 upgrade head（README 10.1/10.2 主线）=====")
    db = SCRATCH / "b_p2_upgrade.db"
    shutil.copyfile(P2_BACKUP, db)

    before_ver = version_num(db)
    before_faults = fault_snapshot(db)
    before_pipelines = scalar(db, "SELECT COUNT(*) FROM pipelines")
    check("B1 副本起点确认为 P2 结构（a74bf448a946 / 17 故障 / 无 priority 列）",
          before_ver == PRE_P3_REV
          and len(before_faults) == 17
          and "priority" not in column_names(db, "pipeline_faults"),
          f"ver={before_ver} faults={len(before_faults)} pipelines={before_pipelines}")

    alembic(db, "upgrade", "head")

    after_ver = version_num(db)
    after_faults = fault_snapshot(db)
    check("B2 升级后版本=head", after_ver == HEAD_REV, str(after_ver))
    check("B3 故障行数不变（未删库重录）", len(after_faults) == len(before_faults),
          f"{len(before_faults)} → {len(after_faults)}")
    diff = [(b, a) for b, a in zip(before_faults, after_faults) if b != a]
    check("B4 原 17 行逐字段不变（编号/流水线/位置/发生时间/现象/状态/说明/创建/更新/完成时间）",
          not diff, f"{len(diff)} 行有差异")
    if diff:
        for b, a in diff[:3]:
            print("   before:", b)
            print("   after :", a)

    # 六.1：旧库升级时 priority 回填 normal；六.2：人员关联留 NULL，不随意分配
    check("B5 旧行 priority 回填为 normal（非 NULL、非乱值）",
          scalar(db, "SELECT COUNT(*) FROM pipeline_faults WHERE priority IS NULL "
                     "OR priority <> 'normal'") == 0)
    check("B6 旧行 created_by_id / assignee_id 留 NULL（未关联账号）",
          scalar(db, "SELECT COUNT(*) FROM pipeline_faults WHERE created_by_id IS NOT NULL "
                     "OR assignee_id IS NOT NULL") == 0)
    check("B7 新表 users / fault_timelines 为空（未编造历史操作人）",
          scalar(db, "SELECT COUNT(*) FROM users") == 0
          and scalar(db, "SELECT COUNT(*) FROM fault_timelines") == 0)
    check("B8 流水线主数据保留", scalar(db, "SELECT COUNT(*) FROM pipelines") == before_pipelines)
    done_rows = scalar(db, "SELECT COUNT(*) FROM pipeline_faults WHERE status='done'")
    done_closed = scalar(db, "SELECT COUNT(*) FROM pipeline_faults WHERE status='done' "
                             "AND closed_at IS NULL")
    check("B9 原已完成故障仍为 done 且保留完成时间（六.3）",
          (done_rows or 0) > 0 and done_closed == 0, f"done={done_rows} 缺closed_at={done_closed}")

    # 升级后再跑一次：结构不动、数据不减（对应七.3 容器反复启动）
    alembic(db, "upgrade", "head")
    check("B10 升级后重复 upgrade head 不改动数据", fault_snapshot(db) == after_faults)


# ── 路径 C：无 alembic_version 的历史卷（README 10.2 告警 + 接管步骤）──
def path_c_unstamped() -> None:
    print("\n===== C 无版本标记的历史卷（README 10.2 告警复现与接管）=====")
    db = SCRATCH / "c_unstamped.db"
    shutil.copyfile(P2_BACKUP, db)
    execute(db, "DROP TABLE alembic_version")
    before_faults = fault_snapshot(db)
    check("C1 造出「建过表但无 alembic_version」的历史卷",
          "alembic_version" not in table_names(db) and len(before_faults) == 17)

    r = alembic(db, "upgrade", "head", expect_fail=True)
    check("C2 直接 upgrade head 如 README 所述失败（基线 CREATE TABLE 撞已存在表）",
          r.returncode != 0, f"rc={r.returncode}")
    check("C3 失败未破坏原有数据（17 行原样）", fault_snapshot(db) == before_faults)

    alembic(db, "stamp", PRE_P3_REV)
    check("C4 stamp 只写版本号、不动数据",
          version_num(db) == PRE_P3_REV and fault_snapshot(db) == before_faults)

    alembic(db, "upgrade", "head")
    check("C5 stamp 后接管升级到 head", version_num(db) == HEAD_REV)
    after_cols = set(column_names(db, "pipeline_faults"))
    check("C6 接管后结构与空库一致",
          {"priority", "created_by_id", "assignee_id"} <= after_cols)
    check("C7 接管全程数据零丢失（逐字段比对）", fault_snapshot(db) == before_faults)


def main() -> int:
    keep = "--keep" in sys.argv
    if not P2_BACKUP.exists():
        raise SystemExit(f"缺少 P2 备份库：{P2_BACKUP}")
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    SCRATCH.mkdir(parents=True)

    try:
        path_a_empty()
        path_b_upgrade()
        path_c_unstamped()
    finally:
        if keep:
            print(f"\n临时库保留在：{SCRATCH}")
        else:
            shutil.rmtree(SCRATCH, ignore_errors=True)

    print(f"\n以上为逐项结果；失败项 {len(failures)} 个"
          + (f"：{failures}" if failures else "（全部通过）"))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
