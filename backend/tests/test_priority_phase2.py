# 第二阶段（故障优先级）专项测试 —— 按既有四层体系分层落点：
#   第 1 层 schemas 校验 → 第 2 层 crud 业务与筛选 → 第 3/4 层 API 集成与错误路径。
# 独立成文件与既有 test_schemas/test_crud/test_api_* 并列，需求条目可逐条回溯。
#
# 验收标准清单（先写标准，再落测试；对应需求文档二.1~二.3、五）：
#
# 【schemas 层】
#   P-N1 FaultCreate 不传 priority → 缺省 normal（需求二.1 "默认普通"）
#   P-N2 FaultCreate 显式传 urgent → 保留原值
#   P-N3 FaultUpdate 传 priority → 构造成功；空 body 仍合法（不传=不改）
#   P-E1 priority 非法取值（如 "high"）→ ValidationError，loc 指向 priority
#   P-E2 FaultCreate 传 null / 数字等错误类型 → ValidationError
# 【crud 层】
#   P-N4 create_fault 默认入库 normal、显式传 urgent 生效
#   P-N5 list_faults 按 priority 单独筛选正确，total 与 items 口径一致
#   P-N6 priority 与 pipeline_id/status 组合筛选（需求二.2 "可组合使用"）
#   P-N7 update_fault 改 priority 成功，且【不改变】status/其他字段（需求二.1）
#   P-N8 done 记录仍可改 priority（不受 handling_note 锁定牵连）
#   P-N9 状态流转不丢 priority（transition 后仍为原优先级）
#   P-N10 list_faults_for_export 支持 priority 筛选，口径与 list_faults 一致
# 【API 层】
#   P-N11 POST 响应含 priority 字段；缺省 normal / 显式 urgent 均可
#   P-N12 GET /api/faults?priority=urgent 组合筛选 → 只含匹配行且 total 不虚报
#   P-N13 PATCH /api/faults/{id} 改 priority → 200，status 与 handling_note 不变
#   P-E3 POST 非法 priority → 422 validation_error，details 指向 priority，不落库（需求二.3）
#   P-E4 PATCH 非法 priority → 422；GET 筛选参数非法 priority → 422
#   P-B1 PATCH 多传未声明字段（如 priority2）→ 422（extra=forbid 不 regress）
#   P-B2 导出 CSV：表头含 priority 列，行值与库内一致；?priority= 筛选导出生效

from datetime import datetime, timedelta

import httpx
import pytest
from pydantic import ValidationError

from app import crud, schemas
from app.models import FaultPriority, FaultStatus


def _fault_payload(**overrides):
    data = {
        "pipeline_id": 1,
        "location": "3号工位传送带",
        "occurred_at": (datetime.now() - timedelta(hours=1)).isoformat(),
        "symptom": "传送带异响并卡死",
    }
    data.update(overrides)
    return data


# ---- crud 层造数工具（同 test_crud 风格）----
def _make_pipeline(db, code: str = "LINE-A"):
    return crud.create_pipeline(db, schemas.PipelineCreate(code=code, name=f"名称-{code}"))


def _make_fault(db, pipeline_id, *, minutes_ago=60, priority=None, status_push=None):
    """经 crud 造一条故障；priority 不传走 schema 缺省，status_push 先推进到目标状态。"""
    kwargs = {"priority": priority} if priority is not None else {}
    fault = crud.create_fault(
        db,
        schemas.FaultCreate(
            pipeline_id=pipeline_id,
            location="3号工位传送带",
            occurred_at=datetime.now() - timedelta(minutes=minutes_ago),
            symptom="传送带异响并卡死",
            **kwargs,
        ),
    )
    if status_push is not None:
        fault = crud.transition_fault(db, fault.id, status_push, None)
    return fault


# ══ 第 1 层：schemas ═══════════════════════════════════════════════════
class TestSchemasPriority:
    def test_p_n1_create_defaults_to_normal(self):
        fc = schemas.FaultCreate(**_fault_payload())
        assert fc.priority is FaultPriority.normal   # 需求二.1：默认"普通"

    def test_p_n2_create_accepts_urgent(self):
        fc = schemas.FaultCreate(**_fault_payload(priority="urgent"))
        assert fc.priority is FaultPriority.urgent

    def test_p_n3_update_optional_priority(self):
        fu = schemas.FaultUpdate(priority="urgent")
        assert fu.model_dump(exclude_unset=True) == {"priority": "urgent"}
        # 空 body 仍合法（不传=不改），priority 不出现在 changes 里
        assert schemas.FaultUpdate().model_dump(exclude_unset=True) == {}

    @pytest.mark.parametrize("bad", ["high", "NORMAL", "", "1"])
    def test_p_e1_create_invalid_priority_value(self, bad):
        with pytest.raises(ValidationError) as exc_info:
            schemas.FaultCreate(**_fault_payload(priority=bad))
        assert ("priority",) in {err["loc"] for err in exc_info.value.errors()}

    def test_p_e2_create_wrong_type_priority(self):
        with pytest.raises(ValidationError):
            schemas.FaultCreate(**_fault_payload(priority=None))   # 显式 null 不接受（字段非 Optional）
        with pytest.raises(ValidationError):
            schemas.FaultCreate(**_fault_payload(priority=3))      # 数字不在枚举取值内


# ══ 第 2 层：crud ══════════════════════════════════════════════════════
class TestCrudPriority:
    def test_p_n4_create_persist_default_and_urgent(self, db_session):
        p = _make_pipeline(db_session)
        f_default = _make_fault(db_session, p.id)
        assert f_default.priority is FaultPriority.normal
        f_urgent = _make_fault(db_session, p.id, priority="urgent")
        assert f_urgent.priority is FaultPriority.urgent

    def test_p_n5_filter_by_priority(self, db_session):
        p = _make_pipeline(db_session)
        f_urgent = _make_fault(db_session, p.id, priority="urgent")
        _make_fault(db_session, p.id, minutes_ago=30)
        items, total = crud.list_faults(db_session, priority=FaultPriority.urgent)
        assert total == 1 and [f.id for f in items] == [f_urgent.id]
        # "查看全部"：不传 priority = 两种都在（需求二.2）
        _, total_all = crud.list_faults(db_session)
        assert total_all == 2

    def test_p_n6_combined_filters(self, db_session):
        p1 = _make_pipeline(db_session, "LINE-A")
        p2 = _make_pipeline(db_session, "LINE-B")
        hit = _make_fault(db_session, p2.id, priority="urgent", status_push=FaultStatus.processing)
        # 干扰项：同优先级不同流水线 / 同流水线不同优先级 / 同流水线同优先级不同状态
        _make_fault(db_session, p1.id, priority="urgent", status_push=FaultStatus.processing)
        _make_fault(db_session, p1.id, minutes_ago=30, status_push=FaultStatus.processing)
        _make_fault(db_session, p1.id, priority="urgent")

        items, total = crud.list_faults(
            db_session, pipeline_id=p2.id, status=FaultStatus.processing, priority=FaultPriority.urgent
        )
        assert total == 1 and items[0].id == hit.id

        # 导出与列表口径一致（同参数同结果集）
        exported = crud.list_faults_for_export(
            db_session, pipeline_id=p2.id, status=FaultStatus.processing, priority=FaultPriority.urgent
        )
        assert [f.id for f in exported] == [hit.id]

    def test_p_n7_update_priority_keeps_status(self, db_session):
        p = _make_pipeline(db_session)
        f = _make_fault(db_session, p.id, priority="urgent", status_push=FaultStatus.processing)
        updated = crud.update_fault(db_session, f.id, schemas.FaultUpdate(priority="normal"))
        assert updated.priority is FaultPriority.normal
        assert updated.status is FaultStatus.processing   # 需求二.1：改优先级不动状态
        assert updated.location == f.location and updated.symptom == f.symptom

    def test_p_n8_update_priority_allowed_after_done(self, db_session):
        p = _make_pipeline(db_session)
        f = _make_fault(db_session, p.id)
        crud.transition_fault(db_session, f.id, FaultStatus.done, "更换皮带并复测正常")
        # done 后 handling_note 锁定，但 priority 不在锁定范围（基础信息维护仍合理）
        updated = crud.update_fault(db_session, f.id, schemas.FaultUpdate(priority="urgent"))
        assert updated.priority is FaultPriority.urgent
        assert updated.status is FaultStatus.done
        assert updated.handling_note == "更换皮带并复测正常"

    def test_p_n9_transition_keeps_priority(self, db_session):
        p = _make_pipeline(db_session)
        f = _make_fault(db_session, p.id, priority="urgent")
        moved = crud.transition_fault(db_session, f.id, FaultStatus.processing, None)
        assert moved.priority is FaultPriority.urgent     # 流转只动 status，不碰优先级

    def test_p_n10_export_priority_filter_no_match(self, db_session):
        p = _make_pipeline(db_session)
        _make_fault(db_session, p.id)  # 仅一条 normal
        assert crud.list_faults_for_export(db_session, priority=FaultPriority.urgent) == []


# ══ 第 3+4 层：API 集成 ════════════════════════════════════════════════
async def _seed_pipeline(client):
    resp = await client.post("/api/pipelines", json={"code": "LINE-A", "name": "名称-A"})
    assert resp.status_code == 201
    return resp.json()["id"]


def _api_fault_body(pipeline_id, **overrides):
    body = {
        "pipeline_id": pipeline_id,
        "location": "3号工位传送带",
        "occurred_at": (datetime.now() - timedelta(hours=1)).isoformat(),
        "symptom": "传送带异响并卡死",
    }
    body.update(overrides)
    return body


# 只标 API 类：本文件混排 sync（schemas/crud）与 async（API）用例，
# 文件级 pytestmark 会给 sync 用例挂上无意义的 anyio 标记。
@pytest.mark.anyio
class TestApiPriority:
    async def test_p_n11_create_response_contains_priority(self, client):
        pid = await _seed_pipeline(client)
        resp = await client.post("/api/faults", json=_api_fault_body(pid))
        assert resp.status_code == 201
        assert resp.json()["priority"] == "normal"                    # 缺省普通
        resp = await client.post("/api/faults", json=_api_fault_body(pid, priority="urgent"))
        assert resp.status_code == 201 and resp.json()["priority"] == "urgent"

    async def test_p_n12_list_combined_priority_filter(self, client):
        pid = await _seed_pipeline(client)
        f_u1 = await client.post("/api/faults", json=_api_fault_body(pid, priority="urgent"))
        f_u2 = await client.post(
            "/api/faults",
            json=_api_fault_body(pid, priority="urgent",
                                 occurred_at=(datetime.now() - timedelta(hours=2)).isoformat()),
        )
        await client.post("/api/faults", json=_api_fault_body(pid))
        await client.patch(f"/api/faults/{f_u2.json()['id']}/transition",
                           json={"target_status": "processing"})

        resp = await client.get("/api/faults", params={"priority": "urgent", "status": "pending"})
        data = resp.json()
        assert resp.status_code == 200
        assert data["total"] == 1 and data["items"][0]["id"] == f_u1.json()["id"]
        # 排序仍按 occurred_at 倒序（需求二.2）
        resp = await client.get("/api/faults", params={"priority": "urgent"})
        ids = [f["id"] for f in resp.json()["items"]]
        assert ids == [f_u1.json()["id"], f_u2.json()["id"]]

    async def test_p_n13_patch_priority_keeps_other_fields(self, client):
        pid = await _seed_pipeline(client)
        created = await client.post("/api/faults", json=_api_fault_body(pid, priority="urgent"))
        fid = created.json()["id"]
        await client.patch(f"/api/faults/{fid}", json={"handling_note": "已安排维修工跟进处理"})
        resp = await client.patch(f"/api/faults/{fid}", json={"priority": "normal"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["priority"] == "normal"
        assert data["status"] == "pending"                            # 需求二.1
        assert data["handling_note"] == "已安排维修工跟进处理"          # 未传字段不动

    @pytest.mark.parametrize("payload", [{"priority": "high"}, {"priority": None}, {"priority": 3}])
    async def test_p_e3_post_invalid_priority_422_not_saved(self, client, payload):
        pid = await _seed_pipeline(client)
        resp = await client.post("/api/faults", json={**_api_fault_body(pid), **payload})
        assert resp.status_code == 422
        body = resp.json()
        assert body["code"] == "validation_error"
        assert any(d["field"].endswith("priority") for d in body["details"])
        # 需求二.3 "不保存"：库里没有多出记录
        listed = (await client.get("/api/faults")).json()
        assert listed["total"] == 0

    async def test_p_e4_invalid_priority_on_patch_and_query(self, client):
        # PATCH 非法值 → 422 且不落库；GET 筛选非法值 → 422（Query 枚举同 status 口径）
        pid = await _seed_pipeline(client)
        created = await client.post("/api/faults", json=_api_fault_body(pid, priority="urgent"))
        fid = created.json()["id"]
        resp = await client.patch(f"/api/faults/{fid}", json={"priority": "asap"})
        assert resp.status_code == 422
        assert (await client.get(f"/api/faults/{fid}")).json()["priority"] == "urgent"
        resp = await client.get("/api/faults", params={"priority": "asap"})
        assert resp.status_code == 422

    async def test_p_b1_patch_extra_field_rejected(self, client):
        pid = await _seed_pipeline(client)
        created = await client.post("/api/faults", json=_api_fault_body(pid))
        resp = await client.patch(f"/api/faults/{created.json()['id']}", json={"priority2": "urgent"})
        assert resp.status_code == 422
        assert resp.json()["code"] == "validation_error"

    async def test_p_b2_export_csv_contains_priority_column(self, client):
        pid = await _seed_pipeline(client)
        await client.post("/api/faults", json=_api_fault_body(pid))
        await client.post("/api/faults", json=_api_fault_body(pid, priority="urgent",
                                                              symptom="紧急故障需优先处置"))
        resp = await client.get("/api/faults/export")
        assert resp.status_code == 200
        lines = resp.text.lstrip("\ufeff").strip().splitlines()
        header = lines[0].split(",")
        assert "priority" in header
        idx = header.index("priority")
        values = {row.split(",")[idx] for row in lines[1:]}
        assert values == {"normal", "urgent"}
        # 带筛选导出：只导出 urgent
        resp = await client.get("/api/faults/export", params={"priority": "urgent"})
        lines = resp.text.lstrip("\ufeff").strip().splitlines()
        assert len(lines) == 2 and lines[1].split(",")[idx] == "urgent"
