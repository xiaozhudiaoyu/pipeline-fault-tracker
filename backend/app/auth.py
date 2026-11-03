# 模块：认证（第三阶段需求二）—— 密码哈希、JWT 签发/校验、当前用户依赖。
#
# 分工：
#   hash_password / verify_password   —— bcrypt 直用（D4），盐值内嵌哈希串；
#   create_token / decode_token       —— PyJWT HS256（D3），payload 携带 sub + tv；
#   get_current_user                  —— FastAPI 依赖，任何需要登录的接口 Depends 它即可。
#
# token_version 即时失效（D3）：
#   签发时把 user.token_version 写入 payload 的 tv 字段；
#   校验时对比 user.token_version 与 tv，任一 bump（停用/改密/登出）后旧 token 立即失效。
#   —— 不用黑名单/短期过期，理由：本项目规模小，一次数据库读就够。
#
# 敏感处理：
#   · settings.secret_key 缺失时启动不报错但会打日志提醒（.env 未配 → 生产上必须配）；
#   · 密码明文只在 verify_password 参数里存活几毫秒，不落日志、不入异常堆栈；
#   · username/user_id 可以进日志，password/token 绝不进日志。

import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import User

logger = logging.getLogger("app.auth")


# ── 密码哈希 ────────────────────────────────────────────────────────────
def hash_password(plain: str) -> str:
    """bcrypt 加盐哈希。同一明文每次返回不同字符串（盐随机），比对靠 checkpw。

    bcrypt 输出固定 60 字节，前 7 字节自描述（算法+轮数+盐），
    因此 User.password_hash 用 String(200) 足够未来换算法时留空间。
    """
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """恒定时间比对。hashed 格式异常（非 bcrypt 输出）也返回 False，不抛异常。"""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ── JWT 签发 / 解析 ─────────────────────────────────────────────────────
def create_token(user: User) -> str:
    """签发访问令牌。

    payload 字段：
      sub       —— 用户 ID（字符串，符合 JWT RFC 7519 对 sub 的类型要求）
      username  —— 便于前端展示，不作为查询依据（防用户名改名后 token 里的与实际不符，
                   仍以下方 sub 查库为准）
      role      —— 便于前端菜单/按钮控制（服务端仍以数据库角色为准）
      tv        —— 用户 token_version，即时失效判定用
      iat / exp —— 签发与过期时间（UTC 秒）
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role.value,
        "tv": user.token_version,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def _unauthorized(detail: str) -> HTTPException:
    """401 统一出口，带 WWW-Authenticate 头（HTTP 规范对 401 的要求）。"""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def decode_token(token: str) -> dict:
    """解析并校验签名与 exp。任何异常都翻成 401，不暴露具体原因（防枚举攻击）。"""
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        raise _unauthorized("登录已过期，请重新登录")
    except jwt.InvalidTokenError:
        # 签名错误 / 算法不匹配 / payload 非 JSON 等，一律同一话术
        raise _unauthorized("身份凭证无效")


# ── FastAPI 依赖：当前登录用户 ──────────────────────────────────────────
# auto_error=False 关掉 HTTPBearer 默认的 403，改由我们抛 401；
# 缺失 Authorization 头时 credentials=None，走我们自己写的分支。
_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """解析 Bearer Token → 查库 → 校验有效性 → 返回 User 对象。

    校验链（任一失败即 401）：
      ① Header 存在且形如 "Bearer xxx"；
      ② JWT 签名有效且未过期；
      ③ 用户仍存在于数据库（防管理员删号）；
      ④ 用户 is_active（防停用账号继续操作）；
      ⑤ payload.tv == user.token_version（防旧 token 复用，实现即时失效）。

    使用方式：路由签名写 `user: CurrentUser` 即可，FastAPI 自动注入。
    """
    if credentials is None or not credentials.credentials:
        raise _unauthorized("未提供身份凭证")

    payload = decode_token(credentials.credentials)

    # sub 必须是整数用户 ID；被篡改的 token 即使签名对（不可能，除非密钥泄漏）也不应绕过查询
    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub.isdigit():
        raise _unauthorized("身份凭证无效")
    user = db.get(User, int(sub))
    if user is None:
        raise _unauthorized("账号不存在")
    if not user.is_active:
        raise _unauthorized("账号已被停用")
    if payload.get("tv") != user.token_version:
        # 停用/改密/登出后 bump token_version，之前签发的所有 token 立即失效
        raise _unauthorized("凭证已失效，请重新登录")
    return user


# 供路由签名使用的类型别名：`user: CurrentUser` 等价于 `user: User = Depends(get_current_user)`
CurrentUser = Annotated[User, Depends(get_current_user)]
