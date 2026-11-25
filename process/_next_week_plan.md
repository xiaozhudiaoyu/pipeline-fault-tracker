# 下周练习计划（Pipeline Fault Tracker · 依据阶段评估反馈）

> 来源：2026-09-18 阶段评估邮件（王潼老师评估：朱常乐 78 分）所列「下周建议学习方向」5 条 + 王潼老师工程化建议。
> 练习载体：**现有项目 `pipeline-fault-tracker`**（backend FastAPI + SQLAlchemy 2 / frontend Vue 3 + TS），在真项目上练，不另起新仓库。
> 总原则（呼应王潼老师建议）：精力前移到需求澄清、接口边界、验收标准；形成「先规划、分步实现、及时验证」习惯；全程保持约定式提交（`type(scope): subject`），为 Agent / 老师提供清晰上下文。

## 排期总览

| 天 | 方向 | 主题 | 验收标准 |
|---|---|---|---|
| D1 | ① FastAPI/Pydantic | 输入校验与异常响应 | 能列出每条校验的正常/异常请求与 422 `details` |
| D2 | ② Alembic | 引入迁移 + 一次增量结构变更 | `alembic upgrade head` / `downgrade -1` 可逆 |
| D3 | ② 会话/事务 + ③ Git | 回滚用例 + 提交整理 | 说清 session 生命周期与回滚触发点；每个 commit 只做一件事 |
| D4 | ④ uv | 从零重建 backend 环境 | 零到可运行；能说清 uv vs pip 差异 |
| D5 | ⑤ WSL | Linux 下跑通前后端两服务 | WSL 下两服务起得来、curl 通 |
| 延伸 | ⑤ Docker | 仅概念，可选 dockerize backend | 不强制 |

---

## D1 —— 巩固 FastAPI 与 Pydantic（输入校验、异常响应、业务规则）

**目标**：完善输入校验、异常响应和业务规则，并用接口文档验证正常及异常场景。

**练习**：
1. 给 `backend/app/schemas.py` 加边界校验：用 `Field` 的 `min_length` / `max_length` / `ge` / `le` / `pattern`，例如故障现象长度、发生位置格式、`occurred_at` 不晚于当前时间。
2. 补 1–2 条业务规则校验（如「状态推进到 done 时 `handling_note` 必填」已有，可再加一条新的业务约束）。
3. 逐条用 Swagger `/docs` 验证**正常 + 异常**两种请求：异常应返回 422 且 `details` 可读、能定位到字段。

**验收**：能列出每条新增校验的正常/异常请求与响应；422 的 `details` 结构清晰、字段可定位。

**说明**：此条邮件中为黄帅重点加强项，你同样自查巩固；异常场景统一走 `exceptions.py` 的统一 handler，不新造错误格式。

---

## D2 —— 数据库与迁移：引入 Alembic 并完成一次结构变更

**目标**：补齐数据库与迁移理解；用 Alembic 完成一次数据库结构变更。

**练习**：
1. `alembic init` 初始化；`env.py` 接通 `models` 的 metadata 与 `config.py` 的 `database_url`。
2. 先生成 **baseline**（对齐当前已有表），再做**一次增量变更**：如给 `pipeline_faults.occurred_at` 加索引，或新增一列（如 `severity` 等级）；写好 `upgrade()` / `downgrade()`。
3. 执行 `alembic upgrade head` 与 `alembic downgrade -1`，确认**可逆**。

**验收**：upgrade / downgrade 往返成功、数据不丢；能说清 Alembic 版本表（`alembic_version`）作用。

**注意**：`python_learn/day18_alembic` 有参考实现，可对照但**在本项目上亲手做**；中文 Windows 下 `alembic.ini` 须 ASCII-only（locale/GBK 读取坑，见长期记忆）。

---

## D3 —— SQLAlchemy 会话/事务 + Git 提交整理

**目标**：加深对 SQLAlchemy 会话、事务和约束的理解；巩固规范 Git 提交。

**练习**：
1. 通读 `backend/app/crud.py` 的 `commit` / `rollback` 与 `database.py` 的 `get_db`（请求级 Session），画出 session 生命周期。
2. 写一个「多表写、中途失败需整体回滚」的用例（如同时写 fault + 关联表，第二步抛错），验证第一步不残留。
3. 在**练习分支**（不动 main）上练 `git rebase -i` 整理杂乱提交：合并琐碎提交、改写清晰 subject/body。

**验收**：能说清 session 何时提交/回滚/关闭；回滚用例证明事务原子性；整理后每个 commit 的 diff 只含一件事、body 说明「为什么」。

---

## D4 —— 环境管理：用 uv 重建 backend 环境

**目标**：掌握 Python 虚拟环境管理，选定环境管理工具（uv），避免多项目依赖混乱。

**练习**：
1. `uv venv` 创建虚拟环境；`uv pip install -r requirements.lock.txt` 精确复现依赖。
2. 用该环境跑通 backend（`uvicorn app.main:app`），请求 `/api/faults` 验证 200。
3. 对比 uv 与 pip + venv 的速度/用法差异；理解 lock 文件在 uv 下的角色。

**验收**：从零（删掉旧 venv）到可运行全程用 uv 完成；能说清 uv vs pip 的差异与适用场景。

**说明**：项目 `.gitignore` 已忽略 uv 产物（`pyproject.toml` / `uv.lock`），本次可顺势把 uv 用法固化进 README/台账（若引入新依赖须按规则 2.6 登记）。

---

## D5 —— 工程化：WSL / Linux 下跑通前后端

**目标**：通过 WSL 熟悉 Linux 下的开发与运行方式（呼应「Agent 更擅长 Linux、WSL 贴近部署环境」）。

**练习**：
1. 启用 WSL2（Ubuntu）；把项目放入 WSL 文件系统（或理解 `/mnt/...` 互访与性能差异）。
2. 在 WSL 内用 **Linux 命令**（`ls` / `ps` / `kill` / `curl`，而非 PowerShell）启动 backend 与 frontend。
3. 理解 Windows ↔ WSL 的端口转发：在 Windows 浏览器经 `localhost` 访问 WSL 内服务。
4. 用 `curl` 验证 `/api/faults` 与前端页面返回。

**验收**：WSL 下两服务均启动、`curl` 验证通过；能用 Linux 命令完成查看/停止进程。

---

## 延伸 —— Docker / Docker Compose（本周仅概念）

邮件明确「后续按实际项目需要学习 Docker 和 Docker Compose」，本周不强制。可选：概念了解镜像/容器/卷/网络；有余力再尝试把 backend 容器化（Dockerfile + 暴露 8000）。

---

## 与评估核对（清单 A）的衔接

- 评估两条扣分「缺少 Git 历史记录 / 环境配置仍有不足」与仓库现状**不符**（已证实：`.git` 在、10 条约定式提交、`.env.example`×2 / 双 lock / `DEPENDENCIES.md` 齐全）；最大嫌疑是**交付物未含 `.git`**。D3（Git）/ D4（uv）/ D5（WSL/Docker）正好补「能力缺口」层。
- 仓库真实缺口（「没做」而非「做错」）：无 Alembic（→D2）、无 uv（→D4）、无 WSL/Docker（→D5/延伸），与下周方向一一对应。
