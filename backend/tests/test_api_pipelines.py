# 第 3+4 层：/api/pipelines 集成测试 —— 主数据端点的正常与错误路径。
#
# 验收标准清单（先写标准，再落测试）：
#
# 【正常】
#   N1 GET /api/pipelines 空库 → 200 []
#   N2 POST 合法 → 201 + PipelineOut 结构（id/code/name/description）
#   N3 GET 多条 → 按 code 升序
# 【异常】
#   E1 POST code 重复 → 409 pipeline_code_duplicate，details 指向 body.code
#   E2 POST code 空串 → 422 validation_error
#   E3 POST 多传未声明字段 → 422（extra=forbid）
# 【边界】
#   B1 POST description 不传 → 响应中为 null

import httpx
import pytest

pytestmark = pytest.mark.anyio


class TestHappyPath:
    async def test_n1_empty_list(self, client: httpx.AsyncClient):
        resp = await client.get("/api/pipelines")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_n2_create(self, client: httpx.AsyncClient):
        resp = await client.post("/api/pipelines", json={"code": "LINE-A", "name": "总装线A"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] is not None
        assert data["code"] == "LINE-A" and data["name"] == "总装线A"
        assert data["description"] is None  # B1：选填字段未传 → null

    async def test_n3_list_ordered_by_code(self, client: httpx.AsyncClient):
        for code in ("LINE-C", "LINE-A", "LINE-B"):
            await client.post("/api/pipelines", json={"code": code, "name": f"名称-{code}"})
        resp = await client.get("/api/pipelines")
        assert [p["code"] for p in resp.json()] == ["LINE-A", "LINE-B", "LINE-C"]


class TestErrorPath:
    async def test_e1_duplicate_code(self, client: httpx.AsyncClient):
        await client.post("/api/pipelines", json={"code": "LINE-A", "name": "总装线A"})
        resp = await client.post("/api/pipelines", json={"code": "LINE-A", "name": "另一条线"})
        assert resp.status_code == 409
        payload = resp.json()
        assert payload["code"] == "pipeline_code_duplicate"
        assert payload["details"][0]["field"] == "body.code"

    async def test_e2_empty_code_rejected(self, client: httpx.AsyncClient):
        resp = await client.post("/api/pipelines", json={"code": "", "name": "总装线A"})
        assert resp.status_code == 422
        assert resp.json()["code"] == "validation_error"

    async def test_e3_extra_field_rejected(self, client: httpx.AsyncClient):
        resp = await client.post(
            "/api/pipelines", json={"code": "LINE-A", "name": "总装线A", "owner": "张三"}
        )
        assert resp.status_code == 422
        assert resp.json()["code"] == "validation_error"
