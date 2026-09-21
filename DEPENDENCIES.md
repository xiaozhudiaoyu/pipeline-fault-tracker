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
