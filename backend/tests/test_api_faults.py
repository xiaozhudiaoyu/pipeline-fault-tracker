# 第 3+4 层：/api/faults 集成测试 —— httpx ASGITransport 走完整请求链路，
# 错误路径逐一断言状态码与 {code, message, details} 统一响应体结构。
#
# 第三阶段调整：
#   · 旧 N6 / E5 / E6 / E7（基于 PATCH /{id}/transition 的状态流转）已删除：
#     /transition 端点不存在，新状态机由 SM1–SM12 红测试（test_phase3_workflow.py）覆盖；
#   · N3 不再依赖 transition，改为验证“pipeline_id 筛选 + 分页”与“列表预加载”；
#   · client 默认以 admin 身份注入，所有创建故障的 created_by 即 admin。
#
# 验收标准清单：
#
# 【正常】
#   N1 POST /api/faults 合法 → 201 + Location 头 + FaultOut 结构
#   N2 GET /api/faults → 200，items+total+page+size 四件套，occurred_at 倒序
#   N3 GET /api/faults?pipeline_id=&page=&size= 筛选分页生效（列表项含 created_by）
#   N4 GET /api/faults/{id} → 200 完整详情
#   N5 PATCH /api/faults/{id} 改 location → 200，未传字段不变
# 【异常】
#   E1 GET 不存在 id → 404 fault_not_found
#   E2 POST pipeline_id 不存在 → 404 pipeline_not_found
#   E3 POST symptom 过短 → 422
#   E4 POST 多传 status 字段 → 422（extra=forbid）
#   E8 GET /api/faults/abc（路径参数非整数）→ 422
#   E9 查询参数越界 → 422
# 【边界】
#   B1 空库列表 → items=[] total=0
#   B2 POST 合法但 occurred_at 为未来（超容差）→ 422

from datetime import datetime, timedelta

import httpx
import pytest

# 所有 async 测试统一跑 anyio 插件的 asyncio 后端（见 conftest.anyio_backend）
pytestmark = pytest.mark.anyio


async def _seed_pipeline(client: httpx.AsyncClient, code: str = "LINE-A") -> int:
    """经 API 造一条流水线，返回 id（集成测试从入口造数，链路更真）。"""
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


def _assert_error_shape(payload: dict, code: str) -> None:
    """断言统一错误结构 ErrorOut：{code, message, details}，details 为列表。"""
    assert payload["code"] == code
    assert isinstance(payload["message"], str) and payload["message"]
    assert isinstance(payload["details"], list)


# ──【正常】───────────────────────────────────────────────────────────────
class TestHappyPath:
    async def test_n1_create_fault(self, client):
        pid = await _seed_pipeline(client)
        resp = await client.post("/api/faults", json=_fault_body(pid))
        assert resp.status_code == 201
        assert resp.headers["Location"] == f"/api/faults/{resp.json()['id']}"
        data = resp.json()
        assert data["status"] == "pending"          # 初始状态由后端强制
        assert data["pipeline"]["code"] == "LINE-A"  # 嵌套 pipeline
        assert data["handling_note"] is None and data["closed_at"] is None

    async def test_n2_list_shape_and_order(self, client):
        pid = await _seed_pipeline(client)
        f_old = await _seed_fault(client, pid, occurred_at=(datetime.now() - timedelta(hours=3)).isoformat())
        f_new = await _seed_fault(client, pid, occurred_at=(datetime.now() - timedelta(minutes=5)).isoformat())
        resp = await client.get("/api/faults")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2 and data["page"] == 1 and data["size"] == 20
        assert [f["id"] for f in data["items"]] == [f_new["id"], f_old["id"]]  # 倒序

    async def test_n3_list_filters_and_pagination(self, client):
        p1 = await _seed_pipeline(client, "LINE-A")
        p2 = await _seed_pipeline(client, "LINE-B")
        f1 = await _seed_fault(client, p1)
        f2 = await _seed_fault(client, p2)

        resp = await client.get("/api/faults", params={"pipeline_id": p1})
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["id"] == f1["id"]
        # 预加载验证：列表项包含 created_by（admin）与 assignee（未指派=null）
        item = resp.json()["items"][0]
        assert item["created_by"] is not None and item["created_by"]["role"] == "admin"
        assert item["assignee"] is None

        resp = await client.get("/api/faults", params={"page": 1, "size": 1})
        assert len(resp.json()["items"]) == 1 and resp.json()["total"] == 2
        # 验证 f2 存在（反序首项）
        assert resp.json()["items"][0]["id"] == f2["id"]

    async def test_n4_get_detail(self, client):
        pid = await _seed_pipeline(client)
        created = await _seed_fault(client, pid)
        resp = await client.get(f"/api/faults/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == created["id"]
        assert resp.json()["pipeline"]["id"] == pid

    async def test_n5_patch_update(self, client):
        pid = await _seed_pipeline(client)
        created = await _seed_fault(client, pid)
        resp = await client.patch(f"/api/faults/{created['id']}", json={"location": "5号工位电机"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["location"] == "5号工位电机"
        assert data["symptom"] == "传送带异响并卡死"  # 未传字段不动

    async def test_n6_patch_priority_silently_ignored(self, client):
        """第三阶段：PATCH 仅支持 location/symptom，传 priority 不报错但不生效（引导走 /priority 端点）。"""
        pid = await _seed_pipeline(client)
        created = await _seed_fault(client, pid, priority="urgent")
        resp = await client.patch(f"/api/faults/{created['id']}", json={"priority": "normal"})
        assert resp.status_code == 200
        assert resp.json()["priority"] == "urgent"  # 未被修改


# ──【异常】───────────────────────────────────────────────────────────────
class TestErrorPath:
    async def test_e1_get_not_found(self, client):
        resp = await client.get("/api/faults/999")
        assert resp.status_code == 404
        _assert_error_shape(resp.json(), "fault_not_found")
        assert resp.json()["details"][0]["field"] == "path.fault_id"

    async def test_e2_create_unknown_pipeline(self, client):
        resp = await client.post("/api/faults", json=_fault_body(999))
        assert resp.status_code == 404
        _assert_error_shape(resp.json(), "pipeline_not_found")
        assert resp.json()["details"][0]["field"] == "body.pipeline_id"

    async def test_e3_create_symptom_too_short(self, client):
        pid = await _seed_pipeline(client)
        resp = await client.post("/api/faults", json=_fault_body(pid, symptom="响了"))
        assert resp.status_code == 422
        _assert_error_shape(resp.json(), "validation_error")
        assert any(d["field"] == "symptom" for d in resp.json()["details"])

    async def test_e4_create_extra_field_rejected(self, client):
        pid = await _seed_pipeline(client)
        resp = await client.post("/api/faults", json=_fault_body(pid, status="done"))
        assert resp.status_code == 422
        _assert_error_shape(resp.json(), "validation_error")

    async def test_e8_path_param_not_int(self, client):
        resp = await client.get("/api/faults/abc")
        assert resp.status_code == 422
        _assert_error_shape(resp.json(), "validation_error")

    @pytest.mark.parametrize(
        "params",
        [{"page": 0}, {"size": 999}, {"status": "archived"}, {"pipeline_id": 0}],
    )
    async def test_e9_query_param_out_of_range(self, client, params):
        resp = await client.get("/api/faults", params=params)
        assert resp.status_code == 422
        _assert_error_shape(resp.json(), "validation_error")


# ──【边界】───────────────────────────────────────────────────────────────
class TestBoundary:
    async def test_b1_empty_list(self, client):
        resp = await client.get("/api/faults")
        assert resp.status_code == 200
        assert resp.json() == {"items": [], "total": 0, "page": 1, "size": 20}

    async def test_b2_future_occurred_at_rejected(self, client):
        pid = await _seed_pipeline(client)
        future = (datetime.now() + timedelta(hours=2)).isoformat()
        resp = await client.post("/api/faults", json=_fault_body(pid, occurred_at=future))
        assert resp.status_code == 422
        _assert_error_shape(resp.json(), "validation_error")
        assert any(d["field"] == "occurred_at" for d in resp.json()["details"])
