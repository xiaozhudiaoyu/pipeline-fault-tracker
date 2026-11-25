# M10 验收脚本（二）：需求九.2~九.5 业务闭环与越权回归 —— 直接请求接口，不看按钮。
#
# 对应计划（process/_p3_implementation_plan.md · M10）口径：
#   「全流程时间线完整性；直接请求接口验证越权拦截（非只看按钮隐藏）；改派后旧负责人
#     失权；创建人停用后管理员代确认；非法值/空白/重复操作不产生脏数据」
# 覆盖需求条目：九.2 / 九.3 / 九.4 / 九.5，以及二.6、三、四.1~4.4、五.1~5.3 的接口层表现。
#
# 链路形态（规则 4.2「不启动项目」+ 需求九.3「通过直接请求接口验证」的折中）：
#   不起 uvicorn、不占端口、不开浏览器 —— httpx.ASGITransport 直连 app 走完整
#   ASGI 栈（CORS 中间件 → 路由 → Pydantic 校验 → 权限依赖 → crud → SQLite），
#   认证用【真实登录换来的 JWT】（不覆盖 get_current_user，与 conftest 的注入式
#   client 不同：这条链把 auth.py 的签名校验、token_version 失效也一起验了）。
#   库：process/_m10_scratch/api.db —— 先 alembic upgrade head 再 create_admin，
#   【不碰】backend/fault_tracker.db 真实开发库。
#
# 八个场景：
#   S1 账号与登录：管理员建号、真实 JWT、密码哈希入库、无权角色管用户被拒（九.1/九.3）
#   S2 主数据门槛：流水线仅管理员可建（四.4 前置）
#   S3 全流程闭环：报修→指派→开始→多条进展→调优先级→提交→退回→再进展→再提交→确认，
#      时间线 11 条逐条核对手艺人/动作/前后状态/前后负责人，done 后八类动作全拒（九.2/三/四.1/四.2）
#   S4 改派：旧负责人失权、新负责人接手、状态延续、理由必填、待确认不可改派（九.4）
#   S5 停用与代确认：创建人停用→旧 token 立即失效→管理员带理由代确认；
#      创建人在用时代确认被拒；重置密码使旧 token 失效；管理员不能停用自己（九.4/二.5/二.6）
#   S6 历史故障：created_by/assignee 均为 NULL 的存量故障，非管理员看不到，
#      管理员指派→负责人处理→管理员带理由代确认（六.2）
#   S7 脏数据防护：空白说明/空白理由/非法值/重复动作/越权失败后，
#      故障状态、handling_note、时间线条数三者逐次比对不变（九.5/五.2/五.3）
#   S8 原有功能与时间显示：筛选组合、occurred_at 倒序、已完成记录保护、
#      CSV 导出含创建人/负责人、时区输入-存储-回显-导出四点一致（九.5/五.1）
#
# 用法（在 backend/ 目录）：.venv\Scripts\python.exe -X utf8 ..\process\verify_m10_api.py [--keep]
import asyncio
import os
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
SCRATCH = ROOT / "process" / "_m10_scratch"
API_DB = SCRATCH / "api.db"

ADMIN_USER = "admin"
ADMIN_PASSWORD = "m10-admin-passw0rd"      # 仅本次演练的一次性口令，不代表任何真实账号
USER_PASSWORD = "m10-demo-passw0rd"

# ── 必须在导入 app 之前固化配置（config/database 都是模块级单例，见 conftest 同段说明）──
os.environ["DATABASE_URL"] = f"sqlite:///{API_DB.as_posix()}"
# 密钥长度 ≥ 32 字节：PyJWT 对短于 32 字节的 HMAC 密钥会打 InsecureKeyLengthWarning
# 到 stderr（项目自带开发默认密钥 34 字节，不触发）。
os.environ["SECRET_KEY"] = "m10-offline-verify-only-secret-0000"
os.environ["DB_ECHO"] = "false"
sys.path.insert(0, str(BACKEND))

from app.main import app as FASTAPI_APP  # noqa: E402  必须晚于上面的 env 赋值

failures: list[str] = []


class FlowAbort(Exception):
    """关键前置步骤失败：后续用例失去意义，带着原因中止并如实登记。"""


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}{'  ' + detail if detail else ''}")
    if not ok:
        failures.append(name)


# ── 库侧直读（规则 4.3：接口说改了不算，磁盘上要真有）──────────────────
def db_rows(sql: str, params: tuple = ()) -> list[tuple]:
    con = sqlite3.connect(API_DB.as_posix())
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


def db_scalar(sql: str, params: tuple = ()):
    rows = db_rows(sql, params)
    return rows[0][0] if rows else None


def db_exec(sql: str, params: tuple = ()) -> None:
    con = sqlite3.connect(API_DB.as_posix())
    try:
        con.execute(sql, params)
        con.commit()
    finally:
        con.close()


def timeline_rows(fault_id: int) -> list[tuple]:
    """按落库顺序取时间线骨架列（动作/操作人/前后状态/前后负责人/说明/导入标记）。"""
    return db_rows(
        "SELECT action, operator_id, from_status, to_status, from_assignee_id, "
        "to_assignee_id, note, is_imported FROM fault_timelines "
        "WHERE fault_id=? ORDER BY created_at, id",
        (fault_id,),
    )


def fault_state(fault_id: int) -> tuple:
    return db_rows(
        "SELECT status, priority, handling_note, closed_at, assignee_id, created_by_id "
        "FROM pipeline_faults WHERE id=?",
        (fault_id,),
    )[0]


# ── 前置：迁移 + 初始管理员（走 README 10.1 的同一批命令，不是另造数据）──
def prepare_db() -> None:
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    SCRATCH.mkdir(parents=True)
    for label, args in (("alembic", ("upgrade", "head")), ("create_admin", None)):
        env = dict(os.environ)
        if label == "alembic":
            cmd = [sys.executable, "-X", "utf8", "-m", "alembic", *args]
            cwd = BACKEND
        else:
            cmd = [sys.executable, "-X", "utf8", "create_admin.py"]
            cwd = BACKEND
            env["ADMIN_PASSWORD"] = ADMIN_PASSWORD
        r = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            print(r.stdout, r.stderr, file=sys.stderr)
            raise FlowAbort(f"{label} 前置执行失败（rc={r.returncode}）")


# ── 请求封装：who=None 匿名，who=<token 字符串> 带 Bearer ───────────────
class Ctx:
    def __init__(self, client) -> None:
        self.c = client
        self.tok: dict[str, str] = {}
        self.pipeline_id: int | None = None   # S2 建出，后续登记都走它
        self.f1: int | None = None            # S3 的已完单故障，S8 拿它验终态保护

    async def login(self, username: str, password: str, key: str, *, expect_ok: bool = True):
        r = await self.c.post("/api/auth/login",
                              json={"username": username, "password": password})
        if expect_ok:
            if r.status_code != 200:
                raise FlowAbort(f"登录失败：{username} → {r.status_code} {r.text[:160]}")
            token = r.json()["access_token"]
            self.tok[key] = token
            return token
        return r

    def header(self, who):
        return {} if who is None else {"Authorization": f"Bearer {self.tok[who]}"}

    async def req(self, method, url, who=None, *, json=None, params=None, expect=None,
                  label="", fatal=False):
        r = await self.c.request(method, url, headers=self.header(who),
                                 json=json, params=params)
        if expect is not None:
            body = r.text[:180] if r.status_code >= 400 else ""
            check(label or f"{method} {url} → {expect}", r.status_code == expect,
                  f"实际 {r.status_code} {body}")
            if r.status_code != expect and fatal:
                raise FlowAbort(f"{label or method + ' ' + url}：期望 {expect} 实际 {r.status_code}")
        return r

    async def create_fault(self, who, *, occurred_at, location, symptom,
                           priority=None, expect=201):
        body = {"pipeline_id": self.pipeline_id, "location": location,
                "occurred_at": occurred_at, "symptom": symptom}
        if priority:
            body["priority"] = priority
        r = await self.req("POST", "/api/faults", who, json=body, expect=expect,
                           label=f"登记故障（{location}）→ {expect}")
        return r.json()["id"] if expect == 201 else None


async def scenarios(ctx) -> None:
    ids: dict[str, int] = {}

    # ══ S1 账号与登录（需求九.1 后半段多账号登录 + 九.3 非管理员不能管用户）══
    print("\n===== S1 账号、登录与认证门槛 =====")
    await ctx.login(ADMIN_USER, ADMIN_PASSWORD, "admin")
    me = await ctx.req("GET", "/api/auth/me", "admin")
    check("S1-1 管理员登录后的 me 返回本人且角色为 admin",
          me.status_code == 200 and me.json().get("role") == "admin", str(me.text[:120]))

    await ctx.req("GET", "/api/faults", None, expect=401, label="S1-2 未登录查故障列表 → 401")
    await ctx.req("GET", "/api/pipelines", None, expect=401, label="S1-3 未登录查流水线 → 401")
    bad = await ctx.c.post("/api/auth/login",
                           json={"username": "reporter01", "password": "wrong-password-1"})
    check("S1-4 错误密码登录 → 401", bad.status_code == 401, f"{bad.status_code} {bad.text[:120]}")

    forged = await ctx.c.get("/api/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    check("S1-5 持无效 token 请求 → 401", forged.status_code == 401, f"{forged.status_code}")

    for key, username, role, display in (
        ("r1", "reporter01", "user", "报修人甲"),
        ("r2", "reporter02", "user", "报修人乙"),
        ("h1", "handler01", "handler", "处理员丙"),
        ("h2", "handler02", "handler", "处理员丁"),
    ):
        r = await ctx.req(
            "POST", "/api/users", "admin",
            json={"username": username, "password": USER_PASSWORD,
                  "display_name": display, "role": role},
            expect=201, label=f"S1-6 管理员建号 {username}（{role}）→ 201",
        )
        ids[key] = r.json()["id"]

    for key in ("r1", "r2", "h1", "h2"):
        await ctx.login({"r1": "reporter01", "r2": "reporter02",
                         "h1": "handler01", "h2": "handler02"}[key], USER_PASSWORD, key)
    check("S1-7 四个账号均可用同一演示口令登录（seed 同款多账号验收前提）", len(ctx.tok) == 5)

    hashes = db_rows("SELECT username, password_hash FROM users")
    check("S1-8 库内共 5 个账号（1 admin + 4 演示）", len(hashes) == 5, str(len(hashes)))
    check("S1-9 密码均为 bcrypt 哈希入库，无明文",
          all(h.startswith("$2b$") for _, h in hashes)
          and USER_PASSWORD not in " ".join(h for _, h in hashes))

    await ctx.req("POST", "/api/users", "admin",
                  json={"username": "reporter01", "password": USER_PASSWORD,
                        "display_name": "重名账号", "role": "user"},
                  expect=409, label="S1-10 重复用户名 → 409")
    await ctx.req("POST", "/api/users", "admin",
                  json={"username": "shortpw", "password": "12345",
                        "display_name": "短密码", "role": "user"},
                  expect=422, label="S1-11 密码不足 6 位 → 422")
    await ctx.req("GET", "/api/users", "r1", expect=403,
                  label="S1-12 普通用户查用户列表 → 403（九.3）")
    await ctx.req("POST", "/api/users", "h1",
                  json={"username": "sneaky01", "password": USER_PASSWORD,
                        "display_name": "自架号", "role": "admin"},
                  expect=403, label="S1-13 处理人员自行建号 → 403（九.3）")
    check("S1-14 被拒的建号未落库", db_scalar(
        "SELECT COUNT(*) FROM users WHERE username='sneaky01'") == 0)

    # ══ S2 主数据门槛 ══
    print("\n===== S2 流水线主数据 =====")
    p = await ctx.req("POST", "/api/pipelines", "admin",
                      json={"code": "LINE-M10A", "name": "M10 验收线"},
                      expect=201, label="S2-1 管理员建流水线 → 201")
    ctx.pipeline_id = p.json()["id"]
    await ctx.req("POST", "/api/pipelines", "r1",
                  json={"code": "LINE-M10B", "name": "报修人想建线"},
                  expect=403, label="S2-2 普通用户建流水线 → 403")
    await ctx.req("POST", "/api/pipelines", "admin",
                  json={"code": "LINE-M10A", "name": "重复编码"},
                  expect=409, label="S2-3 编码重复 → 409")

    # ══ S3 全流程闭环（需求九.2）——报修→指派→开始→多条进展→调优先级→提交
    #     →退回→再处理→再提交→确认，时间线逐条核对 ══
    print("\n===== S3 全流程闭环与时间线完整性 =====")
    f1 = await ctx.create_fault("r1", occurred_at="2026-11-10T13:00:00",
                                location="3号工位传送带", symptom="传送带异响并中途停机")
    ctx.f1 = f1
    d = (await ctx.req("GET", f"/api/faults/{f1}", "r1")).json()
    check("S3-1 新故障状态为 pending，优先级默认普通",
          d["status"] == "pending" and d["priority"] == "normal", str(d["status"]))
    check("S3-2 创建人由后端按登录账号写入（不接受客户端传值）",
          d["created_by"]["username"] == "reporter01", str(d["created_by"]))
    check("S3-3 登记时负责人为空", d["assignee"] is None)
    check("S3-4 输入 13:00 回显 13:00（需求五.1 时区回归）",
          d["occurred_at"].startswith("2026-11-10T13:00:00"), d["occurred_at"])
    check("S3-5 登记即写 create 时间线",
          [r[0] for r in timeline_rows(f1)] == ["create"])

    await ctx.req("POST", f"/api/faults/{f1}/start", "h1", expect=403,
                  label="S3-6 未指派时负责人点「开始处理」→ 403（三.1）", fatal=True)
    await ctx.req("POST", f"/api/faults/{f1}/assign", "r1",
                  json={"assignee_id": ids["h1"]}, expect=403,
                  label="S3-7 普通用户自行指派 → 403")
    await ctx.req("POST", f"/api/faults/{f1}/assign", "admin",
                  json={"assignee_id": 99999}, expect=403,
                  label="S3-8 指派给不存在的账号 → 403")
    await ctx.req("POST", f"/api/faults/{f1}/assign", "admin",
                  json={"assignee_id": ids["r2"]}, expect=403,
                  label="S3-9 指派给非处理人员 → 403")
    await ctx.req("POST", f"/api/faults/{f1}/assign", "admin",
                  json={"assignee_id": ids["h1"]}, expect=200, fatal=True,
                  label="S3-10 管理员指派 handler01 → 200")
    check("S3-11 指派后状态仍为 pending，仅设负责人",
          fault_state(f1)[0] == "pending" and fault_state(f1)[4] == ids["h1"])

    await ctx.req("POST", f"/api/faults/{f1}/start", "h1", expect=200, fatal=True,
                  label="S3-12 负责人开始处理 → processing")
    await ctx.req("POST", f"/api/faults/{f1}/progress", "h1",
                  json={"note": "已到现场检查联轴器，发现固定螺栓松动"}, expect=200,
                  label="S3-13 追加进展① → 200")
    await ctx.req("POST", f"/api/faults/{f1}/progress", "h1",
                  json={"note": "复测张力偏差 0.8mm，初步判断轴承磨损"}, expect=200,
                  label="S3-14 追加进展② → 200")
    check("S3-15 多次追加进展不改变状态",
          fault_state(f1)[0] == "processing" and len(timeline_rows(f1)) == 5)
    await ctx.req("POST", f"/api/faults/{f1}/priority", "admin",
                  json={"priority": "urgent"}, expect=200,
                  label="S3-16 管理员调优先级为紧急 → 200（二.4）")
    await ctx.req("POST", f"/api/faults/{f1}/submit", "h1",
                  json={"result_note": "已紧固螺栓并更换轴承，空载试运行 10 分钟无异响"},
                  expect=200, fatal=True, label="S3-17 提交处理结果 → awaiting_confirmation")
    check("S3-18 提交时 handling_note 同步落库",
          fault_state(f1)[2] == "已紧固螺栓并更换轴承，空载试运行 10 分钟无异响")

    mid_rows = timeline_rows(f1)
    await ctx.req("POST", f"/api/faults/{f1}/confirm", "h1", expect=403,
                  json={}, label="S3-19 负责人自行确认完成 → 403（三.4）")
    await ctx.req("POST", f"/api/faults/{f1}/confirm", "r2", expect=403,
                  json={}, label="S3-20 他人确认 → 403（九.3 直接请求接口）")
    await ctx.req("POST", f"/api/faults/{f1}/return", "r2",
                  json={"reason": "不是本人报修"}, expect=403, label="S3-21 他人退回 → 403")
    await ctx.req("POST", f"/api/faults/{f1}/return", "r1",
                  json={"reason": "夜班开机后仍有轻微异响，请复查"}, expect=200, fatal=True,
                  label="S3-22 创建人退回 → processing")
    check("S3-23 退回后负责人保持不变", fault_state(f1)[4] == ids["h1"])
    await ctx.req("POST", f"/api/faults/{f1}/progress", "h1",
                  json={"note": "更换联轴器弹性块并做动平衡"}, expect=200,
                  label="S3-24 退回后再次追加进展 → 200")
    await ctx.req("POST", f"/api/faults/{f1}/submit", "h1",
                  json={"result_note": "弹性块已换新，连续三个班次跟踪无异常"},
                  expect=200, fatal=True, label="S3-25 再次提交结果 → awaiting_confirmation")
    await ctx.req("POST", f"/api/faults/{f1}/confirm", "r1", json={}, expect=200, fatal=True,
                  label="S3-26 创建人确认完成 → done")
    st = fault_state(f1)
    check("S3-27 确认后状态 done 且写入完成时间",
          st[0] == "done" and bool(st[3]), str(st[3]))

    acts = [r[0] for r in timeline_rows(f1)]
    # 库侧存的是 SQLAlchemy Enum 的【成员名】（Enum(TimelineAction) 未设 values_callable，
    # 默认按 name 落库），return 是 Python 关键字故成员名为 return_；
    # 对外 JSON 走的是枚举【值】"return"，两者由 S3-32b 一并核对该差异。
    expect_acts = ["create", "assign", "start", "progress", "progress", "priority_change",
                   "submit", "return_", "progress", "submit", "confirm"]
    check("S3-28 时间线动作序列完整且无多余（11 条）", acts == expect_acts, str(acts))
    check("S3-29 旧记录未被覆盖（新记录只追加）",
          timeline_rows(f1)[:len(mid_rows)] == mid_rows)
    assign_row = next(r for r in timeline_rows(f1) if r[0] == "assign")
    check("S3-30 指派记录含前后负责人（空 → handler01）且状态不变",
          assign_row[2] == "pending" and assign_row[3] == "pending"
          and assign_row[4] is None and assign_row[5] == ids["h1"], str(assign_row))
    start_row = next(r for r in timeline_rows(f1) if r[0] == "start")
    check("S3-31 开始处理记录 pending → processing",
          start_row[2] == "pending" and start_row[3] == "processing")
    return_row = next(r for r in timeline_rows(f1) if r[0] == "return_")
    check("S3-32 退回记录 awaiting_confirmation → processing 并保留原因",
          return_row[2] == "awaiting_confirmation" and return_row[3] == "processing"
          and "夜班" in (return_row[6] or ""), str(return_row))
    # 前端 types/timeline.ts 声明「JSON 里就是 return」，此处按接口实测定该说法
    tl_json = await ctx.req("GET", f"/api/faults/{f1}/timelines", "r1", expect=200,
                            label="S3-32b 创建人拉取时间线 → 200")
    api_acts = [e["action"] for e in tl_json.json()]
    check("S3-32c 时间线接口 JSON 的退回动作值为 return（与库内成员名 return_ 不同）",
          api_acts == [a.replace("return_", "return") for a in expect_acts], str(api_acts))
    prio_row = next(r for r in timeline_rows(f1) if r[0] == "priority_change")
    check("S3-33 优先级调整记录含前后值且不改状态",
          "normal" in (prio_row[6] or "") and "urgent" in (prio_row[6] or "")
          and prio_row[2] == prio_row[3], str(prio_row))
    confirm_row = next(r for r in timeline_rows(f1) if r[0] == "confirm")
    check("S3-34 确认记录 awaiting_confirmation → done",
          confirm_row[2] == "awaiting_confirmation" and confirm_row[3] == "done")
    check("S3-35 每条时间线都有操作人快照",
          all(r[1] is not None for r in timeline_rows(f1)))
    check("S3-36 本次未产生 is_imported 记录（导入标记只给历史数据）",
          all(not r[7] for r in timeline_rows(f1)))

    # done 终态：八类动作 + 基础信息修改全拒，且一条时间线也不多加
    n_before = len(timeline_rows(f1))
    closed_at_before = fault_state(f1)[3]
    for action, body, who in (("start", None, "h1"), ("progress", {"note": "再记一笔"}, "h1"),
                              ("submit", {"result_note": "重新提交结果说明"}, "h1"),
                              ("confirm", {}, "r1"), ("return", {"reason": "再次退回试试"}, "r1"),
                              ("priority", {"priority": "normal"}, "r1")):
        await ctx.req("POST", f"/api/faults/{f1}/{action}", who, json=body or {}, expect=409,
                      label=f"S3-37 done 后「{action}」→ 409（三.4 终态不可逆）")
    await ctx.req("POST", f"/api/faults/{f1}/assign", "admin",
                  json={"assignee_id": ids["h2"]}, expect=409, label="S3-38 done 后指派 → 409")
    await ctx.req("POST", f"/api/faults/{f1}/reassign", "admin",
                  json={"assignee_id": ids["h2"], "reason": "已完成还要改派"}, expect=409,
                  label="S3-39 done 后改派 → 409")
    await ctx.req("PATCH", f"/api/faults/{f1}", "r1",
                  json={"location": "已完成还想改位置"}, expect=409,
                  label="S3-40 done 后改基本信息 → 409")
    check("S3-41 终态拒绝未产生任何新时间线",
          len(timeline_rows(f1)) == n_before, f"{n_before} → {len(timeline_rows(f1))}")
    check("S3-42 终态拒绝未改动数据（状态/优先级/说明/完成时间/负责人/创建人全不变）",
          fault_state(f1) == ("done", "urgent",
                              "弹性块已换新，连续三个班次跟踪无异常",
                              closed_at_before, ids["h1"], ids["r1"]),
          str(fault_state(f1)))


    # 剩下的场景拆成独立函数，按需求九.4 → 九.5 递进
    await s4_reassign(ctx, ids)
    await s5_deactivate(ctx, ids)
    await s6_legacy(ctx, ids)
    await s7_dirty_data(ctx, ids)
    await s8_filters_and_time(ctx, ids)


# ══ S4 改派（需求九.4 前半）═══════════════════════════════════════
async def s4_reassign(ctx, ids) -> None:
    print("\n===== S4 改派后旧负责人失权 =====")
    f2 = await ctx.create_fault("r2", occurred_at="2026-11-09T09:00:00",
                                location="5号灌装机", symptom="灌装机计量偏差超出允许范围")
    await ctx.req("POST", f"/api/faults/{f2}/assign", "admin",
                  json={"assignee_id": ids["h1"]}, expect=200, fatal=True,
                  label="S4-1 指派 handler01")
    await ctx.req("POST", f"/api/faults/{f2}/start", "h1", expect=200, fatal=True,
                  label="S4-2 handler01 开始处理")
    await ctx.req("POST", f"/api/faults/{f2}/progress", "h2",
                  json={"note": "旁人先来插一手"}, expect=403,
                  label="S4-3 非负责人追加进展 → 403")
    await ctx.req("POST", f"/api/faults/{f2}/reassign", "h1",
                  json={"assignee_id": ids["h2"], "reason": "自己给自己换人"}, expect=403,
                  label="S4-4 负责人自行改派 → 403（二.3）")
    await ctx.req("POST", f"/api/faults/{f2}/reassign", "admin",
                  json={"assignee_id": ids["h2"], "reason": "handler01 转去支援别的线"},
                  expect=200, fatal=True, label="S4-5 管理员改派 handler02 → 200")
    st = fault_state(f2)
    check("S4-6 改派后状态延续（processing）、负责人已换、已有处理记录不丢",
          st[0] == "processing" and st[4] == ids["h2"], str(st))

    await ctx.req("POST", f"/api/faults/{f2}/progress", "h1",
                  json={"note": "旧负责人再补一条进展"}, expect=403,
                  label="S4-7 改派后旧负责人追加进展 → 403（九.4）", fatal=True)
    await ctx.req("POST", f"/api/faults/{f2}/start", "h1", expect=403,
                  label="S4-8 旧负责人点开始处理 → 403")
    await ctx.req("POST", f"/api/faults/{f2}/submit", "h1",
                  json={"result_note": "旧负责人抢着提交结果"}, expect=403,
                  label="S4-9 旧负责人提交结果 → 403")
    await ctx.req("GET", f"/api/faults/{f2}", "h1", expect=404,
                  label="S4-10 旧负责人查看该故障 → 404（失权且不泄露存在性）")
    await ctx.req("POST", f"/api/faults/{f2}/progress", "h2",
                  json={"note": "新负责人接手，复查流量计读数"}, expect=200,
                  label="S4-11 新负责人可继续处理 → 200")

    tl_before = len(timeline_rows(f2))
    await ctx.req("POST", f"/api/faults/{f2}/reassign", "admin",
                  json={"assignee_id": ids["h1"], "reason": "     "}, expect=422,
                  label="S4-12 改派理由只填空格 → 422")
    check("S4-13 改派失败后负责人不变且时间线不新增",
          fault_state(f2)[4] == ids["h2"] and len(timeline_rows(f2)) == tl_before)
    await ctx.req("POST", f"/api/faults/{f2}/reassign", "admin",
                  json={"assignee_id": ids["r1"], "reason": "改成报修人接手"}, expect=403,
                  label="S4-14 改派给非处理人员 → 403")
    check("S4-15 非法接手人不影响现负责人", fault_state(f2)[4] == ids["h2"])

    re_rows = [r for r in timeline_rows(f2) if r[0] == "reassign"]
    check("S4-16 改派时间线含前后负责人与原因，且状态列前后一致",
          len(re_rows) == 1 and re_rows[0][4] == ids["h1"] and re_rows[0][5] == ids["h2"]
          and "支援" in (re_rows[0][6] or "") and re_rows[0][2] == re_rows[0][3] == "processing",
          str(re_rows))

    await ctx.req("POST", f"/api/faults/{f2}/submit", "h2",
                  json={"result_note": "更换流量计并重新标定，偏差回到允许范围"},
                  expect=200, fatal=True, label="S4-17 新负责人提交结果 → awaiting")
    await ctx.req("POST", f"/api/faults/{f2}/reassign", "admin",
                  json={"assignee_id": ids["h1"], "reason": "待确认了还能换人吗"}, expect=409,
                  label="S4-18 待确认状态改派 → 409（D6）")
    await ctx.req("POST", f"/api/faults/{f2}/assign", "admin",
                  json={"assignee_id": ids["h1"]}, expect=409,
                  label="S4-19 待确认状态指派 → 409")
    await ctx.req("POST", f"/api/faults/{f2}/confirm", "r2", json={}, expect=200, fatal=True,
                  label="S4-20 创建人确认 → done")


# ══ S5 停用与代确认（需求九.4 后半、二.5、二.6）═══════════════════
async def s5_deactivate(ctx, ids) -> None:
    print("\n===== S5 创建人停用后的管理员代确认 =====")
    admin_id = (await ctx.req("GET", "/api/auth/me", "admin")).json()["id"]
    f3 = await ctx.create_fault("r2", occurred_at="2026-11-08T15:00:00",
                                location="2号包装机", symptom="包装机封口不到位批量返工")
    await ctx.req("POST", f"/api/faults/{f3}/assign", "admin",
                  json={"assignee_id": ids["h1"]}, expect=200, fatal=True, label="S5-1 指派 handler01")
    await ctx.req("POST", f"/api/faults/{f3}/start", "h1", expect=200, fatal=True,
                  label="S5-2 开始处理")
    await ctx.req("POST", f"/api/faults/{f3}/submit", "h1",
                  json={"result_note": "调整封头温度与压力，首件检验合格"},
                  expect=200, fatal=True, label="S5-3 提交结果 → awaiting")

    await ctx.req("PATCH", f"/api/users/{ids['r2']}/active", "admin",
                  json={"is_active": False}, expect=200, fatal=True,
                  label="S5-4 管理员停用创建人 reporter02")
    await ctx.req("GET", "/api/auth/me", "r2", expect=401,
                  label="S5-5 停用后【已登录】的旧 token 立即失效 → 401（二.6）", fatal=True)
    dead_login = await ctx.c.post("/api/auth/login",
                                  json={"username": "reporter02", "password": USER_PASSWORD})
    check("S5-6 停用账号不能重新登录 → 401", dead_login.status_code == 401,
          f"{dead_login.status_code}")

    await ctx.req("POST", f"/api/faults/{f3}/confirm", "admin", json={}, expect=403,
                  label="S5-7 代确认不填理由 → 403（二.5）")
    check("S5-8 被拒的代确认未改状态", fault_state(f3)[0] == "awaiting_confirmation")
    await ctx.req("POST", f"/api/faults/{f3}/confirm", "admin",
                  json={"reason": "报修人已离职停用，电话确认可结案"}, expect=200, fatal=True,
                  label="S5-9 管理员带理由代确认 → done")
    c_row = next(r for r in timeline_rows(f3) if r[0] == "confirm")
    check("S5-10 代确认时间线记管理员操作人与原因",
          c_row[1] == admin_id and "电话确认" in (c_row[6] or ""), str(c_row))

    # 对照组：创建人仍启用时，管理员不得代确认
    f4 = await ctx.create_fault("r1", occurred_at="2026-11-07T10:00:00",
                                location="7号输送机", symptom="输送机跑偏并报警停机")
    await ctx.req("POST", f"/api/faults/{f4}/assign", "admin",
                  json={"assignee_id": ids["h2"]}, expect=200, fatal=True, label="S5-11 指派 handler02")
    await ctx.req("POST", f"/api/faults/{f4}/start", "h2", expect=200, fatal=True,
                  label="S5-12 开始处理")
    await ctx.req("POST", f"/api/faults/{f4}/submit", "h2",
                  json={"result_note": "重调导向轮并清洁滚筒"}, expect=200, fatal=True,
                  label="S5-13 提交结果")
    await ctx.req("POST", f"/api/faults/{f4}/confirm", "admin",
                  json={"reason": "创建人还在启用中就想代确认"}, expect=403,
                  label="S5-14 创建人启用中，管理员代确认 → 403（二.5）")

    # 重置密码：被重置者旧 token 全失效，新密码可用
    await ctx.req("POST", f"/api/users/{ids['h2']}/reset-password", "admin",
                  json={"password": "m10-new-passw0rd"}, expect=200, fatal=True,
                  label="S5-15 管理员重置 handler02 密码")
    await ctx.req("GET", "/api/auth/me", "h2", expect=401,
                  label="S5-16 被重置者旧 token 立即失效 → 401", fatal=True)
    await ctx.login("handler02", "m10-new-passw0rd", "h2")
    check("S5-17 新密码可登录（token 已刷新）", "h2" in ctx.tok)
    old_pw = await ctx.c.post("/api/auth/login",
                               json={"username": "handler02", "password": USER_PASSWORD})
    check("S5-18 旧密码不再可用 → 401", old_pw.status_code == 401, f"{old_pw.status_code}")
    check("S5-19 新旧密码均不落明文（哈希已变）",
          all(h.startswith("$2b$") for (h,) in db_rows("SELECT password_hash FROM users")))

    await ctx.req("PATCH", f"/api/users/{admin_id}/active", "admin",
                  json={"is_active": False}, expect=403,
                  label="S5-20 管理员停用自己 → 403（防自锁）")

# ══ S6 历史故障（无创建人 / 无负责人）——需求六.2、九.4 后半 ═══════
async def s6_legacy(ctx, ids) -> None:
    print("\n===== S6 升级而来的历史故障处理路径 =====")
    # 直接落库一单“旧库升级后人员字段全 NULL”的故障（不走接口，否则又有了创建人）
    db_exec(
        "INSERT INTO pipeline_faults (pipeline_id, location, occurred_at, symptom, "
        "status, priority, handling_note) VALUES (?, '9号码垓机器人', '2026-11-06T08:00:00', "
        "'码垓抓取位置偏移，早期人工跟线记录', 'pending', 'normal', '历史：由当班人员口头跟进')",
        (ctx.pipeline_id,),
    )
    legacy = db_scalar("SELECT id FROM pipeline_faults WHERE location='9号码垓机器人'")
    db_exec(
        "INSERT INTO pipeline_faults (pipeline_id, location, occurred_at, symptom, "
        "status, priority) VALUES (?, '1号喷标机', '2026-11-05T07:30:00', "
        "'喷标不清且处理中但无负责人', 'processing', 'normal')",
        (ctx.pipeline_id,),
    )
    legacy2 = db_scalar("SELECT id FROM pipeline_faults WHERE location='1号喷标机'")
    check("S6-1 两单历史故障的 created_by_id / assignee_id 均为 NULL",
          fault_state(legacy)[4:6] == (None, None) and fault_state(legacy2)[4:6] == (None, None),
          str(fault_state(legacy)))

    await ctx.req("GET", f"/api/faults/{legacy}", "r1", expect=404,
                  label="S6-2 普通用户看历史故障 → 404（不属任何人视图）")
    await ctx.req("GET", f"/api/faults/{legacy}", "h1", expect=404,
                  label="S6-3 处理人员看历史故障 → 404")
    d = await ctx.req("GET", f"/api/faults/{legacy}", "admin")
    check("S6-4 管理员可看，且 created_by/assignee 返回 null（前端渲染“历史数据/未关联账号”）",
          d.status_code == 200 and d.json()["created_by"] is None
          and d.json()["assignee"] is None)
    check("S6-5 原填写的处理人名称保留（handling_note 未被清空）",
          "口头跟进" in (d.json()["handling_note"] or ""), str(d.json()["handling_note"]))

    # 未完成的旧故障：管理员指定负责人继续处理（二.5 / 六.2）
    await ctx.req("POST", f"/api/faults/{legacy}/assign", "admin",
                  json={"assignee_id": ids["h1"]}, expect=200, fatal=True,
                  label="S6-6 管理员为 pending 历史故障指派负责人 → 200")
    await ctx.req("POST", f"/api/faults/{legacy2}/assign", "admin",
                  json={"assignee_id": ids["h1"]}, expect=200,
                  label="S6-7 管理员为 processing 历史故障补指派 → 200（BUG-C 对齐）")
    await ctx.req("POST", f"/api/faults/{legacy}/start", "h1", expect=200, fatal=True,
                  label="S6-8 接手人开始处理")
    await ctx.req("POST", f"/api/faults/{legacy}/submit", "h1",
                  json={"result_note": "重做示教点并验证 20 循环无偏差"}, expect=200,
                  fatal=True, label="S6-9 接手人提交结果 → awaiting")
    await ctx.req("POST", f"/api/faults/{legacy}/confirm", "r1", json={}, expect=403,
                  label="S6-10 历史故障无归属人时他人确认 → 403")
    await ctx.req("POST", f"/api/faults/{legacy}/confirm", "admin", json={}, expect=403,
                  label="S6-11 管理员代确认不填原因 → 403")
    await ctx.req("POST", f"/api/faults/{legacy}/confirm", "admin",
                  json={"reason": "原报修账号已在升级前注销，经与车间确认后结案"},
                  expect=200, fatal=True, label="S6-12 管理员带原因代确认 → done")
    acts = [r[0] for r in timeline_rows(legacy)]
    check("S6-13 历史故障时间线从 assign 起，不编造旧时的 create 记录",
          acts == ["assign", "start", "submit", "confirm"], str(acts))
    check("S6-14 全程无 is_imported 伪历史标记，且每条有真实操作人",
          all((not r[7]) and r[1] is not None for r in timeline_rows(legacy)))


# ══ S7 非法值 / 空白 / 重复 / 越权失败不产生脏数据——需求九.5、五.2、五.3 ═══
async def s7_dirty_data(ctx, ids) -> None:
    print("\n===== S7 非法值、空白与重复操作：拒绝且零脏数据 =====")
    f6 = await ctx.create_fault("r1", occurred_at="2026-11-03T16:00:00",
                                location="6号贴标机", symptom="贴标偏移且气泡率偏高")
    await ctx.req("POST", f"/api/faults/{f6}/assign", "admin",
                  json={"assignee_id": ids["h1"]}, expect=200, fatal=True, label="S7-1 指派")
    await ctx.req("POST", f"/api/faults/{f6}/start", "h1", expect=200, fatal=True,
                  label="S7-2 开始处理")

    total_before = db_scalar("SELECT COUNT(*) FROM pipeline_faults")
    tl_total_before = db_scalar("SELECT COUNT(*) FROM fault_timelines")
    base = fault_state(f6)
    n = len(timeline_rows(f6))

    async def rejected(method, url, who, *, body=None, code, label):
        """被拒请求本身 + “拒完数据一动没动”各记一条。"""
        await ctx.req(method, url, who, json=body, expect=code, label=label)
        check(f"{label} ‖ 拒后状态/说明/时间线条数全不变",
              fault_state(f6) == base and len(timeline_rows(f6)) == n, str(fault_state(f6)))

    await rejected("POST", f"/api/faults/{f6}/progress", "h1",
                   body={"note": "        "}, code=422, label="S7-3 进展只填空格 → 422")
    await rejected("POST", f"/api/faults/{f6}/progress", "h1",
                   body={"note": "短"}, code=422, label="S7-4 进展不足 2 字 → 422")
    await rejected("POST", f"/api/faults/{f6}/submit", "h1",
                   body={"result_note": "     "}, code=422, label="S7-5 提交结果只填空格 → 422")
    await rejected("POST", f"/api/faults/{f6}/submit", "h1",
                   body={"result_note": "修好了"}, code=422, label="S7-6 结果说明不足 5 字 → 422")
    await rejected("PATCH", f"/api/faults/{f6}", "r1",
                   body={"handling_note": "     "}, code=422,
                   label="S7-7 用空格覆盖处理说明 → 422（五.2）")
    await rejected("PATCH", f"/api/faults/{f6}", "r1",
                   body={"priority": None}, code=422, label="S7-8 priority:null → 422（非 500）")
    await rejected("PATCH", f"/api/faults/{f6}", "r1",
                   body={"location": None}, code=422, label="S7-9 location:null → 422（非 500）")
    await rejected("PATCH", f"/api/faults/{f6}", "r1",
                   body={"location": "     "}, code=422, label="S7-10 location 只填空格 → 422")
    await rejected("POST", f"/api/faults/{f6}/start", "h1", body={}, code=409,
                   label="S7-11 重复点「开始处理」→ 409")
    await rejected("POST", f"/api/faults/{f6}/progress", "h2",
                   body={"note": "别的处理人员插一笔"}, code=403, label="S7-12 越权追加进展 → 403")
    await rejected("POST", f"/api/faults/{f6}/return", "r1",
                   body={"reason": "  "}, code=422, label="S7-13 退回理由只填空格 → 422")

    # 合法值仍要能过（防“校验过严”假成功）
    await ctx.req("POST", f"/api/faults/{f6}/progress", "h1",
                  json={"note": "已排除标带张力"}, expect=200, label="S7-14 合法短进展仍可通过")
    base, n = fault_state(f6), len(timeline_rows(f6))

    # 不存在的故障与非法请求体（五.3：“故障不存在”要明确提示）
    for action, body in (("start", None), ("progress", {"note": "不存在也要报"}),
                         ("confirm", {}), ("assign", {"assignee_id": ids["h1"]})):
        await ctx.req("POST", f"/api/faults/999999/{action}", "admin", json=body or {},
                      expect=404, label=f"S7-15 对不存在的故障「{action}」→ 404")
    await ctx.req("GET", "/api/faults/999999", "admin", expect=404,
                  label="S7-16 查不存在的故障详情 → 404")
    await ctx.req("PATCH", "/api/faults/999999", "admin", json={"location": "不存在"},
                  expect=404, label="S7-17 改不存在的故障 → 404")

    # 登记环节：伪造型字段与非法值均被 422 拦下，不入库
    cnt_before = db_scalar("SELECT COUNT(*) FROM pipeline_faults")
    await ctx.req("POST", "/api/faults", "r1",
                  json={"pipeline_id": ctx.pipeline_id, "location": "伪造型入口",
                        "occurred_at": "2026-11-03T10:00:00", "symptom": "企图把创建人写成管理员",
                        "created_by_id": admin_id_of(ctx)},
                  expect=422, label="S7-18 登记时伪造型 created_by_id → 422（extra=forbid）")
    await ctx.req("POST", "/api/faults", "r1",
                  json={"pipeline_id": ctx.pipeline_id, "location": "未来时间",
                        "occurred_at": "2099-01-01T00:00:00", "symptom": "发生时间不可能在未来"},
                  expect=422, label="S7-19 发生时间晚于当前 → 422")
    await ctx.req("POST", "/api/faults", "r1",
                  json={"pipeline_id": ctx.pipeline_id, "location": "空白现象",
                        "occurred_at": "2026-11-03T10:00:00", "symptom": "     "},
                  expect=422, label="S7-20 现象只填空格 → 422（五.2）")
    await ctx.req("POST", "/api/faults", "r1",
                  json={"pipeline_id": ctx.pipeline_id, "location": "非法枚举",
                        "occurred_at": "2026-11-03T10:00:00", "symptom": "优先级取 high 不在枚举内",
                        "priority": "high"},
                  expect=422, label="S7-21 优先级非法枚举 → 422")
    await ctx.req("POST", "/api/faults", "r1",
                  json={"pipeline_id": 999999, "location": "不存在的流水线",
                        "occurred_at": "2026-11-03T10:00:00", "symptom": "pipeline_id 指向不存在的线"},
                  expect=404, label="S7-22 登记时流水线不存在 → 404")
    check("S7-23 以上非法登记零入库",
          db_scalar("SELECT COUNT(*) FROM pipeline_faults") == cnt_before)
    # 本轮只有一条合法进展（S7-14）写入时间线，余下全被拒 → 总量应恰好 +1
    check("S7-24 全部被拒请求零写入时间线（仅 S7-14 那一条合法进展入库）",
          db_scalar("SELECT COUNT(*) FROM fault_timelines") == tl_total_before + 1,
          f"{tl_total_before} → {db_scalar('SELECT COUNT(*) FROM fault_timelines')}")

    # 列表/导出参数非法 → 422，但随后正常请求仍可用（五.2“列表不能因报错打不开”）
    await ctx.req("GET", "/api/faults", "admin", params={"status": "bogus"}, expect=422,
                  label="S7-25 非法状态筛选值 → 422")
    await ctx.req("GET", "/api/faults", "admin", params={"page": 0}, expect=422,
                  label="S7-26 page=0 → 422")
    await ctx.req("GET", "/api/faults", "admin", params={"size": 200}, expect=422,
                  label="S7-27 size 超上限 → 422")
    await ctx.req("GET", "/api/faults", "admin", params={"status": "processing"}, expect=200,
                  label="S7-28 之后正常筛选仍可用（列表未挂）")
    check("S7-29 全程故障总数未因非法请求变动",
          db_scalar("SELECT COUNT(*) FROM pipeline_faults") == total_before,
          f"{total_before} → {db_scalar('SELECT COUNT(*) FROM pipeline_faults')}")


# ══ S8 原有筛选/优先级/时间显示/导出与已完成保护——需求九.5、四.4、五.1 ═══
async def s8_filters_and_time(ctx, ids) -> None:
    print("\n===== S8 筛选、时间显示与导出回归 =====")
    # 角色默认视图（四.4）：接口层以 SQL 直查作交叉验证
    total_all = db_scalar("SELECT COUNT(*) FROM pipeline_faults")
    admin_list = await ctx.req("GET", "/api/faults", "admin", params={"size": 100})
    check("S8-1 管理员默认视图=全部",
          admin_list.json()["total"] == total_all,
          f"total={admin_list.json().get('total')} sql={total_all}")
    r1_cnt = db_scalar("SELECT COUNT(*) FROM pipeline_faults WHERE created_by_id=?", (ids["r1"],))
    r1_list = await ctx.req("GET", "/api/faults", "r1", params={"size": 100})
    check("S8-2 普通用户默认视图=本人报修", r1_list.json()["total"] == r1_cnt,
          f"total={r1_list.json().get('total')} sql={r1_cnt}")
    h1_cnt = db_scalar(
        "SELECT COUNT(*) FROM pipeline_faults WHERE assignee_id=? OR created_by_id=?",
        (ids["h1"], ids["h1"]))
    h1_list = await ctx.req("GET", "/api/faults", "h1", params={"size": 100})
    check("S8-3 处理人员默认视图=本人任务（含自己报修）",
          h1_list.json()["total"] == h1_cnt, f"total={h1_list.json().get('total')} sql={h1_cnt}")
    r1_ids = {i["id"] for i in r1_list.json()["items"]}
    own_ids = {r[0] for r in db_rows(
        "SELECT id FROM pipeline_faults WHERE created_by_id=?", (ids["r1"],))}
    check("S8-4 普通用户列表集不混入他人故障（九.3）", r1_ids == own_ids,
          f"api={sorted(r1_ids)} sql={sorted(own_ids)}")

    # 组合筛选（四.4）：逐个筛选条件与库内 SQL 直查的 id 集逐一对齐
    for params, sql, args in (
        ({"status": "done"}, "SELECT id FROM pipeline_faults WHERE status='done'", ()),
        ({"priority": "urgent"}, "SELECT id FROM pipeline_faults WHERE priority='urgent'", ()),
        ({"assignee_id": ids["h1"]},
         "SELECT id FROM pipeline_faults WHERE assignee_id=?", (ids["h1"],)),
        ({"unassigned": "true"},
         "SELECT id FROM pipeline_faults WHERE assignee_id IS NULL", ()),
        ({"pipeline_id": ctx.pipeline_id, "status": "processing"},
         "SELECT id FROM pipeline_faults WHERE pipeline_id=? AND status='processing'",
         (ctx.pipeline_id,)),
    ):
        expected = {r[0] for r in db_rows(sql, args)}
        got = {i["id"] for i in (await ctx.req("GET", "/api/faults", "admin",
                                              params=params)).json()["items"]}
        check(f"S8-5 筛选 {params} 结果与库内直查一致", got == expected,
              f"api={sorted(got)} sql={sorted(expected)}")

    # 列表默认按发生时间倒序（四.4）
    times = [i["occurred_at"] for i in admin_list.json()["items"]]
    check("S8-6 列表默认按发生时间倒序", times == sorted(times, reverse=True), str(times[:3]))

    # 时区（五.1）：传 UTC 写法也要存回本地墙钟，输入-存储-回显-导出四点一致
    utc_morning = "2026-11-02T05:00:00Z"
    expect_local = datetime.fromisoformat("2026-11-02T05:00:00+00:00") \
        .astimezone().replace(tzinfo=None).isoformat()
    f7 = await ctx.create_fault("r1", occurred_at=utc_morning,
                                location="8号检测台", symptom="检测台显示偶发性重启")
    d = (await ctx.req("GET", f"/api/faults/{f7}", "r1")).json()
    check("S8-7 传 UTC 写法落库为本地墙钟（刷新/重开不至于偏 8 小时）",
          d["occurred_at"] == expect_local, f"实际 {d['occurred_at']} 期望 {expect_local}")
    stored = db_scalar("SELECT occurred_at FROM pipeline_faults WHERE id=?", (f7,))
    check("S8-8 库内直读为本地 naive（不带 Z/偏移）",
          "T" not in (stored or "") and (stored or "").startswith(
              expect_local[:19].replace("T", " ")), str(stored))

    # 已完成记录保护（二.5 / 三.4）：管理员也不能改已完成的故障
    await ctx.req("PATCH", f"/api/faults/{ctx.f1}", "admin",
                  json={"handling_note": "管理员改已成交接说明"},
                  expect=409, label="S8-9 已完成的故障改基础信息 → 409")
    await ctx.req("POST", f"/api/faults/{ctx.f1}/priority", "admin",
                  json={"priority": "normal"}, expect=409,
                  label="S8-10 已完成故障调优先级 → 409")

    # CSV 导出（四.4 口径与列表一致 + 第三阶段 creator/assignee）
    # 计数重取：S8-7 那单（f7）在本段之前才建，沿用段首的 total_all 会少一单
    total_now = db_scalar("SELECT COUNT(*) FROM pipeline_faults")
    r1_now = db_scalar("SELECT COUNT(*) FROM pipeline_faults WHERE created_by_id=?",
                       (ids["r1"],))
    exp = await ctx.req("GET", "/api/faults/export", "admin")
    lines = exp.text.lstrip("\ufeff").strip().splitlines()
    check("S8-11 导出表头含创建人/负责人两列",
          lines and lines[0].endswith("creator,assignee"), lines[0] if lines else "")
    check("S8-12 导出行数=管理员视图条数+表头", len(lines) - 1 == total_now,
          f"数据行={len(lines) - 1} sql={total_now}")
    check("S8-13 导出时间列为 YYYY-MM-DD HH:mm:ss（非 ISO T 格式）",
          any("2026-11-10 13:00:00" in ln for ln in lines[1:]))
    r1_exp = await ctx.req("GET", "/api/faults/export", "r1")
    r1_lines = r1_exp.text.lstrip("\ufeff").strip().splitlines()
    check("S8-14 导出同样受角色视图收敛（不泄露他人故障）",
          len(r1_lines) - 1 == r1_now, f"数据行={len(r1_lines) - 1} sql={r1_now}")
    other_symptom = db_rows("SELECT symptom FROM pipeline_faults WHERE created_by_id IS NOT NULL "
                            "AND created_by_id <> ?", (ids["r1"],))
    check("S8-15 导出内容不包含非本人故障的现象描述",
          all((r[0] or "") not in r1_exp.text for r in other_symptom))


def admin_id_of(ctx) -> int:
    """伪造型登记请求里填的 created_by_id 只要是个真 id 就够（被拒是因为 extra=forbid）。"""
    return db_scalar("SELECT id FROM users WHERE username='admin'")



async def run_all() -> None:
    import httpx

    transport = httpx.ASGITransport(app=FASTAPI_APP)
    async with httpx.AsyncClient(transport=transport, base_url="http://m10.test",
                                 timeout=20.0) as client:
        await scenarios(Ctx(client))


def dispose_engine() -> None:
    """释放模块级 engine 的连接池。

    Windows 下 SQLite 文件句柄被池内连接持有会让 rmtree 删不掉临时库（首次实跑就
    遇到了：api.db 残留），因此清理前显式 dispose，不依赖 ignore_errors 默吞。
    """
    from app.database import engine

    engine.dispose()


def main() -> int:
    keep = "--keep" in sys.argv
    prepare_db()
    try:
        asyncio.run(run_all())
    except FlowAbort as e:
        check("关键前置步骤失败，后续用例未执行", False, str(e))
    finally:
        dispose_engine()
        if keep:
            print(f"\n临时库保留在：{API_DB}")
        else:
            shutil.rmtree(SCRATCH, ignore_errors=False)
    print(f"\n以上为逐项结果；失败项 {len(failures)} 个"
          + (f"：{failures}" if failures else "（全部通过）"))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
