# 第三阶段红测试：用户权限与处理闭环 —— 需求三/四/五/九规则先行固化为失败用例。
#
# 本文件引用的模块/模型/端点（auth、User、FaultTimeline、awaiting_confirmation、
# 各动作端点）尚未实现，预期全部 FAIL（红）。M5 实现后逐条转绿。
#
# 验收标准清单（需求原文条款 → 测试编号）：
#
# ── 状态机（需求三）──
#   SM1 pending + 指派 → 状态仍 pending，assignee 被设置
#   SM2 pending + 未指派 → 不允许开始处理（409）
#   SM3 pending + 已指派 + 负责人开始 → processing
#   SM4 processing + 负责人追加进展（note 非空）→ processing 保持，时间线多一条
#   SM5 processing + 进展 note 纯空格 → 422
#   SM6 processing + 负责人提交结果（note 必填）→ awaiting_confirmation
#   SM7 awaiting_confirmation + 创建人确认 → done，closed_at 写入
#   SM8 awaiting_confirmation + 创建人退回（原因必填）→ processing，assignee 不变
#   SM9 done 终态：任何动作拒绝（409）
#   SM10 重复执行同一动作（如已 processing 再 start）→ 409
#   SM11 非当前负责人不能 start/progress/submit → 403
#   SM12 负责人不能自行确认 → 403
#   SM13 普通用户不能指派/改派 → 403
#
# ── 权限（需求二）──
#   AU1 未登录访问业务接口 → 401
#   AU2 停用账号的 token 继续请求 → 401（token_version bump）
#   AU3 普通用户列表只看自己创建的
#   AU4 处理人员列表只看分派给自己的
#   AU5 管理员列表看全部 + 可按负责人筛选 + 可查未分派
#   AU6 普通用户不能查看/修改他人故障 → 403/404
#   AU7 管理员改派需填原因，改派后旧负责人失权、新负责人可操作
#   AU8 创建人停用时管理员可代确认（需原因）
#   AU8b 创建人停用/无创建人时管理员可代退回（需原因），负责人不变（需求二.5）
#   AU9 管理员在故障完成前可调优先级，优先级调整记入时间线
#
# ── 时间线（需求四）──
#   TL1 每个动作产生一条时间线记录（操作人/时间/动作/前后值/说明）
#   TL2 新记录不可覆盖旧记录（append-only）
#   TL3 状态变更与时间线同事务：若时间线写入失败，状态不变
#   TL4 时间线列表按 created_at 正序
#
# ── 存量缺陷（需求五）──
#   FX1 时区：aware 输入（+08:00 / Z 两种写法）归一为本地 naive，13:00 存后仍显示 13:00
#   FX2 空格校验：登记与修改两个通道，必填字段都不能只填空格；合法值 strip 后入库
#   FX3 显式 null：priority/location/symptom 传 null → 422 明确提示（原为 500 或静默忽略），数据不变
#   FX4 data 目录：SQLite 库文件父目录不存在时自动创建（含 alembic 迁移进程）
#   FX5 进程时区：进程时区为 UTC（容器实况）时，北京墙钟“此刻”仍可登记且 created_at 仍为北京墙钟
#
# ── 旧数据兼容（需求六）──
#   HD1 旧故障 created_by_id/assignee_id 为 NULL → 响应显示"历史数据"
#   HD2 旧 handling_note 导入为 is_imported=true 的时间线记录
#   HD3 管理员可对"历史数据"故障指派负责人继续处理

# ─── 以下 import 在实现前会失败（预期行为：ModuleNotFoundError = 红） ───
# 实现后逐步取消注释或替换为正确路径。

import os
import pytest
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from sqlalchemy.orm import Session

from app import timeutil
from app.config import settings

# 这些在 M1/M3 实现后才能正常导入
# from app.models import User, FaultTimeline, FaultStatus, FaultRole, PipelineFault
# from app.auth import hash_password, verify_password, create_token, decode_token
# from app import crud, schemas


# ═══════════════════════════════════════════════════════════════════════════
# 第一部分：模型层测试（M1 实现后转绿）
# ═══════════════════════════════════════════════════════════════════════════

class TestModelsPhase3:
    """验证新增模型：User、FaultTimeline、FaultStatus 新枚举值。"""

    def test_sm_new_status_value(self):
        from app.models import FaultStatus
        assert hasattr(FaultStatus, "awaiting_confirmation")
        assert FaultStatus.awaiting_confirmation.value == "awaiting_confirmation"

    def test_user_model_fields(self, db_session: Session):
        from app.models import User, FaultRole
        u = User(
            username="handler01",
            password_hash="$2b$hashed_value",
            display_name="张处理",
            role=FaultRole.handler,
            is_active=True,
            token_version=0,
        )
        db_session.add(u)
        db_session.commit()
        db_session.refresh(u)
        assert u.id is not None
        assert u.created_at is not None

    def test_fault_new_columns(self, db_session: Session):
        # 需要 User 表先存在（外键依赖）
        from app.models import User, Pipeline, PipelineFault, FaultRole
        u = User(username="u1", password_hash="x", display_name="U1",
                 role=FaultRole.user, is_active=True, token_version=0)
        db_session.add(u)
        db_session.commit()
        p = Pipeline(code="L1", name="线1")
        db_session.add(p)
        db_session.commit()
        f = PipelineFault(
            pipeline_id=p.id, location="工位1",
            occurred_at=timeutil.business_now(), symptom="测试故障现象描述",
            created_by_id=u.id, assignee_id=None,
        )
        db_session.add(f)
        db_session.commit()
        db_session.refresh(f)
        assert f.created_by_id == u.id
        assert f.assignee_id is None  # 未指派

    def test_timeline_model_fields(self, db_session: Session):
        from app.models import User, Pipeline, PipelineFault, FaultTimeline, FaultRole, TimelineAction
        u = User(username="admin1", password_hash="x", display_name="Admin",
                 role=FaultRole.admin, is_active=True, token_version=0)
        db_session.add(u)
        db_session.commit()
        p = Pipeline(code="L2", name="线2")
        db_session.add(p)
        db_session.commit()
        f = PipelineFault(pipeline_id=p.id, location="工位2",
                          occurred_at=timeutil.business_now(), symptom="时间线测试故障",
                          created_by_id=u.id)
        db_session.add(f)
        db_session.commit()
        tl = FaultTimeline(
            fault_id=f.id, action=TimelineAction.create,
            operator_id=u.id, operator_name_snapshot="Admin",
            to_status="pending", note="登记测试", is_imported=False,
        )
        db_session.add(tl)
        db_session.commit()
        db_session.refresh(tl)
        assert tl.id is not None
        assert tl.created_at is not None


# ═══════════════════════════════════════════════════════════════════════════
# 第二部分：认证模块测试（M3 实现后转绿）
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.anyio
class TestAuth:
    """POST /api/auth/login、GET /api/auth/me、token_version 失效机制。

    M3/M4 已实现本模块，本组测试走 raw_client（不预注入 admin 身份），
    观察真实 JWT 校验链；建用户走 crud.create_user 以保持密码哈希路径一致。
    """

    @pytest.fixture(autouse=True)
    def _require_auth(self):
        pytest.importorskip("app.auth", reason="M3: auth 模块尚未实现")

    async def test_au1_unauthenticated_returns_401(self, raw_client):
        """未登录访问业务接口 → 401。M4 已给 GET /api/faults 挂 require_login。"""
        resp = await raw_client.get("/api/faults")
        assert resp.status_code == 401

    async def test_login_success_and_me(self, raw_client, db_session):
        """正确用户名密码 → 200 token；带 token 访问 me → 200 含 username/role。"""
        from app import crud, schemas
        from app.models import FaultRole

        crud.create_user(
            db_session,
            schemas.UserCreate(
                username="testuser", password="pass123",
                display_name="测试用户", role=FaultRole.user,
            ),
        )
        resp = await raw_client.post(
            "/api/auth/login", json={"username": "testuser", "password": "pass123"}
        )
        assert resp.status_code == 200
        token = resp.json()["access_token"]
        me_resp = await raw_client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert me_resp.status_code == 200
        body = me_resp.json()
        assert body["username"] == "testuser"
        assert body["role"] == "user"

    async def test_au2_deactivated_token_invalidated(self, raw_client, db_session):
        """管理员停用账号后，该用户原 token 立即失效 → 401（set_user_active 顺手 bump tv）。"""
        from app import crud, schemas
        from app.models import FaultRole

        u = crud.create_user(
            db_session,
            schemas.UserCreate(
                username="deactuser", password="password123",
                display_name="待停用", role=FaultRole.user,
            ),
        )
        login = await raw_client.post(
            "/api/auth/login", json={"username": "deactuser", "password": "password123"}
        )
        assert login.status_code == 200
        token = login.json()["access_token"]
        # 走真实停用路径：is_active=False + token_version 同步 bump
        crud.set_user_active(db_session, u, False)
        me_resp = await raw_client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert me_resp.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════
# 第三部分：工作流闭环测试（M5 实现后转绿）
# 本段为 crud 层单元测试，直接调函数不经 HTTP，便于隔离验证状态机与时间线。
# ═══════════════════════════════════════════════════════════════════════════

class TestWorkflowCrud:
    """需求三：完整处理流程 pending → assign → start → progress → submit → confirm/return → done。"""

    @pytest.fixture(autouse=True)
    def _require_auth(self):
        """app.auth 尚未实现时整组 skip，不污染其他测试的 fixture 链。"""
        pytest.importorskip("app.auth", reason="M3: auth 模块尚未实现")

    @pytest.fixture(autouse=True)
    def _setup(self, db_session: Session):
        """准备流水线 + 三个角色用户 + 一条故障，供各用例复用。"""
        self.db = db_session
        from app.models import User, FaultRole
        from app.auth import hash_password
        from app import crud, schemas

        self.p = crud.create_pipeline(db_session, schemas.PipelineCreate(code="WF-A", name="工作流A"))
        self.creator = User(username="creator", password_hash=hash_password("pw_placeholder"),
                            display_name="报修人", role=FaultRole.user, is_active=True, token_version=0)
        self.handler = User(username="handler", password_hash=hash_password("pw_placeholder"),
                            display_name="处理人", role=FaultRole.handler, is_active=True, token_version=0)
        self.admin = User(username="admin", password_hash=hash_password("pw_placeholder"),
                          display_name="管理员", role=FaultRole.admin, is_active=True, token_version=0)
        db_session.add_all([self.creator, self.handler, self.admin])
        db_session.commit()

        # M5 后 create_fault 接受 creator，内部写入 created_by_id 与 create 时间线（同事务）
        self.fault = crud.create_fault(
            db_session,
            schemas.FaultCreate(
                pipeline_id=self.p.id, location="1号工位",
                occurred_at=timeutil.business_now() - timedelta(minutes=30),
                symptom="传送带异响并卡死需要紧急处理",
            ),
            creator=self.creator,
        )

    def test_sm1_assign(self):
        """指派：pending 状态下管理员指派负责人，状态不变，assignee 设置。"""
        from app import crud
        f = crud.assign_fault(self.db, self.fault.id, self.handler.id, actor=self.admin)
        assert f.status.value == "pending"
        assert f.assignee_id == self.handler.id

    def test_sm3_start(self):
        """开始处理：已指派的 pending → processing（仅负责人可操作）。"""
        from app import crud
        crud.assign_fault(self.db, self.fault.id, self.handler.id, actor=self.admin)
        f = crud.start_fault(self.db, self.fault.id, actor=self.handler)
        assert f.status.value == "processing"

    def test_sm4_progress(self):
        """追加进展：processing 状态下负责人可多次记录，时间线增加。"""
        from app import crud
        from app.models import FaultTimeline
        crud.assign_fault(self.db, self.fault.id, self.handler.id, actor=self.admin)
        crud.start_fault(self.db, self.fault.id, actor=self.handler)
        crud.add_progress(self.db, self.fault.id, "检查电机发现轴承磨损", actor=self.handler)
        crud.add_progress(self.db, self.fault.id, "已更换轴承待复测", actor=self.handler)
        timelines = self.db.query(FaultTimeline).filter_by(fault_id=self.fault.id).all()
        progress_records = [t for t in timelines if t.action.value == "progress"]
        assert len(progress_records) == 2

    def test_sm6_submit(self):
        """提交结果：processing → awaiting_confirmation，结果说明必填。"""
        from app import crud
        crud.assign_fault(self.db, self.fault.id, self.handler.id, actor=self.admin)
        crud.start_fault(self.db, self.fault.id, actor=self.handler)
        f, _tid = crud.submit_fault(self.db, self.fault.id, "更换轴承并复测３０分钟正常", actor=self.handler)
        assert f.status.value == "awaiting_confirmation"

    def test_sm7_confirm(self):
        """确认完成：awaiting_confirmation + 创建人确认 → done。"""
        from app import crud
        crud.assign_fault(self.db, self.fault.id, self.handler.id, actor=self.admin)
        crud.start_fault(self.db, self.fault.id, actor=self.handler)
        crud.submit_fault(self.db, self.fault.id, "更换轴承并复测正常", actor=self.handler)
        f = crud.confirm_fault(self.db, self.fault.id, None, actor=self.creator)
        assert f.status.value == "done"
        assert f.closed_at is not None

    def test_sm8_return(self):
        """退回：awaiting_confirmation + 创建人退回 → processing，assignee 不变。"""
        from app import crud
        crud.assign_fault(self.db, self.fault.id, self.handler.id, actor=self.admin)
        crud.start_fault(self.db, self.fault.id, actor=self.handler)
        crud.submit_fault(self.db, self.fault.id, "更换轴承并复测正常", actor=self.handler)
        f = crud.return_fault(self.db, self.fault.id, "复测仍有异响未彻底解决", actor=self.creator)
        assert f.status.value == "processing"
        assert f.assignee_id == self.handler.id  # 负责人不变

    def test_sm9_done_terminal(self):
        """done 后任何操作拒绝。"""
        from app import crud
        from app.exceptions import InvalidTransitionError
        crud.assign_fault(self.db, self.fault.id, self.handler.id, actor=self.admin)
        crud.start_fault(self.db, self.fault.id, actor=self.handler)
        crud.submit_fault(self.db, self.fault.id, "更换轴承并复测正常", actor=self.handler)
        crud.confirm_fault(self.db, self.fault.id, None, actor=self.creator)
        with pytest.raises(InvalidTransitionError):
            crud.start_fault(self.db, self.fault.id, actor=self.handler)

    def test_sm11_wrong_handler_rejected(self):
        """非当前负责人不能 start/progress/submit → PermissionError。"""
        from app import crud
        from app.exceptions import PermissionDeniedError
        crud.assign_fault(self.db, self.fault.id, self.handler.id, actor=self.admin)
        with pytest.raises(PermissionDeniedError):
            crud.start_fault(self.db, self.fault.id, actor=self.creator)

    def test_au7_reassign(self):
        """管理员改派：旧负责人失权、新负责人可操作。"""
        from app import crud
        from app.exceptions import PermissionDeniedError
        from app.models import User, FaultRole
        from app.auth import hash_password
        handler2 = User(username="handler2", password_hash=hash_password("pw_placeholder"),
                        display_name="处理人2", role=FaultRole.handler, is_active=True, token_version=0)
        self.db.add(handler2)
        self.db.commit()
        # 指派 handler → start → 改派 handler2
        crud.assign_fault(self.db, self.fault.id, self.handler.id, actor=self.admin)
        crud.start_fault(self.db, self.fault.id, actor=self.handler)
        f = crud.reassign_fault(self.db, self.fault.id, handler2.id, "原负责人出差", actor=self.admin)
        assert f.assignee_id == handler2.id
        # 旧 handler 不能再 progress
        with pytest.raises(PermissionDeniedError):
            crud.add_progress(self.db, self.fault.id, "旧负责人试图操作", actor=self.handler)
        # 新 handler2 可以
        crud.add_progress(self.db, self.fault.id, "新负责人继续跟进处理", actor=handler2)

    def test_au8_admin_confirm_on_behalf(self):
        """创建人停用后管理员可代确认（需原因）。"""
        from app import crud
        crud.assign_fault(self.db, self.fault.id, self.handler.id, actor=self.admin)
        crud.start_fault(self.db, self.fault.id, actor=self.handler)
        crud.submit_fault(self.db, self.fault.id, "更换轴承并复测正常", actor=self.handler)
        # 停用创建人（check_can_confirm 内会判 creator.is_active）
        self.creator.is_active = False
        self.creator.token_version += 1
        self.db.commit()
        # 管理员代确认：reason 必填（crud 层已校验 is_delegated 分支）
        f = crud.confirm_fault(self.db, self.fault.id, "创建人已停用，管理员代确认", actor=self.admin)
        assert f.status.value == "done"

    def test_au8b_admin_return_on_behalf(self):
        """创建人停用后管理员可代退回（需求二.5）：状态回 processing、负责人不变、时间线记操作人与原因。"""
        from app import crud
        from app.models import FaultTimeline
        crud.assign_fault(self.db, self.fault.id, self.handler.id, actor=self.admin)
        crud.start_fault(self.db, self.fault.id, actor=self.handler)
        crud.submit_fault(self.db, self.fault.id, "更换轴承并复测正常", actor=self.handler)
        # 停用创建人（走真实停用路径，顺手 bump token_version，与代确认用例同口径）
        crud.set_user_active(self.db, self.creator, False)
        f = crud.return_fault(self.db, self.fault.id, "创建人已停用，管理员代退回", actor=self.admin)
        assert f.status.value == "processing"
        assert f.assignee_id == self.handler.id  # 负责人不变
        entries = self.db.query(FaultTimeline).filter_by(fault_id=f.id).all()
        returned = [t for t in entries if t.action.value == "return"]
        assert len(returned) == 1
        assert returned[0].operator_id == self.admin.id
        assert returned[0].note == "创建人已停用，管理员代退回"


# ═══════════════════════════════════════════════════════════════════════════
# 第四部分：时间线原子性测试（需求四.2，M5 实现后转绿）
# ═══════════════════════════════════════════════════════════════════════════

class TestTimelineAtomicity:
    """状态变更与时间线同事务：任一步失败整体回滚。"""

    def test_tl3_atomic_rollback(self, db_session: Session, monkeypatch):
        """若时间线写入失败，状态不应被改变（同事务 commit 从未执行）。"""
        from app import crud, schemas
        from app.auth import hash_password
        from app.models import (
            FaultRole, FaultStatus, FaultTimeline, Pipeline, PipelineFault, User,
        )

        admin = User(username="tl3-admin", password_hash=hash_password("pw_placeholder"),
                     display_name="A", role=FaultRole.admin, is_active=True, token_version=0)
        handler = User(username="tl3-handler", password_hash=hash_password("pw_placeholder"),
                       display_name="H", role=FaultRole.handler, is_active=True, token_version=0)
        creator = User(username="tl3-creator", password_hash=hash_password("pw_placeholder"),
                       display_name="C", role=FaultRole.user, is_active=True, token_version=0)
        db_session.add_all([admin, handler, creator])
        db_session.commit()

        p = Pipeline(code="TL3", name="原子性")
        db_session.add(p)
        db_session.commit()
        fault = crud.create_fault(
            db_session,
            schemas.FaultCreate(
                pipeline_id=p.id, location="工位", occurred_at=timeutil.business_now(),
                symptom="原子性测试故障现象描述",
            ),
            creator=creator,
        )
        crud.assign_fault(db_session, fault.id, handler.id, actor=admin)
        crud.start_fault(db_session, fault.id, actor=handler)
        # 记录当前数据库状态，确保回滚后仍一致
        db_session.expire_all()
        assert db_session.get(PipelineFault, fault.id).status == FaultStatus.processing

        # 让时间线实例化抛异常：_write_timeline 里 FaultTimeline(...) 会即时报，
        # 导致 submit_fault 末尾的 db.commit() 永远执行不到。
        def _boom(*args, **kwargs):
            raise RuntimeError("模拟时间线写入失败")

        monkeypatch.setattr(FaultTimeline, "__init__", _boom)

        with pytest.raises(RuntimeError):
            crud.submit_fault(db_session, fault.id, "不该生效", actor=handler)

        # 事务未 commit → 数据库里状态仍为 processing；handling_note 仍为空。
        db_session.rollback()
        db_session.expire_all()
        reloaded = db_session.get(PipelineFault, fault.id)
        assert reloaded.status == FaultStatus.processing
        assert reloaded.handling_note in (None, "")
        # 时间线列表不应出现 submit 记录
        assert not [t for t in reloaded.timelines if t.action.value == "submit"]


# ═══════════════════════════════════════════════════════════════════════════
# 第五部分：存量缺陷修复测试（需求五，M7 实现后转绿）
# ═══════════════════════════════════════════════════════════════════════════

class TestBugFixes:
    """需求五（FX1~FX4）：时区口径 / 空白必填 / 显式 null / SQLite 目录。

    四条由 M0 的 xfail 红测试改写而来（原写法不构成有效验证）：fx1 调的是已废弃的
    `create_fault(created_by_id=)` 签名（报 TypeError 而非断言失败）、fx2/fx3 是
    `assert False` 占位、fx4 直接测 SQLAlchemy 的 create_engine 而非本项目代码。
    """

    def test_fx1_timezone_preserved(self, db_session: Session, admin_user):
        """FX1 时区：naive/+08:00/Z 三种写法入库后都是同一业务时区墙钟（需求五.1）。

        修复前 validator 原样返回入参，SQLite 落库只看墙钟字段、忽略 tzinfo，
        传 "05:00Z"（= 北京 13:00）就存成 05:00 → 前端按本地解析显示 05:00。
        断言用 expire_all 后从库重读，避免拿到 session 里尚未刷新的写入实例。
        """
        from app import crud, schemas
        from app.models import PipelineFault

        p = crud.create_pipeline(db_session, schemas.PipelineCreate(code="TZ", name="时区测试"))
        for iso in (
            "2026-11-01T13:00:00",        # 前端 el-date-picker 的实际写法（无偏移）
            "2026-11-01T13:00:00+08:00",  # 带本地偏移
            "2026-11-01T05:00:00+00:00",  # 同一时刻的 UTC 写法（toISOString 产物）
        ):
            body = schemas.FaultCreate(
                pipeline_id=p.id,
                location="1号工位",
                occurred_at=datetime.fromisoformat(iso),
                symptom="时区测试故障现象描述",
            )
            # 出口即业务时区 naive，与 models._local_now()（created_at 等）口径一致
            assert body.occurred_at.tzinfo is None, iso
            f = crud.create_fault(db_session, body, creator=admin_user)
            db_session.expire_all()
            stored = db_session.get(PipelineFault, f.id).occurred_at
            aware = datetime.fromisoformat(iso)
            expected = timeutil.to_business_naive(aware)
            assert stored == expected, iso
            # 需求五.1 的具体场景（业务时区 +08）：三种写法都落在北京墙钟 13:00。
            # 判据取自 settings 而不是进程时区（旧写法 astimezone() 在 CI 的 UTC runner
            # 上会算出 05:00，导致该断言被整段跳过、缺陷漏网）。
            if settings.business_utc_offset_hours == 8:
                assert stored.hour == 13, iso

    @pytest.mark.anyio
    async def test_fx1b_api_response_has_no_utc_offset(self, client):
        """FX1 链路级：POST 传 Z 写法，响应与重查都返回业务时区墙钟且不带时区后缀。

        响应若带 +00:00/Z，前端 new Date() 会按 UTC 解析再转本地 → 显示偏移；
         naive ISO 被前端按本地解析，故响应必须是“本地时间 + 无后缀”这一套。
        """
        pid = (await client.post("/api/pipelines", json={"code": "TZAPI", "name": "时区链路线"})).json()["id"]
        resp = await client.post(
            "/api/faults",
            json={
                "pipeline_id": pid,
                "location": "1号工位",
                "occurred_at": "2026-11-01T05:00:00Z",  # 北京 13:00 的 UTC 写法
                "symptom": "时区链路验证故障现象",
            },
        )
        assert resp.status_code == 201
        local_noon = datetime(2026, 11, 1, 5, 0, tzinfo=timezone.utc)
        expected = timeutil.to_business_naive(local_noon).isoformat()
        assert resp.json()["occurred_at"] == expected
        detail = await client.get(f"/api/faults/{resp.json()['id']}")
        got = detail.json()["occurred_at"]
        assert got == expected and "+" not in got and not got.endswith("Z"), got

    @pytest.mark.anyio
    async def test_fx2_whitespace_rejected(self, client):
        """FX2 空格：必填内容不能只填空格（登记+修改双通道），合法值入库为 strip 后干净值。"""
        pid = (await client.post("/api/pipelines", json={"code": "WS", "name": "空白校验线"})).json()["id"]
        # 登记通道：修复前 symptom="     " 能过 min_length=5 → 201 入库
        blank = await client.post(
            "/api/faults",
            json={
                "pipeline_id": pid,
                "location": "2号工位",
                "occurred_at": (timeutil.business_now() - timedelta(minutes=5)).isoformat(),
                "symptom": "     ",
            },
        )
        assert blank.status_code == 422
        assert blank.json()["code"] == "validation_error"
        assert blank.json()["details"][0]["field"] == "symptom"

        created = await client.post(
            "/api/faults",
            json={
                "pipeline_id": pid,
                "location": "3号工位",
                "occurred_at": (timeutil.business_now() - timedelta(minutes=5)).isoformat(),
                "symptom": "传送带异响并卡死",
            },
        )
        assert created.status_code == 201
        fid = created.json()["id"]

        # 修改通道：纯空格 / 不足长度 都 422，不产生脏数据
        for payload in ({"symptom": "     "}, {"symptom": "  只三个字  "}):
            bad = await client.patch(f"/api/faults/{fid}", json=payload)
            assert bad.status_code == 422, payload

        # 首字符空白仍由字段级 pattern 拦（既有裁定不动，不同于尾部空白的“抹平后接受”）
        head = await client.patch(f"/api/faults/{fid}", json={"location": " 3号工位"})
        assert head.status_code == 422

        # 合法但带首尾空白：200，且入库为 trim 后的值
        ok = await client.patch(
            f"/api/faults/{fid}", json={"location": "4号工位 ", "symptom": "  传送带异响并卡死  "}
        )
        assert ok.status_code == 200
        assert ok.json()["location"] == "4号工位"
        assert ok.json()["symptom"] == "传送带异响并卡死"

    @pytest.mark.anyio
    async def test_fx3_explicit_null_rejected_not_500(self, client):
        """FX3 显式 null：priority/location/symptom 传 null → 422 明确提示，不报 500、不改数据。

        修复前的三种行为：priority=null 被 crud 过滤后静默忽略（200，调用方以为改成了）；
        location/symptom=null 直达 setattr → NOT NULL 约束 → IntegrityError 500（已实测复现）。
        """
        pid = (await client.post("/api/pipelines", json={"code": "NULLV", "name": "显式空值线"})).json()["id"]
        created = await client.post(
            "/api/faults",
            json={
                "pipeline_id": pid,
                "location": "7号工位",
                "occurred_at": (timeutil.business_now() - timedelta(minutes=5)).isoformat(),
                "symptom": "显式 null 验证故障现象",
                "priority": "urgent",
            },
        )
        assert created.status_code == 201
        fid = created.json()["id"]

        for field in ("priority", "location", "symptom", "handling_note"):
            resp = await client.patch(f"/api/faults/{fid}", json={field: None})
            assert resp.status_code == 422, field
            assert resp.json()["code"] == "validation_error", field
            assert [d["field"] for d in resp.json()["details"]] == [field], field

        # 四次失败请求都没改坏原数据
        detail = await client.get(f"/api/faults/{fid}")
        assert detail.json()["priority"] == "urgent"
        assert detail.json()["location"] == "7号工位"
        assert detail.json()["symptom"] == "显式 null 验证故障现象"

    def test_fx4_sqlite_parent_dir_auto_created(self, tmp_path):
        """FX4 目录：DATABASE_URL 指向不存在的子目录时自动创建；内存库与 PG 不造目录（需求五.4）。

        原缺陷：alembic/env.py 自己 create_engine，不经过 app.database，故新解压项目无
        backend/data 目录时 `alembic upgrade head` 直接报 unable to open database file；
        修复后两处共用 app.database.ensure_sqlite_dir，本测试直接测该函数 + 真实连库。
        """
        from sqlalchemy import create_engine, text

        from app.database import ensure_sqlite_dir

        nested = tmp_path / "data" / "sub" / "test.db"
        assert not nested.parent.exists()
        ensure_sqlite_dir(f"sqlite:///{nested}")
        assert nested.parent.is_dir()

        engine = create_engine(f"sqlite:///{nested}")
        with engine.connect() as conn:
            assert conn.execute(text("select 1")).scalar() == 1
        engine.dispose()

        # 内存库不需目录；PG 的 database 段是库名，误当路径 mkdir 会凭空造目录
        ensure_sqlite_dir("sqlite:///:memory:")
        ensure_sqlite_dir("postgresql+psycopg://u:p@localhost:5432/pft_guard_db")
        assert not Path("pft_guard_db").exists()

    @pytest.mark.anyio
    async def test_fx5_process_timezone_does_not_leak_into_business_time(self, client):
        """FX5 进程时区：把进程时区切成 UTC（backend 容器实况）后，两个口径都得站住。

        ① 北京墙钟的“此刻”仍能登记；② created_at 仍是北京（业务）墙钟，不是 UTC。

        修复前两处都隐式依赖进程时区：validator 的 `naive.astimezone()` 把无偏移输入
        按进程时区补 tzinfo，容器（UTC）里北京 16:26 被当成 UTC 16:26 → 误判“未来 8
        小时”422；models._local_now 的 `datetime.now()` 直接取 UTC 墙钟 → 登记时间比
        业务时间早 8 小时。断言基准内联写死 +08:00，不复用被测模块的 helper。

        os.environ["TZ"] + time.tzset() 只在 POSIX 生效（Windows 无 tzset），本机 skip；
        CI 的 ubuntu runner 与容器内跑 pytest 时会真实执行本用例。
        """
        if not hasattr(time, "tzset"):
            pytest.skip("time.tzset 仅 POSIX 可用，Windows 上 TZ 环境变量无效")

        saved_tz = os.environ.get("TZ")
        os.environ["TZ"] = "UTC"
        time.tzset()
        try:
            pid = (await client.post("/api/pipelines", json={"code": "ProcTZ", "name": "进程时区线"})).json()["id"]
            beijing_wall = datetime.now(timezone(timedelta(hours=8))).replace(tzinfo=None, microsecond=0)

            created = await client.post(
                "/api/faults",
                json={
                    "pipeline_id": pid,
                    "location": "8号工位",
                    "occurred_at": beijing_wall.isoformat(),
                    "symptom": "进程时区为 UTC 时的登记验证",
                },
            )
            assert created.status_code == 201, created.text

            detail = await client.get(f"/api/faults/{created.json()['id']}")
            body = detail.json()
            # 业务时间原样落北京墙钟（不被进程时区二次换算）
            assert datetime.fromisoformat(body["occurred_at"]) == beijing_wall
            # 系统时间与业务时区对齐：容器进程是 UTC 时也得写北京墙钟（容差 5 分钟）
            beijing_now = datetime.now(timezone(timedelta(hours=8))).replace(tzinfo=None)
            assert abs((beijing_now - datetime.fromisoformat(body["created_at"])).total_seconds()) < 300, body["created_at"]
        finally:
            if saved_tz is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = saved_tz
            time.tzset()


# ═══════════════════════════════════════════════════════════════════════════
# 第六部分：旧数据兼容测试（需求六，M2/M5 实现后转绿）
# ═══════════════════════════════════════════════════════════════════════════

class TestHistoricalData:
    """需求六：旧故障 NULL 外键、handling_note 导入时间线、管理员指派。"""

    def test_hd1_null_creator_display(self, db_session: Session, admin_user):
        """created_by_id=NULL 的故障，admin 视角响应里 created_by 为 None（前端渲染为“历史数据”）。"""
        from app import crud
        from app.models import Pipeline, PipelineFault

        p = Pipeline(code="HD1", name="历史数据")
        db_session.add(p)
        db_session.commit()
        f = PipelineFault(
            pipeline_id=p.id, location="旧数据工位",
            occurred_at=timeutil.business_now(), symptom="旧数据故障现象描述",
            created_by_id=None, assignee_id=None,
        )
        db_session.add(f)
        db_session.commit()

        loaded = crud.get_fault(db_session, f.id, viewer=admin_user)
        assert loaded.created_by_id is None
        assert loaded.created_by is None
        assert loaded.assignee is None

    @pytest.mark.xfail(reason="M2 补测：旧 handling_note → timeline(is_imported=True) 需旧库副本升级，本文件仅覆盖单库行为")
    def test_hd2_imported_note_timeline(self):
        """迁移后旧故障 handling_note 对应一条 is_imported=True 的时间线记录。"""
        assert False, "TODO M2 补测：旧库升级后验证 handling_note → timeline(is_imported=True)"

    def test_hd3_admin_assign_historical(self, db_session: Session, admin_user):
        """历史数据故障（无创建人），管理员指派→完整流程→管理员代确认（需求六.3）。"""
        from app import crud, schemas
        from app.auth import hash_password
        from app.models import FaultRole, Pipeline, PipelineFault, User

        handler = User(username="hd3-handler", password_hash=hash_password("pw_placeholder"),
                       display_name="处理人", role=FaultRole.handler, is_active=True, token_version=0)
        db_session.add(handler)
        db_session.commit()

        p = Pipeline(code="HD3", name="历史流")
        db_session.add(p)
        db_session.commit()
        f = PipelineFault(
            pipeline_id=p.id, location="历史工位",
            occurred_at=timeutil.business_now(), symptom="历史数据可继续处理验证",
            created_by_id=None, assignee_id=None,
        )
        db_session.add(f)
        db_session.commit()

        crud.assign_fault(db_session, f.id, handler.id, actor=admin_user)
        crud.start_fault(db_session, f.id, actor=handler)
        crud.submit_fault(db_session, f.id, "已更换传感器并复测正常", actor=handler)
        # admin 代确认：created_by_id 为 None→is_delegated=True→reason 必填
        done = crud.confirm_fault(
            db_session, f.id, "创建人为空的历史数据，管理员代确认", actor=admin_user,
        )
        assert done.status.value == "done"
        assert done.closed_at is not None


# ═══════════════════════════════════════════════════════════════════════
# 第七部分：M6 验收反馈缺陷（时间线操作人序列化 + 系统时间本地口径）
#   BUG-A operator_name：TimelineOut.operator_name 恒为 null——ORM FaultTimeline 上没有
#     该属性（只有 operator_name_snapshot 列），from_attributes 取不到就落默认值 None。
#     此前的 TL 测试只直构 ORM 对象未经序列化，缺陷漏网 → 本组走完整 HTTP 链补盖。
#   BUG-B 时间口径：created_at/updated_at 用 server_default=func.now()，SQLite 的
#     CURRENT_TIMESTAMP 与 PG 容器都产生 UTC；naive ISO 被前端按本地解析 → 早 8 小时。
#     口径已定（统一存业务时区墙钟，走 timeutil.business_now()，与 closed_at 对齐），免 DDL 迁移。
# ═══════════════════════════════════════════════════════════════════════


class TestTimelineOperatorAndClock:
    """TL1「谁、何时」在 HTTP 响应层的真实落地验证（client 默认身份 admin，display_name=测试管理员）。"""

    @staticmethod
    async def _seed_fault(client) -> int:
        """造一条流水线 + 一条故障，返回故障 id（集成链路从入口造数，同 test_api_faults 手法）。"""
        p = await client.post("/api/pipelines", json={"code": "OPCLK", "name": "口径验证线"})
        assert p.status_code == 201
        f = await client.post(
            "/api/faults",
            json={
                "pipeline_id": p.json()["id"],
                "location": "6号工位",
                "occurred_at": (timeutil.business_now() - timedelta(hours=1)).isoformat(),
                "symptom": "时间线与操作人口径验证",
            },
        )
        assert f.status_code == 201
        return f.json()["id"]

    @pytest.mark.anyio
    async def test_bug_a_timeline_operator_name_serialized(self, client):
        """BUG-A：create 动作的时间线序列化必须带操作人显示名（此前恒为 null → 前端全员「历史数据」）。"""
        fid = await self._seed_fault(client)
        resp = await client.get(f"/api/faults/{fid}/timelines")
        assert resp.status_code == 200
        entries = resp.json()
        assert len(entries) == 1
        assert entries[0]["action"] == "create"
        assert entries[0]["operator_name"] == "测试管理员"

    @pytest.mark.anyio
    async def test_bug_b_system_time_is_local_clock(self, client):
        """BUG-B：故障与时间线的 created_at 应为业务时区墙钟（与 timeutil.business_now() 同口径，容差 5 分钟）。

        修复前存的是 UTC → 差约 8 小时，本断言即红；不拿 occurred_at（业务时间由用户填）做基准。
        基准走 business_now() 而不走 datetime.now()：否则在 UTC 进程（CI/容器）上两边一起偏，
        缺陷同样被抵消 —— FX5 则是把进程时区真的切成 UTC 来跑同一链路。
        """
        fid = await self._seed_fault(client)
        now = timeutil.business_now()

        detail = await client.get(f"/api/faults/{fid}")
        fault_ts = datetime.fromisoformat(detail.json()["created_at"])
        assert abs((now - fault_ts).total_seconds()) < 300, (
            f"故障 created_at={fault_ts} 与业务时间 {now} 相差超 5 分钟（疑似 UTC 口径）"
        )

        tl = await client.get(f"/api/faults/{fid}/timelines")
        timeline_ts = datetime.fromisoformat(tl.json()[0]["created_at"])
        assert abs((now - timeline_ts).total_seconds()) < 300, (
            f"时间线 created_at={timeline_ts} 与业务时间 {now} 相差超 5 分钟（疑似 UTC 口径）"
        )


# ═══════════════════════════════════════════════════════════════════════════
# 第八部分：指派/改派响应体缺陷（BUG-C）
#   BUG-C assignee 陈旧：crud.assign_fault / reassign_fault 用 `fault.assignee_id = ...`
#     只写外键列，而同 Session 内该实例的 assignee 关系已被开头 get_fault 的 selectinload
#     加载过（值 NULL 也算已加载）；SessionLocal 又是 expire_on_commit=False，commit 后
#     属性不过期，末尾再 get_fault 命中 identity map 返回同一实例，eager loader 默认不
#     覆盖已加载的关系属性（要覆盖需 populate_existing）——于是库里写对了，响应体却返回
#     assignee=null（改派场景是旧负责人）。
#   现象：前端详情动作成功后只 setQueryData(响应) 写回、不补发 GET（见 useFaultMutations
#     的 useActionBase），故指派后「负责人」原地不动，F5 刷新才显示。
#   既有 SM1/SM13 只断言状态与外键，未看响应体，缺陷漏网 → 本组走完整 HTTP 链补盖。
# ═══════════════════════════════════════════════════════════════════════════


class TestAssignResponseAssignee:
    """BUG-C：指派/改派动作的响应体必须带回新负责人（它是前端详情缓存的唯一数据源）。"""

    @staticmethod
    async def _seed_fault(client) -> int:
        """造一条 pending 且未指派的故障（client 默认身份 admin），返回故障 id。"""
        p = await client.post("/api/pipelines", json={"code": "ASSIGNRES", "name": "响应体验证线"})
        assert p.status_code == 201
        f = await client.post(
            "/api/faults",
            json={
                "pipeline_id": p.json()["id"],
                "location": "8号工位",
                "occurred_at": (timeutil.business_now() - timedelta(hours=1)).isoformat(),
                "symptom": "指派响应体负责人验证",
            },
        )
        assert f.status_code == 201
        return f.json()["id"]

    @pytest.mark.anyio
    async def test_bug_c_assign_response_contains_assignee(self, client, handler_user):
        """BUG-C-1：POST /assign 响应体的 assignee 应是刚指派的处理员（修复前为 null → 红）。"""
        fid = await self._seed_fault(client)

        resp = await client.post(f"/api/faults/{fid}/assign", json={"assignee_id": handler_user.id})
        assert resp.status_code == 200
        body = resp.json()
        assert body["assignee"] is not None, "指派响应体未带负责人，前端详情会被写成「未指派」"
        assert body["assignee"]["id"] == handler_user.id
        assert body["assignee"]["username"] == handler_user.username

        # 库里一直是对的：详情接口二次读取给出同一个负责人（用于区分「写库失败」与「响应陈旧」）
        detail = await client.get(f"/api/faults/{fid}")
        assert detail.json()["assignee"]["id"] == handler_user.id

    @pytest.mark.anyio
    async def test_bug_c_reassign_response_contains_new_assignee(
        self, client, handler_user, db_session: Session
    ):
        """BUG-C-2：改派响应体的 assignee 应是新负责人，不能留任旧负责人（修复前红）。"""
        from app import crud, schemas
        from app.models import FaultRole

        second = crud.create_user(
            db_session,
            schemas.UserCreate(
                username="reassign-target", password="pass123",
                display_name="接手处理员", role=FaultRole.handler,
            ),
        )
        fid = await self._seed_fault(client)
        first = await client.post(f"/api/faults/{fid}/assign", json={"assignee_id": handler_user.id})
        assert first.status_code == 200

        resp = await client.post(
            f"/api/faults/{fid}/reassign",
            json={"assignee_id": second.id, "reason": "原处理员当班调整"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["assignee"] is not None, "改派响应体未带负责人"
        assert body["assignee"]["id"] == second.id, "改派响应体仍返回旧负责人"

