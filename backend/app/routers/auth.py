# 路由模块：/api/auth —— 登录、登出、当前用户（第三阶段需求二）。
#
# 端点清单：
#   POST /api/auth/login   —— 用户名密码换 JWT，公开接口
#   POST /api/auth/logout  —— 使当前 token 立即失效（token_version bump），需登录
#   GET  /api/auth/me      —— 返回当前登录用户，前端刷新页面时用于恢复登录态
#
# 边界提示（已由其他模块承接）：
#   · 业务接口（faults/pipelines）的登录校验——M4/M5 已统一挂 CurrentUser/AdminUser；
#   · 用户管理接口（/api/users）——M6 提供（routers/users.py，仅管理员）。
#
# 为什么 login 抛 401 而不是 404：
#   "用户名不存在" 与 "密码错误" 使用同一话术，防止攻击者用返回信息枚举有效账号。

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import crud, schemas
from ..auth import CurrentUser, create_token
from ..config import settings
from ..database import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=schemas.TokenResponse,
    summary="用户名密码登录，返回 JWT",
)
def login(body: schemas.LoginRequest, db: Session = Depends(get_db)) -> schemas.TokenResponse:
    """校验用户名与密码。

    四种失败均返回 401 且 message 一致（防枚举）：
      · 用户名不存在
      · 密码不匹配
      · 账号已被停用（is_active=False）——同样返回"用户名或密码错误"，
        不额外区分，避免攻击者通过差异判断该账号有效但被停用
    """
    user = crud.authenticate(db, body.username, body.password)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_token(user)
    return schemas.TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="登出：使当前用户此前签发的全部 token 立即失效",
)
def logout(user: CurrentUser, db: Session = Depends(get_db)) -> None:
    """token_version += 1，之前发出的所有 token 中的 tv 与库中值不再匹配，即刻失效。

    无响应体（204）。前端负责本地清空 token。
    """
    crud.bump_token_version(db, user)


@router.get(
    "/me",
    response_model=schemas.UserOut,
    summary="返回当前登录用户，前端刷新时用于恢复登录态",
)
def me(user: CurrentUser) -> schemas.UserOut:
    """依赖 get_current_user 完成认证后，把 User ORM 转成 UserOut 契约。"""
    return schemas.UserOut.model_validate(user)
