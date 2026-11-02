# P4 导出 CSV 测试 —— 需求文档 process/_p4_export_csv_requirements.md 第 3 节验收标准逐条落地。
#
# 验收标准清单（先写标准，再落测试；编号与需求文档一致）：
#
# 【正常】
#   N1 无筛选导出 → 200 + text/csv + 表头与全部记录行 + occurred_at 倒序
#       + 时间列格式 YYYY-MM-DD HH:mm:ss（与前端展示一致，非 ISO "T" 格式）
#   N2 带 pipeline_id / status 筛选 → 只含匹配行，口径与列表接口一致
#   N3(后端部分) UTF-8 BOM 开头 + Content-Disposition attachment 文件名 faults_<ts>.csv
# 【异常】
#   E5 非法 status（xxx）→ 422 统一 ErrorOut 结构
#   E6 非法 pipeline_id（0）→ 422 同上
#   E7 GET /api/faults/export 不被 /{fault_id} 路由吞掉（注册顺序回归）
# 【边界】
#   B8 空库导出 → 200，只含表头行（D1 决策：不视为错误）
#   B9 字段含逗号/引号/换行 → CSV 转义正确，解析回原文
#   B10 crud 上限截断 → limit 生效且截断后仍按 occurred_at 倒序取最近的
#
# 分层：API 集成层（httpx ASGITransport，走完整请求链路）+ crud 单元层（B10），
# 会话隔离与建表全部复用 conftest 既有夹具（db_session / client）。

import csv
import io
import re
from datetime import datetime, timedelta

import httpx
import pytest

from app import crud
from app.models import FaultStatus

# 所有 async 测试统一跑 anyio 插件的 asyncio 后端（见 conftest.anyio_backend）
pytestmark = pytest.mark.anyio

# 与 routers/faults.py 的表头保持同源断言基准（10 列，顺序即导出顺序）
EXPECTED_HEADER = [
    "id",
    "pipeline_code",
    "pipeline_name",
    "location",
    "occurred_at",
    "symptom",
    "status",
    "handling_note",
    "created_at",
    "closed_at",
]


async def _seed_pipeline(client: httpx.AsyncClient, code: str = "LINE-A") -> int:
    """经 API 造一条流水线，返回 id（同 test_api_faults 的造数方式）。"""
    resp = await client.post("/api/pipelines", json={"code": code, "name": f"名称-{code}"})
    assert resp.status_code == 201
    return resp.json()["id"]


def _fault_body(pipeline_id: int, **overrides) -> dict:
    body = {
        "pipeline_id": pipeline_id,
        "location": "3号工位传送带",
        "occurred_at": (datetime.now() - timedelta(hours=1)).isoformat(),
        "symptom": "传送带异响并卡死",
    }
    body.update(overrides)
    return body


async def _seed_fault(client: httpx.AsyncClient, pipeline_id: int, **overrides) -> dict:
    resp = await client.post("/api/faults", json=_fault_body(pipeline_id, **overrides))
    assert resp.status_code == 201
    return resp.json()


def _parse_csv(resp: httpx.Response) -> list[list[str]]:
    """把响应 body 解析成 CSV 行列表（含表头行）。

    utf-8-sig 解码顺带剥掉 BOM（BOM 字节本身由 N3 单独断言）；
    csv.reader 处理转义（引号包裹的逗号/换行还原回单字段）。
    """
    text = resp.content.decode("utf-8-sig")
    return list(csv.reader(io.StringIO(text, newline="")))


def _assert_error_shape(payload: dict, code: str) -> None:
    """断言统一错误结构 ErrorOut：{code, message, details}（同 test_api_faults）。"""
    assert payload["code"] == code
    assert isinstance(payload["message"], str) and payload["message"]
    assert isinstance(payload["details"], list)


# ──【正常】───────────────────────────────────────────────────────────────
class TestExportHappyPath:
    async def test_n1_export_all_shape_and_order(self, client):
        """N1：无筛选导出 → 200 + text/csv + 表头 + 全部行 + occurred_at 倒序。"""
        pid = await _seed_pipeline(client)
        f_old = await _seed_fault(client, pid, occurred_at=(datetime.now() - timedelta(hours=3)).isoformat())
        f_new = await _seed_fault(client, pid, occurred_at=(datetime.now() - timedelta(minutes=5)).isoformat())

        resp = await client.get("/api/faults/export")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/csv")

        rows = _parse_csv(resp)
        assert rows[0] == EXPECTED_HEADER
        assert len(rows) == 3  # 表头 + 2 条记录
        assert [r[0] for r in rows[1:]] == [str(f_new["id"]), str(f_old["id"])]  # 倒序
        # 冗余列内容正确：pipeline_code/name 展平、status 用枚举值
        assert rows[1][1] == "LINE-A" and rows[1][2] == "名称-LINE-A"
        assert rows[1][6] == "pending"
        # 时间列格式：YYYY-MM-DD HH:mm:ss（与前端展示一致，不带 ISO 的 "T"）；
        # occurred_at/created_at 有值，未结案的 closed_at 为空串
        ts_pattern = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")
        assert ts_pattern.fullmatch(rows[1][4]), rows[1][4]  # occurred_at
        assert ts_pattern.fullmatch(rows[1][8]), rows[1][8]  # created_at
        assert rows[1][9] == ""  # closed_at（pending 未结案）

    async def test_n2_export_filters_match_list_scope(self, client):
        """N2：pipeline_id / status 筛选只含匹配行，口径与列表接口一致。"""
        p1 = await _seed_pipeline(client, "LINE-A")
        p2 = await _seed_pipeline(client, "LINE-B")
        await _seed_fault(client, p1)
        f2 = await _seed_fault(client, p2)
        await client.patch(f"/api/faults/{f2['id']}/transition", json={"target_status": "processing"})

        resp = await client.get("/api/faults/export", params={"pipeline_id": p1})
        rows = _parse_csv(resp)
        assert len(rows) == 2 and all(r[1] == "LINE-A" for r in rows[1:])

        resp = await client.get("/api/faults/export", params={"status": "processing"})
        rows = _parse_csv(resp)
        assert len(rows) == 2 and rows[1][0] == str(f2["id"]) and rows[1][6] == "processing"

        # 口径交叉验证：列表接口 total 与导出行数一致
        list_resp = await client.get("/api/faults", params={"status": "processing"})
        assert list_resp.json()["total"] == 1

    async def test_n3_bom_and_content_disposition(self, client):
        """N3（后端部分）：body 以 UTF-8 BOM 开头；Content-Disposition 下发 faults_<ts>.csv 文件名。"""
        resp = await client.get("/api/faults/export")
        assert resp.status_code == 200
        assert resp.content.startswith(b"\xef\xbb\xbf")  # BOM 的 UTF-8 字节序列
        disposition = resp.headers["content-disposition"]
        assert disposition.startswith("attachment;")
        assert re.fullmatch(r'attachment; filename=faults_\d{14}\.csv', disposition)


# ──【异常】───────────────────────────────────────────────────────────────
class TestExportErrors:
    async def test_e5_invalid_status_422(self, client):
        """E5：非法 status 枚举值 → 422 + 统一 ErrorOut 结构。"""
        resp = await client.get("/api/faults/export", params={"status": "xxx"})
        assert resp.status_code == 422
        _assert_error_shape(resp.json(), "validation_error")

    async def test_e6_invalid_pipeline_id_422(self, client):
        """E6：pipeline_id 越界（ge=1）→ 422 + 统一 ErrorOut 结构。"""
        resp = await client.get("/api/faults/export", params={"pipeline_id": 0})
        assert resp.status_code == 422
        _assert_error_shape(resp.json(), "validation_error")

    async def test_e7_export_route_not_shadowed_by_fault_id(self, client):
        """E7：/export 注册在 /{fault_id} 之前，不被路径参数路由吞掉。

        若被吞掉，症状是 422（"export" 转 int 失败）且 content-type 为 JSON ——
        两个断言合起来即回归网。
        """
        resp = await client.get("/api/faults/export")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/csv")


# ──【边界】───────────────────────────────────────────────────────────────
class TestExportBoundary:
    async def test_b8_empty_db_header_only(self, client):
        """B8：空库导出 → 200，只含表头行（D1 决策：空集是合法结果，不报错）。"""
        resp = await client.get("/api/faults/export")
        assert resp.status_code == 200
        rows = _parse_csv(resp)
        assert rows == [EXPECTED_HEADER]

    async def test_b9_csv_escaping(self, client):
        """B9：字段含逗号/引号/换行 → csv.writer 转义正确，解析回原文无损。"""
        pid = await _seed_pipeline(client)
        tricky = '症状含逗号,引号"和\n换行'
        created = await _seed_fault(client, pid, symptom=tricky)

        resp = await client.get("/api/faults/export")
        rows = _parse_csv(resp)
        assert len(rows) == 2  # 换行被引号包裹，不会多出一行
        assert rows[1][0] == str(created["id"])
        assert rows[1][5] == tricky  # 解析回原文

    async def test_b10_crud_limit_truncation(self, client, db_session):
        """B10：crud 上限截断 → limit 生效且保留 occurred_at 最近的行。

        经 API 造数后直接用测试 session 调 crud（conftest 已把 get_db 覆盖到同一
        session，数据互通）；不真造一万行，用小 limit 验证截断逻辑本身。
        """
        pid = await _seed_pipeline(client)
        for hours_ago in (5, 3, 1):  # 三条不同时间的记录
            await _seed_fault(client, pid, occurred_at=(datetime.now() - timedelta(hours=hours_ago)).isoformat())

        rows = crud.list_faults_for_export(db_session, limit=2)
        assert len(rows) == 2
        # 截断保留"最近的"：倒序 + limit，5 小时前的那条被截掉
        occurred = [r.occurred_at for r in rows]
        assert occurred == sorted(occurred, reverse=True)
        assert all(isinstance(r.status, FaultStatus) for r in rows)

        # 筛选口径与不传 limit 的全量结果一致（同一 where 构造）
        all_rows = crud.list_faults_for_export(db_session)
        filtered = crud.list_faults_for_export(db_session, pipeline_id=pid, status=FaultStatus.pending)
        assert len(all_rows) == 3 and len(filtered) == 3
