# 阶段二计划：从"能跑"到"可靠"（工程质量深化）

> 来源：`_next_week_plan.md`（五天）与 `_docker_plan.md`（Docker/Compose）均已完成（2026-09-23 实测核验，见第 0 节）；本计划为下一阶段主线，经用户确认取**完整范围 P0–P4**。
> 主题依据：评估已认可"完成度/错误处理"，扣分项（环境配置、Git 历史）均已补救；王潼老师"精力前移：需求澄清/接口边界/验收标准"建议尚未系统练过 → 本阶段核心差距是**测试、CI、真实数据库形态、需求全流程**。
> 载体：pipeline-fault-tracker（主）+ python_learn（P0 收尾）。制定日期：2026-09-23。

## 0. 现状基线（2026-09-23 全部实测）

| 项 | 结论 | 证据 |
|---|---|---|
| 五天计划 | 已完成 + 超额（day19/day20 模块） | pft 提交 `8866298`(D1)、`5ccc13e`、`1463a87`(D2)、`80068fd`(D3)；python_learn `25793a1`~`3b336ad`（day18–20）；versions 目录 3 个迁移文件 |
| uv | Windows 已装 0.12.8；**pft backend 已迁移 uv 工作流**（09-22） | `uv --version`；提交 `c865236`+`5ecde64`；`pyproject.toml`/`uv.lock` 在、`requirements.lock.txt` 已删 |
| Docker | 路线 B 完成：WSL Ubuntu 内 Docker 29.8.1 + Compose v5.5.1 | `wsl docker --version`；练习镜像 pft-backend/frontend:0.1 + compose 双镜像 + busybox（卷备份演练）在；volumes 已清空（练完清理，正常） |
| Docker 产物归属 | 已入库 | 提交 `7ab3d84`（D1-D3 产物）、`e847e88`（compose 编排） |
| Git 历史缺口 | **已补救**：remote 指向 GitHub，main 与 origin/main 同步 | `git remote -v` → `git@github.com:WSD2007zhuchangle/pipeline-fault-tracker.git`；`status -sb` 无 ahead/behind |
| 文档同步 | README 已改 uv sync（×3）；DEPENDENCIES 含 uv 记录（×5）+ pip 历史台账（合规保留） | Select-String 计数 |
| 遗留（P0 处理） | python_learn 未提交：`ae51b7d217ff` 增量迁移未跟踪、`.gitignore` 修改、bat 替换（删 run_todo_api.bat / 新增 dev.bat） | `git status --short` |

## 1. 目标与非目标

- **目标**：建立自动化质量防线（pytest 分层测试 + GitHub Actions CI）；数据库升级到 PostgreSQL（Docker 学以致用）；完整演练一次"需求→评审→实现→测试→提交"全流程。
- **非目标**：前端测试体系（Vitest，Node 16 兼容性需另核）、真实服务器部署、K8s、性能压测——本阶段不碰。

## 2. 分节安排

### P0 —— 收尾与一致性检查（半天，卫生项）

- **python_learn 三处遗留逐一决策**（AI 只给建议，提交由用户执行——规则 5.1）：
  1. `day18_alembic/versions/ae51b7d217ff_add_xxx_column.py`（D2 练习增量迁移）：判定"保留提交"或"清理"——若 day18 演示依赖它则提交（`feat(day18):` 或并入练习提交），否则 down 后删除；
  2. `M .gitignore`：确认修改意图后提交或还原；
  3. bat 替换（`D run_todo_api.bat` + `?? dev.bat`）：确认为重命名/替换后一次提交，避免半状态。
- **pft 文档轻核对**：README 快速开始、DEPENDENCIES 台账与 `pyproject.toml`/`uv.lock` 实际一致（直接依赖表、复现步骤）；发现不一致按规则 2.5 补台账。
- **验收**：两仓库 `git status` 干净（或剩余项均有明确"故意不提交"理由）；文档描述可照抄复现环境。

### P1 —— 测试体系化：pytest + httpx（2-3 天）⭐核心

- **依赖引入**（规则 2.5：先确认再装 + 补台账）：`uv add --dev pytest httpx`（进入 pyproject dev 依赖组 + uv.lock）。
- **测试分层**（目录 `backend/tests/`，按 app/ 既有分层组织）：
  1. **schemas 单元**：校验规则（必填/长度/枚举/边界值）逐条断言——把 D1 练过的 Field 约束变成回归网；
  2. **crud 单元**：内存 SQLite（`sqlite:///:memory:` + StaticPool）独立建表，测增删改查与业务规则，不碰开发库；
  3. **API 集成**：httpx `ASGITransport`（或 FastAPI TestClient）+ 依赖覆盖（override get_session 到测试会话），走完整请求链路含 lifespan 建表；
  4. **错误路径**：404（不存在 id）/ 409（业务冲突）/ 422（校验失败）逐一断言状态码与响应体结构——现状只有手工冒烟，这是最大增量。
- **方法练习（回应老师建议）**：每个测试文件**先写验收标准清单（正常/异常/边界）再落成测试**，验收标准以注释或 docstring 形式留在测试里。
- **验证**：`uv run pytest -v` 全绿；故意改坏一条业务规则 → 对应测试变红（证明测试有效）→ 改回。
- **验收**：四层各有至少 1 个文件；能说清"单元用内存库、集成走 ASGI、依赖覆盖隔离"三件事；测试可重复跑（无脏数据残留）。

### P2 —— CI：GitHub Actions（1-2 天）

- **前置**：仓库已在 GitHub（基线已证）；P1 测试就绪（否则 CI 只跑构建，价值减半）。
- **workflow**（`.github/workflows/ci.yml`，版本与用法以官方文档为准——规则 3.4）：
  - 触发：push main + pull_request；
  - backend job：`astral-sh/setup-uv`（带缓存）→ `uv sync` → `uv run pytest`；
  - frontend job：`actions/setup-node`（node 16，cache npm）→ `npm ci` → type-check → `npm run build`；
  - 可选第三 job：`docker build` 双镜像（GitHub runner 自带 docker，不用 compose up）。
- **概念清单**：workflow/job/step 层级、runner、secrets（本阶段用不到但要知道）、缓存键、矩阵策略（了解即可）。
- **验证**：push 后 Actions 页全绿；故意提交一个类型错误 → CI 变红 → 修复变绿（闭环演练）。
- **验收**：能看懂 ci.yml 每一行的作用；本地命令与 CI 步骤一一对应；红灯-修复-绿灯走通一次。

### P3 —— SQLite → PostgreSQL（Docker 学以致用，2-3 天）

- **依赖引入走单独通道**（规则 3.5 + 2.5）：`uv add "psycopg[binary]"` 独立提交，不与功能改动混合；台账补记。
- **compose 改造**：`docker-compose.yml` 加 `postgres:16-alpine` 服务（POSTGRES_DB/USER/PASSWORD env + named volume `pft-pgdata` + healthcheck `pg_isready`）；backend 服务 `DATABASE_URL=postgresql+psycopg://...@postgres:5432/...`，depends_on 加 postgres healthy。
- **迁移路径**（二选一，动手前定）：
  - a. 保守：继续靠启动 `create_all(checkfirst=True)` 在 PG 建表，Alembic 仅作练习产物——改动最小；
  - b. 进阶：backend 入口改 entrypoint 先 `alembic upgrade head`（Docker 计划 D5 的可选项），讨论与 create_all 的分工与表结构漂移风险——涉代码改动，按规则 2.2 先出方案。
- **练习点**：SQLAlchemy 2.0 多方言（URL 换驱动即切换）；SQLite vs PG 类型/约束差异（如自增、日期）；连接池参数（pool_size 等）；PG 数据在 named volume 中持久化验证。
- **验证**：compose up 后走通全闭环（登记/列表/详情/修改）；P1 测试切 PG 连接串再跑一遍全绿；`down` 再 `up` 数据仍在。
- **验收**：能说清方言切换点在哪、哪些代码零改动、哪些行为有差异；SQLite 开发库与 PG 容器库可并存切换。
- **当前状态（2026-09-30）**：代码与编排已提交（`cd858fd` psycopg、`1c6a250` 双方言、`aae9e3e` compose+PG），但**容器验收未通过**。
  - 已定位根因：`docker compose up -d` 未带 `--build`，复用了 P3 之前的旧 backend 镜像（证据：容器日志 `ModuleNotFoundError: No module named 'psycopg'`；镜像内 site-packages 无 psycopg；镜像内 `database.py` 无 `_is_sqlite` 方言分支，而源码侧三项均具备）；
  - 待执行：`docker compose build backend && docker compose up -d`（预检已过：uv.lock 含 `psycopg_binary-3.3.6-cp314-manylinux2014_x86_64` wheel）；
  - 重建后补两步：① 灌 seed（`seed.py` 未被 Dockerfile COPY 进镜像，需 `compose cp` 后 `exec ... uv run --no-sync python /app/seed.py`）；② `down` 再 `up -d` 验数据持久化 + `TEST_DATABASE_URL` 切 PG 重跑 P1 测试；
  - 附带发现（非故障原因）：WSL 侧 `~/pipeline-fault-tracker` 全树 61 文件显示 modified 且增删行数对称（5648/5648），为 CRLF/LF 行尾差异，对构建无影响，但会使那边 `git status` 常驻脏状态。

### P4 —— 功能迭代练习：需求全流程（2-3 天）

- **功能候选**（启动时选定，AI 不代替取舍——规则 1.1）：
  - 统计看板（按状态/日期聚合，低风险，前后端都练）；
  - 导出 CSV（文件响应 + 流式处理，低风险）；
  - JWT 认证（**高风险面**，规则 2.4：人主导设计与审查，AI 只出方案建议）。
- **全流程演练**（每一步落盘成文档，回应"精力前移"）：
  1. 需求文档：三要素（参考标杆/目标范围/具体约束）+ 验收标准（正常/异常/边界）+ 非目标；
  2. 接口边界：端点/方法/请求响应 schema/错误码表，先评审后动手；
  3. 实现：后端（schema→crud→router）+ 前端（api→页面）跟随既有分层（规则 3.2）；
  4. 测试：新功能配 P1 风格测试再合入；
  5. 提交：约定式、小步（规则 5.1，用户执行）。
- **验收**：需求文档在实现前完成且实现与之对照无漂移；新功能测试进 CI 绿灯；全程提交历史清晰可回溯。

## 3. 压缩变体（时间紧时 3 次）

- S1 = P0 + P1（质量防线立起来）；S2 = P2 + P3（CI + PG）；S3 = P4（需求全流程，功能选最小的导出 CSV）。

## 4. 执行纪律与衔接

- 与前两份计划衔接：`_next_week_plan.md`（基础巩固）→ `_docker_plan.md`（容器化）→ 本计划（质量与真实形态）；三份均为 `process\_pft_staging\` 内部文档，不入 target 交付仓库。
- 纪律映射：AI 不自行 commit（5.1）；新依赖先确认+台账（2.5：pytest/httpx、psycopg）；依赖与功能改动分通道（3.5：P3）；高风险面人主导（2.4：JWT 选项）；改前方案后代码按 S/M/L 分档（2.2）。
- 顺序建议：P0 可立即做；P1→P2 严格先后（CI 需要测试）；P3 可与 P4 并行或互换顺序。
