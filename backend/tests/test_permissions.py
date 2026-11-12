# M4 权限层单元测试：check_can_* 函数的"角色×归属×状态"组合覆盖。
#
# 与 test_phase3_workflow.py 红测试的分工：
#   - 红测试（TestAuth/TestWorkflowCrud）走端到端 HTTP 与 crud 函数层，需要 M5 完成后才转绿；
#   - 本文件聚焦 M4 交付物本身——纯函数权限判定，不依赖路由与状态写入；
#   - 目的是把"越权请求一定被拒"（需求九.3）在函数层就固化为回归防线，M5 拆任何 endpoint 都动不到这层。
#
# 覆盖矩阵（对应 auth.py 内 8 个函数）：
#   can_view_fault           admin/handler/user × 归属（create/assign/none）
#   check_can_assign         角色 × 状态 × 现有 assignee
#   check_can_reassign       角色 × 状态（含 D6：awaiting 禁改派）
#   check_can_start          角色 × 归属 × 状态
#   check_can_progress       同上
#   check_can_submit         同上
#   check_can_confirm        SM7/SM12 + AU8（管理员代确认，创建人停用/历史数据）
#   check_can_return         SM8：创建人 + AU8b（创建人停用/历史数据时管理员可代退回）
#   check_can_priority_change AU9：done 前管理员或创建人

from datetime import datetime

import pytest
from sqlalchemy.orm import Session

from app.auth import (
    can_view_fault,
    check_can_assign,
    check_can_confirm,
    check_can_priority_change,
    check_can_progress,
    check_can_reassign,
    check_can_return,
    check_can_start,
    check_can_submit,
)
from app.exceptions import InvalidTransitionError, PermissionDeniedError
from app.models import FaultRole, FaultStatus, Pipeline, PipelineFault, User


# ── Fixture：三种角色 + 流水线 + 可配置的故障 ─────────────────────────
@pytest.fixture
def pipeline(db_session: Session) -> Pipeline:
    p = Pipeline(code="P4", name="权限线")
    db_session.add(p)
    db_session.commit()
    return p


@pytest.fixture
def alice(db_session: Session) -> User:
    """普通用户：报修人角色。"""
    u = User(username="alice", password_hash="x", display_name="A",
             role=FaultRole.user, is_active=True, token_version=0)
    db_session.add(u)
    db_session.commit()
    return u


@pytest.fixture
def bob(db_session: Session) -> User:
    """处理人员。"""
    u = User(username="bob", password_hash="x", display_name="B",
             role=FaultRole.handler, is_active=True, token_version=0)
    db_session.add(u)
    db_session.commit()
    return u


@pytest.fixture
def carol(db_session: Session) -> User:
    """另一名处理人员（改派目标 / 越权尝试者）。"""
    u = User(username="carol", password_hash="x", display_name="C",
             role=FaultRole.handler, is_active=True, token_version=0)
    db_session.add(u)
    db_session.commit()
    return u


@pytest.fixture
def admin(db_session: Session) -> User:
    u = User(username="admin", password_hash="x", display_name="Admin",
             role=FaultRole.admin, is_active=True, token_version=0)
    db_session.add(u)
    db_session.commit()
    return u


def _make_fault(
    db: Session,
    pipeline: Pipeline,
    *,
    creator: User | None = None,
    assignee: User | None = None,
    status: FaultStatus = FaultStatus.pending,
) -> PipelineFault:
    """按参数造一条故障。关系字段用直接列写入避免 lazy 干扰。"""
    f = PipelineFault(
        pipeline_id=pipeline.id,
        location="工位1",
        occurred_at=datetime(2026, 11, 1, 10, 0, 0),
        symptom="M4 权限测试故障现象描述",
        status=status,
        created_by_id=creator.id if creator else None,
        assignee_id=assignee.id if assignee else None,
    )
    db.add(f)
    db.commit()
    db.refresh(f)
    return f


# ═════════════════════════════════════════════════════════════════════
class TestCanViewFault:
    """查看权限：需求二.4 + 需求四.4。"""

    def test_admin_views_any(self, db_session, pipeline, alice, bob, admin):
        f = _make_fault(db_session, pipeline, creator=alice, assignee=bob)
        assert can_view_fault(admin, f) is True

    def test_handler_views_assigned(self, db_session, pipeline, alice, bob):
        f = _make_fault(db_session, pipeline, creator=alice, assignee=bob)
        assert can_view_fault(bob, f) is True

    def test_handler_cannot_view_others(self, db_session, pipeline, alice, bob, carol):
        f = _make_fault(db_session, pipeline, creator=alice, assignee=bob)
        # carol 是另一 handler，非负责人非创建人
        assert can_view_fault(carol, f) is False

    def test_handler_views_own_created(self, db_session, pipeline, bob, carol):
        """处理人自己登记的故障（分派给别人），仍可见。"""
        f = _make_fault(db_session, pipeline, creator=bob, assignee=carol)
        assert can_view_fault(bob, f) is True

    def test_user_views_own_created(self, db_session, pipeline, alice, bob):
        f = _make_fault(db_session, pipeline, creator=alice, assignee=bob)
        assert can_view_fault(alice, f) is True

    def test_user_cannot_view_others(self, db_session, pipeline, bob, carol):
        """普通用户看不到别人创建、也不属于自己责任的故障（此处 bob 是 handler，
        用他创建但没有他的关系的场景验证"user 只看自己创建"）。"""
        f = _make_fault(db_session, pipeline, creator=carol, assignee=None)
        # 造一个纯 user 角色
        dave = User(username="dave", password_hash="x", display_name="D",
                    role=FaultRole.user, is_active=True, token_version=0)
        db_session.add(dave)
        db_session.commit()
        assert can_view_fault(dave, f) is False

    def test_historical_fault_only_admin_visible(self, db_session, pipeline, alice, bob, admin):
        """created_by_id/assignee_id 全 NULL 的历史数据：仅管理员可看。"""
        f = _make_fault(db_session, pipeline, creator=None, assignee=None)
        assert can_view_fault(alice, f) is False
        assert can_view_fault(bob, f) is False
        assert can_view_fault(admin, f) is True


# ═════════════════════════════════════════════════════════════════════
class TestCheckCanAssign:
    def test_admin_assigns_pending_unassigned(self, db_session, pipeline, alice, bob, admin):
        f = _make_fault(db_session, pipeline, creator=alice, assignee=None,
                        status=FaultStatus.pending)
        check_can_assign(admin, f)  # 不抛

    def test_assigner_must_be_admin(
        self, db_session, pipeline, alice, bob, admin
    ):
        """普通用户/处理人都不能指派（AU13：SM13）。"""
        f = _make_fault(db_session, pipeline, creator=alice, assignee=None,
                        status=FaultStatus.pending)
        with pytest.raises(PermissionDeniedError):
            check_can_assign(alice, f)
        with pytest.raises(PermissionDeniedError):
            check_can_assign(bob, f)

    def test_assign_on_done_rejected(self, db_session, pipeline, alice, admin):
        f = _make_fault(db_session, pipeline, creator=alice, assignee=None,
                        status=FaultStatus.done)
        with pytest.raises(InvalidTransitionError):
            check_can_assign(admin, f)

    def test_assign_on_awaiting_rejected(self, db_session, pipeline, alice, bob, admin):
        """D6：awaiting_confirmation 不允许直接指派，需先退回至 processing。"""
        f = _make_fault(db_session, pipeline, creator=alice, assignee=bob,
                        status=FaultStatus.awaiting_confirmation)
        with pytest.raises(InvalidTransitionError):
            check_can_assign(admin, f)

    def test_assign_with_existing_assignee_rejected(self, db_session, pipeline, alice, bob, admin):
        f = _make_fault(db_session, pipeline, creator=alice, assignee=bob,
                        status=FaultStatus.pending)
        with pytest.raises(PermissionDeniedError):
            check_can_assign(admin, f)


# ═════════════════════════════════════════════════════════════════════
class TestCheckCanReassign:
    def test_admin_reassign_pending(self, db_session, pipeline, alice, bob, admin):
        f = _make_fault(db_session, pipeline, creator=alice, assignee=bob,
                        status=FaultStatus.pending)
        check_can_reassign(admin, f)

    def test_admin_reassign_processing(self, db_session, pipeline, alice, bob, admin):
        f = _make_fault(db_session, pipeline, creator=alice, assignee=bob,
                        status=FaultStatus.processing)
        check_can_reassign(admin, f)

    def test_awaiting_cannot_reassign(self, db_session, pipeline, alice, bob, admin):
        """D6：awaiting_confirmation 状态禁止改派。"""
        f = _make_fault(db_session, pipeline, creator=alice, assignee=bob,
                        status=FaultStatus.awaiting_confirmation)
        with pytest.raises(InvalidTransitionError):
            check_can_reassign(admin, f)

    def test_done_cannot_reassign(self, db_session, pipeline, alice, bob, admin):
        f = _make_fault(db_session, pipeline, creator=alice, assignee=bob,
                        status=FaultStatus.done)
        with pytest.raises(InvalidTransitionError):
            check_can_reassign(admin, f)

    def test_unassigned_cannot_reassign(self, db_session, pipeline, alice, admin):
        f = _make_fault(db_session, pipeline, creator=alice, assignee=None,
                        status=FaultStatus.pending)
        with pytest.raises(PermissionDeniedError):
            check_can_reassign(admin, f)

    def test_reassigner_must_be_admin(self, db_session, pipeline, alice, bob, carol):
        f = _make_fault(db_session, pipeline, creator=alice, assignee=bob,
                        status=FaultStatus.pending)
        with pytest.raises(PermissionDeniedError):
            check_can_reassign(carol, f)  # 处理人（即便自己是负责人）不能改派


# ═════════════════════════════════════════════════════════════════════
class TestCheckCanStart:
    def test_assignee_starts_pending(self, db_session, pipeline, alice, bob):
        f = _make_fault(db_session, pipeline, creator=alice, assignee=bob,
                        status=FaultStatus.pending)
        check_can_start(bob, f)

    def test_non_assignee_cannot_start(self, db_session, pipeline, alice, bob, carol, admin):
        """SM11/AU7：非当前负责人一律拒。管理员也不能代开始。"""
        f = _make_fault(db_session, pipeline, creator=alice, assignee=bob,
                        status=FaultStatus.pending)
        for u in (alice, carol, admin):
            with pytest.raises(PermissionDeniedError):
                check_can_start(u, f)

    def test_unassigned_cannot_start(self, db_session, pipeline, alice, bob):
        """SM2：pending + 未指派，即使 bob 想开始也不行（他非负责人）。"""
        f = _make_fault(db_session, pipeline, creator=alice, assignee=None,
                        status=FaultStatus.pending)
        with pytest.raises(PermissionDeniedError):
            check_can_start(bob, f)

    def test_start_on_processing_rejected(self, db_session, pipeline, alice, bob):
        """SM10：重复执行 start。"""
        f = _make_fault(db_session, pipeline, creator=alice, assignee=bob,
                        status=FaultStatus.processing)
        with pytest.raises(InvalidTransitionError):
            check_can_start(bob, f)

    def test_start_on_done_rejected(self, db_session, pipeline, alice, bob):
        f = _make_fault(db_session, pipeline, creator=alice, assignee=bob,
                        status=FaultStatus.done)
        with pytest.raises(InvalidTransitionError):
            check_can_start(bob, f)


# ═════════════════════════════════════════════════════════════════════
class TestCheckCanProgress:
    def test_assignee_progresses(self, db_session, pipeline, alice, bob):
        f = _make_fault(db_session, pipeline, creator=alice, assignee=bob,
                        status=FaultStatus.processing)
        check_can_progress(bob, f)

    def test_non_assignee_cannot_progress(self, db_session, pipeline, alice, bob, carol):
        f = _make_fault(db_session, pipeline, creator=alice, assignee=bob,
                        status=FaultStatus.processing)
        with pytest.raises(PermissionDeniedError):
            check_can_progress(carol, f)

    def test_wrong_state_rejected(self, db_session, pipeline, alice, bob):
        f = _make_fault(db_session, pipeline, creator=alice, assignee=bob,
                        status=FaultStatus.pending)
        with pytest.raises(InvalidTransitionError):
            check_can_progress(bob, f)


# ═════════════════════════════════════════════════════════════════════
class TestCheckCanSubmit:
    def test_assignee_submits(self, db_session, pipeline, alice, bob):
        f = _make_fault(db_session, pipeline, creator=alice, assignee=bob,
                        status=FaultStatus.processing)
        check_can_submit(bob, f)

    def test_non_assignee_cannot_submit(self, db_session, pipeline, alice, bob, admin):
        f = _make_fault(db_session, pipeline, creator=alice, assignee=bob,
                        status=FaultStatus.processing)
        with pytest.raises(PermissionDeniedError):
            check_can_submit(admin, f)

    def test_wrong_state_rejected(self, db_session, pipeline, alice, bob):
        f = _make_fault(db_session, pipeline, creator=alice, assignee=bob,
                        status=FaultStatus.awaiting_confirmation)
        with pytest.raises(InvalidTransitionError):
            check_can_submit(bob, f)


# ═════════════════════════════════════════════════════════════════════
class TestCheckCanConfirm:
    def test_creator_confirms(self, db_session, pipeline, alice, bob):
        """SM7：创建人确认 → OK。"""
        f = _make_fault(db_session, pipeline, creator=alice, assignee=bob,
                        status=FaultStatus.awaiting_confirmation)
        check_can_confirm(alice, f)

    def test_handler_self_confirm_rejected(self, db_session, pipeline, alice, bob):
        """SM12：负责人不能自行确认。"""
        f = _make_fault(db_session, pipeline, creator=alice, assignee=bob,
                        status=FaultStatus.awaiting_confirmation)
        with pytest.raises(PermissionDeniedError):
            check_can_confirm(bob, f)

    def test_stranger_rejected(self, db_session, pipeline, alice, bob, carol):
        f = _make_fault(db_session, pipeline, creator=alice, assignee=bob,
                        status=FaultStatus.awaiting_confirmation)
        with pytest.raises(PermissionDeniedError):
            check_can_confirm(carol, f)

    def test_admin_proxy_when_creator_inactive(
        self, db_session, pipeline, alice, bob, admin
    ):
        """AU8：创建人停用后，管理员可代确认。"""
        alice.is_active = False
        alice.token_version += 1
        db_session.commit()
        f = _make_fault(db_session, pipeline, creator=alice, assignee=bob,
                        status=FaultStatus.awaiting_confirmation)
        check_can_confirm(admin, f)

    def test_admin_proxy_when_creator_missing(
        self, db_session, pipeline, bob, admin
    ):
        """历史数据（无创建人）：管理员可代确认。"""
        f = _make_fault(db_session, pipeline, creator=None, assignee=bob,
                        status=FaultStatus.awaiting_confirmation)
        check_can_confirm(admin, f)

    def test_admin_cannot_proxy_when_creator_active(
        self, db_session, pipeline, alice, bob, admin
    ):
        """创建人仍可自己确认时，管理员不能代确认（避免绕开业务方）。"""
        f = _make_fault(db_session, pipeline, creator=alice, assignee=bob,
                        status=FaultStatus.awaiting_confirmation)
        with pytest.raises(PermissionDeniedError):
            check_can_confirm(admin, f)

    def test_wrong_state_rejected(self, db_session, pipeline, alice, bob):
        f = _make_fault(db_session, pipeline, creator=alice, assignee=bob,
                        status=FaultStatus.processing)
        with pytest.raises(InvalidTransitionError):
            check_can_confirm(alice, f)

    def test_admin_self_assigned_cannot_confirm(self, db_session, pipeline, alice, admin):
        """管理员兼任负责人时，即便创建人停用也不能自行确认（防自闭环）。"""
        alice.is_active = False
        db_session.commit()
        f = _make_fault(db_session, pipeline, creator=alice, assignee=admin,
                        status=FaultStatus.awaiting_confirmation)
        with pytest.raises(PermissionDeniedError):
            check_can_confirm(admin, f)


# ═════════════════════════════════════════════════════════════════════
class TestCheckCanReturn:
    def test_creator_returns(self, db_session, pipeline, alice, bob):
        """SM8：创建人退回。"""
        f = _make_fault(db_session, pipeline, creator=alice, assignee=bob,
                        status=FaultStatus.awaiting_confirmation)
        check_can_return(alice, f)

    def test_non_creator_rejected(self, db_session, pipeline, alice, bob, admin):
        """退回是业务方权力：负责人不能代退；创建人仍启用时管理员也不能代退。"""
        f = _make_fault(db_session, pipeline, creator=alice, assignee=bob,
                        status=FaultStatus.awaiting_confirmation)
        with pytest.raises(PermissionDeniedError):
            check_can_return(bob, f)
        with pytest.raises(PermissionDeniedError):
            check_can_return(admin, f)

    def test_admin_proxy_when_creator_inactive(
        self, db_session, pipeline, alice, bob, admin
    ):
        """AU8b：创建人停用后，管理员可代退回（需求二.5）。"""
        alice.is_active = False
        alice.token_version += 1
        db_session.commit()
        f = _make_fault(db_session, pipeline, creator=alice, assignee=bob,
                        status=FaultStatus.awaiting_confirmation)
        check_can_return(admin, f)

    def test_admin_proxy_when_creator_missing(
        self, db_session, pipeline, bob, admin
    ):
        """历史数据（无创建人）：管理员可代退回。"""
        f = _make_fault(db_session, pipeline, creator=None, assignee=bob,
                        status=FaultStatus.awaiting_confirmation)
        check_can_return(admin, f)

    def test_admin_self_assigned_can_proxy_return(
        self, db_session, pipeline, alice, admin
    ):
        """裁定：管理员兼任负责人时仍可代退回（与代确认不同，需求二.5 未设此限制）。

        代确认侧有防自闭环拦截（TestCheckCanConfirm.test_admin_self_assigned_cannot_confirm），
        退回方向按用户当场裁定不加限制：待确认的故障打回给负责人重做本就是退回语义本身。
        """
        alice.is_active = False
        alice.token_version += 1
        db_session.commit()
        f = _make_fault(db_session, pipeline, creator=alice, assignee=admin,
                        status=FaultStatus.awaiting_confirmation)
        check_can_return(admin, f)

    def test_wrong_state_rejected(self, db_session, pipeline, alice, bob):
        f = _make_fault(db_session, pipeline, creator=alice, assignee=bob,
                        status=FaultStatus.processing)
        with pytest.raises(InvalidTransitionError):
            check_can_return(alice, f)


# ═════════════════════════════════════════════════════════════════════
class TestCheckCanPriorityChange:
    def test_admin_can_change_before_done(self, db_session, pipeline, alice, bob, admin):
        """AU9：done 之前管理员都可调优先级。"""
        for st in (
            FaultStatus.pending,
            FaultStatus.processing,
            FaultStatus.awaiting_confirmation,
        ):
            f = _make_fault(db_session, pipeline, creator=alice, assignee=bob, status=st)
            check_can_priority_change(admin, f)

    def test_creator_can_change_own_fault(self, db_session, pipeline, alice, bob):
        f = _make_fault(db_session, pipeline, creator=alice, assignee=bob,
                        status=FaultStatus.processing)
        check_can_priority_change(alice, f)

    def test_done_rejected(self, db_session, pipeline, alice, bob, admin):
        f = _make_fault(db_session, pipeline, creator=alice, assignee=bob,
                        status=FaultStatus.done)
        with pytest.raises(InvalidTransitionError):
            check_can_priority_change(admin, f)

    def test_handler_not_creator_rejected(self, db_session, pipeline, alice, bob):
        """负责人不是创建人，不能调优先级。"""
        f = _make_fault(db_session, pipeline, creator=alice, assignee=bob,
                        status=FaultStatus.processing)
        with pytest.raises(PermissionDeniedError):
            check_can_priority_change(bob, f)
