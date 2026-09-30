# 依赖变更台账（Pipeline Fault Tracker）

> 记录本项目 `backend/.venv` 与 `frontend/node_modules` 的依赖变化。
> 每条均标注证据来源（`dist-info` 时间戳、`pip freeze`、`npm ls`、`package-lock.json`、git 提交），不做推断。
> 维护约定：每次增删依赖后补一节；刷新锁文件时同步更新「时间线总览」。
> 风格参照 `python_learn/DEPENDENCIES.md`（规则 2.6 / 5.3）。

## 一、时间线总览

| 日期时间 | 事件 | 包数变化 | 证据 |
|---|---|---|---|
| 2026-09-18 | backend：`pip install -r requirements.txt`（FastAPI / SQLAlchemy 2 / Pydantic 2 / uvicorn 链） | 0 → 21 | `requirements.lock.txt`（`pip freeze`）+ `pip check`（见「五」） |
| 2026-09-20 | backend：`pip install alembic`（D2 数据库迁移支持，含 Mako / MarkupSafe 传递依赖） | 21 → 24 | `pip freeze`（锁文件重生成）+ `pip check` + dist-info 时间戳（见「六」） |
| 2026-09-21 | backend：uv 重建虚拟环境（删 pip venv → `uv venv` + `uv pip install -r requirements.lock.txt`） | 24 → 24（纯重建） | `uv pip check` + 锁文件逐项版本一致 + `/api/faults` 200（见「七」） |
| 2026-09-22 | backend：迁移 uv 工作流（requirements.txt/lock.txt → pyproject.toml + uv.lock，`uv sync` 复现） | 24 → 24（锁定格式变更，版本零漂移） | uv.lock 与旧锁逐项对比 + `uv sync` 全命中 + `uv pip check` + `/api/faults` 200（见「八」） |
| 2026-09-29 | backend：`uv add --dev pytest httpx`（阶段二 P1 测试体系，dev 依赖组，不进运行时） | 24 → 33（+2 直接 +7 传递） | `pyproject.toml [dependency-groups] dev` + `uv.lock` + `uv run pytest` 72 通过（见「九」） |
| 2026-09-30 | backend：`uv add "psycopg[binary]"`（阶段二 P3 PostgreSQL 驱动，运行时依赖） | 33 → 36（+1 直接 +2 传递） | `pyproject.toml dependencies` + `uv.lock`（+91 行）+ 安装日志（见「十」） |
| 2026-09-18 | frontend：`npm install`（Vue 3.4 / Vite 4.5 / Element Plus 2.5 / TanStack Query v4 / Zod 3 链） | 0 → 75 | `package-lock.json` + `npm ls --depth=0`（见「四」） |

## 二、版本锁定决策（2026-09-18）

### 背景

本机 Node 为 **v16.20.2**（2023-09 EOL），无法支撑 Vite 5 / TanStack Query v5 / Element Plus 2.7+（均要求 Node ≥18）。经用户确认，采用 **Node 16 兼容版本组合**，不升级 Node。

### 锁定清单（frontend）

| 包 | 锁定版本范围 | 理由 |
|---|---|---|
| vue | ^3.4（<3.5） | Vue 3.5 起倾向 Node 18+ |
| vite | ^4.5（<5.0） | Vite 5 要求 Node ^18 \|\| >=20 |
| @vitejs/plugin-vue | ^4.6 | 配套 Vite 4 |
| vue-router | ^4.2 | Vue 3 配套 |
| element-plus | ^2.5（<2.7） | 2.7+ 要求 Node 18+ |
| @tanstack/vue-query | ^4.36（<5.0） | v5 要求 Node ≥18 |
| zod | ^3.22 | 纯 TS，无 Node 版本硬约束 |
| typescript | ^5.3 | Vite 4 配套 |
| vue-tsc | ^1.8 | Vue 3.4 配套 |

### 锁定清单（backend）

| 包 | 锁定版本范围 | 理由 |
|---|---|---|
| fastapi | 最新稳定 | Python 3.14 兼容（python_learn 已验证） |
| uvicorn[standard] | 最新稳定 | 含 watchfiles / httptools，`--reload` 硬需求 |
| sqlalchemy | >=2.0 | 需求文档指定 SQLAlchemy 2 |
| pydantic | >=2.0 | 需求文档指定 Pydantic 2 |
| pydantic-settings | 最新稳定 | 从 .env 读配置 |
| python-dotenv | 最新稳定 | pydantic-settings 传递依赖，显式声明 |

> 具体版本号在首次 `pip install` / `npm install` 后，由 `pip freeze` 与 `package-lock.json` 固化，并回填到本台账与 `requirements.lock.txt`。

## 三、待补章节（安装后填写）

- [x] backend 首批安装：见「五、backend 首批安装记录（2026-09-18）」
- [x] frontend 首批安装：见「四、frontend 首批安装记录（2026-09-18）」
- [x] 锁文件生成：`requirements.lock.txt`（`pip freeze`）/ `package-lock.json`（`npm install`）——命令与提交见「四」「五」
- [ ] 后续任何增删：按 python_learn 台账风格逐节记录

## 四、frontend 首批安装记录（2026-09-18）

- **环境**：Node v16.20.2 / npm 8.3.0；registry `https://registry.npmmirror.com/`
- **命令**：`npm install` → `added 75 packages`，**无 ERESOLVE 冲突**
- **顶层依赖实测版本**（`npm ls --depth=0`，全部命中「二、版本锁定决策」窗口）：

  | 包 | 实测版本 | 锁定窗口 | 命中 |
  |---|---|---|---|
  | vue | 3.4.38 | <3.5 | ✓ |
  | vue-router | 4.2.5 | ^4.2 | ✓ |
  | element-plus | 2.5.6 | <2.7 | ✓ |
  | @tanstack/vue-query | 4.36.2 | <5.0 | ✓ |
  | zod | 3.22.5 | ^3.22 | ✓ |
  | vite | 4.5.14 | <5.0 | ✓ |
  | @vitejs/plugin-vue | 4.6.2 | ^4.6 | ✓ |
  | typescript | 5.3.3 | ^5.3 | ✓ |
  | vue-tsc | 1.8.27 | ^1.8 | ✓ |

- **锁文件**：`frontend/package-lock.json` 已生成并随 stage-4 提交入库（`npm ci` 可复现）
- **构建验证**：`npm run build`（vite 4.5.14）1458 模块转换成功；`npm run type-check`（vue-tsc 1.8.27）**exit 0**
- **依赖边界**：严格等于用户预授权清单，未新增 `@types/node` / `@element-plus/icons-vue`——vite.config.ts 不用 node 内置模块、Element Plus 采用全量引入，故无需它们（规则 2.6）
- **已知提示**：build 有「chunk >500kB」告警（Element Plus 全量引入所致），属预期；如需瘦身再改按需引入，本次不处理（规则 3.1）

## 五、backend 首批安装记录（2026-09-18）

- **环境**：Python 3.14.7 / pip 26.2.1；虚拟环境 `backend/.venv`（`python -m venv .venv` 创建）
- **命令**：`pip install -r requirements.txt` → 安装 **21 项**（6 直接依赖 + 15 传递依赖），**无版本冲突**
- **`pip check`**：`No broken requirements found.`（依赖一致性通过）
- **直接依赖实测版本**（`pip freeze`，全部满足 `requirements.txt` 声明的下限）：

  | 包 | 实测版本 | 声明下限 | 命中 |
  |---|---|---|---|
  | fastapi | 0.141.1 | `>=0.115` | ✓ |
  | uvicorn[standard] | 0.53.0 | `>=0.30` | ✓ |
  | pydantic | 2.13.5 | `>=2.9` | ✓ |
  | pydantic-settings | 2.15.0 | `>=2.5` | ✓ |
  | python-dotenv | 1.2.3 | `>=1.0` | ✓ |
  | SQLAlchemy | 2.0.54 | `>=2.0` | ✓ |

- **传递依赖（15 项）**：annotated-doc / annotated-types / anyio / click / greenlet / h11 / httptools / idna / pydantic_core / PyYAML / starlette / typing-inspection / typing_extensions / watchfiles / websockets（其中 watchfiles / httptools / websockets / PyYAML 由 `uvicorn[standard]` 的 `[standard]` extra 引入，为 `--reload` 与 HTTP 解析所需）
- **锁文件**：`backend/requirements.lock.txt` 由 `.venv\Scripts\python.exe -m pip freeze` 生成（2026-09-18），随 backend 基础工程提交入库（commit `2f75a67`）；`pip install -r requirements.lock.txt` 可精确复现本机环境
- **运行验证**：`uvicorn app.main:app --port 8000` 启动成功，`GET /api/faults` 返回 200 + JSON；前后端联调全链路（列表 / 筛选 / 登记 / 详情 / 状态推进）经真实浏览器驱动验证通过（stage-7）
- **SQLite 驱动**：Python 内置 `sqlite3`，无需额外安装依赖

## 六、backend alembic 安装记录（2026-09-20）

- **背景**：D2 练习引入数据库迁移工具 alembic；SQLAlchemy 2.0.54 已存在，仅新增 alembic 本体与其模板渲染依赖
- **命令**：`.venv\Scripts\python.exe -m pip install alembic` → 安装 **3 项**（alembic + Mako + MarkupSafe），包数 21 → 24，**无版本冲突**
- **`pip check`**：`No broken requirements found.`（依赖一致性通过）
- **实测版本与证据**（dist-info 时间戳，`site-packages` 目录创建时间）：

  | 包 | 实测版本 | 声明下限 | 命中 | dist-info 时间戳 |
  |---|---|---|---|---|
  | alembic | 1.20.0 | `>=1.20`（本次写入 requirements.txt） | ✓ | 2026-09-20 17:23:26 |
  | Mako | 1.4.1 | 传递依赖（alembic 的 autogenerate 模板渲染引擎） | — | 2026-09-20 17:23:22 |
  | MarkupSafe | 3.0.3 | 传递依赖（Mako 的转义层） | — | 2026-09-20 17:23:20 |

- **声明与锁文件同步**：`requirements.txt` 新增 `alembic>=1.20`（ORM/数据库 分组）；`requirements.lock.txt` 由 `pip freeze` 重新生成（2026-09-20，24 项 = 7 直接 + 17 传递）
- **引入用途**：backend/alembic/ 迁移目录（D2：baseline `843f28b00698` + 增量索引 `a74bf448a946`），未影响运行时 API 依赖面（alembic 仅迁移期使用）

## 七、backend uv 环境重建记录（2026-09-21 · D4）

- **背景**：D4 练习选定 uv 作为虚拟环境管理工具，按验收要求「从零（删掉旧 venv）」重建 backend 环境
- **工具**：uv 0.12.8（2026-08-31 构建，`uv --version` 证实；本机此前已安装，本次未新增安装）
- **命令**：删除旧 `backend/.venv`（pip 创建，Python 3.14.7）→ `uv venv .venv`（CPython 3.14.7）→ `uv pip install -r requirements.lock.txt`
- **结果**：24 项按锁文件精确复现（7 直接 + 17 传递，版本逐项一致）；`uv pip check` → `All installed packages are compatible`（21ms）
- **耗时**：解析 4.47s + 安装 1m04s，总计约 72s（另有 hardlink 失败回退 copy 的警告：uv 缓存与项目目录不在同一文件系统，属正常降级，无功能影响）
- **运行验证**：`.venv\Scripts\python.exe -m uvicorn app.main:app --port 8001` 启动成功，`GET /api/faults` 返回 200 + JSON（8000 被 `E:\python_uv` 目录的另一实例占用，改用 8001 验证，未干扰他人进程）；`.venv\Scripts\python.exe -m alembic current` = `a74bf448a946 (head)`，D2 迁移链在新环境正常
- **依赖边界**：纯环境重建，未增删任何包（24 项不变），requirements.txt / requirements.lock.txt 均无变化；未使用 `uv add` / `uv init`，故未生成 pyproject.toml / uv.lock，git 工作区无新增文件

## 八、backend 迁移 uv 工作流（pyproject.toml + uv.lock）（2026-09-22）

- **背景**：D4 选定 uv 管理环境后，将依赖管理迁移为 pyproject.toml（声明）+ uv.lock（锁定）工作流，取代 requirements.txt / requirements.lock.txt（经用户确认全删）
- **命令**：新建 `backend/pyproject.toml`（PEP 621 `[project]`，7 直接依赖，下界声明与旧 requirements.txt 完全一致）→ `uv lock` → `uv sync`（现有 .venv 24 项全部命中，无安装动作）→ 删除 requirements 两文件
- **锁对比**：uv.lock 26 项 = 24 项旧包 + `uvloop 0.22.1`（uvicorn[standard] 的 Linux-only extra，跨平台锁定新增，Windows 上不安装）+ 项目自身条目 `pipeline-fault-tracker-backend 0.1.0`；pydantic-core / typing-extensions 的命名差异为连字符规范化，同一包同版本；`watchfiles` 解析到 1.3.0 后经用户确认钉回 1.2.0（`[tool.uv] constraint-dependencies`，迁移零漂移，升级将来单独走提交）
- **删除证据链**：requirements 两文件的全部引用点（README 目录树 / 安装流程 / 依赖管理节、本台账）已同步更新；`backend/dev.bat` 仅在「环境缺失」错误提示中引用 requirements.txt（本地脚本，被 .gitignore 忽略，GBK 编码未改动），无功能依赖
- **运行验证**：`uv pip check` → `All installed packages are compatible`（18ms）；`.venv\Scripts\python.exe -m alembic current` → `a74bf448a946 (head)`；uvicorn 启动后 `GET /api/faults` → 200（服务日志证实）
- **依赖边界**：无任何包版本变化（24 项与旧锁逐项一致）；pyproject.toml + uv.lock 新增入库，requirements 两文件删除

## 九、backend 测试依赖 pytest + httpx（dev 组）（2026-09-29 · 阶段二 P1）

- **背景**：阶段二计划 P1「测试体系化」：pytest 分层测试（schemas / crud / API 集成 / 错误路径）+ httpx `ASGITransport` 走完整请求链路；经用户确认方案后引入（规则 2.5）
- **命令**：`backend/` 下 `uv add --dev pytest httpx` → 解析 35 包，安装 **9 包**：pytest 9.1.1、httpx 0.28.1（直接）+ 传递依赖 certifi 2026.7.22、colorama 0.4.6、httpcore 1.0.9、iniconfig 2.3.0、packaging 26.3、pluggy 1.6.0、pygments 2.21.0（安装日志原文）
- **声明与锁同步**：`pyproject.toml` 新增 `[dependency-groups] dev = ["httpx>=0.28.1", "pytest>=9.1.1"]`（uv 自动写入）；`uv.lock` 同步更新；dev 组仅开发期安装，**不进运行时依赖面**（Docker 镜像等生产链路不受影响）
- **配套配置**：`pyproject.toml` 新增 `[tool.pytest.ini_options]`（testpaths=tests、pythonpath="."、addopts="-v --tb=short"）
- **运行验证**：`uv run pytest` → **72 passed**（Python 3.14.7 + pytest 9.1.1 兼容性实测通过）；红绿闭环演练：临时注释 crud.py「done 不可逆」规则 → 3 条测试变红（test_e6×2 + API 层 test_e5）→ 恢复后复绿（`git diff` 证实 crud.py 与 HEAD 零差异）；开发库 `fault_tracker.db` SHA256 测试前后一致（内存库隔离生效）
- **依赖边界**：未动任何运行时包版本；新增文件仅 `backend/tests/`（conftest.py + 4 个测试文件）

## 十、backend PostgreSQL 驱动 psycopg[binary]（2026-09-30 · 阶段二 P3）

- **背景**：阶段二计划 P3「SQLite → PostgreSQL」：compose 新增 `postgres:16-alpine` 服务，backend 通过 `DATABASE_URL=postgresql+psycopg://...` 切换方言（迁移路径选 a 保守：建表仍靠 `create_all(checkfirst=True)`，Alembic 仅作练习产物）；经用户确认后引入（规则 2.5），与功能改动分通道单独提交（规则 3.5）
- **命令**：`backend/` 下 `uv add "psycopg[binary]"` → 解析 38 包，安装 **3 包**：psycopg 3.3.6（直接）+ 传递依赖 psycopg-binary 3.3.6（预编译 libpq，免本机装 PostgreSQL 客户端库）、tzdata 2026.4（psycopg 3 声明的 IANA 时区数据，Windows 无系统 zoneinfo 时兜底）（安装日志原文）
- **声明与锁同步**：`pyproject.toml` `dependencies` 新增 `"psycopg[binary]>=3.3.6"`（ORM/数据库 分组，含用途注释）；`uv.lock` 同步更新（git diff +91 行）；与「九」dev 组不同，本包属**运行时依赖**，会进入 Docker 镜像（`uv sync --frozen --no-dev`）
- **运行验证**：安装后 `uv run pytest` 全绿（见提交前验证报告）；PG 容器内全闭环验证见 P3 交付说明
- **依赖边界**：未动任何既有包版本（git diff 仅 pyproject.toml +1 行、uv.lock +91 行，无删改）；SQLite 开发库路线不变，本地默认仍走 `config.py` 的 SQLite URL，PG 仅由 compose 环境变量注入
