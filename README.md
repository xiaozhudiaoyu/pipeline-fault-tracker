# 流水线故障记录系统（Pipeline Fault Tracker）

> 用于记录和跟踪流水线故障的小型 Web 应用，覆盖「用户报修 → 管理员指派 → 负责人处理 → 报修人确认」的完整闭环，按时间留存处理过程，并提供 Docker 一键部署。
> 本项目为 `python_learn` 学习计划的综合小测试。

## 一、技术栈

| 层 | 技术 | 版本（实际验证） |
|---|---|---|
| 前端框架 | Vue 3 + TypeScript | Vue ^3.4（实测 3.4.38）、TS ^5.3（实测 5.3.3） |
| 构建工具 | Vite | ^4.5（实测 4.5.14，Node 16 兼容） |
| 路由 | Vue Router | ^4.2（实测 4.2.5） |
| 数据请求 | TanStack Query (vue-query) | ^4.36（实测 4.36.2） |
| 前端校验 | Zod | ^3.22（实测 3.22.5） |
| UI 组件库 | Element Plus | ^2.5（实测 2.5.6） |
| 后端框架 | FastAPI | ≥0.115（实测 0.141.1） |
| 数据校验 | Pydantic 2 | ≥2.9（实测 2.13.5） |
| ORM | SQLAlchemy 2 | ≥2.0（实测 2.0.54） |
| 数据库 | SQLite（默认）/ PostgreSQL（可选） | 内置 / postgres:16-alpine |
| 认证 | JWT（HS256）+ bcrypt 口令哈希 | PyJWT ≥2.15、bcrypt ≥5.0 |
| 迁移 | Alembic | ≥1.20（容器启动自动 `upgrade head`） |
| 运行时 | Python 3.14.7 / Node v16.20.2 / npm 8.3.0 | Windows 10 22H2 |
| 部署 | Docker + Docker Compose | Engine 29.8.1 / Compose v5.5.1 |

> **版本选择说明**：本机 Node 为 v16.20.2（已于 2023-09 EOL），Vite 5 / TanStack Query v5 / Element Plus 2.7+ 均要求 Node ≥18，故锁定 Vite 4.5 + TanStack Query v4 + Element Plus 2.5 组合。若升级至 Node 20 LTS，可同步升级上述依赖。

## 二、项目结构

```
pipeline-fault-tracker/
├── backend/                  # FastAPI + SQLAlchemy 2 + SQLite/PG
│   ├── app/
│   │   ├── main.py / config.py / database.py / models.py
│   │   ├── schemas.py / crud.py / exceptions.py / auth.py
│   │   └── routers/{auth.py, users.py, pipelines.py, faults.py}
│   ├── alembic/              # 数据库迁移（4 个版本，head=105a10b2f697）
│   ├── seed.py               # 演示数据播种（5 账号 + 3 流水线 + 5 故障，幂等）
│   ├── create_admin.py       # 初始管理员创建（幂等、不重置已有密码，需求七.4）
│   ├── entrypoint.sh         # 容器入口：alembic upgrade head → uvicorn
│   ├── Dockerfile / .dockerignore
│   ├── pyproject.toml / uv.lock   # 依赖声明（uv 工作流）
│   └── .env.example
├── frontend/                 # Vue 3 + TS + Vite + Element Plus
│   ├── src/{api, components, composables, router, schemas, styles, types, utils, views}
│   ├── Dockerfile / nginx.conf / .dockerignore / .npmrc
│   ├── package.json / package-lock.json
│   ├── vite.config.ts / tsconfig.json
│   └── .env.example
├── docker-compose.yml        # 默认编排：SQLite + 前后端（named volume 持久化）
├── docker-compose.pg.yml     # 可选覆盖：切换 PostgreSQL
├── .env.example              # compose 层配置模板（SECRET_KEY）
├── DEPENDENCIES.md           # 依赖变更台账
└── README.md                 # 本文件
```

## 三、环境准备

> 本地开发路线（第四、五节）需 Python/Node；**若走 Docker 部署（第十一节），本机只需装 Docker 与 Compose，无需安装 Python/Node.js 或配置虚拟环境。**

| 组件 | 要求版本 | 验证命令 |
|---|---|---|
| Python | ≥ 3.11（本项目验证于 3.14.7） | `python --version` |
| uv | ≥ 0.4（本项目验证于 0.12.8，虚拟环境管理工具） | `uv --version` |
| Node.js | ≥ 16（本项目验证于 v16.20.2） | `node --version` |
| npm | ≥ 8 | `npm --version` |
| Git | ≥ 2.20 | `git --version` |
| Docker / Compose | 部署路线必需（验证于 Engine 29.8.1 / Compose v5.5.1） | `docker compose version` |

## 四、后端本地安装与启动（开发路线）

```powershell
cd backend

# 1. 安装依赖（uv sync 按 uv.lock 精确复现；.venv 不存在时自动创建）
uv sync

# 2. 复制配置示例（按需修改端口、DB 路径、SECRET_KEY）
Copy-Item .env.example .env

# 3. 初始化数据库（自动建表 + 写入演示账号与模拟数据；密码不写死在代码里，取自 SEED_PASSWORD）
$env:SEED_PASSWORD="你的演示密码"     # ≥6 位；库中演示账号已齐时可省略（也可写进 .env，见下方说明）
.venv\Scripts\python.exe seed.py

# 4. 启动服务（默认 http://127.0.0.1:8000）
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

验证：浏览器打开 `http://127.0.0.1:8000/docs`，应看到 Swagger UI 与全部接口。

> **演示账号（需求八.3）**：`seed.py` 写入 5 个测试账号 —— `reporter01`/`reporter02`（普通用户）、`handler01`/`handler02`（处理人员）、`admin01`（管理员），密码统一为上面设置的 `SEED_PASSWORD`（入库为 bcrypt 哈希，不存明文）。脚本幂等：按用户名逐个补齐，重复执行不会重复插号，也不会重置已有密码；同时写入 3 条流水线与覆盖四种状态的 5 条演示故障（库中已有流水线则跳过数据播种）。`SEED_PASSWORD` 有两种给法：环境变量（上方写法，不落盘）或写进 `backend/.env`（同名键），两处同时存在时环境变量优先。仅当库中缺少账号时才需要它，两种给法都没提供则直接中止并提示，不会用默认密码建号。

## 五、前端本地安装与启动（开发路线）

```powershell
cd frontend

# 1. 安装依赖（按锁文件精确复现）
npm ci

# 2. 复制配置示例
Copy-Item .env.example .env

# 3. 启动开发服务器（默认 http://127.0.0.1:5173）
npm run dev
```

验证：浏览器打开 `http://127.0.0.1:5173`（`localhost:5173` 亦可，两者均在后端 CORS 白名单），先用 seed 账号登录，应看到故障列表页。

## 六、角色权限与业务流程（第三阶段）

**三类固定角色**（账号仅由管理员或初始化脚本创建，**不开放自助注册**；权限判定一律以后端为准，前端只隐藏无权按钮）：

| 角色 | 能做什么 |
|---|---|
| 普通用户（user） | 登记故障；查看**本人创建**的故障及时间线；待处理阶段改基本信息/优先级；对本人故障**确认完成**或**退回处理**。 |
| 处理人员（handler） | 查看**分派给本人**的故障；**开始处理**、**追加进展**、**提交处理结果**；不得处理他人任务、不得自行分派或自行确认完成。 |
| 管理员（admin） | 查看全部故障；**指派/改派**负责人（改派须填原因，状态与既有记录不变）；完成前调整优先级；账号新增/启停/重置密码；创建人已停用或旧故障无对应账号时，**填原因后代为确认/退回**。 |

**状态机（四态闭环）**：`pending 待处理 → processing 处理中 → awaiting_confirmation 待确认 → done 已完成`。

```
登记(普通用户)          → pending，创建人自动记为本人，优先级默认普通
管理员 指派/改派         → 仍是 pending（只设负责人；未指派不能开始）
负责人 开始处理          → pending → processing
负责人 追加进展（可多次） → processing（说明必填非空白）
负责人 提交处理结果       → processing → awaiting_confirmation（结果说明必填）
创建人 确认 / 管理员代确认 → awaiting_confirmation → done（写 closed_at）
创建人 退回处理          → awaiting_confirmation → processing（原因必填，负责人不变）
done 为终态：不可再流转、不可改回；历史记录只读，任何角色都不能删除故障及其历史。
```

**处理时间线**：每个动作在同一事务内写一条时间线（状态变更与时间线记录同生共死，任一步失败整体回滚）。详情页按「谁在什么时间做了什么 + 说明」倒序展示，指派/改派额外展示前后负责人，优先级调整记录前后值。**页面直接给「开始处理 / 提交处理结果 / 确认完成 / 退回处理」等按钮，只渲染当前有权执行的操作**，不再用「下拉选状态 + 推进」的旧交互。列表默认视图按角色收敛（普通用户=本人报修、处理人员=本人任务、管理员=全部），支持流水线/状态/优先级组合筛选，管理员另可按负责人筛选与查看「未分派」。旧库无法归属账号的故障显示「历史数据 / 未关联账号」，旧 `handling_note` 单独作为「历史处理说明」呈现。

## 七、后端接口一览

> 完整交互式文档见 `http://127.0.0.1:8000/docs`（Swagger UI）。所有业务接口需先登录（请求头 `Authorization: Bearer <token>`）；错误响应统一为 `{ code, message, details[] }`。

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| POST | `/api/auth/login` | 账号密码登录，返回 JWT（写 httpOnly 无关，前端存内存/localStorage） | 公开 |
| POST | `/api/auth/logout` | 登出（bump `token_version`，旧 token 即时失效） | 登录 |
| GET | `/api/auth/me` | 当前登录用户信息 | 登录 |
| GET | `/api/users` | 用户列表（含停用；供管理页与指派下拉） | 管理员 |
| POST | `/api/users` | 创建账号（username 唯一 409；密码 bcrypt 入库） | 管理员 |
| PATCH | `/api/users/{id}/active` | 启用/停用（停用即时失效其全部 token；禁止自停） | 管理员 |
| POST | `/api/users/{id}/reset-password` | 重置密码（被重置者旧 token 全失效） | 管理员 |
| GET | `/api/pipelines` | 流水线列表（登记/筛选下拉数据源） | 登录 |
| POST | `/api/pipelines` | 新建流水线（供直接调用/扩展） | 登录 |
| GET | `/api/faults` | 故障列表（按角色默认视图 + `pipeline_id`/`status`/`priority`/`assignee_id`/`unassigned` 筛选 + 分页，按发生时间倒序） | 登录（角色过滤） |
| GET | `/api/faults/export` | 导出 CSV（复用列表筛选口径，含创建人/负责人列，UTF-8 带 BOM） | 登录（角色过滤） |
| GET | `/api/faults/{id}` | 故障详情 | 归属校验 |
| POST | `/api/faults` | 登记故障（201 + `Location`；`occurred_at` 不晚于当前、`symptom` 5~1000 字） | 登录 |
| PATCH | `/api/faults/{id}` | 改基本信息（`location`/`symptom`/`handling_note`；done 后说明锁定） | 归属+状态校验 |
| GET | `/api/faults/{id}/timelines` | 处理时间线（倒序） | 归属校验 |
| POST | `/api/faults/{id}/assign` | 指派负责人（仅 pending，不改状态） | 管理员 |
| POST | `/api/faults/{id}/reassign` | 改派负责人（原因必填，状态与记录不变） | 管理员 |
| POST | `/api/faults/{id}/start` | 开始处理：pending → processing | 负责人 |
| POST | `/api/faults/{id}/progress` | 追加进展：processing 内多次，说明必填非空白 | 负责人 |
| POST | `/api/faults/{id}/submit` | 提交结果：processing → awaiting_confirmation（结果说明必填） | 负责人 |
| POST | `/api/faults/{id}/confirm` | 确认完成：awaiting_confirmation → done | 创建人 / 管理员代确认 |
| POST | `/api/faults/{id}/return` | 退回处理：awaiting_confirmation → processing（原因必填，负责人不变） | 创建人 |
| POST | `/api/faults/{id}/priority` | 调整优先级（done 前，状态不变） | 管理员 / 创建人 |
| GET | `/api/health`、`/` | 健康检查（容器 healthcheck 探活 `/api/health`） | 公开 |

> 越权、故障不存在、状态已被他人改动、重复执行同一动作，分别返回 403 / 404 / 409，且不产生脏数据、不重复写入时间线。旧 `PATCH /api/faults/{id}/transition` 已按需求四.3 移除。

## 八、配置说明

后端配置项由 `pydantic-settings` 读取，**环境变量优先，其次 `backend/.env`**；compose 层的 `SECRET_KEY` 由根目录 `.env` 提供。

| 变量 | 出现位置 | 作用 | 默认 |
|---|---|---|---|
| `DATABASE_URL` | backend/.env、compose | 连接串；scheme 决定方言（`sqlite:///…` 或 `postgresql+psycopg://…`） | `sqlite:///./fault_tracker.db` |
| `SECRET_KEY` | 根 .env（compose）、backend/.env | JWT 签名密钥，**生产必改**，不入库不入镜像 | 开发占位（compose 用 `:?` 强制填写） |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | backend/.env | Token 有效期（分钟） | `720`（12 小时） |
| `CORS_ORIGINS` | backend/.env | 跨域白名单（逗号分隔；容器同源经 nginx 代理，一般无需改） | 本地 5173 |
| `HOST` / `PORT` / `DB_ECHO` | backend/.env | 监听地址/端口、SQL 回显 | `127.0.0.1` / `8000` / `false` |
| `SEED_PASSWORD` | backend/.env 或环境变量 | `seed.py` 演示账号统一初始密码（≥6 位，缺账号时才需要） | 无（不给即中止） |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` / `ADMIN_DISPLAY_NAME` | backend/.env 或环境变量 | `create_admin.py` 初始管理员账号/密码/显示名 | `admin` / 无 / `系统管理员` |
| `VITE_API_BASE_URL` | frontend/.env | 前端 API 基址（容器构建留空走同源代理，本地开发指后端） | 空 |

配置文件模板：`backend/.env.example`、`frontend/.env.example`、根目录 `.env.example`。

## 九、依赖管理

- 后端：`pyproject.toml`（声明，`[project].dependencies`）+ `uv.lock`（锁定，`uv lock` 生成，`uv sync` 复现）。
- 前端：`package.json`（声明）+ `package-lock.json`（锁定，`npm install` 生成，`npm ci` 复现）。
- 变更历史与证据见 [DEPENDENCIES.md](./DEPENDENCIES.md)。

## 十、数据库迁移（Alembic）

- 迁移目录 `backend/alembic/`，配置 `backend/alembic.ini`（保持 ASCII-only，中文 Windows 下避免编码坑）。
- **连接串与 app 同源**：`env.py` 从 `app.config.settings` 取 `database_url`，ini 里的 `sqlalchemy.url` 仅是占位；故迁移命令须在 `backend/` 下执行。临时验证可用环境变量 `DATABASE_URL` 覆盖指向其他库文件。
- **SQLite 库文件父目录自动创建**（需求五.4）：把 `DATABASE_URL` 指到带子目录的路径（如 `sqlite:///./data/fault_tracker.db`）时，`app/database.py` 的 `ensure_sqlite_dir()` 会在建 engine 与跑迁移前 `mkdir(parents=True)` 兜住，**无需手工建目录**；内存库 `:memory:` 与 PostgreSQL 不涉及此路径。
- **容器内自动迁移**：`entrypoint.sh` 每次启动先执行 `alembic upgrade head` 再起服务；靠 `alembic_version` 表记录当前版本，**幂等——反复重启既不清库也不重复迁移**。
- **常用命令**（在 `backend/` 下，`.venv\Scripts\python.exe -m alembic ...`）：

  | 命令 | 作用 |
  |---|---|
  | `upgrade head` | 升级到最新版本 |
  | `downgrade -1` | 回退一个版本 |
  | `stamp <rev>` | 给现有库打标记（只写版本号，不执行迁移；老库接入时用） |
  | `history` | 查看迁移链 |
  | `revision -m "..."` | 生成新迁移脚本（`--autogenerate` 自动对比模型与库差异） |

- **迁移链（4 个版本，head = `105a10b2f697`）**：
  - `843f28b00698` baseline —— 手写基线，照抄现有库真实 DDL；空库可由此从零重建，现有库用 `stamp` 打标。
  - `a74bf448a946` —— 给 `pipeline_faults.occurred_at` 建索引 `ix_pipeline_faults_occurred_at`（列表倒序/时间筛选热点）。
  - `b3e19c4d7a52`（第二阶段）—— 加 `priority` 列（normal/urgent，默认普通），旧库升级用 `server_default` 回填后 `batch_alter_table` 摘默认（SQLite 需 batch，PG 自动退化）。
  - `105a10b2f697`（第三阶段）—— 新建 `users`、`fault_timelines` 两表 + `pipeline_faults` 加 `created_by_id`/`assignee_id`（可空外键，旧数据留 NULL）。

### 10.1 空库初始化（全新环境，无旧数据）

> 适用：第一次搭建、或拿到一个空目录。下面命令均在 `backend/` 下执行（Docker 部署无需手工执行，见第十一节）。

```powershell
cd backend
uv sync                                   # 装依赖（.venv 不存在时自动创建）
Copy-Item .env.example .env               # 配置模板（默认 DATABASE_URL=sqlite:///./fault_tracker.db）
# 确保目标库文件不存在（或是全新空文件）；若已有一份旧库想保留，走 10.2
.venv\Scripts\python.exe -m alembic upgrade head   # 空库依次跑完 4 个迁移，一次建到最新结构，库内 alembic_version=105a10b2f697
.venv\Scripts\python.exe create_admin.py           # 创建初始管理员（先设 ADMIN_PASSWORD，见第八节）
$env:SEED_PASSWORD="你的演示密码"                   # （可选）演示数据：5 测试账号 + 流水线 + 故障
.venv\Scripts\python.exe seed.py
```

### 10.2 旧库升级（已有自动建表产生、无 alembic_version 表的库）

> 适用：上一版项目用 `Base.metadata.create_all()` 自动建表、表里已有故障记录，想接入迁移并升到最新结构。**不得通过删库/清数据/重录完成**（需求六.1）。

```powershell
cd backend
# 1. 先备份旧库（升级前必做，回退手段）
Copy-Item fault_tracker.db ..\process\fault_tracker.db.bak-p3-<日期>
# 2. 打标：告诉 alembic “此库已在加 priority 前的版本”，只写版本号、不动数据
.venv\Scripts\python.exe -m alembic stamp a74bf448a946
# 3. 升到最新：仅执行差量（加 priority 列 + 建 users/时间线表 + 故障加两列）
.venv\Scripts\python.exe -m alembic upgrade head
```

升级后验证（不启服务，直接查库）：原有记录的编号、状态、优先级、处理说明逐字段不变；新增列为空。若需回退：`alembic downgrade`，或用备份文件覆盖回去（数据类变更需单独回数据，代码回退不等于数据恢复）。

> ⚠️ 容器场景同理：若复用一个「只靠 create_all 建过表、从未 `stamp` 过 `alembic_version`」的旧数据卷，`entrypoint.sh` 的 `upgrade head` 会因基线 `CREATE TABLE` 撞已存在表而失败——这种历史卷须先按 10.2 `stamp` 再接管。**全新空卷首次启动不受此限**（迁移从空库正常建全表）。

## 十一、Docker 部署

> 目标（需求七）：只装了 Docker 与 Compose 的机器，按本节配置后 `docker compose up -d --build` 即可跑起系统，无需本机安装 Python/Node/虚拟环境。

### 11.1 前置：准备 SECRET_KEY

```powershell
# 仓库根目录（不是 backend/）
Copy-Item .env.example .env
# 编辑 .env，把 SECRET_KEY 改成一段足够长的随机串（compose 用 ${SECRET_KEY:?} 强制：不填则拒绝启动）
```

### 11.2 启动（默认 SQLite）

```bash
docker compose up -d --build
```

- 访问地址：**http://localhost:8080**（前端 nginx 同源反代 `/api/` 到后端，无需另配 CORS）。
- 后端仅由前端经 nginx 访问，本身未映射宿主端口；健康检查 `docker compose ps` 看 backend 是否 `healthy`。
- **数据位置**：SQLite 库文件在 named volume `pft-data`（容器内 `/app/data/fault_tracker.db`），`down` 不删、`down -v` 才删。
- **迁移**：首次启动 backend 自动 `alembic upgrade head` 建全表，之后重启幂等。

### 11.3 创建初始管理员 / 演示数据（一次性命令）

```bash
# 初始管理员（需求七.4：账号密码可配置，重复执行不重建、绝不重置已有密码）
docker compose run --rm -e ADMIN_PASSWORD="你的管理员密码" backend uv run --no-sync python create_admin.py

# （可选）演示数据：5 个测试账号 + 3 流水线 + 5 条闭环故障，便于验收多账号越权
docker compose run --rm -e SEED_PASSWORD="你的演示密码" backend uv run --no-sync python seed.py
```

> 管理员与演示账号可只选其一：`create_admin.py` 只建一个 admin（生产最小入口）；`seed.py` 建 5 个演示账号（含 `admin01`）+ 模拟业务数据（验收/演示用）。两者都幂等，密码均走环境变量、不写死在代码或镜像里。

### 11.4 切换 PostgreSQL（可选形态）

保留阶段二 PG 成果，用 Compose 多文件叠加，**不影响默认 SQLite**：

```bash
docker compose -f docker-compose.yml -f docker-compose.pg.yml up -d --build
# PG 数据落在 named volume pft-pgdata；backend DATABASE_URL 覆盖为 postgresql+psycopg://…
```

### 11.5 停止、日志、备份

| 操作 | 命令 | 说明 |
|---|---|---|
| 停止（保留数据） | `docker compose down` | 删容器与网络，**数据卷保留** |
| 停止并删数据 | `docker compose down -v` | 连 `pft-data`（/`pft-pgdata`）一起删，**不可逆，慎用** |
| 查看状态 | `docker compose ps` | backend 应 `healthy` |
| 查看日志 | `docker compose logs -f backend` | 加服务名看单服务；含 entrypoint 迁移输出 |
| 备份 SQLite | `docker compose cp backend:/app/data/fault_tracker.db ./backup-<日期>.db` | 拷出库文件即快照；恢复反向 `cp` 回该路径后 `down`/`up` |
| 备份 PG | `docker compose exec postgres pg_dump -U pft pft > backup-<日期>.sql` | 恢复：`cat backup.sql \| docker compose exec -T postgres psql -U pft pft` |

> 本机 Docker 在 WSL 内时，上述 `docker` 命令从 PowerShell 经 `wsl -e bash -c "..."` 进入（见项目环境说明）；在已装 Docker Desktop 的机器上直接执行即可。

## 十二、自检结果与已知问题（需求八.4）

**已实测通过（静态/离线，AI 直读磁盘或跑脚本为证）**：

- `create_admin.py`：临时库 5 场景 18 项断言全绿——缺口令且无账号即中止（零账号写入）、带口令建 `admin`（bcrypt `$2b$` 哈希、明文不入库）、重跑跳过不重置不新增、改密码重跑仍拒改、自定义 `ADMIN_USERNAME` 生效。
- 空库 `alembic upgrade head`（容器 entrypoint 首启路径）：一路建 `pipelines/pipeline_faults/users/fault_timelines/alembic_version` 五表，版本至 `105a10b2f697`，`pipeline_faults` 含 `priority/created_by_id/assignee_id`。
- Compose 静态校验：SQLite 主线无 postgres、URL 为 `sqlite:////app/data/…`、卷 `pft-data`；PG 覆盖合并出 `postgres:16-alpine` + 双方言 URL + 双卷；缺 `SECRET_KEY` 被 `${:?}` 拒绝启动。
- 后端 `uv run pytest` 分层回归（见第十三节前置提交历史）。

**交用户运行态自验（未由 AI 起容器实测）**：干净环境 `docker compose up -d --build` 一条龙、容器重启数据保留、浏览器三账号走通闭环与越权拦截（见验收清单）。

**已知问题 / 技术债**：

1. **PG 形态的容器内首启迁移未实测**：迁移链此前只在 SQLite 上完整演练，PG 走 `alembic upgrade head` 建全表（含原生 ENUM）理论兼容但未实盘验证，若 PG 首启报迁移错，以 SQLite 主线为准或临时置空 PG 卷重试。
2. **旧 `handling_note` 未导入为 `is_imported=true` 时间线**（`test_phase3_workflow.py` HD2 仍 `xfail`）：当前按需求六.3「单独显示为历史处理说明」一路满足，不影响功能。
3. **复用旧数据卷的接管限制**：见 10.2 末尾告警——只被 `create_all` 建过表、无 `alembic_version` 的旧卷，容器 `upgrade head` 会撞表，需先 `stamp`。
4. SQLite 为单文件库，不适合高并发生产；PG 形态为可选升级路径。

## 十三、已知限制

- 本轮采用固定三角色权限，不含自助注册、组织架构或自定义权限配置。
- 已完成故障与历史记录只读，任何角色（含管理员）都不能从数据库删除故障及其历史。
- 列表页操作、按钮渲染等界面态验证依赖人工按第十一节 Docker（或第四、五节本地）路线走查；后端权限/状态机为最终裁判。
