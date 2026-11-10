# 路由模块：/api/users —— 用户管理（第三阶段 M6 补充，仅管理员）。
#
# 端点清单（全部 AdminUser，非 admin 403）：
#   GET   /api/users                     —— 用户列表（管理页表格 + 指派下拉共用，
#                                            指派下拉由前端按 role=handler 且 is_active 过滤）
#   POST  /api/users                     —— 创建账号（不开放自助注册，需求二）
#   PATCH /api/users/{id}/active         —— 启用/停用（停用即时失效其全部 token；禁止自停）
#   POST  /api/users/{id}/reset-password —— 重置密码（bump token_version，被重置者需重新登录）
#
# 为什么 GET 也限 admin 而不是"登录即可"：
#   列表返回 UserOut（含 is_active/created_at 等账户字段），普通用户无查看他人的业务需要；
#   故障卡片上的创建人/负责人展示走 FaultOut.created_by/assignee（UserBrief），不依赖本接口。
#
# 权限判定分层（同 routers/faults.py 的"薄路由"原则）：
#   角色守卫由 AdminUser 依赖完成；"不能停用我自己"这类业务规则在路由层拦
#   （它不是数据访问规则，而是账户安全规则，放 crud 反而离调用语义远）。

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from .. import crud, schemas
from ..auth import AdminUser
from ..database import get_db
from ..exceptions import PermissionDeniedError

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get(
    "",
    response_model=list[schemas.UserOut],
    summary="用户列表（管理员）",
)
def list_users(user: AdminUser, db: Session = Depends(get_db)) -> list[schemas.UserOut]:
    """返回全部用户（含停用账号，按 username 升序），供管理页与指派/改派下拉使用。"""
    return [schemas.UserOut.model_validate(u) for u in crud.list_users(db)]


@router.post(
    "",
    response_model=schemas.UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="创建账号（管理员）",
    responses={409: {"model": schemas.ErrorOut, "description": "用户名已存在"}},
)
def create_user(
    body: schemas.UserCreate, user: AdminUser, db: Session = Depends(get_db)
) -> schemas.UserOut:
    """创建用户。username 全表唯一（重复 409），密码入库前 bcrypt 哈希（crud.create_user）。"""
    return schemas.UserOut.model_validate(crud.create_user(db, body))


@router.patch(
    "/{user_id}/active",
    response_model=schemas.UserOut,
    summary="启用/停用账号（管理员）",
    responses={
        403: {"model": schemas.ErrorOut, "description": "管理员停用自己账号被拒绝"},
        404: {"model": schemas.ErrorOut, "description": "用户不存在"},
    },
)
def set_user_active(
    user_id: int,
    body: schemas.UserActiveIn,
    user: AdminUser,
    db: Session = Depends(get_db),
) -> schemas.UserOut:
    """启用/停用。停用顺手 bump token_version（已登录会话即时失效，需求二.6）。

    业务规则：不允许管理员停用【自己】——防止把最后一个可用管理员锁在门外
    （本项目无"找回管理员"流程，自停即不可逆自锁）。
    """
    target = crud.get_user(db, user_id)
    if not body.is_active and target.id == user.id:
        raise PermissionDeniedError("不能停用自己的账号")
    return schemas.UserOut.model_validate(crud.set_user_active(db, target, body.is_active))


@router.post(
    "/{user_id}/reset-password",
    response_model=schemas.UserOut,
    summary="重置密码（管理员）",
    responses={404: {"model": schemas.ErrorOut, "description": "用户不存在"}},
)
def reset_password(
    user_id: int,
    body: schemas.UserResetPasswordIn,
    user: AdminUser,
    db: Session = Depends(get_db),
) -> schemas.UserOut:
    """重置指定用户密码。被重置者旧 token 全部失效（crud.reset_password 内 bump）。"""
    target = crud.get_user(db, user_id)
    return schemas.UserOut.model_validate(crud.reset_password(db, target, body.password))
