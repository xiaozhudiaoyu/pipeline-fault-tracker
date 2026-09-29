# 第 2 层：crud 单元测试 —— 内存 SQLite 独立建表，测数据访问与业务规则，不碰开发库。
#
# 验收标准清单（先写标准，再落测试）：
#
# 【正常】
#   N1 create_pipeline 成功入库，id/created_at 由数据库生成
#   N2 list_pipelines 按 code 升序返回全部
#   N3 create_fault 成功，返回对象含预加载 pipeline；初始状态强制 pending
#   N4 list_faults 默认按 occurred_at 倒序；pipeline_id/status 筛选正确；total 与 items 口径一致
#   N5 分页：page/size 切片正确，total 仍为全量
#   N6 get_fault / get_pipeline 命中返回对象
#   N7 update_fault 只改传入字段（exclude_unset 语义），未传字段原样
#   N8 合法流转 4 条：pending→processing、processing→pending（回退）、
#      processing→done（note 必填满足）、pending→done
#   N9 →done 写入 closed_at 与 handling_note；回退到非 done 清空 closed_at
# 【异常】
#   E1 get_pipeline 不存在 → PipelineNotFoundError
#   E2 get_fault 不存在 → FaultNotFoundError
#   E3 create_fault 引用不存在的 pipeline → PipelineNotFoundError
#   E4 create_pipeline 编码重复 → PipelineCodeDuplicateError
#   E5 同状态流转（pending→pending 等 3 种）→ InvalidTransitionError
#   E6 done 终态不可逆（done→pending / done→processing / done→done）→ InvalidTransitionError
#   E7 →done 未填 note / note 纯空格 → HandlingNoteRequiredError
#   E8 done 后 update_fault 改 handling_note → HandlingNoteLockedError；改 location/symptom 仍放行
# 【边界】
#   B1 list_faults 空库 → ([], 0)
#   B2 页码超出数据量 → 空 items 但 total 不变
#   B3 →done 时 note 恰为 5 个有效字符（strip 后）→ 放行

from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app import crud, schemas
from app.exceptions import (
    FaultNotFoundError,
    HandlingNoteLockedError,
    HandlingNoteRequiredError,
    InvalidTransitionError,
    PipelineCodeDuplicateError,
    PipelineNotFoundError,
)
from app.models import FaultStatus


# ---- 造数工具：保持用例本体简洁 ----
def _make_pipeline(db: Session, code: str = "LINE-A", name: str = "总装线A"):
    return crud.create_pipeline(db, schemas.PipelineCreate(code=code, name=name))


def _make_fault(db: Session, pipeline_id: int, minutes_ago: int = 60, symptom: str = "传送带异响并卡死"):
    """登记一条故障；minutes_ago 控制 occurred_at，便于排序/分页断言。"""
    return crud.create_fault(
        db,
        schemas.FaultCreate(
            pipeline_id=pipeline_id,
            location="3号工位传送带",
            occurred_at=datetime.now() - timedelta(minutes=minutes_ago),
            symptom=symptom,
        ),
    )


def _to_done(db: Session, fault_id: int, note: str = "更换皮带并复测正常"):
    """把故障推到 done 终态（先 processing 再 done），供锁定/不可逆类用例复用。"""
    crud.transition_fault(db, fault_id, FaultStatus.processing, None)
    return crud.transition_fault(db, fault_id, FaultStatus.done, note)


# ── 流水线：正常 ─────────────────────────────────────────────────────────
class TestPipelineHappy:
    def test_n1_create_pipeline(self, db_session):
        p = _make_pipeline(db_session)
        assert p.id is not None            # 数据库自增生成
        assert p.created_at is not None    # server_default 生成
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


# ── 流水线：异常 ─────────────────────────────────────────────────────────
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
        p = _make_pipeline(db_session)
        f = _make_fault(db_session, p.id)
        assert f.status is FaultStatus.pending   # 初始状态强制 pending
        assert f.pipeline.code == "LINE-A"       # 返回对象含预加载 pipeline
        assert f.handling_note is None
        assert f.closed_at is None

    def test_n4_list_default_order_and_filters(self, db_session):
        p1 = _make_pipeline(db_session, code="LINE-A")
        p2 = _make_pipeline(db_session, code="LINE-B")
        f_old = _make_fault(db_session, p1.id, minutes_ago=120)
        f_mid = _make_fault(db_session, p1.id, minutes_ago=60)
        f_new = _make_fault(db_session, p2.id, minutes_ago=10)

        items, total = crud.list_faults(db_session)
        assert total == 3
        assert [f.id for f in items] == [f_new.id, f_mid.id, f_old.id]  # occurred_at 倒序

        items, total = crud.list_faults(db_session, pipeline_id=p1.id)
        assert total == 2 and {f.id for f in items} == {f_old.id, f_mid.id}

        crud.transition_fault(db_session, f_mid.id, FaultStatus.processing, None)
        items, total = crud.list_faults(db_session, status=FaultStatus.processing)
        assert total == 1 and items[0].id == f_mid.id

    def test_n5_pagination(self, db_session):
        p = _make_pipeline(db_session)
        # faults[0] 最近（10 分钟前）… faults[4] 最早（50 分钟前）；倒序后顺序即 faults[0..4]
        faults = [_make_fault(db_session, p.id, minutes_ago=i * 10) for i in range(1, 6)]
        items, total = crud.list_faults(db_session, page=2, size=2)
        assert total == 5                                    # total 是全量
        assert [f.id for f in items] == [faults[2].id, faults[3].id]  # 倒序第 3、4 条

    def test_n6_get_fault(self, db_session):
        p = _make_pipeline(db_session)
        f = _make_fault(db_session, p.id)
        got = crud.get_fault(db_session, f.id)
        assert got.id == f.id and got.pipeline.code == "LINE-A"

    def test_n7_update_only_passed_fields(self, db_session):
        p = _make_pipeline(db_session)
        f = _make_fault(db_session, p.id)
        updated = crud.update_fault(db_session, f.id, schemas.FaultUpdate(location="5号工位电机"))
        assert updated.location == "5号工位电机"
        assert updated.symptom == "传送带异响并卡死"   # 未传字段原样不动

    def test_n8_n9_legal_transitions_and_closed_at(self, db_session):
        p = _make_pipeline(db_session)
        f = _make_fault(db_session, p.id)
        # pending → processing：note 可不传
        f = crud.transition_fault(db_session, f.id, FaultStatus.processing, None)
        assert f.status is FaultStatus.processing and f.closed_at is None
        # processing → pending：回退合法
        f = crud.transition_fault(db_session, f.id, FaultStatus.pending, None)
        assert f.status is FaultStatus.pending
        # pending → done：note 必填，满足则写入 closed_at
        f = crud.transition_fault(db_session, f.id, FaultStatus.done, "更换皮带并复测正常")
        assert f.status is FaultStatus.done
        assert f.handling_note == "更换皮带并复测正常"
        assert f.closed_at is not None

    def test_n9_rollback_clears_closed_at(self, db_session):
        p = _make_pipeline(db_session)
        f = _make_fault(db_session, p.id)
        crud.transition_fault(db_session, f.id, FaultStatus.processing, None)
        # processing 状态下传 note 更新说明，目标非 done → closed_at 保持 None
        f = crud.transition_fault(db_session, f.id, FaultStatus.pending, "已安排维修工跟进处理")
        assert f.closed_at is None
        assert f.handling_note == "已安排维修工跟进处理"


# ── 故障：异常 ───────────────────────────────────────────────────────────
class TestFaultError:
    def test_e2_get_fault_not_found(self, db_session):
        with pytest.raises(FaultNotFoundError):
            crud.get_fault(db_session, 999)

    def test_e3_create_fault_unknown_pipeline(self, db_session):
        with pytest.raises(PipelineNotFoundError):
            _make_fault(db_session, pipeline_id=999)

    @pytest.mark.parametrize("target", [FaultStatus.pending, FaultStatus.processing, FaultStatus.done])
    def test_e5_same_status_transition(self, db_session, target):
        p = _make_pipeline(db_session)
        f = _make_fault(db_session, p.id)  # 初始 pending
        if target is not FaultStatus.pending:
            f = crud.transition_fault(db_session, f.id, target, "先推进到目标状态再测同状态")
        with pytest.raises(InvalidTransitionError):
            crud.transition_fault(db_session, f.id, target, None)

    @pytest.mark.parametrize("target", [FaultStatus.pending, FaultStatus.processing, FaultStatus.done])
    def test_e6_done_is_terminal(self, db_session, target):
        p = _make_pipeline(db_session)
        f = _make_fault(db_session, p.id)
        _to_done(db_session, f.id)
        with pytest.raises(InvalidTransitionError):
            crud.transition_fault(db_session, f.id, target, "试图复活已完成记录")

    @pytest.mark.parametrize("note", [None, "", "     "])
    def test_e7_done_requires_note(self, db_session, note):
        p = _make_pipeline(db_session)
        f = _make_fault(db_session, p.id)
        with pytest.raises(HandlingNoteRequiredError):
            crud.transition_fault(db_session, f.id, FaultStatus.done, note)

    def test_e8_note_locked_after_done(self, db_session):
        p = _make_pipeline(db_session)
        f = _make_fault(db_session, p.id)
        _to_done(db_session, f.id)
        with pytest.raises(HandlingNoteLockedError):
            crud.update_fault(db_session, f.id, schemas.FaultUpdate(handling_note="事后篡改结案结论"))
        # location / symptom 不受锁定限制（错别字修正在 done 后仍合理）
        updated = crud.update_fault(db_session, f.id, schemas.FaultUpdate(location="5号工位电机"))
        assert updated.location == "5号工位电机"


# ── 边界 ─────────────────────────────────────────────────────────────────
class TestBoundary:
    def test_b1_empty_list(self, db_session):
        items, total = crud.list_faults(db_session)
        assert items == [] and total == 0

    def test_b2_page_beyond_data(self, db_session):
        p = _make_pipeline(db_session)
        _make_fault(db_session, p.id)
        items, total = crud.list_faults(db_session, page=5, size=10)
        assert items == [] and total == 1   # 页码超界：空页但 total 不虚报

    def test_b3_done_note_exactly_five_chars(self, db_session):
        p = _make_pipeline(db_session)
        f = _make_fault(db_session, p.id)
        done = crud.transition_fault(db_session, f.id, FaultStatus.done, "已修复完成")
        assert done.status is FaultStatus.done
        assert done.handling_note == "已修复完成"
