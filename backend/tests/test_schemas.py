# 第 1 层：schemas 单元测试 —— 把 Pydantic Field 约束变成回归网。
#
# 验收标准清单（先写标准，再落测试 —— P1「方法练习」要求）：
#
# 【正常】
#   N1 FaultCreate 四字段合法 → 构造成功，字段值原样保留
#   N2 FaultTransition 合法枚举 + note≥5 字 / note 不传 → 构造成功
#   N3 FaultUpdate 空 body（一个字段都不传）→ 构造成功（PATCH 全可选语义）
#   N4 PipelineCreate 合法 code/name → 构造成功
# 【异常】
#   E1 FaultCreate 缺任一必填字段 → ValidationError，loc 指向该字段
#   E2 FaultCreate 多传未声明字段（extra="forbid"）→ ValidationError
#   E3 FaultTransition target_status 非法枚举值 → ValidationError
#   E4 FaultUpdate handling_note 显式传 null → ValidationError（不支持清空）
#   E5 occurred_at 晚于当前+60s → ValidationError（不得登记未来故障）
# 【边界】
#   B1 location：1 字拒 / 2 字过；首字符空白拒（pattern ^\S.*$）；201 字拒
#   B2 symptom：4 字拒 / 5 字过 / 1000 字过 / 1001 字拒
#   B3 pipeline_id：0 拒 / 1 过（ge=1）
#   B4 occurred_at：未来 +30s（60s 容差内）过；naive 与 aware 两种时态都能比较
#   B5 handling_note（Transition）：strip 后 4 字拒 / 5 字过；纯空格拒；2001 字拒
#   B6 PipelineCreate code：空串拒 / 1 字过 / 51 字拒
#   B7 FaultReturnIn.reason：纯空格视同未填拒；strip 后 <2 字拒；合法值 首尾空白剔除后入库
# 【业务时区】（T1~T3，见 TestBusinessTimezone；回归 backend 容器跑在 UTC 的现场缺陷）
#   T1 业务时区改成 UTC 后，北京墙钟的 naive“此刻”按业务口径就是未来 → 拒
#   T2 业务时区为 +08 时，北京墙钟的 naive“此刻”放行，且墙钟原样保留（naive 出口）
#   T3 aware（+00:00）写法按业务时区归一为北京墙钟

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app import timeutil
from app.config import settings
from app.models import FaultStatus
from app.schemas import FaultCreate, FaultReturnIn, FaultTransition, FaultUpdate, PipelineCreate


def _fault_payload(**overrides):
    """合法的 FaultCreate 输入基底；overrides 覆盖单字段制造非法用例。"""
    data = {
        "pipeline_id": 1,
        "location": "3号工位传送带",
        "occurred_at": (timeutil.business_now() - timedelta(hours=1)).isoformat(),
        "symptom": "传送带异响并卡死",
    }
    data.update(overrides)
    return data


def _error_fields(exc: ValidationError) -> set[tuple]:
    """提取 ValidationError 里所有出错字段的 loc，便于断言"错的正是这个字段"。"""
    return {err["loc"] for err in exc.errors()}


# ──【正常】───────────────────────────────────────────────────────────────
class TestHappyPath:
    def test_n1_fault_create_valid(self):
        fc = FaultCreate(**_fault_payload())
        assert fc.pipeline_id == 1
        assert fc.location == "3号工位传送带"
        assert fc.symptom == "传送带异响并卡死"

    def test_n2_transition_valid_with_note(self):
        ft = FaultTransition(target_status="done", handling_note="更换皮带并复测正常")
        assert ft.target_status is FaultStatus.done

    def test_n2_transition_valid_without_note(self):
        ft = FaultTransition(target_status="processing")
        assert ft.handling_note is None

    def test_n3_fault_update_empty_body(self):
        fu = FaultUpdate()  # 一个字段都不传 = 什么都不改，必须合法
        assert fu.model_dump(exclude_unset=True) == {}

    def test_n4_pipeline_create_valid(self):
        pc = PipelineCreate(code="LINE-A", name="总装线A")
        assert pc.description is None  # 选填字段默认 None


# ──【异常】───────────────────────────────────────────────────────────────
class TestErrorPath:
    @pytest.mark.parametrize("missing", ["pipeline_id", "location", "occurred_at", "symptom"])
    def test_e1_missing_required_field(self, missing):
        payload = _fault_payload()
        del payload[missing]
        with pytest.raises(ValidationError) as exc_info:
            FaultCreate(**payload)
        assert (missing,) in _error_fields(exc_info.value)

    def test_e2_extra_field_forbidden(self):
        with pytest.raises(ValidationError) as exc_info:
            FaultCreate(**_fault_payload(status="done"))  # 登记时不允许指定状态
        assert ("status",) in _error_fields(exc_info.value)

    def test_e3_invalid_enum_value(self):
        with pytest.raises(ValidationError) as exc_info:
            FaultTransition(target_status="archived")  # 不在 pending/processing/done 内
        assert ("target_status",) in _error_fields(exc_info.value)

    def test_e4_update_note_explicit_null_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            FaultUpdate(handling_note=None)  # 显式 null 被 validator 拒绝（不支持清空）
        assert ("handling_note",) in _error_fields(exc_info.value)

    def test_e5_occurred_at_far_future_rejected(self):
        future = (timeutil.business_now() + timedelta(hours=1)).isoformat()
        with pytest.raises(ValidationError) as exc_info:
            FaultCreate(**_fault_payload(occurred_at=future))
        assert ("occurred_at",) in _error_fields(exc_info.value)


# ──【边界】───────────────────────────────────────────────────────────────
class TestBoundary:
    def test_b1_location_length_and_pattern(self):
        with pytest.raises(ValidationError):
            FaultCreate(**_fault_payload(location="A"))            # 1 字 < min_length=2
        with pytest.raises(ValidationError):
            FaultCreate(**_fault_payload(location=" 工位"))         # 首字符空白违反 pattern
        with pytest.raises(ValidationError):
            FaultCreate(**_fault_payload(location="x" * 201))      # 201 > max_length=200
        assert FaultCreate(**_fault_payload(location="AB")).location == "AB"  # 恰好 2 字过

    def test_b2_symptom_length(self):
        with pytest.raises(ValidationError):
            FaultCreate(**_fault_payload(symptom="异响了"))          # 4 字 < 5
        assert FaultCreate(**_fault_payload(symptom="x" * 5))       # 恰好 5 字过
        assert FaultCreate(**_fault_payload(symptom="x" * 1000))    # 恰好 1000 字过
        with pytest.raises(ValidationError):
            FaultCreate(**_fault_payload(symptom="x" * 1001))       # 1001 > 1000

    def test_b3_pipeline_id_ge_one(self):
        with pytest.raises(ValidationError):
            FaultCreate(**_fault_payload(pipeline_id=0))
        assert FaultCreate(**_fault_payload(pipeline_id=1)).pipeline_id == 1

    def test_b4_occurred_at_clock_skew_tolerance(self):
        # naive 时态：未来 30s，在 60s 容差内 → 放行
        naive = timeutil.business_now() + timedelta(seconds=30)
        assert FaultCreate(**_fault_payload(occurred_at=naive.isoformat()))
        # aware 时态（UTC）：未来 30s → 放行；证明 validator 的 aware/naive 换算不炸
        aware = datetime.now(timezone.utc) + timedelta(seconds=30)
        assert FaultCreate(**_fault_payload(occurred_at=aware.isoformat()))
        # aware 时态：未来 120s 超出容差 → 拒绝
        aware_far = datetime.now(timezone.utc) + timedelta(seconds=120)
        with pytest.raises(ValidationError):
            FaultCreate(**_fault_payload(occurred_at=aware_far.isoformat()))

    def test_b5_transition_note_strip_and_max(self):
        with pytest.raises(ValidationError):
            FaultTransition(target_status="done", handling_note="  ok  ")   # strip 后 2 字 < 5
        with pytest.raises(ValidationError):
            FaultTransition(target_status="done", handling_note="     ")    # 纯空格视同未填
        with pytest.raises(ValidationError):
            FaultTransition(target_status="done", handling_note="x" * 2001)  # 超 max_length
        assert FaultTransition(target_status="done", handling_note="x" * 5)  # 恰好 5 字过

    def test_b6_pipeline_code_length(self):
        with pytest.raises(ValidationError):
            PipelineCreate(code="", name="总装线A")           # 空串 < min_length=1
        with pytest.raises(ValidationError):
            PipelineCreate(code="C" * 51, name="总装线A")     # 51 > max_length=50
        assert PipelineCreate(code="C", name="总装线A").code == "C"  # 恰好 1 字过

    def test_b7_return_reason_strip(self):
        """退回理由的空白口径（固化，非新增行为）。

        校验位 schema 层，不区分操作人：创建人自退与管理员代退回走同一个
        FaultReturnIn，因此“纯空格不算填写”对两种角色同等生效。
        """
        with pytest.raises(ValidationError):
            FaultReturnIn(reason="    ")                     # 纯空格视同未填
        with pytest.raises(ValidationError):
            FaultReturnIn(reason=" 常 ")                      # strip 后 1 字 < 2
        assert FaultReturnIn(reason=" 未彻底解决 ").reason == "未彻底解决"  # 首尾空白剔除入库


# ──【业务时区】────────────────────────────────────────────────────────────
class TestBusinessTimezone:
    """T1~T3：occurred_at 的“未来”判定只看【业务时区】，与进程所在机器的时区无关。

    缺陷现场：backend 容器时区是 UTC，前端 date-picker 发的是北京墙钟的 naive 串
    （value-format="YYYY-MM-DD[T]HH:mm:ss"，无偏移）。旧 validator 用
    `naive.astimezone()` 解释无偏移输入 —— 该方法按【进程时区】补 tzinfo，容器里即
    按 UTC 补，于是北京 16:26 被当成 UTC 16:26，比当时（UTC 08:26）晚 8 小时 → 近 8
    小时内的发生时间一律 422“不得晚于当前时间”。

    本机进程时区恰为 +08:00，两种口径结论相同、复现不出来，故用例把
    business_utc_offset_hours 显式改成 0 来扮演“部署在 UTC 区域的服务器”，
    此时旧实现仍按进程时区（+08）判 → 接受 → T1 红。
    """

    def test_t1_naive_wallclock_read_as_business_tz(self, monkeypatch):
        # 业务时区=UTC：北京墙钟的“此刻”在业务口径下是未来 8 小时 → 拒
        monkeypatch.setattr(settings, "business_utc_offset_hours", 0)
        beijing_wall = datetime.now(timezone(timedelta(hours=8))).replace(tzinfo=None)
        with pytest.raises(ValidationError) as exc_info:
            FaultCreate(**_fault_payload(occurred_at=beijing_wall.isoformat()))
        assert ("occurred_at",) in _error_fields(exc_info.value)

    def test_t2_business_now_wallclock_accepted(self, monkeypatch):
        # 业务时区=+08：北京墙钟的“此刻”合法，且墙钟不被进程时区二次换算
        monkeypatch.setattr(settings, "business_utc_offset_hours", 8)
        beijing_wall = datetime.now(timezone(timedelta(hours=8))).replace(tzinfo=None)
        fc = FaultCreate(**_fault_payload(occurred_at=beijing_wall.isoformat()))
        assert fc.occurred_at.tzinfo is None
        assert abs((fc.occurred_at - beijing_wall).total_seconds()) < 2

    def test_t3_aware_input_normalized_to_business_wallclock(self, monkeypatch):
        # 同一时刻的 UTC 写法（05:00Z）在 +08 业务时区下归一为北京墙钟 13:00
        monkeypatch.setattr(settings, "business_utc_offset_hours", 8)
        fc = FaultCreate(**_fault_payload(occurred_at="2026-11-01T05:00:00+00:00"))
        assert fc.occurred_at == datetime(2026, 11, 1, 13, 0)
