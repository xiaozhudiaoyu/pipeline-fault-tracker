#!/bin/sh
# backend 容器入口（第三阶段 M9，需求七.3）：先跑数据库迁移，再起服务。
#
# 为什么迁移放这里而不是塞进应用启动：
#   · 迁移是一次性、需在“接业务流量之前”完成的动作；放进 entrypoint 与 uvicorn 生命周期解耦，
#     本地开发（uvicorn --reload）不经过本文件，仍由 seed/create_admin 里的 init_models 兜底建表。
#   · alembic upgrade head 幂等：alembic_version 表记录当前版本，已应用的迁移不会重跑，
#     故容器【反复重启既不清库、也不重复执行迁移】（需求七.3）。
#   · 首次启动（空数据卷）：基线迁移 843f28b00698 从空库建全表 → 一路 head；
#     旧库卷：已在 head 或落后若干版本，upgrade 只补差量。
#     注意：若复用一个“只靠 create_all 自动建过表、从未 stamp 过 alembic_version”的旧库卷，
#     upgrade 会因基线 CREATE TABLE 撞已存在表而失败——这种历史库须先按 README 10.2 stamp 再接管。
#
# set -e：任一步失败即中止，绝不带着未迁移的库去起服务（宁可容器退出暴露问题）。
# 之后 exec "$@" 把 PID 1 交给 CMD（uvicorn），保证信号（docker stop 的 SIGTERM）能正确透传。
set -e

echo "[entrypoint] applying database migrations: alembic upgrade head"
uv run --no-sync alembic upgrade head

echo "[entrypoint] starting service: $*"
exec "$@"
