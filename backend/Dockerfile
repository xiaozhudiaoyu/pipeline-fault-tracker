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

# 3) 再拷业务代码与迁移目录
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .

# 考点三：必须绑 0.0.0.0（容器内 127.0.0.1 外部不可达）
EXPOSE 8000
CMD ["uv", "run", "--no-sync", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
