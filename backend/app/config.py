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

    # ---- CORS ----
    # .env 里写逗号分隔字符串，Pydantic 自动按 JSON 或逗号解析为 list
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # ---- 认证（第三阶段）----
    # secret_key 生产环境必须通过 .env 或环境变量覆盖，默认值仅供本地开发；
    # 一旦泄露等同于所有 token 失效保护失效，故不入库、不入日志。
    secret_key: str = "dev-only-insecure-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 720  # 12 小时

    # ---- 演示数据播种（仅 seed.py 读取，不参与服务运行）----
    # 两种给法都支持（pydantic-settings 的标准优先级）：环境变量 SEED_PASSWORD > .env 同名键。
    # 默认 None = 不给密码，seed 遇到库中缺账号即中止，【绝不内置默认口令】（需求七.4）。
    # 映射关系：字段名 seed_password 自动对应环境变量 SEED_PASSWORD（case_sensitive 默认 False，
    # 且 Windows 上 os.environ 本身不区分大小写），故 seed.py 里只写 settings.seed_password、
    # 看不到 getenv —— 代价是密码来源不在那个文件显眼，本字段就是它的源头。
    seed_password: str | None = None


@lru_cache
def get_settings() -> Settings:
    """缓存配置实例：整个进程只读一次 .env，避免每次访问都解析文件。

    lru_cache 无参 = 最多缓存 1 个实例（无入参，天然单例）。
    FastAPI 的 Depends(get_settings) 也靠它保证每个请求拿到同一份配置。
    """
    return Settings()


# 模块级单例，供非 Depends 场景直接 import 使用（如 database.py 建 engine）
settings = get_settings()
