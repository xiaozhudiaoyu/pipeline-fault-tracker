# 模块：create_admin.py —— 初始管理员账号创建脚本（第三阶段 M9，需求七.4）。
#
# 与 seed.py 的分工：
#   · seed.py 播的是【演示数据】——5 个测试账号 + 3 流水线 + 5 故障，用于开发/验收走查；
#   · 本脚本只负责【生产部署的最小可用入口】——建（或补齐）一个管理员账号，不碰任何业务数据。
#   干净环境按需求七.1「只装了 Docker 就能起系统」，首次进入系统需要有一个能登录的管理员，
#   而账号又不开放自助注册（需求二），故用本脚本一次性创建。
#
# 运行（在 backend/ 目录、激活 .venv 后；容器内见 README「Docker 部署」）：
#     $env:ADMIN_PASSWORD="你的管理员密码"; python create_admin.py     # PowerShell（环境变量）
#     ADMIN_PASSWORD=你的管理员密码 python create_admin.py              # bash（环境变量）
#     不导变量也行：把 ADMIN_PASSWORD=你的管理员密码 写进 backend/.env（两处都给时环境变量优先）
#   账号名/显示名可选覆盖：ADMIN_USERNAME（默认 admin）、ADMIN_DISPLAY_NAME（默认 系统管理员）。
#
# 设计要点（对齐 seed.py 与需求七.4）：
#   · 密码取自 settings.admin_password（≥6 位，由 UserCreate 校验把关），不落代码、不入库明文
#     （crud.create_user 内 bcrypt 哈希）；不给密码且账号尚不存在 → 直接中止，【绝不内置默认口令】；
#   · 幂等且【不越权】：按 username 判断，账号已存在则原样跳过，既不重复创建、也【绝不重置已有密码】
#     （重置密码是管理员登录后的显式操作，走 POST /api/users/{id}/reset-password，不由本脚本代劳）；
#   · 只创建 role=admin 的账号；普通用户/处理人员由管理员登录后在用户管理页新增。
#   · 只"加"不做删表/清库等破坏性操作（遵循规则 2.6 / 2.7）。

from app import crud, schemas
from app.config import settings
from app.database import SessionLocal, init_models
from app.models import FaultRole


def create_admin() -> None:
    """确保库中存在名为 settings.admin_username 的管理员；已存在则跳过，不改密码。"""
    init_models()  # 表不存在则创建（容器里通常 alembic 已建好，这里对独立运行兜底，可反复执行）
    db = SessionLocal()
    try:
        existing = crud.get_user_by_username(db, settings.admin_username)
        if existing is not None:
            print(
                f"[skip] 账号「{existing.username}」已存在"
                f"（{existing.display_name} / {existing.role.value}），"
                "不做任何修改——本脚本不会重置已有密码。"
            )
            return

        password = settings.admin_password
        if not password:
            raise SystemExit(
                f"[abort] 库中不存在管理员账号「{settings.admin_username}」且未提供 "
                "ADMIN_PASSWORD（≥6 位）。\n"
                "        两种给法二选一：\n"
                '          · PowerShell：$env:ADMIN_PASSWORD="passw0rd!"; python create_admin.py\n'
                "          · 或在 backend/.env 里写一行：ADMIN_PASSWORD=passw0rd!\n"
                "        两处同时存在时环境变量优先；本脚本不带默认口令。"
            )

        user = crud.create_user(db, schemas.UserCreate(
            username=settings.admin_username,
            password=password,
            display_name=settings.admin_display_name,
            role=FaultRole.admin,
        ))
        print(
            f"[ok] 已创建管理员账号：{user.username}"
            f"（{user.display_name} / {user.role.value}）。请登录后尽快在用户管理页改密。"
        )
    finally:
        db.close()


if __name__ == "__main__":
    create_admin()
