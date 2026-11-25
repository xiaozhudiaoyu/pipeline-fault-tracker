# M8 验收脚本：种子与演示数据（seed.py）幂等性实测。
#
# 对应计划（process/_p3_implementation_plan.md · M8）验收口径：
#   「连续执行两次 seed，账号/流水线数量不变（实测 count）」
# 额外覆盖需求八.3（2 普通用户 + 2 处理人员 + 1 管理员、密码不写死）与
# 需求七.3（多次启动不重复添加演示记录）在 seed 层面的行为。
#
# 两条路径，全部在 process/_m8_scratch/ 下的临时库里跑，
# 【不碰】backend/fault_tracker.db 真实开发库（规则 2.6 不可逆操作人工执行）：
#   A 空库路径：alembic upgrade head → seed ×2 → seed ×1（不带 SEED_PASSWORD，应直接跳过）
#   A0 守护路径：空库 + 不带 SEED_PASSWORD → seed 应中止（密码不写死的反证）
#   B 旧库路径：复制 P2 备份库 → alembic upgrade head → 记基线 → seed ×2
#              → 账号补齐为 5，流水线/故障数量与旧数据逐字段不变
#   C 密码通道：seed_password 字段落地后，.env 通道可用；环境变量与 .env 同时存在时
#              取环境变量那一侧（用 bcrypt 直接比对入库哈希判定，不靠日志措辞）
#
# 用法（在 backend/ 目录）：uv run python -X utf8 ..\process\verify_m8_seed.py [--keep]
#   --keep：保留临时库目录便于手工复核（默认跑完删除）
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import bcrypt  # venv 已装（M3 认证依赖），此处仅用于离线比对入库哈希

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
SCRATCH = ROOT / "process" / "_m8_scratch"
P2_BACKUP = ROOT / "process" / "fault_tracker.db.bak-p2-20261102"
DEMO_PASSWORD = "m8-demo-passw0rd"  # 仅本次演练的一次性口令，不代表任何真实账号

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}{'  ' + detail if detail else ''}")
    if not ok:
        failures.append(name)


def db_url(db: Path) -> str:
    return f"sqlite:///{db.as_posix()}"


def alembic(db: Path, *args: str) -> subprocess.CompletedProcess:
    """对指定库文件跑 alembic（DATABASE_URL 经 env 注入，不走 shell 内联变量）。"""
    env = dict(os.environ, DATABASE_URL=db_url(db))
    r = subprocess.run(
        [sys.executable, "-X", "utf8", "-m", "alembic", *args],
        cwd=BACKEND, env=env, capture_output=True, text=True, encoding="utf-8",
    )
    if r.returncode != 0:
        print(r.stdout)
        print(r.stderr, file=sys.stderr)
        raise SystemExit(f"alembic {' '.join(args)} 失败（rc={r.returncode}）：{db.name}")
    return r


def run_seed(db: Path, *, with_password: bool = True) -> subprocess.CompletedProcess:
    """跑一次 seed.py：DATABASE_URL 指向临时库；with_password=False 模拟未配环境变量。"""
    env = dict(os.environ, DATABASE_URL=db_url(db))
    if with_password:
        env["SEED_PASSWORD"] = DEMO_PASSWORD
    else:
        env.pop("SEED_PASSWORD", None)
    return subprocess.run(
        [sys.executable, "-X", "utf8", "seed.py"],
        cwd=BACKEND, env=env, capture_output=True, text=True, encoding="utf-8",
    )


def run_seed_via_dotenv(workdir: Path, db: Path, *, dotenv_password: str,
                        env_password: str | None = None) -> subprocess.CompletedProcess:
    """走 .env 通道跑 seed：在 workdir 里造一份 .env（含 DATABASE_URL + SEED_PASSWORD），
    cwd 切到该目录再执行 seed.py（pydantic-settings 的 env_file 按当前工作目录找 .env）。
    这样就不必在仓库里新建 backend/.env；脚本按绝对路径调用，app 包仍从 backend/ 导入。
    env_password 非 None 时同时设环境变量，用于验证优先级。
    """
    (workdir / ".env").write_text(
        f"DATABASE_URL={db_url(db)}\nSEED_PASSWORD={dotenv_password}\n", encoding="utf-8"
    )
    env = dict(os.environ)
    env.pop("DATABASE_URL", None)   # 只留 .env 一侧，避免被环境变量顶掉
    if env_password is None:
        env.pop("SEED_PASSWORD", None)
    else:
        env["SEED_PASSWORD"] = env_password
    r = subprocess.run(
        [sys.executable, "-X", "utf8", str(BACKEND / "seed.py")],
        cwd=workdir, env=env, capture_output=True, text=True, encoding="utf-8",
    )
    (workdir / ".env").unlink()     # 用后即删，不在临时目录留密码文件
    return r


def first_hash(db: Path) -> tuple[str, str]:
    """取库里 username 最小的一条 (username, password_hash)，用于离线比对。"""
    return query(db, "SELECT username, password_hash FROM users ORDER BY username LIMIT 1")[0]  # type: ignore[return-value]


def query(db: Path, sql: str):
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def counts(db: Path) -> dict[str, int]:
    """四张表行数直读（不信 seed 的打印，规则 4.3）。"""
    out = {}
    for table in ("users", "pipelines", "pipeline_faults", "fault_timelines"):
        out[table] = query(db, f"SELECT count(*) FROM {table}")[0][0]
    return out


def fmt(c: dict[str, int]) -> str:
    return " / ".join(f"{k}={v}" for k, v in c.items())


def snapshot_faults(db: Path) -> list[tuple]:
    """旧数据逐字段快照（编号/状态/优先级/说明/位置/现象/时间），用于 B 路径比对。"""
    return query(db, (
        "SELECT id, status, priority, handling_note, location, symptom, occurred_at, closed_at "
        "FROM pipeline_faults ORDER BY id"
    ))


# ── A0：缺 SEED_PASSWORD 时守护中止（密码不写死）──────────────────────
def case_guard(db: Path) -> None:
    alembic(db, "upgrade", "head")
    r = run_seed(db, with_password=False)
    check("A0 空库无 SEED_PASSWORD 时 seed 中止（rc!=0）", r.returncode != 0, f"rc={r.returncode}")
    check("A0 中止信息指明缺少 SEED_PASSWORD", "SEED_PASSWORD" in (r.stdout + r.stderr),
          (r.stdout + r.stderr).strip().splitlines()[0] if (r.stdout + r.stderr).strip() else "")
    check("A0 中止后未写入任何账号", counts(db)["users"] == 0)


# ── A：空库 seed ×2 幂等 + 演示数据形态 ───────────────────────────────
def case_empty(db: Path) -> None:
    alembic(db, "upgrade", "head")
    r1 = run_seed(db)
    check("A seed 第一次执行成功", r1.returncode == 0, r1.stderr.strip()[:200])
    c1 = counts(db)
    print(f"       run1 计数：{fmt(c1)}")

    r2 = run_seed(db)
    check("A seed 第二次执行成功", r2.returncode == 0, r2.stderr.strip()[:200])
    c2 = counts(db)
    print(f"       run2 计数：{fmt(c2)}")

    # 第三次：不带环境变量（账号已齐 → 应免密码直接跳过，对应需求七.3「多次启动」）
    r3 = run_seed(db, with_password=False)
    check("A 账号齐全时免 SEED_PASSWORD 也能重复执行", r3.returncode == 0, r3.stderr.strip()[:200])
    c3 = counts(db)
    print(f"       run3 计数（无密码变量）：{fmt(c3)}")

    check("M8 主口径：连续两次 seed 四表计数不变", c1 == c2, f"{fmt(c1)} vs {fmt(c2)}")
    check("第三次（无密码变量）计数仍不变", c2 == c3, f"{fmt(c2)} vs {fmt(c3)}")

    check("A 演示账号 = 5 个", c1["users"] == 5, str(c1["users"]))
    roles = dict(query(db, "SELECT role, count(*) FROM users GROUP BY role"))
    check("A 角色构成 = 2 普通 + 2 处理 + 1 管理（需求八.3）",
          roles.get("user") == 2 and roles.get("handler") == 2 and roles.get("admin") == 1, str(roles))
    check("A 流水线 = 3 条", c1["pipelines"] == 3, str(c1["pipelines"]))
    check("A 故障 = 5 条", c1["pipeline_faults"] == 5, str(c1["pipeline_faults"]))

    hashes = [r[0] for r in query(db, "SELECT password_hash FROM users")]
    check("A 密码为 bcrypt 哈希、库内无明文",
          all(h.startswith("$2") and DEMO_PASSWORD not in h for h in hashes),
          f"{len(hashes)} 条，样例前缀 {hashes[0][:4] if hashes else '-'}")

    dist = dict(query(db, "SELECT status, count(*) FROM pipeline_faults GROUP BY status"))
    need = {"pending", "processing", "awaiting_confirmation", "done"}
    check("A 四种状态都有演示数据", need.issubset(dist.keys()), str(dist))

    no_create = query(db, (
        "SELECT count(*) FROM pipeline_faults f WHERE NOT EXISTS "
        "(SELECT 1 FROM fault_timelines t WHERE t.fault_id = f.id AND t.action = 'create')"
    ))[0][0]
    check("A 每条故障都有 create 时间线（动作链真实落库）", no_create == 0, f"缺 {no_create} 条")
    actions = dict(query(db, "SELECT action, count(*) FROM fault_timelines GROUP BY action"))
    check("A 时间线含指派/改派/进展/提交/确认等闭环动作",
          {"assign", "reassign", "progress", "submit", "confirm"}.issubset(actions.keys()), str(actions))
    anon = query(db, "SELECT count(*) FROM fault_timelines WHERE operator_id IS NULL")[0][0]
    check("A 时间线操作人全部可追溯（operator_id 非空）", anon == 0, f"空操作人 {anon} 条")


# ── B：P2 旧库升级后 seed 只补账号、不动存量数据 ──────────────────────
def case_legacy(db: Path) -> None:
    check("B P2 模拟库备份文件存在（需求八.3 保留）", P2_BACKUP.exists(), str(P2_BACKUP.name))
    shutil.copyfile(P2_BACKUP, db)
    alembic(db, "upgrade", "head")

    before = counts(db)
    snap_before = snapshot_faults(db)
    print(f"       升级后基线：{fmt(before)}")
    check("B 旧库升级后仍无用户（seed 前）", before["users"] == 0, str(before["users"]))

    run_seed(db)
    c1 = counts(db)
    snap1 = snapshot_faults(db)
    run_seed(db)
    c2 = counts(db)
    snap2 = snapshot_faults(db)
    print(f"       seed 后：{fmt(c1)}")
    print(f"       seed×2 ：{fmt(c2)}")

    check("B 旧库路径连续两次 seed 计数不变", c1 == c2, f"{fmt(c1)} vs {fmt(c2)}")
    check("B 账号补齐为 5 个", c2["users"] == 5, str(c2["users"]))
    check("B 流水线数量不变（已有数据 → 跳过故障播种）",
          c1["pipelines"] == before["pipelines"] == c2["pipelines"],
          f"{before['pipelines']} -> {c1['pipelines']} -> {c2['pipelines']}")
    check("B 故障数量不变（未向旧库插演示故障）",
          c1["pipeline_faults"] == before["pipeline_faults"] == c2["pipeline_faults"],
          f"{before['pipeline_faults']} -> {c1['pipeline_faults']} -> {c2['pipeline_faults']}")
    check("B 旧故障逐字段保持不变（编号/状态/优先级/说明/位置/现象/时间）",
          snap_before == snap1 == snap2, f"抽样 {len(snap2)} 行比对")
    legacy_open = query(db, (
        "SELECT count(*) FROM pipeline_faults WHERE status IN ('pending','processing') "
        "AND created_by_id IS NULL"
    ))[0][0]
    print(f"       旧库未完结且无创建人的故障 {legacy_open} 条（需求六.2「历史数据」形态，管理员可接手）")


# ── C：密码的两条通道（config.seed_password 落地后）─────────────────
DOTENV_PWD = "m8-dotenv-pass"   # 只写进 .env 的口令
ENVVAR_PWD = "m8-envvar-pass"   # 只给环境变量的口令


def case_password_channel(workdir: Path, db: Path) -> None:
    workdir.mkdir(parents=True, exist_ok=True)

    # C1：只给 .env、不给环境变量 —— 改前是读不到而中止，现在应当直接建号成功
    alembic(db, "upgrade", "head")
    r1 = run_seed_via_dotenv(workdir, db, dotenv_password=DOTENV_PWD)
    check("C1 只写 .env 也能提供 seed 密码（rc=0）", r1.returncode == 0,
          (r1.stderr or r1.stdout).strip()[:200])
    c1 = counts(db)
    check("C1 .env 通道补齐 5 个账号", c1["users"] == 5, fmt(c1))
    if c1["users"] == 5:
        _, h1 = first_hash(db)
        check("C1 入库哈希 = .env 里那个口令（bcrypt 离线比对）",
              bcrypt.checkpw(DOTENV_PWD.encode(), h1.encode()))

    # C2：两条通道同时给且值不同 —— 环境变量应当胜出
    db2 = workdir / "m8_c2.db"
    alembic(db2, "upgrade", "head")
    r2 = run_seed_via_dotenv(workdir, db2, dotenv_password=DOTENV_PWD, env_password=ENVVAR_PWD)
    c2 = counts(db2)
    check("C2 两通道并存时 seed 正常完成",
          r2.returncode == 0 and c2["users"] == 5, (r2.stderr or r2.stdout).strip()[:200] or fmt(c2))
    if c2["users"] == 5:
        _, h2 = first_hash(db2)
        check("C2 生效的是环境变量侧（SEED_PASSWORD > .env）",
              bcrypt.checkpw(ENVVAR_PWD.encode(), h2.encode())
              and not bcrypt.checkpw(DOTENV_PWD.encode(), h2.encode()))


def main() -> None:
    keep = "--keep" in sys.argv
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    SCRATCH.mkdir(parents=True)
    print(f"[scratch] {SCRATCH}")

    case_guard(SCRATCH / "m8_guard.db")
    case_empty(SCRATCH / "m8_empty.db")
    case_legacy(SCRATCH / "m8_legacy.db")
    case_password_channel(SCRATCH / "dotenv", SCRATCH / "dotenv" / "m8_c1.db")

    print()
    if not keep:
        shutil.rmtree(SCRATCH)
        print(f"[cleanup] 临时目录已删除；真实开发库 backend/fault_tracker.db 未被触碰")
    else:
        print(f"[keep] 临时目录保留：{SCRATCH}")

    if failures:
        print(f"共 {len(failures)} 项失败：{failures}")
        raise SystemExit(1)
    print("M8 验收全部通过")


if __name__ == "__main__":
    main()
