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
from .exceptions import InvalidTransitionError, PermissionDeniedError
from .models import FaultRole, FaultStatus, PipelineFault, User

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


# ══════════════════════════════════════════════════════════════════════
# M4 权限依赖层：角色守卫 + 故障归属×状态守卫
#
# 分层职责（需求二与需求九.3）：
#   1. 未登录 → 401（get_current_user 已处理）；
#   2. 已登录但角色不对 → 403（require_roles）；
#   3. 角色对但不是该资源的归属人 → 403（check_can_*）；
#   4. 归属对但当前状态不允许此动作 → 409（InvalidTransitionError）。
#
# 后端为最终裁判：前端隐藏按钮只为了体验，不作为安全边界；
# 任何客户端直接拼接口请求都要进到上面四道之一。
#
# 不将 check_can_* 直接包装为 FastAPI 依赖的原因：
#   不同动作所需上下文不同（有的需 fault，有的需 fault+creator），且
#   M5 动作端点内部需先取 fault、再判断、再同事务写时间线——拆成依赖反而不能共享事务。
#   因此本层提供“纯净”函数，由 M5 在 crud 层调用。
# ══════════════════════════════════════════════════════════════════════
def _forbidden(detail: str) -> HTTPException:
    """未登录时的 403 统一出口（与领域 PermissionDeniedError 分开：
    本函数用于“角色守卫”给路由抛 HTTPException，确保带上 WWW-Authenticate）。
    业务层（crud）一律抛 PermissionDeniedError，交给 exceptions.py 的 AppError handler。
    """
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_roles(*roles: FaultRole):
    """依赖工厂：要求当前登录用户角色属于传入集合。

    用法：
        from fastapi import Depends
        admin: User = Depends(require_roles(FaultRole.admin))
        或使用下方预置的 Annotated 别名 AdminUser / HandlerUser。

    角色不匹配抛 403（而非 401）：身份已确认，重新登录也不会变。
    """
    if not roles:
        raise ValueError("require_roles 需至少传入一个角色")

    def dep(user: CurrentUser) -> User:
        if user.role not in roles:
            allowed = "/".join(r.value for r in roles)
            raise _forbidden(f"本接口仅限角色：{allowed}")
        return user

    return dep


# 预置别名：路由签名写 `user: AdminUser` 即可，无需每处重写 require_roles
AdminUser = Annotated[User, Depends(require_roles(FaultRole.admin))]
HandlerUser = Annotated[User, Depends(require_roles(FaultRole.handler))]
HandlerOrAdminUser = Annotated[User, Depends(require_roles(FaultRole.handler, FaultRole.admin))]


# ── 故障归属与动作权限校验（M5 各动作端点在 crud 层调用）─────────────
def can_view_fault(user: User, fault: PipelineFault) -> bool:
    """查看权限（需求二.4 + 需求四.4）：
      · admin 看全部；
      · handler 看分派给自己的（包含自己创建的）；
      · user 看自己创建的。
    历史数据（created_by_id/assignee_id 为 NULL）：仅 admin 可看，
    因无从归属到当下任何个人（需求六.2）。
    """
    if user.role == FaultRole.admin:
        return True
    if user.role == FaultRole.handler:
        return fault.assignee_id == user.id or fault.created_by_id == user.id
    # FaultRole.user
    return fault.created_by_id == user.id


def check_can_assign(user: User, fault: PipelineFault) -> None:
    """指派（pending 无负责人 → 设定负责人，状态不变）：
      · 仅管理员；
      · done 终态拒绝；
      · awaiting_confirmation 不允许指派（D6：待确认不改派），需先退回至 processing；
      · 已有负责人时应走 reassign，而非 assign（避免时间线语义混淡）。
    """
    if user.role != FaultRole.admin:
        raise PermissionDeniedError("仅管理员可指派负责人")
    if fault.status == FaultStatus.done:
        raise InvalidTransitionError(current=fault.status.value, target="assign")
    if fault.status == FaultStatus.awaiting_confirmation:
        raise InvalidTransitionError(current=fault.status.value, target="assign")
    if fault.assignee_id is not None:
        raise PermissionDeniedError("该故障已有负责人，请走改派流程")


def check_can_reassign(user: User, fault: PipelineFault) -> None:
    """改派（现有负责人 → 新负责人，状态延续）：
      · 仅管理员，且原因必填（在 M5 层校验，不在本函数）；
      · 仅 pending / processing 可改派（D6：待确认状态需先退回）；
      · 必须已有负责人（否则应走 assign）。
    """
    if user.role != FaultRole.admin:
        raise PermissionDeniedError("仅管理员可改派负责人")
    if fault.status not in (FaultStatus.pending, FaultStatus.processing):
        raise InvalidTransitionError(current=fault.status.value, target="reassign")
    if fault.assignee_id is None:
        raise PermissionDeniedError("尚未指派负责人，无法改派")


def check_can_start(user: User, fault: PipelineFault) -> None:
    """开始处理：仅当前负责人，且状态为 pending（需求三 SM2/SM3）。"""
    if fault.assignee_id != user.id:
        raise PermissionDeniedError("仅当前负责人可以开始处理")
    if fault.status != FaultStatus.pending:
        raise InvalidTransitionError(current=fault.status.value, target="start")


def check_can_progress(user: User, fault: PipelineFault) -> None:
    """追加进展：仅当前负责人，且状态为 processing（SM4）。"""
    if fault.assignee_id != user.id:
        raise PermissionDeniedError("仅当前负责人可以追加进展")
    if fault.status != FaultStatus.processing:
        raise InvalidTransitionError(current=fault.status.value, target="progress")


def check_can_submit(user: User, fault: PipelineFault) -> None:
    """提交处理结果：仅当前负责人，且状态为 processing（SM6）。"""
    if fault.assignee_id != user.id:
        raise PermissionDeniedError("仅当前负责人可以提交结果")
    if fault.status != FaultStatus.processing:
        raise InvalidTransitionError(current=fault.status.value, target="submit")


def check_can_confirm(user: User, fault: PipelineFault) -> None:
    """确认完成（SM7）：
      · 状态必须为 awaiting_confirmation；
      · 创建人自己确认 → 可（且创建人不同时为负责人，避免自处理自闭环）；
      · 管理员代确认 → 仅当创建人已停用或不存在（历史数据/已删账号），需求二.5；
      · 负责人自行确认 → 任何情形都拒绝（SM12）。

    实现细节：读 fault.created_by 会触发 lazy load，调用方需保证当前 session 可查库。
    """
    if fault.status != FaultStatus.awaiting_confirmation:
        raise InvalidTransitionError(current=fault.status.value, target="confirm")
    # 负责人不能自行确认（无论其当前角色为何）
    if fault.assignee_id is not None and fault.assignee_id == user.id:
        raise PermissionDeniedError("负责人不能自行确认完成")
    # 创建人本人确认
    if fault.created_by_id is not None and fault.created_by_id == user.id:
        return
    # 管理员代确认：仅在创建人不可用时
    if user.role == FaultRole.admin:
        creator = fault.created_by
        if creator is None or not creator.is_active:
            return
        raise PermissionDeniedError("创建人仍在启用中，应由创建人本人确认")
    raise PermissionDeniedError("仅创建人可确认完成，或创建人不可用时由管理员代确认")


def check_can_return(user: User, fault: PipelineFault) -> None:
    """退回处理（SM8）：仅创建人本人，且状态为 awaiting_confirmation。
    管理员不默认能代退回（需求未提及，按保守处理）。
    """
    if fault.status != FaultStatus.awaiting_confirmation:
        raise InvalidTransitionError(current=fault.status.value, target="return")
    if fault.created_by_id != user.id:
        raise PermissionDeniedError("仅创建人可以退回处理")


def check_can_priority_change(user: User, fault: PipelineFault) -> None:
    """优先级调整（AU9）：done 之前，管理员或创建人可调。不要求填写原因（需求未提）。"""
    if fault.status == FaultStatus.done:
        raise InvalidTransitionError(current="done", target="priority_change")
    if user.role == FaultRole.admin:
        return
    if fault.created_by_id == user.id:
        return
    raise PermissionDeniedError("仅管理员或创建人可调整优先级")
