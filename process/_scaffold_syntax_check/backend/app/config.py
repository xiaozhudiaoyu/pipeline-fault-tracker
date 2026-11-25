# 模块：应用配置（pydantic-settings）。
#
# 为什么用 BaseSettings 而不是直接 os.getenv？
#   · 类型安全：字段有类型标注，运行时 Pydantic 会做转换与校验；
#   · 单一来源：所有配置项集中声明，IDE 能补全，一眼看全有哪些开关；
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
    database_url: str = "sqlite:///./demo_app.db"
    db_echo: bool = False

    # ---- 服务 ----
    host: str = "127.0.0.1"
    port: int = 8000

    # ---- CORS ----
    # .env 里写逗号分隔字符串，Pydantic 自动按 JSON 或逗号解析为 list
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


@lru_cache
def get_settings() -> Settings:
    """缓存配置实例：整个进程只读一次 .env，避免每次访问都解析文件。

    lru_cache 无参 = 最多缓存 1 个实例（无入参，天然单例）。
    FastAPI 的 Depends(get_settings) 也靠它保证每个请求拿到同一份配置。
    """
    return Settings()


# 模块级单例，供非 Depends 场景直接 import 使用（如 database.py 建 engine）
settings = get_settings()
