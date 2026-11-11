# backend 镜像：uv 工作流（2026-09-22 迁移后，依赖由 pyproject.toml + uv.lock 锁定）。
# 构建：cd backend && docker build -t pft-backend:0.1 .
# 运行：docker run --rm -p 8000:8000 pft-backend:0.1

FROM python:3.14-slim
WORKDIR /app

# 1) 装 uv：从官方发布镜像取单个二进制，免安装脚本
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 2) 先拷依赖声明再装（考点一：层缓存——改代码不重装依赖；
#    考点二：--no-cache 不写缓存目录，对应 pip 路线的 --no-cache-dir 瘦身）
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-cache

# 3) 再拷业务代码、迁移目录与运维/初始化脚本
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .
# seed.py / create_admin.py：容器内以 `docker compose run --rm backend uv run --no-sync python create_admin.py`
# 等一次性命令调用（见 README「Docker 部署」），故须进镜像。
COPY seed.py create_admin.py ./
# entrypoint.sh：容器启动先跑 alembic upgrade head 再起 uvicorn（需求七.3 迁移幂等）。
# 先 sed 去掉 Windows 可能带入的 CR（\r），否则容器内 shebang 变 `#!/bin/sh\r` 直接报错；再赋可执行位。
COPY entrypoint.sh ./entrypoint.sh
RUN sed -i 's/\r$//' /app/entrypoint.sh && chmod +x /app/entrypoint.sh

# 考点三：必须绑 0.0.0.0（容器内 127.0.0.1 外部不可达）
EXPOSE 8000
# ENTRYPOINT 负责“迁移后起服务”，CMD 提供被 entrypoint 的 `exec "$@"` 接管的默认启动命令；
# 这样既能覆盖 CMD（如换日志级别），也能整体覆盖 ENTRYPOINT（如跑一次性脚本）。
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uv", "run", "--no-sync", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
