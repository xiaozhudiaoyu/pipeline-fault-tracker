# 路由模块：/api/faults —— 故障记录接口（本项目核心业务）。
#
# 四个接口对应需求"二、业务功能"：
#   GET    /api/faults              故障查询（按流水线/状态筛选，分页，occurred_at 倒序）
#   POST   /api/faults              故障登记
#   GET    /api/faults/{id}         单条详情
#   PATCH  /api/faults/{id}/transition  故障处理（状态流转 + 处理说明）
#
# 路由层只管"收发请求"，业务规则（状态流转校验）在 crud 层，错误结构由 exceptions 统一。
#
# 命名注意：查询参数 status 与 fastapi.status 模块同名，故本文件【不】import fastapi.status，
# 需要 HTTP 状态码处直接用数字字面量（如 201），避免命名遮蔽。

from fastapi import APIRouter, Depends, Query, Response
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
