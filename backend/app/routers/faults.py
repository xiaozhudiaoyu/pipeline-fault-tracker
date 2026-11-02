# 路由模块：/api/faults —— 故障记录接口（本项目核心业务）。
#
# 接口对应需求"二、业务功能"（导出为 P4 迭代新增）：
#   GET    /api/faults              故障查询（按流水线/状态筛选，分页，occurred_at 倒序）
#   GET    /api/faults/export       导出 CSV（复用列表筛选口径，不分页，流式响应）
#   POST   /api/faults              故障登记
#   GET    /api/faults/{id}         单条详情
#   PATCH  /api/faults/{id}         修改基础信息（location/symptom/handling_note，done 后说明锁定）
#   PATCH  /api/faults/{id}/transition  故障处理（状态流转 + 处理说明）
#
# 路由层只管"收发请求"，业务规则（状态流转校验）在 crud 层，错误结构由 exceptions 统一。
#
# 命名注意：查询参数 status 与 fastapi.status 模块同名，故本文件【不】import fastapi.status，
# 需要 HTTP 状态码处直接用数字字面量（如 201），避免命名遮蔽。

import csv
import io
from datetime import datetime, timezone
from typing import Iterator

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from .. import crud, schemas
from ..database import get_db
from ..models import FaultStatus

router = APIRouter(prefix="/api/faults", tags=["faults"])


@router.get("", response_model=schemas.FaultListOut)
def list_faults(
    pipeline_id: int | None = Query(default=None, ge=1, description="按流水线 ID 筛选，不传=全部"),
    status: FaultStatus | None = Query(default=None, description="按处理状态筛选：pending/processing/done"),
    page: int = Query(default=1, ge=1, description="页码，从 1 开始"),
    size: int = Query(default=20, ge=1, le=100, description="每页条数，1~100，防止一次拉取过多"),
    db: Session = Depends(get_db),
) -> schemas.FaultListOut:
    """分页查询故障列表，默认按发生时间倒序（需求："列表默认优先展示最近发生的故障"）。

    参数取值规则（FastAPI 核心）：这些参数都不在路径里、且是标量/枚举类型，
    故全部按【查询参数】取值，即 /api/faults?pipeline_id=1&status=done&page=1&size=20。
      · status: FaultStatus | None —— FastAPI 自动把字符串 "done" 转成 FaultStatus.done 枚举，
        非法值（如 ?status=xxx）直接 422，业务代码拿到的一定是合法枚举或 None；
      · Query(ge=1, le=100) —— 查询参数也能带校验约束，越界直接 422。

    返回包一层 FaultListOut（items+total+page+size）：前端分页组件需要 total 算总页数。
    """
    items, total = crud.list_faults(
        db, pipeline_id=pipeline_id, status=status, page=page, size=size
    )
    return schemas.FaultListOut(
        items=[schemas.FaultOut.model_validate(f) for f in items],
        total=total,
        page=page,
        size=size,
    )


# 导出 CSV 表头（与需求文档第 2 节 10 列一致）：冗余 pipeline_code/name 便于离线阅读；
# 列顺序即导出顺序，改动前先看需求文档。
EXPORT_CSV_HEADER = [
    "id",
    "pipeline_code",
    "pipeline_name",
    "location",
    "occurred_at",
    "symptom",
    "status",
    "handling_note",
    "created_at",
    "closed_at",
]


def _csv_datetime(value: datetime | None) -> str:
    """导出时间列格式：「YYYY-MM-DD HH:mm:ss」，与前端列表页展示格式一致（formatDateTime），
    Excel 可直接识别为日期时间；空值（如未结案的 closed_at）导空串。

    不用 isoformat()：带 "T" 分隔符的 ISO 8601 在 Excel 里是纯文本且与页面所见不一致
    （需求文档评审后的用户反馈修正，2026-09-30）。库内时间为 naive 本地时间，直接格式化；
    若 P3 切 PG 后出现 aware 时间，此处按原值格式化，时区换算不在导出层做。
    """
    if value is None:
        return ""
    return value.strftime("%Y-%m-%d %H:%M:%S")


@router.get(
    "/export",
    responses={
        200: {"content": {"text/csv": {}}, "description": "CSV 文件流（UTF-8 带 BOM）"},
        422: {"model": schemas.ErrorOut, "description": "查询参数校验失败"},
    },
)
def export_faults(
    pipeline_id: int | None = Query(default=None, ge=1, description="按流水线 ID 筛选，不传=全部"),
    status: FaultStatus | None = Query(default=None, description="按处理状态筛选：pending/processing/done"),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """导出当前筛选条件下的全部故障为 CSV（不分页，上限 crud.EXPORT_MAX_ROWS 行）。

    【路由顺序坑】本端点必须注册在 /{fault_id} 之前：FastAPI 按注册顺序匹配，
    若 /{fault_id} 在前，"export" 会被当作 fault_id 去转整数 → 422，永远到不了这里。
    （test_api_export.py 第 7 条验收标准专门回归这一点。）

    流式实现要点（需求文档 4.1）：
      · 生成器逐行产出：先 BOM、再表头、再逐条记录，不在内存拼全量大字符串；
      · BOM（\\ufeff）：Excel 靠它识别 UTF-8，缺了中文双击打开乱码；
      · csv.writer 负责转义：字段含逗号/引号/换行时自动加引号包裹（RFC 4180）；
        lineterminator="\\n" 覆盖 csv 模块默认的 "\\r\\n"，行分隔符统一可控。

    错误路径只有 422（参数校验，统一 ErrorOut 结构）；空结果不是错误 ——
    返回只含表头的 CSV（需求文档 D1 决策）。
    """
    faults = crud.list_faults_for_export(db, pipeline_id=pipeline_id, status=status)

    def _rows() -> Iterator[bytes]:
        # BOM 单独作为首块产出：它必须在文件最前面，且不属于 csv 内容
        yield "\ufeff".encode("utf-8")
        # 每行用一个临时 StringIO 承接 csv.writer 输出（csv 模块只写文件类对象）
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        writer.writerow(EXPORT_CSV_HEADER)
        yield buf.getvalue().encode("utf-8")
        for f in faults:
            buf.seek(0)
            buf.truncate(0)  # 清空缓冲复用，避免每行新建对象
            writer.writerow(
                [
                    f.id,
                    f.pipeline.code,
                    f.pipeline.name,
                    f.location,
                    _csv_datetime(f.occurred_at),
                    f.symptom,
                    f.status.value,
                    f.handling_note if f.handling_note is not None else "",
                    _csv_datetime(f.created_at),
                    _csv_datetime(f.closed_at),
                ]
            )
            yield buf.getvalue().encode("utf-8")

    # 文件名时间戳用 UTC（与 Content-Disposition 下发口径一致，不受服务器时区影响）
    filename = f"faults_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.csv"
    return StreamingResponse(
        _rows(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get(
    "/{fault_id}",
    response_model=schemas.FaultOut,
    responses={404: {"model": schemas.ErrorOut, "description": "故障记录不存在"}},
)
def get_fault(fault_id: int, db: Session = Depends(get_db)) -> schemas.FaultOut:
    """按编号返回单条故障详情，演示【路径参数】：/api/faults/2。

    fault_id: int —— 名字在路径 {fault_id} 里，故按路径参数取值；
    URL 里的 "2" 自动转整数；转不了（如 /api/faults/abc）直接 422。
    找不到记录时 crud 抛 FaultNotFoundError，由 handler 转成 404 统一错误结构。
    """
    return schemas.FaultOut.model_validate(crud.get_fault(db, fault_id))


@router.patch(
    "/{fault_id}",
    response_model=schemas.FaultOut,
    responses={
        404: {"model": schemas.ErrorOut, "description": "故障记录不存在"},
        409: {"model": schemas.ErrorOut, "description": "done 后处理说明已锁定，不可修改"},
        422: {"model": schemas.ErrorOut, "description": "请求体未通过校验"},
    },
)
def update_fault(
    fault_id: int,
    payload: schemas.FaultUpdate,
    db: Session = Depends(get_db),
) -> schemas.FaultOut:
    """修改故障基础信息（不含状态流转，流转仍走 /transition）。

    与 POST 全量创建不同，PATCH 语义是"部分更新"：FaultUpdate 字段全部可选，
    crud 层用 exclude_unset 只应用客户端传了的字段。

    业务规则在 crud.update_fault：done 后 handling_note 锁定 → 409 handling_note_locked
    （"结案结论"不可篡改，保追溯性）；字段级校验（长度/pattern）由 schemas 层拦 → 422。
    """
    return schemas.FaultOut.model_validate(crud.update_fault(db, fault_id, payload))


@router.post(
    "",
    response_model=schemas.FaultOut,
    status_code=201,
    responses={
        404: {"model": schemas.ErrorOut, "description": "pipeline_id 指向的流水线不存在"},
        422: {"model": schemas.ErrorOut, "description": "请求体未通过校验（统一后的自定义结构）"},
    },
)
def create_fault(
    payload: schemas.FaultCreate,
    response: Response,
    db: Session = Depends(get_db),
) -> schemas.FaultOut:
    """登记新故障，演示【请求体】：客户端 POST 一段 JSON，FastAPI 用 FaultCreate 校验后交给 payload。

    语法要点：
      · payload: FaultCreate —— 参数类型是 Pydantic 模型 → 从"请求体 body"取值；
        校验由 FaultCreate 的 Field 规则完成（location≥2字、symptom≥5字等），非法直接 422；
      · status_code=201 —— "创建成功"的标准状态码（默认 200）；
      · response: Response —— 框架注入的响应对象，用它回写 Location 头（201 的规范动作，
        告诉客户端新资源在哪，前端可直接拿这个 URL 再 GET）；它不是接口参数，Swagger 不会多出表单字段。

    新故障的初始状态由 crud 强制置为 pending，不接受客户端指定（防绕过状态流转校验）。
    """
    fault = crud.create_fault(db, payload)
    response.headers["Location"] = f"/api/faults/{fault.id}"
    return schemas.FaultOut.model_validate(fault)


@router.patch(
    "/{fault_id}/transition",
    response_model=schemas.FaultOut,
    responses={
        400: {"model": schemas.ErrorOut, "description": "目标为 done 但未填写处理说明"},
        404: {"model": schemas.ErrorOut, "description": "故障记录不存在"},
        409: {"model": schemas.ErrorOut, "description": "状态流转非法（如 done 不可逆、同状态变更）"},
        422: {"model": schemas.ErrorOut, "description": "请求体未通过校验"},
    },
)
def transition_fault(
    fault_id: int,
    payload: schemas.FaultTransition,
    db: Session = Depends(get_db),
) -> schemas.FaultOut:
    """推进故障状态（待处理 → 处理中 → 已完成），并可补充处理说明。

    为什么用独立的 /transition 子路径而非直接 PATCH /{id}？
      状态流转是有明确业务规则的"动作"（非任意字段更新），单独成端点语义更清晰，
      也便于施加专门的校验与文档说明。PATCH /{id} 容易被误解为"可改任意字段"。

    业务规则全部在 crud.transition_fault 校验（见其状态流转矩阵）：
      · done 是终态不可逆 → 409（需求硬性要求"已完成不能直接恢复为待处理"）；
      · 同状态变更 → 409；
      · 目标 done 时 handling_note 必填 → 400。
    路由层不重复这些判断，只负责把请求转给 crud、把结果序列化成响应。
    """
    fault = crud.transition_fault(
        db, fault_id, payload.target_status, payload.handling_note
    )
    return schemas.FaultOut.model_validate(fault)
