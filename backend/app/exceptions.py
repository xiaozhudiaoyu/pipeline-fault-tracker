# 模块：异常处理 —— 把"出错"也变成接口契约的一部分。
#
# 设计同 python_learn/todo_api/exceptions.py（已验证的模式），聚焦本项目需要的领域异常。
#
# 为什么用 raise 而不是 return 错误 dict？
#   1) 正常路径不被打断：出事的地方多一行 raise，不用层层 if；
#   2) 错误结构只写一遍：所有接口共用 handler，前端面对的错误格式统一；
#   3) 状态码集中管理：领域异常类自带 status_code，业务代码不用到处写 404/409；
#   4) 业务层（crud）只管抛异常，不用懂 HTTP —— 关注点分离。
#
# FastAPI 错误分四条路，配四个 handler：
#   ① RequestValidationError → 参数/请求体没过 Pydantic 校验（422）
#   ② HTTPException          → 明确的 HTTP 语义错误（含框架的 404/405）
#   ③ AppError               → 我们自己的领域异常（业务规则违反）
#   ④ 其余 Exception         → 程序 bug，兜底 500，绝不泄露堆栈

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("app.exceptions")


# ── ③ 领域异常：业务层（crud）只管抛，不用懂 HTTP ──────────────────────────
class AppError(Exception):
    """业务异常基类。子类声明三个类属性，报错信息就自带语义。"""

    status_code: int = status.HTTP_400_BAD_REQUEST  # 对应的 HTTP 状态码
    code: str = "app_error"                         # 稳定的机器可读错误码（给前端判断用）
    default_message: str = "请求无法被处理"          # 没传 message 时的兜底文案

    def __init__(
        self,
        message: str | None = None,
        details: list[dict[str, str]] | None = None,
    ) -> None:
        self.message = message or self.default_message
        self.details = details or []
        super().__init__(self.message)


class PipelineNotFoundError(AppError):
    """404：流水线不存在（登记故障时 pipeline_id 无效）。"""

    status_code = status.HTTP_404_NOT_FOUND
    code = "pipeline_not_found"
    default_message = "流水线不存在"

    def __init__(self, pipeline_id: int) -> None:
        super().__init__(
            f"没有找到编号为 {pipeline_id} 的流水线",
            details=[{"field": "body.pipeline_id", "type": "not_found", "message": f"{pipeline_id} 不在数据中"}],
        )


class PipelineCodeDuplicateError(AppError):
    """409：流水线编码已存在（code 字段全表唯一）。"""

    status_code = status.HTTP_409_CONFLICT
    code = "pipeline_code_duplicate"
    default_message = "流水线编码已存在"

    def __init__(self, code: str) -> None:
        super().__init__(
            f"编码 '{code}' 已被占用，请更换",
            details=[{"field": "body.code", "type": "duplicate", "message": f"'{code}' 已存在"}],
        )


class FaultNotFoundError(AppError):
    """404：故障记录不存在。把 id 拼进文案，比"not found"对调试友好。"""

    status_code = status.HTTP_404_NOT_FOUND
    code = "fault_not_found"
    default_message = "故障记录不存在"

    def __init__(self, fault_id: int) -> None:
        super().__init__(
            f"没有找到编号为 {fault_id} 的故障记录",
            details=[{"field": "path.fault_id", "type": "not_found", "message": f"{fault_id} 不在数据中"}],
        )


class InvalidTransitionError(AppError):
    """409：状态流转非法（如 done → pending，需求明确禁止"已完成直接恢复为待处理"）。

    为什么用 409 而不是 422？
      422 = 这串 JSON 本身就不合格式（target_status 不是合法枚举值），换谁都会失败；
      409 = 格式没问题，只是和当前服务器状态打架（记录已 done），换个记录可能就成功了。
    """

    status_code = status.HTTP_409_CONFLICT
    code = "invalid_transition"
    default_message = "状态流转不被允许"

    def __init__(self, current: str, target: str) -> None:
        super().__init__(
            f"不允许的状态流转：{current} → {target}",
            details=[{
                "field": "body.target_status",
                "type": "invalid_transition",
                "message": f"当前状态 {current} 不能变更为 {target}",
            }],
        )


class HandlingNoteRequiredError(AppError):
    """400：完成处理（target=done）时未填写处理说明。

    需求："完成处理时应有相应说明"。参数格式没错（handling_note 可选），
    但业务上 done 时必填 —— 这类"格式对、业务缺"用 400 比硬凑 422 贴切。
    """

    status_code = status.HTTP_400_BAD_REQUEST
    code = "handling_note_required"
    default_message = "完成处理时必须填写处理说明"

    def __init__(self) -> None:
        super().__init__(
            "目标状态为 done 时，handling_note 不能为空",
            details=[{"field": "body.handling_note", "type": "required", "message": "完成处理必须填写说明"}],
        )


class HandlingNoteLockedError(AppError):
    """409：故障已完成（done）后，处理说明被锁定，不可再修改。

    业务规则：完成时的说明是"结案结论"，事后篡改会破坏追溯性。
    用 409 而非 422/400：请求格式与字段都合法，只是与记录当前状态（done）冲突，
    同 InvalidTransitionError 的选码理由。
    """

    status_code = status.HTTP_409_CONFLICT
    code = "handling_note_locked"
    default_message = "已完成的故障不可修改处理说明"

    def __init__(self, fault_id: int) -> None:
        super().__init__(
            f"故障 {fault_id} 已完成，处理说明已锁定不可修改",
            details=[{
                "field": "body.handling_note",
                "type": "locked",
                "message": "done 状态下处理说明不可再修改",
            }],
        )


# HTTPException 状态码 → 机器可读码。没列出的自动退化成 http_418 形式。
_HTTP_CODE_MAP: dict[int, str] = {
    status.HTTP_400_BAD_REQUEST: "bad_request",
    status.HTTP_401_UNAUTHORIZED: "unauthorized",
    status.HTTP_403_FORBIDDEN: "forbidden",
    status.HTTP_404_NOT_FOUND: "not_found",
    status.HTTP_405_METHOD_NOT_ALLOWED: "method_not_allowed",
    status.HTTP_409_CONFLICT: "conflict",
    status.HTTP_422_UNPROCESSABLE_CONTENT: "unprocessable_entity",
}


def _field_name(loc: tuple[Any, ...], err_type: str) -> str:
    """把 ("body", "symptom") 这种元组翻译成前端能直接用的字段路径。

    · 第一个元素永远是 body/query/path/header 这种"位置"，对前端没用，去掉；
    · type=json_invalid 时 Starlette 会在末尾塞一个字符偏移量（整数），归到 body 更诚实；
    · 真正的数组下标（如 items.2.name 里的 2）保留，写成 items[2].name。
    """
    parts: list[Any] = list(loc[1:] or loc[:1])
    if err_type == "json_invalid" and parts and isinstance(parts[-1], int):
        parts = parts[:-1] or ["body"]
    rendered = "".join(f"[{p}]" if isinstance(p, int) else f".{p}" for p in parts)
    return rendered.lstrip(".") or "body"


def _error_json(
    status_code: int,
    code: str,
    message: str,
    details: list[dict[str, str]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """四个 handler 共用的出口：保证所有错误的 JSON 形状都是 schemas.ErrorOut 那一套。"""
    return JSONResponse(
        status_code=status_code,
        content={"code": code, "message": message, "details": details or []},
        headers=headers,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """在 main.py 里调用一次，全站错误处理就位。

    写成函数而非直接在模块里 @app.exception_handler：app 在 main.py 才创建，
    函数化能让"错误策略"独立成块，将来换 app 实例一句话复用。
    """

    # ── ① 校验错误（422）：把 Pydantic 报错翻译成 {field, type, message} 列表 ──
    @app.exception_handler(RequestValidationError)
    async def on_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {
                "field": _field_name(err.get("loc", ()), str(err.get("type", ""))),
                "type": str(err.get("type", "invalid")),
                "message": str(err.get("msg", "取值不合法")),
            }
            for err in exc.errors()
        ]
        logger.info("校验失败 %s %s -> %s", request.method, request.url.path, details)
        return _error_json(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "validation_error",
            f"{len(details)} 处参数不符合要求，详见 details",
            details,
        )

    # ── ② HTTPException（含框架自己抛的 404 / 405）─────────────────────────
    @app.exception_handler(StarletteHTTPException)
    async def on_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        # exc.headers 必须回传，否则 401 的 WWW-Authenticate 头等会丢失（行为退化）。
        return _error_json(
            exc.status_code,
            _HTTP_CODE_MAP.get(exc.status_code, f"http_{exc.status_code}"),
            str(exc.detail),
            headers=getattr(exc, "headers", None),
        )

    # ── ③ 领域异常：把 crud 层抛的 AppError 翻译成 HTTP 响应 ───────────────
    @app.exception_handler(AppError)
    async def on_app_error(request: Request, exc: AppError) -> JSONResponse:
        logger.info("业务异常 %s %s -> %s", request.method, request.url.path, exc.code)
        return _error_json(exc.status_code, exc.code, exc.message, exc.details)

    # ── ④ 兜底：程序 bug（500），宁可含糊也不能泄露堆栈 ────────────────────
    @app.exception_handler(Exception)
    async def on_unhandled(request: Request, exc: Exception) -> JSONResponse:
        # 响应正常发给客户端，但 Starlette 仍会把原异常往上抛给服务器，
        # uvicorn 控制台照样打印 traceback（给开发看，不是泄露）。
        logger.exception("未处理异常 %s %s", request.method, request.url.path)
        return _error_json(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "internal_error",
            "服务端内部错误，已记录日志（堆栈不外泄）",
        )
