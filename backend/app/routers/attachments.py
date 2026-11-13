# 路由模块：图片附件端点（第四阶段）。
#
# 两个前缀写在同一个 router（APIRouter 的 prefix 只能一个，故路径全量书写）：
#   POST   /api/faults/{fault_id}/attachments   上传一张图片（multipart），201 返回元数据
#   POST   /api/timelines/{timeline_id}/attachments  向时间线附图（进展/提交，第四阶段追加）
#   GET    /api/faults/{fault_id}/attachments   附件列表（FaultOut.attachments 已内嵌，此端点备用）
#   GET    /api/attachments/{attachment_id}     文件回放（FileResponse，inline 展示）
#
# 权限口径（方案已定）：上传/列表/回放 = can_view_fault（crud 层裁决，无权与不存在
# 同为 404）。第四阶段调整：现场图片删除不再有独立 DELETE 端点，改由「修改故障信息」
# （PATCH /api/faults/{id} 携 remove_attachment_ids）执行，权限/状态门槛收敛到 update_fault。
# 路由层保持"薄"，不做二次判断。
#
# 注意：main.py 必须先于 faults 路由器注册本 router——Starlette 按注册顺序逐个
# 匹配路径模板，附件路由排在前面可确保 /api/faults/{fid}/attachments 优先命中这里
#（回归由 tests/test_api_attachments.py 的上传用例固化）。

from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import crud, schemas
from ..auth import CurrentUser
from ..database import get_db

router = APIRouter(tags=["attachments"])

# UploadFile 带 File(...) 默认值，排在其后的参数须同样给默认值；
# CurrentUser 本身已是 Annotated[..., Depends(...)]，叠加 File 参数时改用显式 Annotated 写法。
UploadFileIn = Annotated[UploadFile, File(description="图片文件（multipart 字段名固定为 file）")]


@router.post(
    "/api/faults/{fault_id}/attachments",
    response_model=schemas.AttachmentOut,
    status_code=201,
    responses={
        404: {"model": schemas.ErrorOut, "description": "故障记录不存在或无权查看"},
        422: {"model": schemas.ErrorOut, "description": "非 PNG/JPEG、超过大小上限或张数已达上限"},
    },
)
def upload_attachment(
    fault_id: int,
    user: CurrentUser,
    file: UploadFileIn,
    db: Session = Depends(get_db),
) -> schemas.AttachmentOut:
    """上传一张故障图片：文件落 settings.upload_dir，库内只登记元数据行。

    类型/大小/张数校验全部在 crud.add_attachment（422 由 AppError handler 翻译），
    本函数只负责转交 UploadFile 与注入当前用户。
    """
    attachment = crud.add_attachment(db, fault_id, file, uploader=user)
    return schemas.AttachmentOut.model_validate(attachment)


@router.post(
    "/api/timelines/{timeline_id}/attachments",
    response_model=schemas.AttachmentOut,
    status_code=201,
    responses={
        403: {"model": schemas.ErrorOut, "description": "非本条时间线操作人且非管理员"},
        404: {"model": schemas.ErrorOut, "description": "时间线不存在或无权查看"},
        422: {"model": schemas.ErrorOut, "description": "非 PNG/JPEG、超过大小上限或本故障张数已达上限"},
    },
)
def upload_timeline_attachment(
    timeline_id: int,
    user: CurrentUser,
    file: UploadFileIn,
    db: Session = Depends(get_db),
) -> schemas.AttachmentOut:
    """向一条时间线记录（追加进展/提交结果）上传随附图片（第四阶段追加）。

    两步式附图的第二步：前端先调 progress/submit 动作（纯 JSON）拿到 timeline_id，
    再逐张调本端点。类型/大小/张数上限与现场图片同源（crud._register_image）；
    新图写入后时间线以 timeline_id 归属（不入现场图片集合）。上传失败仅提示、不回滚动作。
    """
    attachment = crud.add_attachment_for_timeline(db, timeline_id, file, uploader=user)
    return schemas.AttachmentOut.model_validate(attachment)


@router.get(
    "/api/faults/{fault_id}/attachments",
    response_model=list[schemas.AttachmentOut],
    responses={404: {"model": schemas.ErrorOut, "description": "故障记录不存在或无权查看"}},
)
def list_attachments(
    fault_id: int, user: CurrentUser, db: Session = Depends(get_db)
) -> list[schemas.AttachmentOut]:
    """按上传时间正序返回某条故障的全部附件元数据。"""
    entries = crud.list_attachments(db, fault_id, user)
    return [schemas.AttachmentOut.model_validate(a) for a in entries]


@router.get(
    "/api/attachments/{attachment_id}",
    responses={
        200: {"content": {"image/png": {}, "image/jpeg": {}}, "description": "图片文件流"},
        401: {"model": schemas.ErrorOut, "description": "未提供身份凭证"},
        404: {"model": schemas.ErrorOut, "description": "附件不存在、无权查看或磁盘文件缺失"},
    },
)
def download_attachment(
    attachment_id: int, user: CurrentUser, db: Session = Depends(get_db)
) -> FileResponse:
    """回放图片文件本体。

    鉴权说明：浏览器 <img src> 直连本端点带不了 Authorization 头（会 401），
    前端以 fetch(blob) 拉流再 createObjectURL 渲染（见 frontend api/attachments.ts）。
    media_type 用库内判定值而非按文件名猜；filename 参数会触发 attachment 语义，
    图片要页内展示故不设，另显式给 inline。
    """
    attachment, path = crud.get_attachment_for_download(db, attachment_id, user)
    return FileResponse(
        path,
        media_type=attachment.content_type,
        headers={
            "Content-Disposition": "inline",
            # 图片内容不可变（uuid 文件名，删后重建也是新 id 新文件），可放心短缓存；
            # private：中间代理不得留存（附件沿故障权限隔离）。
            "Cache-Control": "private, max-age=3600",
        },
    )
