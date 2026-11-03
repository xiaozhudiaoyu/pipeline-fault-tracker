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
#   AU9 管理员在故障完成前可调优先级，优先级调整记入时间线
#
# ── 时间线（需求四）──
#   TL1 每个动作产生一条时间线记录（操作人/时间/动作/前后值/说明）
#   TL2 新记录不可覆盖旧记录（append-only）
#   TL3 状态变更与时间线同事务：若时间线写入失败，状态不变
#   TL4 时间线列表按 created_at 正序
#
# ── 存量缺陷（需求五）──
#   FX1 时区：输入 13:00 保存后刷新仍显示 13:00
#   FX2 空格校验：必填字段不能只填空格
#   FX3 priority:null → 422 而非 500
#   FX4 data 目录不存在时自动创建
#
# ── 旧数据兼容（需求六）──
#   HD1 旧故障 created_by_id/assignee_id 为 NULL → 响应显示"历史数据"
#   HD2 旧 handling_note 导入为 is_imported=true 的时间线记录
#   HD3 管理员可对"历史数据"故障指派负责人继续处理

# ─── 以下 import 在实现前会失败（预期行为：ModuleNotFoundError = 红） ───
# 实现后逐步取消注释或替换为正确路径。

import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

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
            occurred_at=datetime.now(), symptom="测试故障现象描述",
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
                          occurred_at=datetime.now(), symptom="时间线测试故障",
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
    """POST /api/auth/login、GET /api/auth/me、token_version 失效机制。"""

    @pytest.fixture(autouse=True)
    def _require_auth(self):
        pytest.importorskip("app.auth", reason="M3: auth 模块尚未实现")

    @pytest.mark.xfail(reason="M3: auth 模块尚未实现")
    async def test_au1_unauthenticated_returns_401(self, client):
        """未登录访问业务接口 → 401。"""
        # client 为 async fixture，当前 /api/faults 尚未接入登录校验（属 M4/M5），
        # 因此本用例仍为红。待 M4 将 GET /api/faults 挂上 require_login 后转绿。
        resp = await client.get("/api/faults")
        assert resp.status_code == 401

    @pytest.mark.xfail(reason="M3: login 端点尚未实现")
    async def test_login_success_and_me(self, client):
        """正确用户名密码 → 200 token；带 token 访问 me → 200 含 username/role。"""
        # 先建用户（需 M1 User 模型 + M3 hash_password）
        from app.auth import hash_password
        from app.models import User, FaultRole
        # 此处假设 db_session 可用（conftest 提供）
        # 集成测试中通过 API 造数据更真实，但 User 创建目前无公开端点
        # 暂用直接入库方式
        resp = await client.post("/api/auth/login", json={"username": "testuser", "password": "pass123"})
        assert resp.status_code == 200
        token = resp.json()["access_token"]
        me_resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_resp.status_code == 200
        assert me_resp.json()["username"] == "testuser"

    @pytest.mark.xfail(reason="M3: token_version bump 尚未实现")
    async def test_au2_deactivated_token_invalidated(self, client):
        """管理员停用账号后，该用户原 token 立即失效 → 401。"""
        # 1. 登录拿 token
        # 2. 管理员 bump token_version
        # 3. 用原 token 访问 → 401
        resp = await client.post("/api/auth/login", json={"username": "u1", "password": "p1"})
        assert resp.status_code == 200
        token = resp.json()["access_token"]
        # 模拟停用（直接改 DB 或调管理员端点）
        # ...
        me_resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
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
        # 以下 import 在 M1 实现后生效
        from app.models import User, Pipeline, PipelineFault, FaultRole, FaultStatus
        from app.auth import hash_password
        from app import crud, schemas

        self.p = crud.create_pipeline(db_session, schemas.PipelineCreate(code="WF-A", name="工作流A"))
        self.creator = User(username="creator", password_hash=hash_password("pw"),
                            display_name="报修人", role=FaultRole.user, is_active=True, token_version=0)
        self.handler = User(username="handler", password_hash=hash_password("pw"),
                            display_name="处理人", role=FaultRole.handler, is_active=True, token_version=0)
        self.admin = User(username="admin", password_hash=hash_password("pw"),
                          display_name="管理员", role=FaultRole.admin, is_active=True, token_version=0)
        db_session.add_all([self.creator, self.handler, self.admin])
        db_session.commit()

        self.fault = crud.create_fault(db_session, schemas.FaultCreate(
            pipeline_id=self.p.id, location="1号工位",
            occurred_at=datetime.now() - timedelta(minutes=30),
            symptom="传送带异响并卡死需要紧急处理",
        ))
        # M5 后 create_fault 将接受 created_by_id 形参，目前直接补刷外键列
        self.fault.created_by_id = self.creator.id
        db_session.commit()
        db_session.refresh(self.fault)

    @pytest.mark.xfail(reason="M5: assign_fault 函数尚未实现")
    def test_sm1_assign(self):
        """指派：pending 状态下管理员指派负责人，状态不变，assignee 设置。"""
        from app import crud
        f = crud.assign_fault(self.db, self.fault.id, self.handler.id, operator=self.admin)
        assert f.status.value == "pending"
        assert f.assignee_id == self.handler.id

    @pytest.mark.xfail(reason="M5: start_processing 函数尚未实现")
    def test_sm3_start(self):
        """开始处理：已指派的 pending → processing（仅负责人可操作）。"""
        from app import crud
        crud.assign_fault(self.db, self.fault.id, self.handler.id, operator=self.admin)
        f = crud.start_processing(self.db, self.fault.id, operator=self.handler)
        assert f.status.value == "processing"

    @pytest.mark.xfail(reason="M5: add_progress 函数尚未实现")
    def test_sm4_progress(self):
        """追加进展：processing 状态下负责人可多次记录，时间线增加。"""
        from app import crud, schemas
        from app.models import FaultTimeline
        crud.assign_fault(self.db, self.fault.id, self.handler.id, operator=self.admin)
        crud.start_processing(self.db, self.fault.id, operator=self.handler)
        crud.add_progress(self.db, self.fault.id, "检查电机发现轴承磨损", operator=self.handler)
        crud.add_progress(self.db, self.fault.id, "已更换轴承待复测", operator=self.handler)
        timelines = self.db.query(FaultTimeline).filter_by(fault_id=self.fault.id).all()
        progress_records = [t for t in timelines if t.action.value == "progress"]
        assert len(progress_records) == 2

    @pytest.mark.xfail(reason="M5: submit_result 函数尚未实现")
    def test_sm6_submit(self):
        """提交结果：processing → awaiting_confirmation，结果说明必填。"""
        from app import crud
        crud.assign_fault(self.db, self.fault.id, self.handler.id, operator=self.admin)
        crud.start_processing(self.db, self.fault.id, operator=self.handler)
        f = crud.submit_result(self.db, self.fault.id, "更换轴承并复测30分钟正常", operator=self.handler)
        assert f.status.value == "awaiting_confirmation"

    @pytest.mark.xfail(reason="M5: confirm_fault 函数尚未实现")
    def test_sm7_confirm(self):
        """确认完成：awaiting_confirmation + 创建人确认 → done。"""
        from app import crud
        crud.assign_fault(self.db, self.fault.id, self.handler.id, operator=self.admin)
        crud.start_processing(self.db, self.fault.id, operator=self.handler)
        crud.submit_result(self.db, self.fault.id, "更换轴承并复测正常", operator=self.handler)
        f = crud.confirm_fault(self.db, self.fault.id, operator=self.creator)
        assert f.status.value == "done"
        assert f.closed_at is not None

    @pytest.mark.xfail(reason="M5: return_fault 函数尚未实现")
    def test_sm8_return(self):
        """退回：awaiting_confirmation + 创建人退回 → processing，assignee 不变。"""
        from app import crud
        crud.assign_fault(self.db, self.fault.id, self.handler.id, operator=self.admin)
        crud.start_processing(self.db, self.fault.id, operator=self.handler)
        crud.submit_result(self.db, self.fault.id, "更换轴承并复测正常", operator=self.handler)
        f = crud.return_fault(self.db, self.fault.id, "复测仍有异响未彻底解决", operator=self.creator)
        assert f.status.value == "processing"
        assert f.assignee_id == self.handler.id  # 负责人不变

    @pytest.mark.xfail(reason="M5: done 终态拒绝尚未实现")
    def test_sm9_done_terminal(self):
        """done 后任何操作拒绝。"""
        from app import crud
        from app.exceptions import InvalidTransitionError
        crud.assign_fault(self.db, self.fault.id, self.handler.id, operator=self.admin)
        crud.start_processing(self.db, self.fault.id, operator=self.handler)
        crud.submit_result(self.db, self.fault.id, "更换轴承并复测正常", operator=self.handler)
        crud.confirm_fault(self.db, self.fault.id, operator=self.creator)
        with pytest.raises(InvalidTransitionError):
            crud.start_processing(self.db, self.fault.id, operator=self.handler)

    @pytest.mark.xfail(reason="M5: 权限守卫尚未实现")
    def test_sm11_wrong_handler_rejected(self):
        """非当前负责人不能 start/progress/submit → PermissionError。"""
        from app import crud
        from app.exceptions import PermissionDeniedError
        crud.assign_fault(self.db, self.fault.id, self.handler.id, operator=self.admin)
        with pytest.raises(PermissionDeniedError):
            crud.start_processing(self.db, self.fault.id, operator=self.creator)

    @pytest.mark.xfail(reason="M5: 改派逻辑尚未实现")
    def test_au7_reassign(self):
        """管理员改派：旧负责人失权、新负责人可操作。"""
        from app import crud
        from app.exceptions import PermissionDeniedError
        from app.models import User, FaultRole
        from app.auth import hash_password
        handler2 = User(username="handler2", password_hash=hash_password("pw"),
                        display_name="处理人2", role=FaultRole.handler, is_active=True, token_version=0)
        self.db.add(handler2)
        self.db.commit()
        # 指派 handler → start → 改派 handler2
        crud.assign_fault(self.db, self.fault.id, self.handler.id, operator=self.admin)
        crud.start_processing(self.db, self.fault.id, operator=self.handler)
        f = crud.reassign_fault(self.db, self.fault.id, handler2.id, "原负责人出差", operator=self.admin)
        assert f.assignee_id == handler2.id
        # 旧 handler 不能再 progress
        with pytest.raises(PermissionDeniedError):
            crud.add_progress(self.db, self.fault.id, "旧负责人试图操作", operator=self.handler)
        # 新 handler2 可以
        crud.add_progress(self.db, self.fault.id, "新负责人继续跟进处理", operator=handler2)

    @pytest.mark.xfail(reason="M5: 管理员代确认尚未实现")
    def test_au8_admin_confirm_on_behalf(self):
        """创建人停用后管理员可代确认（需原因）。"""
        from app import crud
        crud.assign_fault(self.db, self.fault.id, self.handler.id, operator=self.admin)
        crud.start_processing(self.db, self.fault.id, operator=self.handler)
        crud.submit_result(self.db, self.fault.id, "更换轴承并复测正常", operator=self.handler)
        # 停用创建人
        self.creator.is_active = False
        self.creator.token_version += 1
        self.db.commit()
        # 管理员代确认
        f = crud.confirm_fault(self.db, self.fault.id, operator=self.admin,
                               reason="创建人已停用，管理员代确认")
        assert f.status.value == "done"


# ═══════════════════════════════════════════════════════════════════════════
# 第四部分：时间线原子性测试（需求四.2，M5 实现后转绿）
# ═══════════════════════════════════════════════════════════════════════════

class TestTimelineAtomicity:
    """状态变更与时间线同事务：任一步失败整体回滚。"""

    @pytest.mark.xfail(reason="M5: 同事务保证尚未实现")
    def test_tl3_atomic_rollback(self, db_session: Session):
        """若时间线写入失败（如模拟异常），状态不应被改变。"""
        # 此测试需要在 crud 实现后，monkeypatch FaultTimeline 插入抛异常，
        # 验证 fault.status 仍为原值。
        assert False, "TODO M5: monkeypatch timeline insert 抛异常后验证 fault.status 未变"


# ═══════════════════════════════════════════════════════════════════════════
# 第五部分：存量缺陷修复测试（需求五，M7 实现后转绿）
# ═══════════════════════════════════════════════════════════════════════════

class TestBugFixes:
    """需求五：时区/空格/priority-null/data目录。"""

    @pytest.mark.xfail(reason="M7-1: 时区 bug 未修复——aware datetime 存库后偏移")
    def test_fx1_timezone_preserved(self, db_session: Session):
        """输入北京时间 13:00（ISO 带 +08:00），存库后读出仍为 13:00 naive 本地。"""
        from app import crud, schemas
        from datetime import datetime
        p = crud.create_pipeline(db_session, schemas.PipelineCreate(code="TZ", name="时区测试"))
        # 模拟前端发送带时区的 ISO 字符串
        body = schemas.FaultCreate(
            pipeline_id=p.id,
            location="1号工位",
            occurred_at=datetime.fromisoformat("2026-11-01T13:00:00+08:00"),
            symptom="时区测试故障现象描述",
        )
        f = crud.create_fault(db_session, body, created_by_id=None)
        # 期望：occurred_at 为 naive 本地 13:00，不是 05:00 UTC
        assert f.occurred_at.hour == 13

    @pytest.mark.xfail(reason="M7-2: 空格校验未补全——symptom 纯空格可能绕过")
    def test_fx2_whitespace_rejected(self):
        """PATCH 传 symptom='     '（纯空格）应 422。"""
        assert False, "TODO M7-2: PATCH /api/faults/{id} body={'symptom':'     '} → 422"

    @pytest.mark.xfail(reason="M7-3: priority:null 当前触发 500 而非 422")
    def test_fx3_priority_null_422(self):
        """PATCH body={"priority": null} → 422 明确提示，不报 500。"""
        assert False, "TODO M7-3: PATCH /api/faults/{id} body={'priority':null} → 422"

    @pytest.mark.xfail(reason="M7-4: data 目录不存在时启动报错")
    def test_fx4_auto_create_directory(self, tmp_path):
        """DATABASE_URL 指向不存在的子目录，engine 创建前自动 mkdir。"""
        from sqlalchemy import create_engine
        nested = tmp_path / "data" / "sub" / "test.db"
        # 当前 database.py 不会自动创建父目录，修复后应能成功
        engine = create_engine(f"sqlite:///{nested}")
        # 建 engine 不报错（但真正连库前需 mkdir）
        with engine.connect() as conn:
            assert conn is not None


# ═══════════════════════════════════════════════════════════════════════════
# 第六部分：旧数据兼容测试（需求六，M2/M5 实现后转绿）
# ═══════════════════════════════════════════════════════════════════════════

class TestHistoricalData:
    """需求六：旧故障 NULL 外键、handling_note 导入时间线、管理员指派。"""

    @pytest.mark.xfail(reason="M5: NULL created_by 响应显示'历史数据'尚未实现")
    def test_hd1_null_creator_display(self):
        """created_by_id=NULL 的故障，API 响应 created_by 字段为 '历史数据'。"""
        assert False, "TODO M5: GET /api/faults/{id} 旧数据 created_by 返回 '历史数据'"

    @pytest.mark.xfail(reason="M2: 旧 handling_note 导入时间线尚未实现")
    def test_hd2_imported_note_timeline(self):
        """迁移后旧故障 handling_note 对应一条 is_imported=True 的时间线记录。"""
        assert False, "TODO M2: 旧库升级后验证 handling_note → timeline(is_imported=True)"

    @pytest.mark.xfail(reason="M5: 管理员对历史数据指派尚未实现")
    def test_hd3_admin_assign_historical(self):
        """历史数据故障（无创建人），管理员可指派负责人继续处理。"""
        assert False, "TODO M5: 无创建人故障 assign → 正常处理，confirm 走管理员代确认"
