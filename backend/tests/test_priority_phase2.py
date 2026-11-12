# 第二阶段（故障优先级）专项测试 —— 按既有四层体系分层落点：
#   第 1 层 schemas 校验 → 第 2 层 crud 业务与筛选 → 第 3/4 层 API 集成与错误路径。
#
# 第三阶段调整（M5）：
#   · crud.create_fault 增加 creator 关键字参数，list_faults / list_faults_for_export
#     增加 viewer 参数（用于角色视图），本文件的辅助函数与调用同步更新；
#   · 状态推进的辅助路径由 transition_fault 改为 assign + start（handler 视角），
#     与新的动作模型保持一致；
#   · P-N7/P-N8（PATCH 改 priority）不再适用：priority 走 POST /{id}/priority 端点，
#     本文件的 API 层用例改走新端点，crud 层用 change_priority。
#
# 验收标准清单：
# 【schemas 层】
#   P-N1 FaultCreate 不传 priority → 缺省 normal
#   P-N2 FaultCreate 显式 urgent → 保留
#   P-N3 FaultUpdate 空 body 合法（不影响 PATCH 语义）
#   P-E1 priority 非法取值 → ValidationError
#   P-E2 priority null / 数字 → ValidationError
# 【crud 层】
#   P-N4 create 默认 normal / 显式 urgent 落库
#   P-N5 list 按 priority 单独筛选（admin 视角）
#   P-N6 priority + pipeline + status 组合筛选
#   P-N7 change_priority 改 priority 且不动 status（需求二.1）
#   P-N8 done 之前 admin/creator 均可改 priority；done 之后拒绝
#   P-N9 状态推进（assign + start）保留 priority
#   P-N10 list_faults_for_export 支持 priority 筛选，口径与 list_faults 一致
# 【API 层】
#   P-N11 POST 响应含 priority 字段
#   P-N12 GET ?priority=urgent 组合筛选（去掉旧 transition 依赖）
#   P-N13 POST /{id}/priority 端点：改 priority 且不动 status/handling_note
#   P-E3 POST 非法 priority → 422，不落库
#   P-E4 GET ?priority=asap → 422
#   P-B1 PATCH 多传字段 → 422（extra=forbid 不 regress）
#   P-B2 导出 CSV：表头含 priority，?priority= 导出生效

from datetime import timedelta

import pytest
from pydantic import ValidationError

from app import crud, schemas, timeutil
from app.models import FaultPriority, FaultRole, FaultStatus


def _fault_payload(**overrides):
    data = {
        "pipeline_id": 1,
        "location": "3号工位传送带",
        "occurred_at": (timeutil.business_now() - timedelta(hours=1)).isoformat(),
        "symptom": "传送带异响并卡死",
    }
    data.update(overrides)
    return data


def _mk_user(db, username: str, role: FaultRole = FaultRole.user):
    return crud.create_user(
        db,
        schemas.UserCreate(
            username=username, password="pw_placeholder", display_name=username, role=role
        ),
    )


def _make_pipeline(db, code: str = "LINE-A"):
    return crud.create_pipeline(db, schemas.PipelineCreate(code=code, name=f"名称-{code}"))


def _make_fault(
    db, pipeline_id, creator, *, minutes_ago=60, priority=None, to_processing=False, handler=None, admin=None
):
    """经 crud 造一条故障。to_processing=True 时执行 assign+start（需 handler 与 admin）。"""
    kwargs = {"priority": priority} if priority is not None else {}
    fault = crud.create_fault(
        db,
        schemas.FaultCreate(
            pipeline_id=pipeline_id,
            location="3号工位传送带",
            occurred_at=timeutil.business_now() - timedelta(minutes=minutes_ago),
            symptom="传送带异响并卡死",
            **kwargs,
        ),
        creator=creator,
    )
    if to_processing:
        assert handler is not None and admin is not None, "推进至 processing 需 handler 与 admin"
        crud.assign_fault(db, fault.id, handler.id, actor=admin)
        fault = crud.start_fault(db, fault.id, actor=handler)
    return fault


# ══ 第 1 层：schemas ═══════════════════════════════════════════════════
class TestSchemasPriority:
    def test_p_n1_create_defaults_to_normal(self):
        fc = schemas.FaultCreate(**_fault_payload())
        assert fc.priority is FaultPriority.normal

    def test_p_n2_create_accepts_urgent(self):
        fc = schemas.FaultCreate(**_fault_payload(priority="urgent"))
        assert fc.priority is FaultPriority.urgent

    def test_p_n3_update_optional_priority(self):
        fu = schemas.FaultUpdate(priority="urgent")
        assert fu.model_dump(exclude_unset=True) == {"priority": "urgent"}
        assert schemas.FaultUpdate().model_dump(exclude_unset=True) == {}

    @pytest.mark.parametrize("bad", ["high", "NORMAL", "", "1"])
    def test_p_e1_create_invalid_priority_value(self, bad):
        with pytest.raises(ValidationError) as exc_info:
            schemas.FaultCreate(**_fault_payload(priority=bad))
        assert ("priority",) in {err["loc"] for err in exc_info.value.errors()}

    def test_p_e2_create_wrong_type_priority(self):
        with pytest.raises(ValidationError):
            schemas.FaultCreate(**_fault_payload(priority=None))
        with pytest.raises(ValidationError):
            schemas.FaultCreate(**_fault_payload(priority=3))


# ══ 第 2 层：crud ══════════════════════════════════════════════════════
class TestCrudPriority:
    def test_p_n4_create_persist_default_and_urgent(self, db_session):
        alice = _mk_user(db_session, "alice")
        p = _make_pipeline(db_session)
        f_default = _make_fault(db_session, p.id, alice)
        assert f_default.priority is FaultPriority.normal
        f_urgent = _make_fault(db_session, p.id, alice, priority="urgent")
        assert f_urgent.priority is FaultPriority.urgent

    def test_p_n5_filter_by_priority(self, db_session):
        admin = _mk_user(db_session, "root", FaultRole.admin)
        alice = _mk_user(db_session, "alice")
        p = _make_pipeline(db_session)
        f_urgent = _make_fault(db_session, p.id, alice, priority="urgent")
        _make_fault(db_session, p.id, alice, minutes_ago=30)
        items, total = crud.list_faults(db_session, viewer=admin, priority=FaultPriority.urgent)
        assert total == 1 and [f.id for f in items] == [f_urgent.id]
        _, total_all = crud.list_faults(db_session, viewer=admin)
        assert total_all == 2

    def test_p_n6_combined_filters(self, db_session):
        admin = _mk_user(db_session, "root", FaultRole.admin)
        alice = _mk_user(db_session, "alice")
        h01 = _mk_user(db_session, "h01", FaultRole.handler)
        p1 = _make_pipeline(db_session, "LINE-A")
        p2 = _make_pipeline(db_session, "LINE-B")
        hit = _make_fault(
            db_session, p2.id, alice, priority="urgent", to_processing=True, handler=h01, admin=admin
        )
        _make_fault(db_session, p1.id, alice, priority="urgent")
        _make_fault(db_session, p1.id, alice, minutes_ago=30)

        items, total = crud.list_faults(
            db_session, viewer=admin, pipeline_id=p2.id,
            status=FaultStatus.processing, priority=FaultPriority.urgent,
        )
        assert total == 1 and items[0].id == hit.id

        exported = crud.list_faults_for_export(
            db_session, viewer=admin, pipeline_id=p2.id,
            status=FaultStatus.processing, priority=FaultPriority.urgent,
        )
        assert [f.id for f in exported] == [hit.id]

    def test_p_n7_change_priority_keeps_status(self, db_session):
        """change_priority 端点：creator 或 admin 均可，pending 或 processing 皆可，只改 priority。"""
        alice = _mk_user(db_session, "alice")
        p = _make_pipeline(db_session)
        f = _make_fault(db_session, p.id, alice, priority="urgent")
        updated = crud.change_priority(db_session, f.id, FaultPriority.normal, actor=alice)
        assert updated.priority is FaultPriority.normal
        assert updated.status is FaultStatus.pending
        assert updated.location == f.location and updated.symptom == f.symptom
        # 时间线新增一条 priority_change
        assert any(t.action.value == "priority_change" for t in updated.timelines)

    def test_p_n8_priority_change_rejected_after_done(self, db_session):
        """done 之后不允许改 priority（InvalidTransitionError，需求 AU9）。"""
        from app.exceptions import InvalidTransitionError
        alice = _mk_user(db_session, "alice")
        admin = _mk_user(db_session, "root", FaultRole.admin)
        h01 = _mk_user(db_session, "h01", FaultRole.handler)
        p = _make_pipeline(db_session)
        f = _make_fault(db_session, p.id, alice)
        crud.assign_fault(db_session, f.id, h01.id, actor=admin)
        crud.start_fault(db_session, f.id, actor=h01)
        crud.submit_fault(db_session, f.id, "更换皮带并复测正常", actor=h01)
        crud.confirm_fault(db_session, f.id, None, actor=alice)  # → done
        with pytest.raises(InvalidTransitionError):
            crud.change_priority(db_session, f.id, FaultPriority.urgent, actor=admin)

    def test_p_n9_state_advance_keeps_priority(self, db_session):
        """推进状态（assign + start）不改变 priority。"""
        admin = _mk_user(db_session, "root", FaultRole.admin)
        alice = _mk_user(db_session, "alice")
        h01 = _mk_user(db_session, "h01", FaultRole.handler)
        p = _make_pipeline(db_session)
        f = _make_fault(db_session, p.id, alice, priority="urgent")
        crud.assign_fault(db_session, f.id, h01.id, actor=admin)
        moved = crud.start_fault(db_session, f.id, actor=h01)
        assert moved.priority is FaultPriority.urgent

    def test_p_n10_export_priority_filter_no_match(self, db_session):
        admin = _mk_user(db_session, "root", FaultRole.admin)
        alice = _mk_user(db_session, "alice")
        p = _make_pipeline(db_session)
        _make_fault(db_session, p.id, alice)
        assert crud.list_faults_for_export(db_session, viewer=admin, priority=FaultPriority.urgent) == []


# ══ 第 3+4 层：API 集成 ════════════════════════════════════════════════
async def _seed_pipeline(client):
    resp = await client.post("/api/pipelines", json={"code": "LINE-A", "name": "名称-A"})
    assert resp.status_code == 201
    return resp.json()["id"]


def _api_fault_body(pipeline_id, **overrides):
    body = {
        "pipeline_id": pipeline_id,
        "location": "3号工位传送带",
        "occurred_at": (timeutil.business_now() - timedelta(hours=1)).isoformat(),
        "symptom": "传送带异响并卡死",
    }
    body.update(overrides)
    return body


@pytest.mark.anyio
class TestApiPriority:
    async def test_p_n11_create_response_contains_priority(self, client):
        pid = await _seed_pipeline(client)
        resp = await client.post("/api/faults", json=_api_fault_body(pid))
        assert resp.status_code == 201
        assert resp.json()["priority"] == "normal"
        resp = await client.post("/api/faults", json=_api_fault_body(pid, priority="urgent"))
        assert resp.status_code == 201 and resp.json()["priority"] == "urgent"

    async def test_p_n12_list_combined_priority_filter(self, client):
        pid = await _seed_pipeline(client)
        f_u1 = await client.post(
            "/api/faults", json=_api_fault_body(pid, priority="urgent")
        )
        f_u2 = await client.post(
            "/api/faults",
            json=_api_fault_body(
                pid, priority="urgent",
                occurred_at=(timeutil.business_now() - timedelta(hours=2)).isoformat(),
            ),
        )
        await client.post("/api/faults", json=_api_fault_body(pid))  # normal 干扰项

        # urgent + pending 命中 2 条（都是 pending，因为都还没走动作端点）
        resp = await client.get("/api/faults", params={"priority": "urgent", "status": "pending"})
        data = resp.json()
        assert resp.status_code == 200
        assert data["total"] == 2
        ids = {f["id"] for f in data["items"]}
        assert ids == {f_u1.json()["id"], f_u2.json()["id"]}

        # 排序仍按 occurred_at 倒序（f_u1 更新，排在前面）
        resp = await client.get("/api/faults", params={"priority": "urgent"})
        listed_ids = [f["id"] for f in resp.json()["items"]]
        assert listed_ids == [f_u1.json()["id"], f_u2.json()["id"]]

    async def test_p_n13_change_priority_endpoint(self, client):
        """走 POST /{id}/priority 端点：admin 视角修改自己的故障，priority 变、status 不变。"""
        pid = await _seed_pipeline(client)
        created = await client.post("/api/faults", json=_api_fault_body(pid, priority="urgent"))
        fid = created.json()["id"]
        # 用 PATCH 补上 handling_note？现在 PATCH 不支持 handling_note，直接测 /priority
        resp = await client.post(f"/api/faults/{fid}/priority", json={"priority": "normal"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["priority"] == "normal"
        assert data["status"] == "pending"

    @pytest.mark.parametrize("payload", [{"priority": "high"}, {"priority": None}, {"priority": 3}])
    async def test_p_e3_post_invalid_priority_422_not_saved(self, client, payload):
        pid = await _seed_pipeline(client)
        resp = await client.post("/api/faults", json={**_api_fault_body(pid), **payload})
        assert resp.status_code == 422
        body = resp.json()
        assert body["code"] == "validation_error"
        assert any(d["field"].endswith("priority") for d in body["details"])
        listed = (await client.get("/api/faults")).json()
        assert listed["total"] == 0

    async def test_p_e4_invalid_priority_on_query(self, client):
        """GET 筛选参数非法 priority → 422（Query 枚举同 status 口径）。"""
        resp = await client.get("/api/faults", params={"priority": "asap"})
        assert resp.status_code == 422

    async def test_p_b1_patch_extra_field_rejected(self, client):
        pid = await _seed_pipeline(client)
        created = await client.post("/api/faults", json=_api_fault_body(pid))
        resp = await client.patch(
            f"/api/faults/{created.json()['id']}", json={"priority2": "urgent"}
        )
        assert resp.status_code == 422
        assert resp.json()["code"] == "validation_error"

    async def test_p_b2_export_csv_contains_priority_column(self, client):
        pid = await _seed_pipeline(client)
        await client.post("/api/faults", json=_api_fault_body(pid))
        await client.post(
            "/api/faults",
            json=_api_fault_body(pid, priority="urgent", symptom="紧急故障需优先处置"),
        )
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
        assert len(lines) == 2  # header + 1 urgent
