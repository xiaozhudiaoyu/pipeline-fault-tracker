# M9 验收脚本：create_admin.py 初始管理员创建（幂等 / 不重置密码 / 缺口令中止）。
#
# 对应计划（process/_p3_implementation_plan.md · M9）与需求七.4：
#   “提供创建初始管理员的方法，账号和密码可以配置；再次执行时，不能重复创建账号
#    或擅自重置已有密码。不要将真实密码和密钥写死在代码或镜像中。”
#
# 手法：create_admin.py 读 settings（进程启动时解析环境变量），故每条路径都用子进程
#       跑一次，靠注入不同的 DATABASE_URL / ADMIN_PASSWORD 复现场景；全部落在
#       process/_m9_scratch/ 下的临时库文件，绝不触碰真实开发库。ASCII-only 输出。
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent          # .../process
BACKEND = HERE.parent / "backend"
SCRATCH = HERE / "_m9_scratch"

PASS, FAIL = 0, []


def check(name: str, ok: bool, detail: str = "") -> None:
    global PASS
    tag = "PASS" if ok else "FAIL"
    print(f"[{tag}] {name}" + (f"  <- {detail}" if detail else ""))
    if ok:
        PASS += 1
    else:
        FAIL.append(name)


def run_admin(db_file: Path, *, password: str | None, username: str = "admin") -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["DATABASE_URL"] = f"sqlite:///{db_file.as_posix()}"
    env["ADMIN_USERNAME"] = username
    env.pop("ADMIN_PASSWORD", None)
    if password is not None:
        env["ADMIN_PASSWORD"] = password
    # 清掉可能从上层继承的其它播种变量，避免干扰
    env.pop("SEED_PASSWORD", None)
    return subprocess.run(
        [sys.executable, "create_admin.py"],
        cwd=BACKEND, env=env, capture_output=True, text=True,
    )


def user_row(db_file: Path, username: str):
    # 只读直查：返回 (password_hash, role, is_active) 或 None。绕开 app，独立证据。
    import sqlite3
    con = sqlite3.connect(db_file)
    try:
        cur = con.execute(
            "SELECT password_hash, role, is_active FROM users WHERE username = ?",
            (username,),
        )
        return cur.fetchone()
    finally:
        con.close()


def table_names(db_file: Path):
    import sqlite3
    con = sqlite3.connect(db_file)
    try:
        rows = con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        return {r[0] for r in rows}
    finally:
        con.close()


def main() -> None:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    # create_admin 会 init_models() 建表，但 users 表依赖先无外键顺序问题？init_models 用
    # create_all 一次建全部，OK。这里用两个独立库文件区分“全新库”与“已有账号库”。

    print("== 场景1：空库 + 无 ADMIN_PASSWORD -> 中止且零账号 ==")
    db1 = SCRATCH / "s1.db"
    if db1.exists():
        db1.unlink()
    r = run_admin(db1, password=None)
    check("S1 退出码非 0", r.returncode != 0, f"rc={r.returncode}")
    combined = (r.stdout or "") + (r.stderr or "")
    check("S1 提示缺少 ADMIN_PASSWORD", "ADMIN_PASSWORD" in combined)
    check("S1 未内置默认口令（无 admin 落库）",
          not (db1.exists() and user_row(db1, "admin")),
          "期望无 admin 账号")

    print("== 场景2：空库 + 带密码 -> 建 1 个 admin（bcrypt）==")
    db2 = SCRATCH / "s2.db"
    if db2.exists():
        db2.unlink()
    r = run_admin(db2, password="pw-original-123")
    check("S2 退出码 0", r.returncode == 0, f"rc={r.returncode} err={r.stderr.strip()[:200]}")
    row2 = user_row(db2, "admin")
    check("S2 admin 已建", row2 is not None)
    if row2:
        h, role, active = row2
        check("S2 role=admin", role == "admin", str(role))
        check("S2 is_active=1", active == 1, str(active))
        check("S2 密码入库为 bcrypt 哈希($2b$)", str(h).startswith("$2b$"), str(h)[:8])
        check("S2 明文密码未入库", "pw-original-123" not in str(h))
        hash_original = h
    else:
        hash_original = None

    print("== 场景3：已有 admin + 带【相同】密码重跑 -> 跳过、不重置、不新增 ==")
    r = run_admin(db2, password="pw-original-123")
    check("S3 退出码 0", r.returncode == 0, f"rc={r.returncode}")
    check("S3 输出含跳过提示", "已存在" in ((r.stdout or "") + (r.stderr or "")))
    row3 = user_row(db2, "admin")
    check("S3 哈希不变（未重置）", row3 and row3[0] == hash_original)
    import sqlite3
    con = sqlite3.connect(db2)
    cnt = con.execute("SELECT COUNT(*) FROM users WHERE username='admin'").fetchone()[0]
    con.close()
    check("S3 admin 仍唯一（未重复创建）", cnt == 1, f"count={cnt}")

    print("== 场景4：已有 admin + 带【不同】密码重跑 -> 仍跳过、绝不改密码 ==")
    r = run_admin(db2, password="pw-EVIL-different-999")
    check("S4 退出码 0", r.returncode == 0, f"rc={r.returncode}")
    row4 = user_row(db2, "admin")
    check("S4 哈希仍为原值（拒绝擅自重置）", row4 and row4[0] == hash_original)

    print("== 场景5：自定义 ADMIN_USERNAME -> 按指定名建号 ==")
    db5 = SCRATCH / "s5.db"
    if db5.exists():
        db5.unlink()
    r = run_admin(db5, password="pw-custom-123", username="root01")
    check("S5 退出码 0", r.returncode == 0, f"rc={r.returncode} err={r.stderr.strip()[:200]}")
    check("S5 root01 已建", user_row(db5, "root01") is not None)
    check("S5 未顺带建默认 admin", user_row(db5, "admin") is None)

    print(f"\n汇总：{PASS} PASS / {len(FAIL)} FAIL")
    if FAIL:
        print("失败项：", FAIL)
        raise SystemExit(1)
    print("M9 create_admin 验收全部通过")


if __name__ == "__main__":
    main()
