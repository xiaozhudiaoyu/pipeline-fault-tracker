# 模块：应用配置（pydantic-settings）。
#
# 为什么用 BaseSettings 而不是直接 os.getenv？
#   · 类型安全：字段有类型标注，Pyright 能检查，运行时 Pydantic 会做转换与校验；
#   · 单一来源：所有配置项集中声明，IDE 能补全，新人一眼看全有哪些开关；
#   · .env 支持：自动读取 backend/.env（由 python-dotenv 解析），本地配置不入库。
#
# 使用方式：
#   from app.config import settings
#   print(settings.database_url)

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置。字段名与 .env 里的键一一对应（大小写不敏感）。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # .env 里多出的键不报错，便于渐进添加
    )

    # ---- 数据库 ----
    database_url: str = "sqlite:///./fault_tracker.db"
    db_echo: bool = False

    # ---- 服务 ----
    host: str = "127.0.0.1"
    port: int = 8000

    # ---- 时间口径 ----
    # 业务时区（相对 UTC 的整小时偏移）：occurred_at 的“不得晚于当前”判定、
    # created_at/updated_at/closed_at 的写入全部以它为准，与容器/宿主进程时区无关
    # （缘由与边界见 timeutil.py 文件头）。默认 8 = 北京时间，异地部署用环境变量
    # BUSINESS_UTC_OFFSET_HOURS 覆盖即可，不需改代码。
    business_utc_offset_hours: int = 8

    # ---- CORS ----
    # .env 里写逗号分隔字符串，Pydantic 自动按 JSON 或逗号解析为 list
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # ---- 认证（第三阶段）----
    # secret_key 生产环境必须通过 .env 或环境变量覆盖，默认值仅供本地开发；
    # 一旦泄露等同于所有 token 失效保护失效，故不入库、不入日志。
    secret_key: str = "dev-only-insecure-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 720  # 12 小时

    # ---- 图片附件（第四阶段）----
    # 附件文件目录：本地开发默认 ./data/uploads（backend/ 下，不入库）；
    # 容器形态由 compose 注入 UPLOAD_DIR=/app/data/uploads，落既有 pft-data 卷（需求七.3 持久化）。
    # 注意：数据 = 库文件 + 本目录两处，备份/迁移都要带上（见 README 11.5）。
    upload_dir: str = "./data/uploads"
    # 单文件大小上限（字节，默认 5 MB）与每条故障张数上限；crud 流式写盘时边写边计数。
    # 前端 schemas/fault.ts 的 FAULT_ATTACHMENT_LIMITS 与此同源，改这里要同步改那边（已踩过的坑）。
    attachment_max_bytes: int = 5_242_880
    attachment_max_per_fault: int = 10

    # ---- 演示数据播种（仅 seed.py 读取，不参与服务运行）----
    # 两种给法都支持（pydantic-settings 的标准优先级）：环境变量 SEED_PASSWORD > .env 同名键。
    # 默认 None = 不给密码，seed 遇到库中缺账号即中止，【绝不内置默认口令】（需求七.4）。
    # 映射关系：字段名 seed_password 自动对应环境变量 SEED_PASSWORD（case_sensitive 默认 False，
    # 且 Windows 上 os.environ 本身不区分大小写），故 seed.py 里只写 settings.seed_password、
    # 看不到 getenv —— 代价是密码来源不在那个文件显眼，本字段就是它的源头。
    seed_password: str | None = None

    # ---- 初始管理员（仅 create_admin.py 读取，不参与服务运行）----
    # 需求七.4：提供创建初始管理员的方法，账号密码可配置，且不把真实密码写死在代码/镜像里。
    # 取值通道与 seed_password 完全一致（环境变量 > backend/.env，pydantic-settings 自动映射）：
    #   ADMIN_USERNAME / ADMIN_PASSWORD / ADMIN_DISPLAY_NAME。
    # username、display_name 有合理默认（非敏感）；password 默认 None = 不给就不建，
    # create_admin.py 缺密码即中止，【绝不内置默认口令】。已存在同名账号则跳过、不重置密码（幂等）。
    admin_username: str = "admin"
    admin_password: str | None = None
    admin_display_name: str = "系统管理员"


@lru_cache
def get_settings() -> Settings:
    """缓存配置实例：整个进程只读一次 .env，避免每次访问都解析文件。

    lru_cache 无参 = 最多缓存 1 个实例（无入参，天然单例）。
    FastAPI 的 Depends(get_settings) 也靠它保证每个请求拿到同一份配置。
    """
    return Settings()


# 模块级单例，供非 Depends 场景直接 import 使用（如 database.py 建 engine）
settings = get_settings()
