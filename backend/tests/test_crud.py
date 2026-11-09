# 第 2 层：crud 单元测试 —— 内存 SQLite 独立建表，测数据访问与业务规则，不碰开发库。
#
# 第三阶段调整：
#   · create_fault / list_faults / update_fault 增加 viewer/creator 关键字参数；
#   · transition_fault 已被 8 个动作函数替代，相关旧用例（N8/N9/E5/E6/E7/E8/B3）
#     迁移至 test_phase3_workflow.py 的 SM* 序列红测试覆盖，本文件不再重复；
#   · update_fault 现在只支持 pending 状态下的 location/symptom 修改，
#     priority/handling_note 走各自端点，本文件的 update 用例相应精简。
#
# 验收标准清单：
# 【正常】
#   N1 create_pipeline 成功入库
#   N2 list_pipelines 按 code 升序
#   N3 create_fault 强制 pending，同事务写 create 时间线
#   N4 list_faults 按 occurred_at 倒序 + 筛选（以 admin 视角）
#   N5 分页 page/size 切片正确
#   N6 get_fault / get_pipeline 命中返回对象
#   N7 update_fault 只改传入字段（pending + 创建人）
# 【异常】
#   E1 get_pipeline 不存在 → PipelineNotFoundError
#   E2 get_fault 不存在 → FaultNotFoundError
#   E3 create_fault 引用不存在的 pipeline → PipelineNotFoundError
#   E4 create_pipeline 编码重复 → PipelineCodeDuplicateError
#   E9 update_fault 非 pending → InvalidTransitionError
#   E10 update_fault 非创建人且非 admin → PermissionDeniedError
# 【边界】
#   B1 list_faults 空库 → ([], 0)
#   B2 页码超出数据量 → 空 items 但 total 不变

from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app import crud, schemas
from app.exceptions import (
    FaultNotFoundError,
    InvalidTransitionError,
    PermissionDeniedError,
    PipelineCodeDuplicateError,
    PipelineNotFoundError,
)
from app.models import FaultRole, FaultStatus


# ---- 造数工具 ----
def _mk_user(db: Session, username: str, role: FaultRole = FaultRole.user) -> "crud.User":
    return crud.create_user(
        db,
        schemas.UserCreate(
            username=username,
            password="pw_placeholder",
            display_name=username,
            role=role,
        ),
    )


def _make_pipeline(db: Session, code: str = "LINE-A", name: str = "总装线A"):
    return crud.create_pipeline(db, schemas.PipelineCreate(code=code, name=name))


def _make_fault(
    db: Session,
    pipeline_id: int,
    creator,
    minutes_ago: int = 60,
    symptom: str = "传送带异响并卡死",
):
    return crud.create_fault(
        db,
        schemas.FaultCreate(
            pipeline_id=pipeline_id,
            location="3号工位传送带",
            occurred_at=datetime.now() - timedelta(minutes=minutes_ago),
            symptom=symptom,
        ),
        creator=creator,
    )


# ── 流水线 ──────────────────────────────────────────────────────────────
class TestPipelineHappy:
    def test_n1_create_pipeline(self, db_session):
        p = _make_pipeline(db_session)
        assert p.id is not None
        assert p.created_at is not None
        assert p.code == "LINE-A"

    def test_n2_list_pipelines_ordered_by_code(self, db_session):
        _make_pipeline(db_session, code="LINE-C")
        _make_pipeline(db_session, code="LINE-A")
        _make_pipeline(db_session, code="LINE-B")
        codes = [p.code for p in crud.list_pipelines(db_session)]
        assert codes == ["LINE-A", "LINE-B", "LINE-C"]

    def test_n6_get_pipeline(self, db_session):
        p = _make_pipeline(db_session)
        assert crud.get_pipeline(db_session, p.id).code == "LINE-A"


class TestPipelineError:
    def test_e1_get_pipeline_not_found(self, db_session):
        with pytest.raises(PipelineNotFoundError):
            crud.get_pipeline(db_session, 999)

    def test_e4_duplicate_code(self, db_session):
        _make_pipeline(db_session, code="LINE-A")
        with pytest.raises(PipelineCodeDuplicateError):
            _make_pipeline(db_session, code="LINE-A", name="另一条线")


# ── 故障：正常 ───────────────────────────────────────────────────────────
class TestFaultHappy:
    def test_n3_create_fault_forces_pending(self, db_session):
        alice = _mk_user(db_session, "alice")
        p = _make_pipeline(db_session)
        f = _make_fault(db_session, p.id, alice)
        assert f.status is FaultStatus.pending
        assert f.pipeline.code == "LINE-A"
        assert f.created_by_id == alice.id
        assert f.handling_note is None
        assert f.closed_at is None
        # create 时间线同事务落库
        assert len(f.timelines) == 1
        assert f.timelines[0].action.value == "create"
        assert f.timelines[0].operator_id == alice.id

    def test_n4_list_default_order_and_filters_admin_view(self, db_session):
        admin = _mk_user(db_session, "root", FaultRole.admin)
        alice = _mk_user(db_session, "alice")
        p1 = _make_pipeline(db_session, code="LINE-A")
        p2 = _make_pipeline(db_session, code="LINE-B")
        f_old = _make_fault(db_session, p1.id, alice, minutes_ago=120)
        f_mid = _make_fault(db_session, p1.id, alice, minutes_ago=60)
        f_new = _make_fault(db_session, p2.id, alice, minutes_ago=10)

        items, total = crud.list_faults(db_session, viewer=admin)
        assert total == 3
        assert [f.id for f in items] == [f_new.id, f_mid.id, f_old.id]

        items, total = crud.list_faults(db_session, viewer=admin, pipeline_id=p1.id)
        assert total == 2 and {f.id for f in items} == {f_old.id, f_mid.id}

    def test_n5_pagination(self, db_session):
        admin = _mk_user(db_session, "root", FaultRole.admin)
        alice = _mk_user(db_session, "alice")
        p = _make_pipeline(db_session)
        faults = [_make_fault(db_session, p.id, alice, minutes_ago=i * 10) for i in range(1, 6)]
        items, total = crud.list_faults(db_session, viewer=admin, page=2, size=2)
        assert total == 5
        assert [f.id for f in items] == [faults[2].id, faults[3].id]

    def test_n6_get_fault(self, db_session):
        alice = _mk_user(db_session, "alice")
        p = _make_pipeline(db_session)
        f = _make_fault(db_session, p.id, alice)
        got = crud.get_fault(db_session, f.id)
        assert got.id == f.id and got.pipeline.code == "LINE-A"

    def test_n7_update_only_passed_fields(self, db_session):
        alice = _mk_user(db_session, "alice")
        p = _make_pipeline(db_session)
        f = _make_fault(db_session, p.id, alice)
        updated = crud.update_fault(
            db_session, f.id, schemas.FaultUpdate(location="5号工位电机"), viewer=alice
        )
        assert updated.location == "5号工位电机"
        assert updated.symptom == "传送带异响并卡死"


# ── 故障：异常 ───────────────────────────────────────────────────────────
class TestFaultError:
    def test_e2_get_fault_not_found(self, db_session):
        admin = _mk_user(db_session, "root", FaultRole.admin)
        with pytest.raises(FaultNotFoundError):
            crud.get_fault(db_session, 999, viewer=admin)

    def test_e3_create_fault_unknown_pipeline(self, db_session):
        alice = _mk_user(db_session, "alice")
        with pytest.raises(PipelineNotFoundError):
            _make_fault(db_session, pipeline_id=999, creator=alice)

    def test_e9_update_rejected_after_pending(self, db_session):
        """D6 保守：pending 之外不能再通过 PATCH 修改基本信息。"""
        alice = _mk_user(db_session, "alice")
        admin = _mk_user(db_session, "root", FaultRole.admin)
        p = _make_pipeline(db_session)
        f = _make_fault(db_session, p.id, alice)
        h = _mk_user(db_session, "h01", FaultRole.handler)
        crud.assign_fault(db_session, f.id, h.id, actor=admin)
        crud.start_fault(db_session, f.id, actor=h)  # → processing
        with pytest.raises(InvalidTransitionError):
            crud.update_fault(
                db_session, f.id, schemas.FaultUpdate(location="改一改"), viewer=alice
            )

    def test_e10_update_by_non_creator_non_admin_rejected(self, db_session):
        alice = _mk_user(db_session, "alice")
        admin = _mk_user(db_session, "root", FaultRole.admin)
        bob = _mk_user(db_session, "bob", FaultRole.handler)
        p = _make_pipeline(db_session)
        f = _make_fault(db_session, p.id, alice)
        # 先指派给 bob，让 bob 有资格看到这条故障（can_view 先过）
        crud.assign_fault(db_session, f.id, bob.id, actor=admin)
        # bob 不是创建人也不是 admin → PermissionDeniedError
        with pytest.raises(PermissionDeniedError):
            crud.update_fault(
                db_session, f.id, schemas.FaultUpdate(location="别人的"), viewer=bob
            )


# ── 边界 ─────────────────────────────────────────────────────────────────
class TestBoundary:
    def test_b1_empty_list(self, db_session):
        admin = _mk_user(db_session, "root", FaultRole.admin)
        items, total = crud.list_faults(db_session, viewer=admin)
        assert items == [] and total == 0

    def test_b2_page_beyond_data(self, db_session):
        admin = _mk_user(db_session, "root", FaultRole.admin)
        alice = _mk_user(db_session, "alice")
        p = _make_pipeline(db_session)
        _make_fault(db_session, p.id, alice)
        items, total = crud.list_faults(db_session, viewer=admin, page=5, size=10)
        assert items == [] and total == 1
